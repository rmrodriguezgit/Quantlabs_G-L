import json
import unittest
from backend.directional import technical_audits
from backend.engine import LayaMLXValidator,QLearningAgent,gan_laya_decision,PaperTradingEngine


def candles(up=True):
    sign=1 if up else -1
    return [dict(open=100+sign*i,close=100+sign*(i+1),volume=10,delta=sign*5) for i in range(60)]

class FakeModel:
    def __init__(self,fail=None):self.calls=[];self.instructions=[];self.fail=fail
    def predict(self,prompt,schema):
        evidence=json.loads(prompt);self.calls.append(evidence);self.instructions.append(schema['audit']['instructions'])
        if evidence['side']==self.fail:raise ValueError('Inference failed')
        return {'answers':{'audit':{'probabilities':{'LAYA_APPROVED':.95}}}}

class DirectionalTests(unittest.TestCase):
    def validator(self,fail=None):
        v=LayaMLXValidator();v.model_name='fake-test-only';v.model=FakeModel(fail);return v
    def test_each_side_has_own_evidence_and_model_call(self):
        v=self.validator();a=v.validate(candles(),.8)
        self.assertEqual([x['side'] for x in v.model.calls],['UP','DOWN'])
        self.assertTrue(a['sides']['UP']['approved']);self.assertFalse(a['sides']['DOWN']['approved'])
        self.assertEqual(a['sides']['DOWN']['score'],0)
        self.assertIn('ENTRY_DOWN',v.model.instructions[1]);self.assertIn('ENTRY_UP',v.model.instructions[0])
    def test_bearish_signal_has_own_approval(self):
        v=self.validator();a=v.validate(candles(False),.2)
        self.assertTrue(a['approved']);self.assertEqual(a['side'],'DOWN')
        self.assertFalse(a['sides']['UP']['approved'])
        self.assertEqual(gan_laya_decision(QLearningAgent(),.2,.7,.3,a)['action'],'DOWN')
    def test_lagged_bullish_indicators_cannot_override_current_price(self):
        rows=candles();rows[-1]['close']=145
        a=self.validator().validate(rows,.8)
        self.assertFalse(a['technical_pass']);self.assertFalse(a['approved'])
        self.assertEqual(gan_laya_decision(QLearningAgent(),.8,.5,.5,a)['action'],'WAIT')
    def test_side_failure_does_not_reuse_opposite_probability(self):
        v=self.validator(fail='DOWN');a=v.validate(candles(False),.2)
        self.assertIsNone(a['model_probability']);self.assertFalse(a['approved'])
        self.assertIsNotNone(a['sides']['UP']['model_probability'])
    def test_missing_directional_confirmation_blocks_execution(self):
        a=self.validator().validate(candles(),.8)
        d=gan_laya_decision(QLearningAgent(),.8,.5,.5,a)
        d['directional_audit']['technical_pass']=False
        self.assertIsNone(PaperTradingEngine().enter(0,100,100,d,1,.5,.5,None,'LAYA_APPROVED'))
    def test_short_or_nonfinite_context_rejected(self):
        with self.assertRaises(ValueError):technical_audits(candles()[:10])
        rows=candles();rows[-1]['close']=float('nan')
        with self.assertRaises(ValueError):technical_audits(rows)

    def test_thresholds_are_independent_and_boundaries_remain_strict(self):
        from unittest.mock import patch
        from backend.directional import POLICIES,SidePolicy,signal_side
        self.assertEqual(signal_side(.58),'WAIT');self.assertEqual(signal_side(.42),'WAIT')
        with patch.dict(POLICIES,{'UP':SidePolicy('UP',min_probability=.7),'DOWN':SidePolicy('DOWN',min_probability=.6)}):
            self.assertEqual(signal_side(.65),'WAIT')
            self.assertEqual(signal_side(.75),'UP')
            self.assertEqual(signal_side(.35),'DOWN')

    def test_entry_keeps_versioned_evidence(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'paper.json';e=PaperTradingEngine(path)
            audit=self.validator().validate(candles(False),.2)
            d=gan_laya_decision(e.agent,.2,.7,.3,audit)
            t=e.enter(300,400,100,d,audit['score'],.7,.3,None,'LAYA_APPROVED')
            self.assertEqual(t.directional_audit['policy_version'],'directional-v1')
            restored=PaperTradingEngine(path).trades[0]
            self.assertEqual(restored.directional_audit['side'],'DOWN')
            self.assertEqual(len(restored.directional_audit['checks']),5)
