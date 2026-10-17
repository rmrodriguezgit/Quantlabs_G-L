import unittest
from backend.simple_rules import edge_decision,SignalConfirmation,execution_gates
from backend.engine import PaperTradingEngine,LayaMLXValidator


def audit(up=.6,down=.6):
    return {'sides':{side:dict(side=side,model_connected=p is not None,model_probability=p,model_error=None) for side,p in [('UP',up),('DOWN',down)]}}

def market(now=400):
    return dict(up=.5,down=.4,fee_rate=.07,slug='btc-updown-5m-300',condition_id='c',timestamp=now,
        quotes={s:dict(timestamp=now,size=100,min_size=5) for s in ('UP','DOWN')})

class SimpleRulesTests(unittest.TestCase):
    def test_value_can_buy_down_without_gan_majority(self):
        d=edge_decision(.6,.8,.3,audit())
        self.assertEqual(d['action'],'DOWN');self.assertAlmostEqual(d['edge'],.1)
    def test_no_58_percent_or_technical_gate(self):
        self.assertEqual(edge_decision(.54,.49,.6,audit())['action'],'UP')
    def test_edge_is_after_fees_and_not_roi(self):
        self.assertEqual(edge_decision(.55,.5,.6,audit(),.07)['action'],'WAIT')
        d=edge_decision(.54,.5,.6,audit(),0)
        self.assertEqual(d['action'],'UP')
    def test_mlx_required_at_boundary_and_errors_fail_closed(self):
        self.assertEqual(edge_decision(.8,.5,.7,audit(up=.35))['action'],'UP')
        for p in [None,.349,float('nan')]:
            self.assertEqual(edge_decision(.8,.5,.7,audit(up=p))['action'],'WAIT')
        a=audit();a['sides']['UP']['model_error']='failed'
        self.assertEqual(edge_decision(.8,.5,.7,a)['action'],'WAIT')
    def test_missing_ask_no_synthetic_fallback(self):
        self.assertEqual(edge_decision(.8,0,.9,audit())['action'],'WAIT')
    def test_q_is_explicitly_diagnostic(self):
        table={};d=edge_decision(.8,.5,.7,audit(),q_table=table)
        table[d['state']]['UP']=-100
        self.assertEqual(edge_decision(.8,.5,.7,audit(),q_table=table)['action'],'UP')
        self.assertEqual(d['q_role'],'diagnostic_only')
    def test_stability_resets_on_gap_rejection_side_and_cycle(self):
        c=SignalConfirmation()
        self.assertFalse(c.observe(300,'UP',400,True));self.assertFalse(c.observe(300,'UP',401,True))
        self.assertTrue(c.observe(300,'UP',402,True))
        self.assertFalse(c.observe(300,'DOWN',403,True));self.assertEqual(c.count,1)
        self.assertFalse(c.observe(300,'DOWN',410,True));self.assertEqual(c.count,1)
        self.assertFalse(c.observe(600,'DOWN',601,True));self.assertEqual(c.count,1)
        c.observe(600,'DOWN',602,False);self.assertEqual(c.count,0)
    def test_window_market_identity_and_data_freshness(self):
        d=edge_decision(.8,.5,.7,audit())
        for now,allowed in [(359.9,False),(360,True),(580,True),(580.1,False)]:
            g=execution_gates(now,300,market(now),now,True,True,False,False,d)
            self.assertEqual(all(x['ok'] for x in g),allowed)
        m=market();m['slug']='wrong'
        self.assertFalse(all(x['ok'] for x in execution_gates(400,300,m,400,True,True,False,False,d)))
        self.assertFalse(all(x['ok'] for x in execution_gates(400,300,market(),390,True,True,False,False,d)))
    def test_fill_rechecks_edge_veto_confirmation_and_fixed_stake(self):
        e=PaperTradingEngine();d=edge_decision(.8,.5,.7,audit(),.07)
        self.assertIsNone(e.enter(300,400,100,d,0,.5,.7,market(),'LAYA_APPROVED'))
        d.update(confirmation_ticks=3,stable_seconds=2,confirmed_cycle=300,confirmed_side='UP')
        t=e.enter(300,400,100,d,0,.5,.7,market(),'LAYA_APPROVED')
        self.assertIsNotNone(t);self.assertEqual(t.stake,1);self.assertEqual(e.cash,999)
        e.resolve('c','UP');self.assertGreater(t.pnl,0)
        self.assertIsNone(e.enter(300,400,100,d,0,.5,.7,market(),'LAYA_APPROVED'))
    def test_fill_rejects_wrong_cycle_quote_and_failed_veto(self):
        for change in ['quote','veto','stake','cycle']:
            d=edge_decision(.8,.5,.7,audit(),.07);d.update(confirmation_ticks=3,stable_seconds=2,confirmed_cycle=300,confirmed_side='UP');m=market()
            if change=='quote':m['quotes']['UP']['timestamp']=380
            if change=='veto':d['laya_model_probability']=.34
            if change=='stake':d['stake_usd']=2
            if change=='cycle':d['confirmed_cycle']=0
            self.assertIsNone(PaperTradingEngine().enter(300,400,100,d,0,.5,.7,m,'LAYA_APPROVED'))
    def test_new_validator_mode_does_not_require_technical_consensus(self):
        class Model:
            def predict(self,prompt,schema):return {'answers':{'audit':{'probabilities':{'LAYA_APPROVED':.5}}}}
        v=LayaMLXValidator();v.model_name='test';v.model=Model()
        candles=[dict(open=100,close=100,volume=0,delta=0) for _ in range(60)]
        strict=v.validate(candles,.8);simple=v.validate(candles,.8,mode='edge')
        self.assertFalse(strict['approved']);self.assertTrue(simple['approved'])
        self.assertFalse(simple['technical_pass']);self.assertEqual(simple['validation_mode'],'edge')
    def test_shadow_payoff_uses_simple_rules_without_58_or_technical_gate(self):
        from backend.research import ResearchStore
        a=audit();a['score']=0
        payload=dict(profile='edge_laya',validator=a,odds=dict(up=.49,down=.6,fee_rate=0,quotes={'UP':dict(size=100,min_size=5)}))
        result=ResearchStore.payoff(payload,.54,'UP')
        self.assertEqual(result['side'],'UP');self.assertGreater(result['pnl'],0)
    def test_fill_uses_current_ask_not_saved_expected_value(self):
        d=edge_decision(.8,.5,.7,audit(),.07);d.update(confirmation_ticks=3,stable_seconds=2,confirmed_cycle=300,confirmed_side='UP')
        m=market();m['up']=.79
        self.assertIsNone(PaperTradingEngine().enter(300,400,100,d,0,.79,.7,m,'LAYA_APPROVED'))
