import csv
import io
import tempfile
import unittest
from pathlib import Path
from backend.research import ResearchStore

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'research.sqlite3';self.store=ResearchStore(self.path)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def snapshot(self,now=570,cycle=300,p=.8,**updates):
        audit=dict(score=1,model_probability=.6,model_connected=True,approved=False,rsi=60,ema_fast=101,ema_slow=100,delta_volume=5)
        s=dict(timestamp=now,cycle=cycle,mode='live',profile='gan_laya',probability=p,remaining=cycle+300-now,
            data_updated_at=now-1,gan_quality={'healthy':True},validator=audit,decision={'action':'WAIT'},
            odds=dict(up=.5,down=.51,fee_rate=.07,timestamp=now,available=True,condition_id=f'c{cycle}',slug=f'btc-updown-5m-{cycle}',quotes={'UP':dict(size=100,min_size=5,timestamp=now),'DOWN':dict(size=100,min_size=5,timestamp=now)}),
            blockers=['LAYA'],error=None)
        s.update(updates);return s
    def test_waits_persist_and_first_anchor_is_frozen(self):
        self.store.record(self.snapshot(560,p=.9))
        self.store.record(self.snapshot(570,p=.8))
        self.store.record(self.snapshot(580,p=.1))
        self.store.record(self.snapshot(590,p=.2))
        report=self.store.report(True)
        self.assertEqual(report['observations'],4);self.assertEqual(report['samples'],1)
        self.assertEqual(report['resolved'],0);self.assertEqual(report['pending'],1);self.assertIsNone(report['brier'])
        self.assertIsNone(report['variants'][0]['pnl'])
        self.store.resolve('c300','UP',610)
        report=self.store.report(True)
        self.assertAlmostEqual(report['brier'],.04)
        self.assertEqual([v['trades'] for v in report['variants']],[1,1,0])
        self.assertAlmostEqual(report['variants'][0]['pnl'],1/.5175-1)
        self.assertLess(report['variants'][0]['stress_pnl'],report['variants'][0]['pnl'])
        self.assertEqual(report['calibration'][8]['count'],1)
    def test_stale_failed_unhealthy_and_late_rows_are_not_samples(self):
        cases=[self.snapshot(data_updated_at=550),self.snapshot(error='offline'),self.snapshot(gan_quality={'healthy':False}),self.snapshot(now=601)]
        old_book=self.snapshot();old_book['odds']['quotes']['UP']['timestamp']=550;cases.append(old_book)
        for s in cases:self.store.record(s)
        r=self.store.report(True);self.assertEqual(r['samples'],0);self.assertEqual(r['observations'],5)
    def test_rejected_ml_does_not_receive_approved_performance(self):
        s=self.snapshot();s['validator'].update(model_probability=.9,approved=True)
        self.store.record(s);self.store.resolve('c300','DOWN',610)
        r=self.store.report(True)
        self.assertEqual([v['trades'] for v in r['variants']],[1,1,1])
        self.assertEqual([v['pnl'] for v in r['variants']],[-1,-1,-1])
        self.store.resolve('c300','UP',620)
        self.assertEqual(self.store.report(True)['variants'][0]['pnl'],-1)
    def test_recovery_export_and_audit_only_resolution_queue(self):
        self.store.record(self.snapshot());self.store.close();self.store=ResearchStore(self.path)
        self.assertEqual(self.store.pending_conditions(599),[])
        self.assertEqual(self.store.pending_conditions(601),['c300'])
        self.store.mark_checked('c300',601)
        self.store.resolve('c300','UP',610)
        rows=list(csv.DictReader(io.StringIO(self.store.export_csv())))
        self.assertEqual(rows[0]['action'],'WAIT');self.assertEqual(rows[0]['official_winner'],'UP')
        self.assertIn('LAYA',rows[0]['blockers_json']);self.assertIn('fee_rate',rows[0]['payload_json'])
    def test_no_leakage_across_new_cycle_and_neutral_prediction_no_trade(self):
        self.store.record(self.snapshot(p=.5));self.store.resolve('c300','UP',610)
        self.store.record(self.snapshot(870,600,p=.8))
        r=self.store.report(True)
        self.assertEqual(r['samples'],2);self.assertEqual(r['resolved'],1);self.assertEqual(r['pending'],1)
        self.assertEqual(r['variants'][0]['trades'],0);self.assertAlmostEqual(r['brier'],.25)
    def test_degraded_nonfinite_diagnostics_are_still_recorded(self):
        s=self.snapshot(gan_quality={'healthy':False,'std_ratio':float('nan')})
        self.store.record(s)
        row=list(csv.DictReader(io.StringIO(self.store.export_csv())))[0]
        self.assertEqual(row['gan_p_up'],'')
        self.assertIsNone(__import__('json').loads(row['payload_json'])['gan_quality']['std_ratio'])

    def test_missing_candidate_ask_keeps_calibration_without_inventing_fill(self):
        s=self.snapshot();s['odds']['up']=0;s['odds']['quotes'].pop('UP')
        self.store.record(s);self.store.resolve('c300','UP',610)
        r=self.store.report(True)
        self.assertEqual(r['resolved'],1)
        self.assertAlmostEqual(r['brier'],.04)
        self.assertEqual(r['variants'][0]['trades'],0)
        self.assertIsNone(r['variants'][0]['stress_pnl'])

    def test_depth_is_respected(self):
        s=self.snapshot();s['odds']['quotes']['UP']['size']=1
        self.store.record(s);self.store.resolve('c300','UP',610)
        self.assertEqual(self.store.report(True)['variants'][0]['trades'],0)
if __name__=='__main__':unittest.main()
