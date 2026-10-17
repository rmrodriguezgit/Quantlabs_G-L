"""Read-only causal shadow experiment. Never changes LAYA or trading decisions."""
import argparse
import json
import math
import random
import sqlite3
from pathlib import Path

PROTOCOL='beta-binomial-shadow-v1'


def group_key(row):
    """One proposed side per cycle; never count UP and DOWN as two outcomes."""
    p=row['probability'];side='UP' if p>=.5 else 'DOWN'
    confidence=p if side=='UP' else 1-p
    band='50-70' if confidence<.7 else '70-90' if confidence<.9 else '90-100'
    audit=row['payload']['validator']
    technical=bool(audit.get('technical_pass',audit.get('score',0)>.7))
    approved=bool(audit.get('model_connected') and audit.get('approved') and (audit.get('model_probability') or 0)>.7)
    # Same anchor protocol (15–30 seconds) and policy cohort are mandatory.
    return (row['cohort'],side,band,technical,approved)


def posterior(row,known,prior=2.,draws=10000):
    if not math.isfinite(prior) or prior<=0:raise ValueError('Positive finite prior required')
    key=group_key(row)
    matches=[r for r in known if r['condition_id']!=row['condition_id'] and
             r['winner'] in ('UP','DOWN') and r['cycle']<row['cycle'] and r['cycle']+300<row['timestamp'] and
             r['resolved_at'] is not None and r['resolved_at']<row['timestamp'] and group_key(r)==key]
    wins=sum(r['winner']==key[1] for r in matches)
    alpha=prior+wins;beta=prior+len(matches)-wins
    side_p=alpha/(alpha+beta)
    rng=random.Random(772)
    samples=sorted(rng.betavariate(alpha,beta) for _ in range(draws))
    lo=samples[int(.025*(draws-1))];hi=samples[int(.975*(draws-1))]
    return dict(side=key[1],key=list(key),n=len(matches),wins=wins,alpha=alpha,beta=beta,
                side_probability=side_p,p_up=side_p if key[1]=='UP' else 1-side_p,
                p_down=1-side_p if key[1]=='UP' else side_p,
                credible_95=[lo,hi],interval_method=f'Monte Carlo Beta posterior, {draws} draws, seed 772',
                ready_for_live=False)


def read_signals(path):
    # mode=ro plus query_only prevents the experiment from modifying the live DB.
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
    try:
        rows=db.execute('''SELECT s.cohort,s.cycle,s.timestamp,s.condition_id,o.probability,o.payload,
                m.winner,m.resolved_at FROM samples s JOIN observations o ON o.id=s.observation_id
                JOIN markets m ON m.condition_id=s.condition_id ORDER BY s.timestamp''').fetchall()
    finally:db.close()
    result=[];seen=set()
    for r in rows:
        row=dict(r)
        if row['winner'] not in ('UP','DOWN') or row['resolved_at'] is None or row['resolved_at']<row['cycle']+300:continue
        p=row['probability']
        if p is None or not math.isfinite(p) or not 0<=p<=1:continue
        if not 15<=row['cycle']+300-row['timestamp']<=30:continue
        key=(row['cohort'],row['cycle'])
        if key in seen:continue
        seen.add(key);row['payload']=json.loads(row['payload']);result.append(row)
    return result


def simulated_trade(row,side_probability):
    """Keep raw signal direction + independent LAYA gates; vary calibrated confidence only."""
    raw=row['probability'];side='UP' if raw>.58 else 'DOWN' if raw<.42 else None
    audit=row['payload']['validator'];odds=row['payload']['odds']
    if side is None or side_probability<=.58:return None
    technical=bool(audit.get('technical_pass',audit.get('score',0)>.7))
    if not (technical and audit.get('score',0)>.7 and audit.get('model_connected') and
            audit.get('approved') and (audit.get('model_probability') or 0)>.7):return None
    if audit.get('side',side)!=side:return None
    price=odds.get(side.lower(),0);rate=odds.get('fee_rate',0)
    if not 0<price<1:return None
    cost=price*(1+rate*(1-price));tokens=1/cost
    if side_probability/cost-1<=.05 or odds.get('quotes',{}).get(side,{}).get('size',0)<tokens:return None
    return dict(side=side,pnl=(tokens if row['winner']==side else 0)-1,stake=1.)


def evaluate(rows,prior=2.):
    predictions=[]
    for row in rows:
        post=posterior(row,rows,prior=prior)
        raw=row['probability'];raw_side=raw if post['side']=='UP' else 1-raw
        predictions.append(dict(cycle=row['cycle'],timestamp=row['timestamp'],cohort=row['cohort'],winner=row['winner'],
            raw_p_up=raw,posterior=post,raw_trade=simulated_trade(row,raw_side),
            bayes_trade=simulated_trade(row,post['side_probability'])))
    cohorts={}
    for cohort in sorted({r['cohort'] for r in predictions}):
        part=[r for r in predictions if r['cohort']==cohort];n=len(part)
        def metrics(key):
            ps=[r['raw_p_up'] if key=='raw' else r['posterior']['p_up'] for r in part]
            ys=[int(r['winner']=='UP') for r in part]
            return dict(brier=sum((p-y)**2 for p,y in zip(ps,ys))/n,
                        log_loss=-sum(y*math.log(max(p,1e-6))+(1-y)*math.log(max(1-p,1e-6)) for p,y in zip(ps,ys))/n)
        cohorts[cohort]=dict(resolved=n,raw=metrics('raw'),bayesian=metrics('bayes'),
            predictions_with_group_history=sum(r['posterior']['n']>0 for r in part),
            max_previous_group_samples=max(r['posterior']['n'] for r in part),
            raw_laya_trades=sum(r['raw_trade'] is not None for r in part),
            bayes_laya_trades=sum(r['bayes_trade'] is not None for r in part),
            raw_pnl=sum(r['raw_trade']['pnl'] for r in part if r['raw_trade']),
            bayes_pnl=sum(r['bayes_trade']['pnl'] for r in part if r['bayes_trade']))
    return dict(protocol=PROTOCOL,prior=dict(alpha=prior,beta=prior,mean=.5,chosen='Fixed before evaluation; not selected by performance'),
        scope='Official Polymarket outcomes; frozen 15–30s anchor samples; cohorts never pooled',
        method='Replay: train only on matching past cycles whose official resolution was already recorded before prediction',
        promoted=False,decision='Technically feasible as shadow module. Insufficient current-policy evidence for live probability adjustment.',
        limitations=['Small dependent temporal sample; no reliable significance or profit inference.',
            'Posterior interval is uncertainty about group win frequency under an exchangeability assumption, not the BTC price or a guaranteed trade outcome.',
            'No claim of an independent final holdout. This is a causal replay feasibility experiment.',
            'Only anchor-window quotes: does not evaluate the full-cycle live entry policy.',
            'Fixed Beta(2,2) prior and coarse buckets are hypotheses; require prospective comparison before selecting hyperparameters.',
            'LAYA remains mandatory; its confidence is not multiplied by GAN probability.'],
        cohorts=cohorts,predictions=predictions)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();rows=read_signals(args.db);report=evaluate(rows)
    # Specified prior sensitivity: report all choices; do not pick a winner.
    report['prior_sensitivity']={str(prior):evaluate(rows,prior)['cohorts'] for prior in [1.,2.,5.]}
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'evaluation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('predictions','prior_sensitivity')},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
