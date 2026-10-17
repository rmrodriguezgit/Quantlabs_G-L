import unittest
import math
import torch
from torch import nn
from backend.gan import GANEstimator

class ConstantGenerator(nn.Module):
    def forward(self,z):return torch.zeros_like(z[:,:1])

class GANTrainingTests(unittest.TestCase):
    def test_training_does_not_collapse_across_seeds(self):
        returns=[.0008*math.sin(i*2.399)+.0003*math.cos(i*.51) for i in range(200)]
        for seed in [1,2,3]:
            with self.subTest(seed=seed):
                torch.manual_seed(seed);m=GANEstimator();q=m.train(returns)
                self.assertTrue(q['healthy'],q)
                self.assertGreater(q['std_ratio'],.5)
                self.assertTrue(.25<m.predict(0,300)<.75)
                self.assertEqual(m.last_scenario_count,1000)
                self.assertEqual(m.predict(-.05,300),0.)
                self.assertEqual(m.predict(.05,300),1.)
    def test_constant_generator_fails_health_check(self):
        m=GANEstimator();m.g=ConstantGenerator().to(m.device)
        self.assertFalse(m.assess_quality()['healthy'])
    def test_invalid_and_flat_returns_do_not_enable_prediction(self):
        m=GANEstimator()
        for returns in [[.1]*10,[float('nan')]*50]:
            with self.assertRaises(ValueError):m.train(returns)
            self.assertFalse(m.ready)
        self.assertFalse(m.train([0.]*50)['healthy'])
        with self.assertRaises(ValueError):m.predict()
if __name__=='__main__':unittest.main()
