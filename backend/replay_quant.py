"""Read-only chronological, frozen-policy diagnostic; never invent missing books.

Split by complete cycles 80/20, no fitting. Early-exit performance is unavailable
when historical executable bids are absent; hold-to-official-resolution is reported.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from .engine import PaperTradingEngine
from .quant_risk import quant_decision, performance
from .simple_rules import SignalConfirmation, execution_gates


def evaluate(rows):
    engine=PaperTradingEngine();confirmation=SignalConfirmation();settlements={};missing_atr=0;missing_bids=0
    for row in rows:
        s=json.loads(row['payload']);now=row['timestamp'];cycle=row['cycle']
        # An eventual winner is never visible to the entry/risk policy before publication.
        for condition,(winner,published) in settlements.items():
            if winner and published is not None and published<=now:engine.resolve(condition,winner,now=now)
        odds=s.get('odds') or {};audit=s.get('validator') or {}
        if odds.get('condition_id'):settlements[odds['condition_id']]=(row['winner'],row['resolved_at'])
        if not (audit.get('market_context',{}).get('atr') or {}).get('value'):missing_atr+=1
        if not odds.get('bids'):missing_bids+=1
        p=row['probability']
        if p is None or s.get('error'):
            confirmation.observe(cycle,None,now,False);continue
        d=quant_decision(p,odds.get('up',0),odds.get('down',0),audit,odds.get('fee_rate',0),engine.snapshot(),s.get('price',0),now)
        side=d['candidate'];a=audit.get('sides',{}).get(side,{})
        gates=execution_gates(now,cycle,odds,s.get('data_updated_at'),s.get('model_ready') and a.get('model_connected'),(s.get('gan_quality') or {}).get('healthy'),False,any(t.cycle==cycle for t in engine.trades),d)
        eligible=all(g['ok'] for g in gates) and d['risk']['allowed'] and d['action']!='WAIT'
        stable=confirmation.observe(cycle,side,now,eligible)
        if not stable:continue
        d.update(confirmation_ticks=confirmation.count,stable_seconds=now-confirmation.first,confirmed_cycle=cycle,confirmed_side=side)
        engine.enter(cycle,now,s['reference'],d,a.get('score',0),odds['up'],odds['down'],odds,'LAYA_APPROVED')
    # End-of-sample scoring, separated from all entry and capital decisions.
    for condition,(winner,_) in settlements.items():
        if winner in ('UP','DOWN'):engine.resolve(condition,winner,now=now)
    result=engine.snapshot();trades=result['trades']
    stress=[]
    for t in trades:
        if t['status']=='OPEN':continue
        # Same fixed entries, adverse extra $0.01/token; not a policy retuned on stress data.
        raw=t['price']+.01
        # Recover known entry fee rate from recorded fill, not a hardcoded schedule.
        rate=t['fee']/(t['tokens']*t['price']*(1-t['price'])) if 0<t['price']<1 else 0
        cost=raw*(1+rate*(1-raw))
        if 0<raw<1:stress.append((1/cost if t['official_outcome']==t['side'] else 0)-1)
    return dict(entries=len(trades),resolved=result['total_trades'],pending=sum(t['status']=='OPEN' for t in trades),
        pnl=result['pnl'],win_rate=result['win_rate'] if result['total_trades'] else None,
        sharpe=result['performance']['sharpe'],sortino=result['performance']['sortino'],
        max_drawdown=result['max_drawdown'],profit_factor=result['profit_factor'],
        stress_same_entries_extra_cent=sum(stress),missing_atr_snapshots=missing_atr,missing_bid_snapshots=missing_bids,trades=trades)


def replay(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows=db.execute('''SELECT o.timestamp,o.cycle,o.payload,o.probability,m.winner,m.resolved_at
        FROM observations o LEFT JOIN markets m ON o.condition_id=m.condition_id
        WHERE o.cohort LIKE 'v1.2.0-%' OR o.cohort LIKE 'v1.3.0-%' ORDER BY o.timestamp,o.id''').fetchall();db.close()
    cycles=sorted({r['cycle'] for r in rows});cut=max(1,int(len(cycles)*.8));boundary=cycles[cut] if cut<len(cycles) else float('inf')
    return dict(version='1.4.0-rc.1',observations=len(rows),cycles=len(cycles),split='80/20 ciclos completos, reglas fijas, sin ajuste',
        development=evaluate([r for r in rows if r['cycle']<boundary]),holdout=evaluate([r for r in rows if r['cycle']>=boundary]),
        limitations=['Replay contrafactual con confianza MLX archivada como proxy; no ejecuta el nuevo prompt.',
          'Pocos ciclos, periodo previamente observado: el 20% final es una separación temporal, no evidencia prospectiva independiente.',
          'Sin bids históricos completos: no se calcula rentabilidad de stops/trailing/TP. Resultados de mantener hasta resolución oficial.',
          'No reconstruye latencia ni profundidad futura; excluye falta de ATR o cuotas. Sharpe/Sortino por trade, sin anualizar.',
          'La GAN estima Binance, no está calibrada para resolución Chainlink. No se ha demostrado rentabilidad.'])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    report=replay(args.db);out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
    print(json.dumps({**report,'development':{k:v for k,v in report['development'].items() if k!='trades'},'holdout':{k:v for k,v in report['holdout'].items() if k!='trades'}},indent=2))
