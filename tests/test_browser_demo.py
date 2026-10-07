"""Browser model inference: current weights, temporal window and session reset."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'webui'))
from cloud_model import CloudFallModel,validate_landmarks,COCO_MP_INDICES
spec=importlib.util.spec_from_file_location('browser_edge_reference',ROOT/'deployment/edge/edge_runtime.py')
sys.path.insert(0,str(ROOT/'deployment/edge'))
edge=importlib.util.module_from_spec(spec);spec.loader.exec_module(edge)

class BrowserDemoTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=ROOT/'artifacts/models/masked_bimamba_quality.onnx'
 def setUp(self):
  self.model=CloudFallModel(Path('/nonexistent'),None,self.path)
  self.points=[[.2+i*.01,.2+(i%7)*.04,1.] for i in range(33)]
 def test_current_model_catalog_and_quality_inputs(self):
  info=self.model.info();self.assertEqual(info['active_model_id'],'masked_bimamba_quality')
  self.assertTrue(info['models'][0]['live_available'])
  self.assertEqual(self.model.select_model('masked_bimamba_quality')['model_id'],'masked_bimamba_quality')
  with self.assertRaises(ValueError):self.model.select_model('missing')
 def test_one_second_window_matches_edge_classifier(self):
  reference=edge.Classifier(self.path)
  with patch('cloud_model.time.time',side_effect=[100+i*.25 for i in range(5)]):
   for i in range(5):
    result=self.model.add_frame('browser_test_session',i,self.points)
    direct=reference.add(100+i*.25,np.asarray([self.points[x] for x in COCO_MP_INDICES],np.float32),1.)
  self.assertTrue(result['ready']);self.assertAlmostEqual(result['fall_probability'],direct['fall_probability'],places=4)
 def test_missing_pose_and_reset_clear_session(self):
  with patch('cloud_model.time.time',side_effect=[100+i*.25 for i in range(7)]):
   for i in range(5):self.model.add_frame('browser_test_session',i,self.points)
   result=self.model.add_frame('browser_test_session',5,[])
   self.assertFalse(result['ready']);self.assertEqual(result['reason'],'no_valid_pose')
   self.assertFalse(self.model.add_frame('browser_test_session',6,self.points)['ready'])
  self.model.reset('browser_test_session');self.assertEqual(len(self.model.sessions),0)
 def test_invalid_landmarks_and_sequence_rejected(self):
  with self.assertRaises(ValueError):validate_landmarks([[0,0,1]])
  self.model.add_frame('browser_test_session',1,self.points)
  with self.assertRaises(ValueError):self.model.add_frame('browser_test_session',1,self.points)
  with self.assertRaises(ValueError):self.model.add_frame('bad',0,self.points)
if __name__=='__main__':unittest.main()
