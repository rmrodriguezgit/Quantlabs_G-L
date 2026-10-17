"""Paper-only execution. Demo quotes never enter the live execution path."""
import math
import os
import random
import json
from pathlib import Path
from dataclasses import dataclass, asdict


class LayaMLXValidator:
    """Transparent technical baseline; external LAYA adapter is intentionally not fabricated."""
    def __init__(self):
        self.model = None
        self.model_name = os.getenv("LAYA_MODEL")
        self.load_error = None

    def validate(self, candles, probability):
        closes = [c['close'] for c in candles]
        changes = [b-a for a,b in zip(closes[-15:-1], closes[-14:])]
        gain = sum(max(x,0) for x in changes)/max(1,len(changes))
        loss = sum(max(-x,0) for x in changes)/max(1,len(changes))
        rsi = 100-100/(1+gain/loss) if loss else (100 if gain else 50)
        def ema(n):
            value=closes[0]
            for c in closes[1:]: value += 2/(n+1)*(c-value)
            return value
        delta=sum(c.get('delta',(1 if c['close']>c['open'] else -1)*c['volume']) for c in candles[-5:])
        up=probability>.5
        votes=[(rsi>50)==up,(ema(9)>ema(21))==up,(delta>0)==up]
        score=sum(votes)/3
        model_probability = None
        if self.model_name:
            try:
                if self.model is None:
                    import laya_mlx
                    self.model = laya_mlx.load(self.model_name)
                result = self.model.predict(
                    json.dumps(dict(side='UP' if up else 'DOWN',gan_probability=probability,rsi=rsi,ema_fast=ema(9),ema_slow=ema(21),delta_volume=delta,technical_agreement=score)),
                    {"audit":{"type":"choice","instructions":"Approve only if RSI direction, EMA cross and signed candle volume agree with the proposed side. This is a consistency audit, not a profitability prediction.","criteria":["LAYA_APPROVED","LAYA_REJECTED"]}})
                model_probability = float(result['answers']['audit']['probabilities']['LAYA_APPROVED'])
                if not math.isfinite(model_probability) or not 0<=model_probability<=1:
                    raise ValueError('Invalid LAYA probability')
                self.load_error = None
            except Exception as exc:
                self.load_error = str(exc)
        approved = score>.7 and (model_probability>.7 if model_probability is not None else not self.model_name)
        return dict(score=score,rsi=rsi,delta_volume=delta,ema_fast=ema(9),ema_slow=ema(21),approved=approved,model_probability=model_probability,model_connected=model_probability is not None,model_error=self.load_error,status='LAYA_APPROVED' if approved and model_probability is not None else 'LAYA_REJECTED' if model_probability is not None else 'TECHNICAL_BASELINE',engine='LAYA MLX + technical audit' if model_probability is not None else 'technical baseline · LAYA MLX not connected')


class QLearningAgent:
    def __init__(self): self.table={}
    def state(self,p,odds,score): return f'{int(p*10)}:{int(odds*10)}:{int(score*10)}'
    def decide(self,p,up,down,score,fee_rate=0):
        side='UP' if p>.58 else 'DOWN' if p<.42 else 'WAIT'
        probability=p if side=='UP' else 1-p
        price=up if side=='UP' else down
        price=price*(1+fee_rate*(1-price))
        ev=probability/price-1 if 0<price<1 else -1
        fraction=min(.05,max(0,.5*(probability-price)/(1-price))) if 0<price<1 else 0
        state=self.state(p,price,score)
        q=self.table.setdefault(state,{'WAIT':0.,'UP':0.,'DOWN':0.})
        # Hard gates cannot be bypassed by exploration or Q-values.
        action=side if side!='WAIT' and score>.7 and ev>.05 and q[side]>=q['WAIT'] else 'WAIT'
        return dict(action=action,ev=ev,fraction=fraction,state=state,q=q.copy())
    def update(self,state,side,reward):
        # Each settled candle is a terminal episode: no bootstrap from future data.
        values=self.table.setdefault(state,{'WAIT':0.,'UP':0.,'DOWN':0.})
        values[side]+=.1*(reward-values[side])


def exploratory_decision(probability, up, down, fee_rate=0.):
    """One-dollar exercise at the cheaper real ask, independent of signal approval."""
    candidates=[(price,side) for price,side in [(up,'UP'),(down,'DOWN')] if 0<price<=1]
    if not candidates: return dict(action='WAIT',ev=0,fraction=0,profile='exploratory')
    _,side=min(candidates)
    raw=up if side=='UP' else down
    price=raw*(1+fee_rate*(1-raw))
    win_probability=probability if side=='UP' else 1-probability
    return dict(action=side,ev=win_probability/price-1,fraction=0.,stake_usd=1.,
                state=f'EXPLORATORY:{side}',profile='exploratory')


def gan_laya_decision(agent, probability, up, down, audit, fee_rate=0.):
    """GAN chooses side; technical agreement and actual MLX approval are mandatory."""
    d=agent.decide(probability,up,down,audit['score'],fee_rate)
    candidate='UP' if probability>.58 else 'DOWN' if probability<.42 else 'WAIT'
    d['q_permits']=candidate!='WAIT' and d['q'][candidate]>=d['q']['WAIT']
    mlp=audit.get('model_probability')
    validated=bool(audit.get('model_connected') and audit.get('approved') and
                   audit['score']>.7 and mlp is not None and mlp>.7)
    if not validated: d['action']='WAIT'
    d.update(profile='gan_laya',stake_usd=1.,fraction=0.,validated=validated,
             gan_probability=probability,laya_model_probability=mlp)
    return d


