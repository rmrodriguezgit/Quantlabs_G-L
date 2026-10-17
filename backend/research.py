"""Prospective signal audit and paired shadow evaluation; never places orders."""
import csv
import io
import json
import math
import sqlite3
import time
from pathlib import Path

def finite_payload(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:finite_payload(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite_payload(v) for v in value]
    return value


VERSION='1.1.0'
COHORT='v1.1.0-anchor30to15-ev005-slippage001'
VARIANTS=[('gan','GAN sola'),('technical','GAN + indicadores'),('laya','GAN + indicadores + LAYA')]


class ResearchStore:
    def __init__(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS observations(
                id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, cycle INTEGER NOT NULL,
                cohort TEXT NOT NULL, condition_id TEXT, action TEXT NOT NULL,
                probability REAL, model_probability REAL, technical_score REAL,
                fresh INTEGER NOT NULL, blockers TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS observations_cohort ON observations(cohort,id);
            CREATE TABLE IF NOT EXISTS markets(
                condition_id TEXT PRIMARY KEY, cycle INTEGER NOT NULL, slug TEXT,
                winner TEXT, resolved_at REAL, checked_at REAL);
            CREATE TABLE IF NOT EXISTS samples(
                cohort TEXT NOT NULL, cycle INTEGER NOT NULL, observation_id INTEGER NOT NULL,
                condition_id TEXT NOT NULL, timestamp REAL NOT NULL,
                PRIMARY KEY(cohort,cycle));
            CREATE INDEX IF NOT EXISTS samples_condition ON samples(condition_id);
        ''')
        if 'checked_at' not in {r[1] for r in self.db.execute('PRAGMA table_info(markets)')}:
            self.db.execute('ALTER TABLE markets ADD COLUMN checked_at REAL')
        self.db.commit()
        self._cached=None;self._cached_at=0

    def record(self,snapshot):
        now=float(snapshot['timestamp']);cycle=int(snapshot['cycle'])
        live=snapshot.get('mode')=='live'
        odds=snapshot.get('odds',{});audit=snapshot.get('validator',{})
        quality=snapshot.get('gan_quality',{})
        data_at=snapshot.get('data_updated_at')
        fresh=bool(live and not snapshot.get('error') and data_at and
                   -3<=now-data_at<=5 and odds.get('available') and
                   -3<=now-odds.get('timestamp',0)<=5 and
                   all(-3<=now-q.get('timestamp',0)<=5 for q in odds.get('quotes',{}).values()))
        p=snapshot.get('probability') if quality.get('healthy') and fresh else None
        if p is not None and (not math.isfinite(p) or not 0<=p<=1):p=None
        # Keep raw contemporaneous evidence, including rejected and unavailable signals.
        payload={k:snapshot.get(k) for k in ('mode','profile','cycle','remaining','price','reference','data_updated_at','estimator','gan_quality','model_ready','validator','decision','odds','gates','blockers','error')}
        payload.update(version=VERSION,cohort=COHORT)
        condition=odds.get('condition_id') if live and odds.get('slug')==f'btc-updown-5m-{cycle}' else None
        with self.db:
            row=self.db.execute('''INSERT INTO observations(timestamp,cycle,cohort,condition_id,action,probability,model_probability,technical_score,fresh,blockers,payload)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(now,cycle,COHORT,condition,snapshot.get('decision',{}).get('action','WAIT'),p,audit.get('model_probability'),audit.get('score'),int(fresh),json.dumps(snapshot.get('blockers',[])),json.dumps(finite_payload(payload),allow_nan=False)))
            if condition:
                self.db.execute('INSERT OR IGNORE INTO markets(condition_id,cycle,slug) VALUES(?,?,?)',(condition,cycle,odds.get('slug')))
            # Freeze ONE paired observation per cycle before outcome publication.
            # Missed windows remain missing; never backfill with later information.
            has_quotes=any(0<odds.get(k,0)<=1 for k in ('up','down'))
            if fresh and condition and p is not None and has_quotes and 15<=cycle+300-now<=30:
                self.db.execute('INSERT OR IGNORE INTO samples VALUES(?,?,?,?,?)',(COHORT,cycle,row.lastrowid,condition,now))
        return row.lastrowid

    def pending_conditions(self,now,limit=8):
        return [r['condition_id'] for r in self.db.execute('SELECT condition_id FROM markets WHERE winner IS NULL AND cycle+300<? ORDER BY COALESCE(checked_at,0),cycle LIMIT ?',(now,limit))]

    def mark_checked(self,condition,now):
        with self.db:self.db.execute('UPDATE markets SET checked_at=? WHERE condition_id=?',(now,condition))

    def resolve(self,condition,winner,now=None):
        if winner not in ('UP','DOWN'):raise ValueError('Invalid official winner')
        with self.db:
            self.db.execute('UPDATE markets SET winner=?,resolved_at=? WHERE condition_id=? AND winner IS NULL',(winner,now or time.time(),condition))
        self._cached=None

    @staticmethod
    def payoff(payload,p,winner,slippage=0.):
        side='UP' if p>.58 else 'DOWN' if p<.42 else None
        if not side:return None
        odds=payload['odds'];raw=odds[side.lower()]
        if not 0<raw<1:return None
        price=raw+slippage
        if not 0<price<1:return None
        fee_rate=odds.get('fee_rate',0)
        cost=price+fee_rate*price*(1-price)
        probability=p if side=='UP' else 1-p
        # Entry eligibility uses only the contemporaneous raw ask, not future stress pricing.
        entry_cost=raw+fee_rate*raw*(1-raw)
        if probability/entry_cost-1<=.05:return None
        quote=odds.get('quotes',{}).get(side,{})
        tokens=1/cost
        # No unlimited size assumptions. Fixed-dollar fractional paper fills only.
        if quote.get('size',0)<tokens:return None
        return dict(pnl=(tokens if side==winner else 0)-1,
                    won=side==winner,below_minimum=tokens<quote.get('min_size',5),side=side)

    def report(self,force=False):
        if not force and self._cached is not None and time.monotonic()-self._cached_at<5:return self._cached
        counts=self.db.execute('SELECT COUNT(*) AS n,MIN(timestamp) AS since,SUM(fresh) AS fresh FROM observations WHERE cohort=?',(COHORT,)).fetchone()
        rows=self.db.execute('''SELECT o.probability,o.payload,m.winner,s.cycle,s.timestamp
            FROM samples s JOIN observations o ON o.id=s.observation_id
            JOIN markets m ON m.condition_id=s.condition_id WHERE s.cohort=? ORDER BY s.cycle''',(COHORT,)).fetchall()
        resolved=[r for r in rows if r['winner'] in ('UP','DOWN')]
        # These are forward-collected outcomes. No claim of historical backtest or fitted calibration.
        variants=[]
        for key,label in VARIANTS:
            base=[];stress=[]
            for r in resolved:
                payload=json.loads(r['payload']);audit=payload['validator']
                if key in ('technical','laya') and audit.get('score',0)<=.7:continue
                if key=='laya' and not (audit.get('model_connected') and audit.get('approved') and (audit.get('model_probability') or 0)>.7):continue
                result=self.payoff(payload,r['probability'],r['winner'])
                if result is not None:
                    base.append(result)
                    stressed=self.payoff(payload,r['probability'],r['winner'],.01)
                    if stressed is not None:stress.append(stressed)
            gains=sum(max(x['pnl'],0) for x in base);losses=-sum(min(x['pnl'],0) for x in base)
            balance=peak=1000.;drawdown=0.
            for trade in base:
                balance+=trade['pnl'];peak=max(peak,balance);drawdown=max(drawdown,(peak-balance)/peak)
            variants.append(dict(key=key,label=label,trades=len(base),win_rate=sum(t['won'] for t in base)/len(base) if base else None,
                pnl=sum(t['pnl'] for t in base) if base else None,profit_factor=gains/losses if losses else None,
                max_drawdown=drawdown if base else None,entry_rate=len(base)/len(resolved) if resolved else None,
                below_minimum=sum(t['below_minimum'] for t in base),stress_trades=len(stress),stress_pnl=sum(t['pnl'] for t in stress) if stress else None))
        bins=[]
        for index in range(10):
            bucket=[r for r in resolved if min(9,int(r['probability']*10))==index]
            bins.append(dict(low=index/10,high=(index+1)/10,count=len(bucket),
                predicted=sum(r['probability'] for r in bucket)/len(bucket) if bucket else None,
                actual=sum(r['winner']=='UP' for r in bucket)/len(bucket) if bucket else None))
        brier=sum((r['probability']-(r['winner']=='UP'))**2 for r in resolved)/len(resolved) if resolved else None
        blockers={}
        # SQL aggregation avoids parsing complete audit payloads for every refresh.
        for row in self.db.execute('SELECT blockers,COUNT(*) AS n FROM observations WHERE cohort=? GROUP BY blockers',(COHORT,)):
            for reason in json.loads(row['blockers']):blockers[reason]=blockers.get(reason,0)+row['n']
        result=dict(cohort=COHORT,version=VERSION,observations=counts['n'],fresh_observations=counts['fresh'] or 0,since=counts['since'],
            samples=len(rows),resolved=len(resolved),pending=len(rows)-len(resolved),brier=brier,brier_reference=.25,
            variants=variants,calibration=bins,blockers=sorted([dict(reason=k,count=v) for k,v in blockers.items()],key=lambda x:-x['count']),
            protocol='Misma señal por ciclo, primera lectura válida entre 30s y 15s del cierre; tamaño paper $1; EV>0.05; sin filtro Q. No altera órdenes.',
            stress_note='Estrés hipotético: +$0.01 por token, más tasas. No reconstruye latencia ni profundidad posterior.',
            evidence='Recopilación prospectiva; todavía no demuestra ventaja ni probabilidades calibradas.' if len(resolved)<200 else 'Muestra prospectiva descriptiva; contrastar incertidumbre y periodos posteriores antes de ajustar reglas.')
        self._cached=result;self._cached_at=time.monotonic()
        return result

    def export_csv(self,limit=10000):
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(['id','timestamp_utc_epoch','cycle','cohort','condition_id','action','gan_p_up','laya_approval','technical_agreement','fresh','blockers_json','official_winner','payload_json'])
        rows=self.db.execute('''SELECT o.*,m.winner FROM observations o LEFT JOIN markets m ON m.condition_id=o.condition_id
            WHERE cohort=? ORDER BY o.id DESC LIMIT ?''',(COHORT,min(max(limit,1),100000))).fetchall()
        for r in reversed(rows):writer.writerow([r[k] for k in ('id','timestamp','cycle','cohort','condition_id','action','probability','model_probability','technical_score','fresh','blockers','winner','payload')])
        return output.getvalue()

    def close(self):self.db.close()
