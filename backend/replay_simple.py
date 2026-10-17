"""Counterfactual policy replay, using archived strict-prompt MLX as a proxy only."""
import argparse
import json
import sqlite3
from pathlib import Path
from .simple_rules import edge_decision,execution_gates,SignalConfirmation


def replay(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows=db.execute('''SELECT o.timestamp,o.cycle,o.payload,m.winner FROM observations o
        LEFT JOIN markets m ON m.condition_id=o.condition_id
        WHERE o.cohort LIKE 'v1.2.0-%' ORDER BY o.timestamp,o.id''').fetchall();db.close()
    confirmation=SignalConfirmation();trades=[];entered=set();cycles=set();baseline=0
    for row in rows:
        s=json.loads(row['payload']);cycle=row['cycle'];now=row['timestamp'];cycles.add(cycle)
        odds=s.get('odds') or {};audit=s.get('validator') or {};p=(s.get('gan_quality') or {}).get('healthy')
        # Actual recorded strict gate snapshots, not recreated predictions or weights.
        if s.get('gates') and all(g['ok'] for g in s['gates']):baseline+=1
        # Probability was stored separately from payload by ResearchStore.
        # Archived decision contains the original GAN input, even on WAIT.
        probability=(s.get('decision') or {}).get('gan_probability')
        if probability is None or s.get('error'):
            confirmation.observe(cycle,None,now,False);continue
        decision=edge_decision(probability,odds.get('up',0),odds.get('down',0),audit,odds.get('fee_rate',0))
        chosen=decision['candidate'];selected=audit.get('sides',{}).get(chosen,{})
        models=bool(s.get('model_ready') and selected.get('model_connected'))
        gates=execution_gates(now,cycle,odds,s.get('data_updated_at'),models,p,False,cycle in entered,decision)
        quote=odds.get('quotes',{}).get(chosen,{})
        cost=decision['candidates'][chosen]['effective_price'];tokens=1/cost if cost else float('inf')
        valid=all(g['ok'] for g in gates) and decision['action']!='WAIT' and quote.get('size',0)>=tokens
        if not confirmation.observe(cycle,chosen,now,valid):continue
        entered.add(cycle)
        winner=row['winner'];pnl=(tokens if winner==chosen else 0)-1 if winner in ('UP','DOWN') else None
        trades.append(dict(cycle=cycle,timestamp=now,side=chosen,ask=odds[chosen.lower()],edge=decision['edge'],
            mlx_proxy=decision['laya_model_probability'],tokens=tokens,official_winner=winner,pnl=pnl))
    resolved=[t for t in trades if t['pnl'] is not None]
    return dict(method='Counterfactual first-fill chronological replay, archived strict-prompt MLX used as proxy; no inference with new prompt',
        observations=len(rows),cycles=len(cycles),strict_all_gates_snapshots=baseline,
        experimental_entries=len(trades),resolved=len(resolved),pending=len(trades)-len(resolved),
        up=sum(t['side']=='UP' for t in trades),down=sum(t['side']=='DOWN' for t in trades),
        pnl=sum(t['pnl'] for t in resolved),win_rate=sum(t['pnl']>0 for t in resolved)/len(resolved) if resolved else None,
        limitations=['Same audited period; not held-out evidence or prospective profit.',
            'New MLX veto prompt was not available historically. Entry counts and PnL are conditional on reusing old confidence as a proxy.',
            'One fill per cycle at first eligible archived ask; gaps reset 3-tick confirmation.',
            'No latency reconstruction; quotes may disappear before a real fill. Fractional paper below minimum only.'],trades=trades)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    report=replay(args.db);p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='trades'},indent=2))
