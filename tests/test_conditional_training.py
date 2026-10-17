import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from backend.training.data import build_examples,temporal_split
from backend.training.conditional_gan import ConditionalEnsemble,ConditionalCritic,gradient_penalty


def candles(count=1000):
    rows=[]
    for i in range(count):
        price=100+np.sin(i/9)+i*.001
        rows.append([i*60000,str(price),str(price+.2),str(price-.2),str(price+.03), '10',i*60000+59999,'0',1,'6'])
    return rows


class ConditionalTrainingTests(unittest.TestCase):
    def test_future_close_cannot_change_features(self):
        rows=candles();a=build_examples(rows)
        chosen=next(r for r in a if r['cycle']==6000 and r['cutoff']==6060)
        rows[104][4]='80'
        b=next(r for r in build_examples(rows) if r['cycle']==6000 and r['cutoff']==6060)
        np.testing.assert_array_equal(chosen['x'],b['x'])
        self.assertNotEqual(chosen['target'],b['target'])

    def test_split_has_purge_and_unique_cycles(self):
        train,cal,test=temporal_split(build_examples(candles()))
        self.assertLess(max(r['label_time'] for r in train),min(r['cycle'] for r in cal)-1200)
        self.assertLess(max(r['label_time'] for r in cal),min(r['cycle'] for r in test)-1200)

    def test_gap_excludes_context(self):
        rows=candles();del rows[99]
        records=build_examples(rows)
        self.assertFalse(any(r['cutoff']==6060 for r in records))

    def test_training_checkpoint_and_calibration(self):
        torch.set_num_threads(1)
        records=build_examples(candles(90));model=ConditionalEnsemble()
        model.fit(records,seeds=(1,),steps=3,batch_size=8)
        p=model.probabilities(records,samples_per_model=32)
        self.assertTrue(np.isfinite(p).all());self.assertGreater(np.std(p),0)
        model.fit_calibration(p,np.array([r['label'] for r in records]))
        self.assertTrue(np.isfinite(model.calibrated(p)).all())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.pt';model.save(path,{'promoted':False})
            restored=ConditionalEnsemble.load(path)
            np.testing.assert_array_equal(p,restored.probabilities(records,samples_per_model=32))
        penalty=gradient_penalty(ConditionalCritic(12),torch.randn(4,12),torch.randn(4,1),torch.randn(4,1))
        self.assertTrue(torch.isfinite(penalty));penalty.backward()
