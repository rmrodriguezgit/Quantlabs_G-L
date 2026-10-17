import asyncio
import math
import tempfile
import time
import unittest
from pathlib import Path
import httpx
from backend.engine import PaperTradingEngine
from backend.market import LiveMarket

class ClosingTests(unittest.TestCase):
    def test_spot_close_is_persisted_without_deciding_binary_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'account.json';e=PaperTradingEngine(path)
            d=e.agent.decide(.8,.5,.5,1)
            m=dict(condition_id='c',slug='s',fee_rate=0,quotes={'UP':dict(size=100,min_size=5)})
            t=e.enter(300,580,100,d,1,.5,.5,m,'LAYA_APPROVED')
            cash=e.cash
            self.assertTrue(e.record_close(300,99,600))
            self.assertEqual(t.status,'OPEN');self.assertEqual(e.cash,cash)
            self.assertFalse(e.record_close(300,101,600));self.assertEqual(t.closing_price,99)
            e.resolve('c','UP');self.assertEqual(t.status,'WON');self.assertEqual(t.official_outcome,'UP')
            saved=PaperTradingEngine(path);self.assertEqual(saved.trades[0].closing_price,99)
            self.assertEqual(saved.trades[0].closing_time,600);self.assertEqual(saved.trades[0].official_outcome,'UP')
            for price,closed_at in [(float('nan'),600),(0,600),(99,599)]:
                with self.assertRaises(ValueError):e.record_close(300,price,closed_at)
    def test_exact_historical_window_and_rejects_wrong_or_unfinished_candle(self):
        async def run():
            calls=[]
            def handler(request):
                calls.append(request)
                self.assertEqual(request.url.params['startTime'],'300000')
                self.assertEqual(request.url.params['endTime'],'599999')
                return httpx.Response(200,json=[[300000,'100','102','99','101','10',599999]])
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                live=LiveMarket(client);result=await live.candle_close(300)
                self.assertEqual(result,dict(price=101,closed_at=600,source='BINANCE'))
                with self.assertRaises(ValueError):await live.candle_close(int(time.time()//300)*300)
                self.assertEqual(len(calls),1)
            def bad(request):return httpx.Response(200,json=[[600000,'100','102','99','101','10',899999]])
            async with httpx.AsyncClient(transport=httpx.MockTransport(bad)) as client:
                with self.assertRaises(ValueError):await LiveMarket(client).candle_close(300)
        asyncio.run(run())
if __name__=='__main__':unittest.main()
