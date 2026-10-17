import unittest
from datetime import datetime,timezone
from backend.market import validate_market,read_book
from backend.engine import PaperTradingEngine
from backend.main import execution_gates

class LiveTests(unittest.TestCase):
    def market(self):
        return dict(slug='btc-updown-5m-300',eventStartTime='1970-01-01T00:05:00Z',endDate='1970-01-01T00:10:00Z',outcomes='["Up","Down"]',closed=False,acceptingOrders=True,enableOrderBook=True,resolutionSource='https://data.chain.link/streams/btc-usd',version='v1',feesEnabled=True,feeSchedule={'exponent':1,'rate':.07})
    def test_wrong_cycle_and_dates_block(self):
        self.assertIsNotNone(validate_market(self.market(),300))
        for key,value in [('slug','btc-updown-5m-0'),('endDate','1970-01-01T00:15:00Z'),('eventStartTime',None),('closed',True),('version','v2'),('feeSchedule',{})]:
            m=self.market();m[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_market(m,300)
    def test_book_sort_stale_and_identity(self):
        b=dict(asset_id='token',market='condition',timestamp='100000',asks=[{'price':'.6','size':'100'},{'price':'.4','size':'30'}],min_order_size='5')
        self.assertEqual(read_book(b,'token','condition',101)['price'],.4)
        for token,now in [('wrong',101),('token',114),('token',95)]:
            with self.assertRaises(ValueError):read_book(b,token,'condition',now)
    def test_inclusive_window_and_blockers(self):
        audit=dict(score=1,approved=True);decision=dict(ev=.2,action='UP')
        for now,allowed in [(569.99,False),(570,True),(585,True),(585.01,False),(600,False)]:
            market={'timestamp':now}
            gates=execution_gates(now,300,.8,audit,decision,market,True,False,False)
            self.assertEqual(all(g['ok'] for g in gates),allowed)
        self.assertFalse(all(g['ok'] for g in execution_gates(580,300,.8,audit,decision,{'timestamp':560},True,False,False)))
        self.assertFalse(all(g['ok'] for g in execution_gates(580,300,.8,audit,decision,{'timestamp':580},False,False,False)))
    def test_fee_budget_liquidity_and_official_resolution(self):
        e=PaperTradingEngine();d=e.agent.decide(.8,.5,.5,1,.07)
        market=dict(condition_id='condition',slug='btc-updown-5m-300',fee_rate=.07,quotes={'UP':dict(size=60,min_size=5)})
        t=e.enter(300,580,100,d,1,.5,.5,market,'LAYA_APPROVED')
        self.assertEqual(t.tokens,60);self.assertAlmostEqual(t.fee,1.05)
        self.assertLessEqual(t.stake,50);self.assertEqual(t.validator_status,'LAYA_APPROVED')
        e.settle(300,200);self.assertEqual(t.status,'OPEN')
        e.resolve('other','UP');self.assertEqual(t.status,'OPEN')
        e.resolve('condition','UP');self.assertEqual(t.status,'WON');self.assertAlmostEqual(e.cash,1028.95)
        e.resolve('condition','UP');self.assertAlmostEqual(e.cash,1028.95)
    def test_min_order_and_net_ev(self):
        e=PaperTradingEngine();d=e.agent.decide(.8,.5,.5,1,.07)
        market=dict(condition_id='c',slug='s',fee_rate=.07,quotes={'UP':dict(size=4,min_size=5)})
        self.assertIsNone(e.enter(300,580,100,d,1,.5,.5,market));self.assertEqual(e.cash,1000)
        self.assertLess(e.agent.decide(.8,.5,.5,1,.07)['ev'],e.agent.decide(.8,.5,.5,1)['ev'])

if __name__=='__main__':unittest.main()
