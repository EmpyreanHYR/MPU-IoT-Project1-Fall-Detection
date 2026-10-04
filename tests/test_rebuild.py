import importlib.util
from pathlib import Path
import tempfile
import json
import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("rebuild",ROOT/"code/scripts/rebuild_primary.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class RebuildTests(unittest.TestCase):
    def test_rebuild_cli_writes_all_four_window_manifests(self):
        frozen=pd.read_csv(ROOT/"datasets/primary_test_folds.csv")
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);segments=[];index=[]
            for i,row in enumerate(frozen.itertuples()):
                cache=work/f"pose_{i}.npz"
                np.savez(cache,timestamps=np.arange(61)/30,
                         keypoints=np.ones((61,17,3),np.float32),bbox=np.ones((61,5),np.float32))
                index.append(dict(video_id=row.video_id,cache_path=str(cache)))
                segments.append(dict(video_id=row.video_id,dataset=row.dataset,
                    subject=row.subject_from_video_id.split(":")[1],path="fixture.avi",
                    view="fixture",label="fall",start=.5,end=1.5))
            pd.DataFrame(segments).to_csv(work/"segments.csv",index=False)
            pd.DataFrame(index).to_csv(work/"index.csv",index=False)
            command=[sys.executable,str(ROOT/"code/scripts/rebuild_primary.py"),
                "--manifest",str(work/"segments.csv"),"--pose-index",str(work/"index.csv"),
                "--output-dir",str(work/"rebuilt")]
            completed=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            metadata=json.loads((work/"rebuilt/REBUILT.json").read_text())
            self.assertFalse(metadata["original_validation_folds"])
            for fold in range(4):
                table=pd.read_csv(work/f"rebuilt/fold_{fold}_windows.csv")
                self.assertEqual(set(table.split),{"train","val","test"})
                self.assertTrue((table.groupby("video_id").split.nunique()==1).all())
                self.assertTrue((table.groupby("subject").split.nunique()==1).all())
                self.assertTrue((table.timesteps==30).all())
            retry=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(retry.returncode,0)

    def test_explicit_dataset_override_matches_frozen_video_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            pd.DataFrame([dict(path="subject/video",dataset="DifferentCasing",subject="1",
                               cam="side",label=1,start=0,end=1)]).to_csv(work/"labels.csv",index=False)
            pd.DataFrame([dict(path="subject/video",video_path="fixture.avi")]).to_csv(work/"mapping.csv",index=False)
            completed=subprocess.run([sys.executable,str(ROOT/"code/scripts/prepare_omnifall_manifest.py"),
                "--labels",str(work/"labels.csv"),"--path-mapping",str(work/"mapping.csv"),
                "--dataset","caucafall","--output",str(work/"segments.csv")],capture_output=True,text=True,timeout=10)
            self.assertEqual(completed.returncode,0,completed.stderr)
            row=pd.read_csv(work/"segments.csv").iloc[0]
            self.assertEqual(row.video_id,"caucafall:subject/video")
            self.assertEqual(row.label,"fall")

    def test_frozen_test_groups_and_dataset_scoped_subjects(self):
        frozen=pd.read_csv(ROOT/"datasets/primary_test_folds.csv")
        rows=[]
        for row in frozen.itertuples():
            rows.append(dict(video_id=row.video_id,dataset=row.dataset,
                subject=row.subject_from_video_id.split(":")[1],path="fixture.avi",
                view="",label="fall",start=0,end=1))
        table=pd.DataFrame(rows)
        folds=module.assign_folds(table,frozen,2026,.2)
        for fold,output in enumerate(folds):
            self.assertEqual(set(output.loc[output.split=="test","video_id"]),
                             set(frozen.loc[frozen.test_fold==fold,"video_id"]))
            self.assertTrue((output.groupby("subject").split.nunique()==1).all())
            self.assertEqual(output.subject.nunique(),14)
            for _,group in output.groupby("split"):
                self.assertEqual(set(group.dataset),set(frozen.dataset))
        for a,b in zip(folds,module.assign_folds(table,frozen,2026,.2)):
            pd.testing.assert_frame_equal(a,b)
        bad=table.copy();bad.loc[0,"subject"]="unknown"
        with self.assertRaises(ValueError):module.assign_folds(bad,frozen,2026,.2)
        with self.assertRaises(ValueError):module.assign_folds(table.iloc[1:],frozen,2026,.2)


if __name__=="__main__":unittest.main()
