import unittest
from backend.engine import QLearningAgent,PaperTradingEngine,gan_laya_decision

class GanLayaTests(unittest.TestCase):
    def audit(self,**updates):
        a=dict(score=1,model_connected=True,approved=True,model_probability=.9);a.update(updates);return a
    def test_direction_follows_gan_even_when_more_expensive(self):
        q=QLearningAgent()
        self.assertEqual(gan_laya_decision(q,.95,.8,.21,self.audit())['action'],'UP')
        self.assertEqual(gan_laya_decision(q,.05,.21,.8,self.audit())['action'],'DOWN')
    def test_strict_probability_and_mlx_gates(self):
        q=QLearningAgent()
        for audit in [self.audit(model_probability=.7),self.audit(model_probability=None),self.audit(model_connected=False),self.audit(approved=False),self.audit(score=.7)]:
            self.assertEqual(gan_laya_decision(q,.95,.8,.21,audit)['action'],'WAIT')
        for p in [.42,.5,.58]:self.assertEqual(gan_laya_decision(q,p,.3,.3,self.audit())['action'],'WAIT')
    def test_one_dollar_fill_records_actual_model_percentages(self):
        e=PaperTradingEngine();d=gan_laya_decision(e.agent,.95,.8,.21,self.audit())
        market=dict(condition_id='c',slug='s',fee_rate=0,quotes={'UP':dict(size=100,min_size=5)})
        t=e.enter(300,350,100,d,1,.8,.21,market,'LAYA_APPROVED')
        self.assertEqual(t.stake,1);self.assertEqual(e.cash,999)
        self.assertEqual(t.profile,'gan_laya');self.assertEqual(t.gan_probability,.95);self.assertEqual(t.laya_model_probability,.9)
        self.assertTrue(t.below_minimum)
    def test_fill_engine_independently_rejects_false_approval(self):
        e=PaperTradingEngine();d=gan_laya_decision(e.agent,.95,.8,.21,self.audit())
        self.assertIsNone(e.enter(300,350,100,d,1,.8,.21,None,'LAYA_REJECTED'))
        d['laya_model_probability']=.7
        self.assertIsNone(e.enter(300,350,100,d,1,.8,.21,None,'LAYA_APPROVED'))
        self.assertEqual(e.cash,1000)
if __name__=='__main__':unittest.main()
