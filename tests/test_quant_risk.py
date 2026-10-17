import json
import math
import tempfile
import unittest
from pathlib import Path
from backend.quant_risk import binary_terms,ruin_probability,quant_decision,risk_assessment,performance,VERSION
from backend.engine import PaperTradingEngine,LayaMLXValidator
from backend.indicators import trend_indicators
from backend.market import read_bid


def audit():
    return dict(sides={s:dict(model_connected=True,model_probability=.8,score=.4) for s in ('UP','DOWN')},market_context=dict(atr=dict(value=2.)))

def market(now=400):
    return dict(condition_id='c',slug='btc-updown-5m-300',timestamp=now,up=.2,down=.25,fee_rate=.07,
        quotes={s:dict(size=100,min_size=5,timestamp=now) for s in ('UP','DOWN')},
        bids={s:dict(price=.2,size=100,timestamp=now) for s in ('UP','DOWN')})

def enter(e=None,side='UP'):
    e=e or PaperTradingEngine();m=market();p=.8 if side=='UP' else .2
    d=quant_decision(p,.2,.25,audit(),.07,e.snapshot(),100,400)
    d.update(confirmation_ticks=3,stable_seconds=2,confirmed_cycle=300,confirmed_side=side)
    t=e.enter(300,400,99,d,.4,.2,.25,m,'LAYA_APPROVED')
    return e,t,d


