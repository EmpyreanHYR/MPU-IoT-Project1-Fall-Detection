"""CPU checks of published weights, input contract and training/deployment preprocessing."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import onnx
import onnxruntime as ort
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"deployment/edge"))
sys.path.insert(0,str(ROOT/"code/src"))
from edge_runtime import Classifier
from fallbench.data import PoseWindowDataset
spec = importlib.util.spec_from_file_location("portable_export",ROOT/"code/scripts/export_mamba_onnx.py")
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ModelTests(unittest.TestCase):
    def test_published_checkpoint_onnx_parity(self):
        model_path=ROOT/"artifacts/models/masked_bimamba_quality.onnx"
        onnx.checker.check_model(onnx.load(model_path))
        saved=torch.load(ROOT/"artifacts/models/masked_bimamba.pt",map_location="cpu",weights_only=True)
        model=module.PortableFallMamba(saved["model_name"],saved["pose_size"],saved["quality_size"],saved["config"]["model"])
        model.load_state_dict(saved["model_state"],strict=True);model.eval()
        session=ort.InferenceSession(str(model_path),providers=["CPUExecutionProvider"])
        rng=np.random.default_rng(2026)
        for case in range(5):
            pose=rng.random((1,30,36),dtype=np.float32)
            quality=rng.random((1,30,3),dtype=np.float32)
            if case==0:pose[:]=0;quality[:]=0
            with torch.no_grad():expected=model(torch.from_numpy(pose),torch.from_numpy(quality)).numpy()
            actual=session.run(None,{"pose":pose,"quality":quality})[0]
            np.testing.assert_allclose(actual,expected,rtol=2e-4,atol=2e-4)

    def test_preprocessing_and_spatial_masking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"pose.npz"
            times=np.arange(31)/30
            points=np.zeros((31,17,3),np.float32)
            points[:,:,0]=np.arange(17)/30+.1
            points[:,:,1]=np.arange(17)/40+.2
            points[:,:,2]=.9
            bbox=np.zeros((31,5),np.float32);bbox[:,4]=.4+np.arange(31)/100
            np.savez(path,timestamps=times,keypoints=points,bbox=bbox)
            table=pd.DataFrame([dict(cache_path=str(path),video_id="fixture",split="test",start=0,end=1,label=0)])
            config=dict(timesteps=30,include_confidence=True,normalization="per_frame_minmax",joints="body12")
            clean=PoseWindowDataset(table,config,"test")[0]
            classifier=Classifier(ROOT/"artifacts/models/masked_bimamba_quality.onnx")
            real=classifier.session
            class CapturingSession:
                def run(self,output,inputs):
                    self.inputs=inputs
                    return real.run(output,inputs)
            classifier.session=CapturingSession()
            for i in range(31):record=classifier.add(times[i],points[i],bbox[i,4])
            self.assertIsNotNone(record)
            np.testing.assert_allclose(classifier.session.inputs["pose"][0],clean["pose"].numpy(),atol=1e-6)
            np.testing.assert_allclose(classifier.session.inputs["quality"][0],clean["quality"].numpy(),atol=1e-6)
            masked=PoseWindowDataset(table,config,"test",corruption="lower_body_missing",severity=1)[0]
            a=clean["pose"].numpy().reshape(30,12,3);b=masked["pose"].numpy().reshape(30,12,3)
            np.testing.assert_array_equal(a[:,:6],b[:,:6])
            np.testing.assert_array_equal(b[:,6:],0)


if __name__=="__main__":unittest.main()