@dataclass
class Position:
    id: int
    cycle: int
    side: str
    price: float
    stake: float
    tokens: float
    reference: float
    state: str
    laya_score: float
    timestamp: float
    status: str='OPEN'
    pnl: float=0.
    condition_id: str=''
    market_slug: str=''
    fee: float=0.
    validator_status: str='TECHNICAL_BASELINE'
    profile: str='strategy'
    entry_ev: float=0.
    below_minimum: bool=False
    gan_probability: float | None=None
    laya_model_probability: float | None=None


class PaperTradingEngine:
    def __init__(self,path=None):
        self.path=Path(path) if path else None
        self.cash=1000.; self.trades=[]; self.equity=[1000.]; self.agent=QLearningAgent(); self.paused=False; self.blocked_through_cycle=-1
        if self.path and self.path.exists():
            d=json.loads(self.path.read_text()); self.cash=d['cash']; self.trades=[Position(**x) for x in d['trades']]; self.equity=d['equity']; self.agent.table=d['q']; self.blocked_through_cycle=d.get('blocked_through_cycle',-1)
    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp'); temp.write_text(json.dumps(dict(cash=self.cash,trades=[asdict(x) for x in self.trades],equity=self.equity,q=self.agent.table,blocked_through_cycle=self.blocked_through_cycle))); temp.replace(self.path)
    def enter(self,cycle,now,reference,decision,score,up,down,market=None,validator_status='TECHNICAL_BASELINE'):
        if self.paused or cycle<=self.blocked_through_cycle or decision['action']=='WAIT' or any(t.cycle==cycle for t in self.trades): return
        if decision.get('profile')=='gan_laya':
            p=decision.get('gan_probability',.5)
            mlp=decision.get('laya_model_probability')
            expected='UP' if p>.58 else 'DOWN' if p<.42 else 'WAIT'
            if not (decision.get('validated') and score>.7 and mlp is not None and mlp>.7
                    and decision['action']==expected and expected!='WAIT' and validator_status=='LAYA_APPROVED'
                    and decision['ev']>.05): return
        fixed=decision.get('stake_usd') if decision.get('profile') in ('exploratory','gan_laya') else None
        if fixed is not None and (fixed!=1. or self.cash<fixed): return
        stake=fixed if fixed is not None else round(self.cash*decision['fraction'],2)
        if stake<.01: return
        side=decision['action']; price=up if side=='UP' else down
        tokens=stake/price
        fee=0.
        below_minimum=False
        if market:
            # Stay within visible best-ask size. Do not assume unlimited liquidity.
            quote=market['quotes'][side]
            tokens=stake/(price*(1+market['fee_rate']*(1-price)))
            if fixed is not None and tokens>quote['size']: return
            tokens=min(tokens,quote['size'])
            below_minimum=tokens<quote['min_size']
            # Fractional paper fills are allowed only in the fixed-dollar exercise.
            # Keep the strict strategy subject to actual market minimums.
            if below_minimum and fixed is None: return
            fee=tokens*market['fee_rate']*price*(1-price)
            stake=fixed if fixed is not None else tokens*price+fee
        self.cash-=stake
        self.trades.append(Position(len(self.trades)+1,cycle,side,price,stake,tokens,reference,decision['state'],score,now,condition_id=market['condition_id'] if market else '',market_slug=market['slug'] if market else '',fee=fee,validator_status=validator_status,profile=decision.get('profile','strategy'),entry_ev=decision['ev'],below_minimum=below_minimum,gan_probability=decision.get('gan_probability'),laya_model_probability=decision.get('laya_model_probability'))); self.save()
        return self.trades[-1]

    def resolve(self,condition,side):
        if side not in ('UP','DOWN'): raise ValueError('Invalid settlement side')
        for t in self.trades:
            if t.status=='OPEN' and t.condition_id==condition:
                self._settle_position(t,t.side==side)

    def _settle_position(self,t,win):
        payout=t.tokens if win else 0
        self.cash+=payout; t.pnl=payout-t.stake; t.status='WON' if win else 'LOST'
        self.agent.update(t.state,t.side,t.pnl/t.stake)
        self.equity.append(self.cash+sum(x.stake for x in self.trades if x.status=='OPEN')); self.save()
    def settle(self,cycle,closing):
        for t in self.trades:
            if t.status!='OPEN' or t.cycle!=cycle: continue
            # Demo convention: tie resolves DOWN. Live resolution must use market rules.
            win=(closing>t.reference)==(t.side=='UP')
            if t.condition_id: continue  # Live positions require official market resolution.
            self._settle_position(t,win)
    def snapshot(self):
        done=[t for t in self.trades if t.status!='OPEN']; profits=sum(max(t.pnl,0) for t in done); losses=-sum(min(t.pnl,0) for t in done)
        balance=self.cash+sum(t.stake for t in self.trades if t.status=='OPEN')
        peak=1000.; dd=0.
        for value in self.equity:
            peak=max(peak,value); dd=max(dd,(peak-value)/peak)
        return dict(cash=self.cash,balance=balance,pnl=balance-1000,win_rate=sum(t.status=='WON' for t in done)/len(done) if done else 0,total_trades=len(done),profit_factor=profits/losses if losses else None,max_drawdown=dd,equity=self.equity,trades=[asdict(t) for t in reversed(self.trades)],paused=self.paused)
