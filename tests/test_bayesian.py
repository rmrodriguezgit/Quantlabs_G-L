import unittest
from backend.bayesian import posterior,evaluate,simulated_trade


def signal(cycle=0,p=.8,winner='UP',resolved_at=310,cohort='policy-test'):
    return dict(cycle=cycle,timestamp=cycle+270,condition_id=str(cycle),cohort=cohort,
        probability=p,winner=winner,resolved_at=resolved_at,
        payload=dict(validator=dict(side='UP' if p>=.5 else 'DOWN',score=1,
            technical_pass=True,approved=True,model_probability=.9,model_connected=True),
            odds=dict(up=.5,down=.5,fee_rate=0,quotes={'UP':{'size':100},'DOWN':{'size':100}})))

class BayesianTests(unittest.TestCase):
    def test_posterior_counts_known_outcomes_and_stays_complementary(self):
        a=signal();b=signal(300,winner='DOWN',resolved_at=610);current=signal(900,resolved_at=1210)
        p=posterior(current,[a,b,current],draws=2000)
        self.assertEqual((p['alpha'],p['beta'],p['n']),(3,3,2))
        self.assertAlmostEqual(p['p_up']+p['p_down'],1)
        self.assertLess(p['credible_95'][0],.5);self.assertGreater(p['credible_95'][1],.5)

    def test_not_yet_published_outcome_cannot_leak(self):
        a=signal(resolved_at=1000);current=signal(300,resolved_at=610)
        self.assertEqual(posterior(current,[a])['n'],0)
        a['winner']='DOWN'
        self.assertEqual(posterior(current,[a])['side_probability'],.5)

    def test_future_rows_do_not_change_past_predictions(self):
        rows=[signal(),signal(300,resolved_at=610)]
        before=evaluate(rows)['predictions']
        after=evaluate(rows+[signal(900,winner='DOWN',resolved_at=1210)])['predictions'][:2]
        self.assertEqual(before,after)

    def test_do_not_mix_policies_directions_or_approval(self):
        current=signal(900,resolved_at=1210)
        other=signal(cohort='older-policy');down=signal(p=.2);rejected=signal()
        rejected['payload']['validator']['approved']=False
        self.assertEqual(posterior(current,[other,down,rejected])['n'],0)

    def test_rejected_laya_cannot_be_overridden_by_bayes(self):
        row=signal();row['payload']['validator']['approved']=False
        self.assertIsNone(simulated_trade(row,.999))
        row['payload']['validator']['approved']=True
        row['payload']['validator']['technical_pass']=False
        self.assertIsNone(simulated_trade(row,.999))

    def test_prior_only_has_wide_uncertainty_and_no_promotion(self):
        p=posterior(signal(),[])
        self.assertEqual(p['n'],0);self.assertEqual(p['side_probability'],.5)
        self.assertLess(p['credible_95'][0],.11);self.assertGreater(p['credible_95'][1],.89)
        self.assertFalse(p['ready_for_live'])
        self.assertFalse(evaluate([signal()])['promoted'])

    def test_fee_liquidity_and_down_payoff(self):
        row=signal(p=.2,winner='DOWN')
        self.assertEqual(simulated_trade(row,.8)['side'],'DOWN')
        self.assertEqual(simulated_trade(row,.8)['pnl'],1.)
        row['payload']['odds']['quotes']['DOWN']['size']=0
        self.assertIsNone(simulated_trade(row,.8))
