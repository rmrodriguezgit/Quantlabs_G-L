import unittest
import tempfile
from pathlib import Path
from backend.engine import PaperTradingEngine, QLearningAgent

class EngineTests(unittest.TestCase):
    def test_gates_and_kelly(self):
        q=QLearningAgent()
        self.assertEqual(q.decide(.58,.5,.5,1)['action'],'WAIT')
        self.assertEqual(q.decide(.8,.5,.5,.7)['action'],'WAIT')
        self.assertEqual(q.decide(.8,.9,.1,1)['action'],'WAIT')
        self.assertEqual(q.decide(.8,.5,.5,1)['fraction'],.05)
    def test_win_duplicate_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'account.json'; e=PaperTradingEngine(p)
            d=e.agent.decide(.8,.5,.5,1)
            for _ in range(2):e.enter(300,570,100,d,1,.5,.5)
            self.assertEqual(len(e.trades),1); self.assertEqual(e.cash,950)
            e=PaperTradingEngine(p); e.settle(300,101); e.settle(300,101)
            self.assertEqual(e.cash,1050); self.assertEqual(e.snapshot()['pnl'],50)
            self.assertGreater(e.agent.table[d['state']]['UP'],0)
    def test_loss_drawdown(self):
        e=PaperTradingEngine();d=e.agent.decide(.8,.5,.5,1);e.enter(0,280,100,d,1,.5,.5);e.settle(0,99)
        self.assertEqual(e.cash,950);self.assertAlmostEqual(e.snapshot()['max_drawdown'],.05)
    def test_pause(self):
        e=PaperTradingEngine();e.paused=True;e.enter(0,280,100,e.agent.decide(.8,.5,.5,1),1,.5,.5);self.assertFalse(e.trades)
if __name__=='__main__':unittest.main()