class QuantTests(unittest.TestCase):
    def test_ev_rr_net_fee_and_slippage(self):
        x=binary_terms(.6,.25,.07)
        cost=.255*(1+.07*(1-.255))
        self.assertAlmostEqual(x['ev'],.6/cost-1)
        self.assertAlmostEqual(x['rr'],1/cost-1)
        self.assertGreater(x['rr'],2)
        self.assertIsNone(binary_terms(.6,.999,.07))
        self.assertIsNone(binary_terms(float('nan'),.2,.07))
    def test_rr_rejects_even_high_probability_high_price(self):
        d=quant_decision(.9,.5,.7,audit(),.07,PaperTradingEngine().snapshot(),100,400)
        self.assertEqual(d['action'],'WAIT');self.assertFalse(d['side_risks']['UP']['allowed'])
    def test_rank_both_after_rr_and_risk(self):
        d=quant_decision(.55,.4,.25,audit(),.07,PaperTradingEngine().snapshot(),100,400)
        self.assertEqual(d['action'],'DOWN')
        self.assertGreater(d['candidates']['DOWN']['rr'],2)
    def test_ruin_exact_first_passage_and_capital_dependence(self):
        self.assertEqual(ruin_probability(1000,1,.1,2,100),0)
        self.assertAlmostEqual(ruin_probability(1,1,.5,1,1),.5)
        self.assertAlmostEqual(ruin_probability(2,1,.5,1,2),.25)
        self.assertEqual(ruin_probability(0,1,.8,2,100),1)
        with self.assertRaises(ValueError):ruin_probability(10,0,.5,1)
    def test_budget_no_raising_one_dollar_and_missing_atr(self):
        a=PaperTradingEngine().snapshot();terms=binary_terms(.8,.2,.07)
        r=risk_assessment(a,terms,2,100,400)
        self.assertTrue(r['allowed']);self.assertEqual(r['stake'],1)
        a['cash']=50;a['balance']=50
        self.assertFalse(risk_assessment(a,terms,2,100,400)['allowed'])
        self.assertFalse(risk_assessment(PaperTradingEngine().snapshot(),terms,None,100,400)['allowed'])
    def test_limits_daily_open_risk_and_drawdown(self):
        terms=binary_terms(.8,.2,.07)
        for kind in ('daily','open','drawdown'):
            a=PaperTradingEngine().snapshot()
            if kind=='daily':a['trades']=[dict(stake=1,pnl=-20,status='LOST',cycle=300,settled_at=400)]
            if kind=='open':a['trades']=[dict(stake=20,pnl=0,status='OPEN',cycle=300)]
            if kind=='drawdown':a['max_drawdown']=.05
            self.assertFalse(risk_assessment(a,terms,2,100,401)['allowed'],kind)
    def test_fill_recomputes_risk_and_current_price(self):
        e,t,d=enter();self.assertIsNotNone(t);self.assertEqual(t.stake,1)
        self.assertAlmostEqual(t.price,.205);self.assertEqual(t.risk_version,VERSION)
        self.assertAlmostEqual(t.tokens*(t.price+.07*t.price*(1-t.price)),1)
        fresh=PaperTradingEngine();m=market();d['risk']['allowed']=True
        fresh.cash=50
        self.assertIsNone(fresh.enter(300,400,99,d,.4,.2,.25,m,'LAYA_APPROVED'))
        self.assertIsNone(PaperTradingEngine().enter(300,400,99,d,.4,.6,.25,m,'LAYA_APPROVED'))
    def test_atr_stop_waits_for_bid_latches_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=PaperTradingEngine(Path(tmp)/'account.json');e,t,d=enter(e)
            self.assertEqual(e.manage(401,300,95,401,None),[])
            self.assertEqual(t.status,'OPEN');self.assertEqual(t.exit_pending,'STOP_ATR')
            restored=PaperTradingEngine(e.path);m=market(402)
            out=restored.manage(402,300,100,402,m)
            self.assertEqual(len(out),1);self.assertEqual(out[0].status,'EXITED')
            self.assertEqual(out[0].exit_reason,'STOP_ATR');self.assertAlmostEqual(out[0].exit_price,.195)
            cash=restored.cash;restored.resolve('c','UP',now=700)
            self.assertEqual(restored.cash,cash);self.assertEqual(out[0].official_outcome,'UP')
    def test_exit_rejects_stale_wrong_market_insufficient_depth(self):
        for kind in ('stale','identity','size','btc'):
            e,t,_=enter();m=market(401);data_at=401
            if kind=='stale':m['bids']['UP']['timestamp']=390
            if kind=='identity':m['condition_id']='wrong'
            if kind=='size':m['bids']['UP']['size']=.1
            if kind=='btc':data_at=390
            self.assertFalse(e.manage(401,300,95,data_at,m),kind);self.assertEqual(t.status,'OPEN')
    def test_down_stop_and_take_profit_symmetry(self):
        for side,stop,take in [('UP',95,109),('DOWN',105,91)]:
            e,t,_=enter(side=side);self.assertTrue(e.manage(401,300,stop,401,market(401)));self.assertEqual(t.exit_reason,'STOP_ATR')
            e,t,_=enter(side=side);self.assertTrue(e.manage(401,300,take,401,market(401)));self.assertEqual(t.exit_reason,'TAKE_PROFIT_ATR')
    def test_trailing_uses_observed_prices_and_entry_atr(self):
        for side,best,retrace in [('UP',105,101),('DOWN',95,99)]:
            e,t,_=enter(side=side);self.assertFalse(e.manage(401,300,best,401,market(401)))
            self.assertTrue(e.manage(402,300,retrace,402,market(402)));self.assertEqual(t.exit_reason,'TRAILING_ATR')
    def test_pause_does_not_disable_exit_and_no_exit_after_expiry(self):
        e,t,_=enter();e.paused=True;self.assertTrue(e.manage(401,300,95,401,market(401)))
        e,t,_=enter();self.assertFalse(e.manage(600,300,95,600,market(600)));e.resolve('c','DOWN',now=700);self.assertEqual(t.status,'LOST')
    def test_closed_indicators_warmup_and_macd_bollinger(self):
        self.assertIsNone(trend_indicators([dict(close=100)]*199)['sma200'])
        x=trend_indicators([dict(close=100)]*201)
        self.assertEqual(x['sma200'],100);self.assertEqual(x['macd'],0);self.assertEqual(x['bollinger']['upper'],100)
        x=trend_indicators([dict(close=100+i) for i in range(201)])
        self.assertGreater(x['sma50'],x['sma200']);self.assertGreater(x['macd'],0)
    def test_laya_quant_receives_trend_but_keeps_side_separate(self):
        class Model:
            def __init__(self):self.prompts=[];self.questions=[]
            def predict(self,prompt,schema):
                self.prompts.append(json.loads(prompt));self.questions.append(schema);return {'answers':{side:{'probabilities':{'LAYA_APPROVED':.8 if side=='UP' else .1}} for side in schema}}
        v=LayaMLXValidator();v.model=Model();v.model_name='test'
        candles=[dict(open=100,high=101,low=99,close=100,volume=1,delta=0)]*202
        result=v.validate(candles,.6,'quant')
        self.assertEqual(len(v.model.prompts),1)
        self.assertEqual(list(v.model.questions[0]),['UP','DOWN'])
        self.assertTrue(result['sides']['UP']['approved']);self.assertFalse(result['sides']['DOWN']['approved'])
        self.assertTrue(all('trend_context' in p and 'atr' in p for p in v.model.prompts))
    def test_bid_is_executable_side_not_ask_or_midpoint(self):
        b=dict(asset_id='t',market='c',timestamp='400000',bids=[dict(price='.2',size='10'),dict(price='.3',size='5')])
        self.assertEqual(read_bid(b,'t','c',400)['price'],.3)
        b['bids']=[];self.assertIsNone(read_bid(b,'t','c',400))
    def test_performance_undefined_until_dispersion_and_exit_profit_counts(self):
        self.assertIsNone(performance([])['sharpe'])
        trades=[dict(status='EXITED',stake=1,pnl=2),dict(status='LOST',stake=1,pnl=-1)]
        x=performance(trades);self.assertAlmostEqual(x['sharpe'],.5/math.sqrt(4.5));self.assertEqual(x['win_rate'],.5)


class BankrollResetTests(unittest.TestCase):
    def test_initial_hundred_persists_and_sets_pnl_and_drawdown_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fresh.json';e=PaperTradingEngine(path,initial_bankroll=100)
            self.assertEqual(e.snapshot()['balance'],100)
            self.assertEqual(e.snapshot()['pnl'],0)
            self.assertEqual(e.agent.table,{})
            e.cash=99;e.equity.append(99);e.save()
            restored=PaperTradingEngine(path)
            self.assertEqual(restored.initial_bankroll,100)
            self.assertEqual(restored.snapshot()['pnl'],-1)
            self.assertAlmostEqual(restored.snapshot()['max_drawdown'],.01)
