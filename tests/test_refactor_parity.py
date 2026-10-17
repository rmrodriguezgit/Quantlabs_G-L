"""Verify trading decisions against the frozen v1.2.2 implementation."""
import math
import random
import unittest
from pathlib import Path
from backend.engine import QLearningAgent
from backend.directional import POLICIES,POLICY_VERSION,signal_side

class RefactorParityTests(unittest.TestCase):
    def test_decision_table_matches_baseline_on_1200_cases(self):
        scope=dict(math=math,POLICIES=POLICIES,POLICY_VERSION=POLICY_VERSION,signal_side=signal_side)
        source=Path(__file__).with_name('fixtures')/'q_agent_v1_2_2.py.txt'
        exec(compile(source.read_text(),str(source),'exec'),scope)
        old=scope['QLearningAgent']();new=QLearningAgent();rng=random.Random(991)
        for i in range(1200):
            p=rng.choice([0.,.42,.5,.58,1.,rng.random()])
            up=rng.choice([0.,1.,rng.uniform(.001,.999)])
            down=rng.choice([0.,1.,rng.uniform(.001,.999)])
            score=rng.choice([0.,.7,.8,1.]);rate=rng.choice([0.,.07])
            expected=old.decide(p,up,down,score,rate)
            actual=new.decide(p,up,down,score,rate)
            self.assertEqual(actual,expected,f'case {i}')
            if actual['action']!='WAIT':
                reward=rng.choice([-1.,.4,1.])
                old.update(expected['state'],expected['action'],reward)
                new.update(actual['state'],actual['action'],reward)
        self.assertEqual(new.table,old.table)
