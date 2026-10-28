"""Regression tests for the additional phase-one review trust boundary."""
import copy
import json
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from validate_gx010021_review import validate_review
from benchmark.validate import load_bundle,validate_bundle

class VideoReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'results/video_review/GX010021_phase1_20261027/review_data.json').read_text(encoding='utf-8'))
        cls.native=load_bundle(ROOT/'datasets/ego_mc/GX010021_video_phase1_20261027')
    def setUp(self):
        self.review=copy.deepcopy(self.source); self.bundle=copy.deepcopy(self.native)
    def errors(self): return validate_review(self.review,self.bundle)
    def test_review_bundle_valid_without_approval(self):
        self.assertEqual(self.errors(),[])
        self.assertEqual(validate_bundle(self.bundle,check_sources=False)['errors'],[])
    def test_sidecar_cannot_confirm_history(self):
        self.review['tasks'][5]['history_necessity']='CONFIRMED'
        self.assertTrue(any('TASK_GATE' in e for e in self.errors()))
    def test_sidecar_cannot_use_future_video(self):
        self.review['tasks'][0]['current_evidence'].append(self.review['timeline'][-1]['evidence_ref'])
        self.assertTrue(any('FUTURE_LEAK' in e for e in self.errors()))
    def test_analysis_fields_required(self):
        del self.review['tasks'][0]['alternative_evidence_check']
        self.assertTrue(any('TASK_FIELDS' in e for e in self.errors()))
    def test_annotation_cannot_be_visual_support(self):
        self.review['tasks'][0]['current_evidence'].append('ego_mc:GX010021:evidence:000')
        self.assertTrue(any('SOURCE_LAYER' in e for e in self.errors()))
    def test_no_fabricated_audio_or_exact_boundaries(self):
        self.review['audio_present']=True
        self.review['timeline'][0]['exact_action_start']=9.608
        self.assertTrue(any('AUDIO_GATE' in e for e in self.errors()))
        self.assertTrue(any('BOUNDARY_GATE' in e for e in self.errors()))
    def test_unreviewed_native_task_cannot_enable(self):
        t=next(r for r in self.bundle['records'] if r['id']==self.review['tasks'][5]['id'])
        t['payload']['enabled']=True
        self.assertTrue(any('TASK_GATE' in e or 'GOLD_GATE' in e for e in validate_bundle(self.bundle,check_sources=False)['errors']))
    def test_gold_stays_empty(self):
        self.assertEqual((ROOT/'datasets/ego_mc/GX010021/gold.jsonl').stat().st_size,0)
        self.assertEqual((ROOT/'datasets/ego_mc/GX010021_video_phase1_20261027/gold.jsonl').stat().st_size,0)

if __name__=='__main__': unittest.main()
