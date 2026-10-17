import unittest
from backend.indicators import market_context

class IndicatorTests(unittest.TestCase):
    def rows(self):return [dict(open=100+i,close=101+i,high=102+i,low=99+i) for i in range(60)]
    def test_wilder_atr_and_levels(self):
        c=market_context(self.rows(),160)
        self.assertEqual(c['atr']['value'],3)
        self.assertEqual(c['fibonacci']['swing'],'UP')
        levels={x['ratio']:x['price'] for x in c['fibonacci']['levels']}
        self.assertEqual(levels[0.],161);self.assertEqual(levels[1.],109)
        self.assertAlmostEqual(levels[.618],161-.618*52)
    def test_price_cannot_change_closed_atr_or_fib_anchors(self):
        a=market_context(self.rows(),160);b=market_context(self.rows(),200)
        self.assertEqual(a['atr'],b['atr'])
        self.assertEqual(a['fibonacci']['levels'],b['fibonacci']['levels'])
        self.assertIsNone(b['fibonacci']['nearest']['UP']['level'])
    def test_missing_ohlc_never_fabricates_atr(self):
        self.assertFalse(market_context([dict(open=100,close=101)]*60,101)['available'])
    def test_same_bar_extremes_are_ambiguous(self):
        rows=[dict(open=100,close=100,high=101,low=99) for _ in range(60)]
        c=market_context(rows,100);self.assertTrue(c['available']);self.assertIsNone(c['fibonacci'])
    def test_gaps_use_previous_close_in_true_range(self):
        rows=[dict(open=100,close=100,high=101,low=99) for _ in range(15)]
        rows.append(dict(open=110,close=110,high=111,low=109))
        self.assertAlmostEqual(market_context(rows,110)['atr']['value'],(2*13+11)/14)
    def test_context_does_not_change_laya_prompts_or_directional_score(self):
        from backend.engine import LayaMLXValidator
        class Model:
            def __init__(self):self.calls=[]
            def predict(self,prompt,schema):
                self.calls.append((prompt,schema))
                return {'answers':{'audit':{'probabilities':{'LAYA_APPROVED':.9}}}}
        rows=[{**r,'volume':10,'delta':5} for r in self.rows()]
        current=dict(open=160,close=161,high=1000000,low=1,volume=1,delta=1)
        v=LayaMLXValidator();v.model_name='test-only';v.model=Model()
        a=v.validate(rows+[current],.8);before=list(v.model.calls)
        for r in rows:r['high']+=5;r['low']-=5
        b=v.validate(rows+[current],.8)
        self.assertEqual(before,v.model.calls[2:])
        self.assertEqual(a['score'],b['score']);self.assertEqual(a['approved'],b['approved'])
        self.assertNotEqual(a['market_context']['atr']['value'],b['market_context']['atr']['value'])
        self.assertEqual(a['market_context']['atr']['value'],3)
