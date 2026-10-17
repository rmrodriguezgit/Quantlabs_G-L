import unittest
from backend.engine import exploratory_decision, PaperTradingEngine
from backend.main import exploratory_gates, execution_gates

class ExploratoryTests(unittest.TestCase):
    def test_exploration_can_fill_rejected_signal_without_claiming_approval(self):
        d=exploratory_decision(.02,.1,.91,.07)
        self.assertEqual(d['action'],'UP');self.assertLess(d['ev'],0);self.assertEqual(d['stake_usd'],1.)
        audit=dict(score=0,approved=False)
        market=dict(timestamp=350,condition_id='c',slug='btc-updown-5m-300',fee_rate=.07,quotes={'UP':dict(size=100,min_size=5)})
        self.assertTrue(all(g['ok'] for g in exploratory_gates(350,300,market,True,False,False)))
        self.assertFalse(all(g['ok'] for g in execution_gates(350,300,.55,audit,d,market,True,False,False)))
        e=PaperTradingEngine();t=e.enter(300,350,100,d,0,.1,.91,market,'LAYA_REJECTED')
        self.assertEqual(t.profile,'exploratory');self.assertEqual(t.validator_status,'LAYA_REJECTED')
        self.assertAlmostEqual(t.stake,1);self.assertEqual(t.status,'OPEN')
        self.assertIsNone(e.enter(300,351,100,d,0,.1,.91,market,'LAYA_REJECTED'))
        e.resolve('c','DOWN');self.assertAlmostEqual(e.cash,999);self.assertEqual(t.status,'LOST')
    def test_exploration_preserves_market_and_control_gates(self):
        for now,market,models,paused,already in [(350,None,True,False,False),(350,{'timestamp':340},True,False,False),(350,{'timestamp':350},False,False,False),(350,{'timestamp':350},True,True,False),(350,{'timestamp':350},True,False,True),(596,{'timestamp':596},True,False,False)]:
            self.assertFalse(all(g['ok'] for g in exploratory_gates(now,300,market,models,paused,already)))
if __name__=='__main__':unittest.main()

class DollarLimitTests(unittest.TestCase):
    def test_does_not_raise_budget_to_meet_minimum(self):
        d=exploratory_decision(.8,.5,.51,.07)
        m=dict(condition_id='c',slug='s',fee_rate=.07,quotes={'UP':dict(size=100,min_size=5)})
        e=PaperTradingEngine()
        t=e.enter(300,350,100,d,1,.5,.51,m,'LAYA_APPROVED')
        self.assertEqual(t.stake,1)
        self.assertTrue(t.below_minimum)
        self.assertEqual(e.cash,999)
    def test_does_not_spend_more_or_fill_partial_budget(self):
        for balance,size in [(.99,100),(1000,1)]:
            e=PaperTradingEngine();e.cash=balance;d=exploratory_decision(.8,.1,.91,.07)
            m=dict(condition_id='c',slug='s',fee_rate=.07,quotes={'UP':dict(size=size,min_size=5)})
            self.assertIsNone(e.enter(300,350,100,d,1,.1,.91,m,'LAYA_APPROVED'))
            self.assertEqual(e.cash,balance)

class AvailableSideTests(unittest.TestCase):
    def test_absent_ask_never_selected(self):
        self.assertEqual(exploratory_decision(.8,.01,0,.07)['action'],'UP')
        self.assertEqual(exploratory_decision(.8,0,.01,.07)['action'],'DOWN')
        self.assertEqual(exploratory_decision(.8,0,0,.07)['action'],'WAIT')
