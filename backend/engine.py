"""Paper-only execution. Demo quotes never enter the live execution path."""
import math
import os
import random
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from .indicators import market_context
from .directional import technical_audits, POLICIES, POLICY_VERSION, signal_side


class LayaMLXValidator:
    """Transparent technical baseline; external LAYA adapter is intentionally not fabricated."""
    def __init__(self):
        self.model = None
        self.model_name = os.getenv("LAYA_MODEL")
        self.load_error = None

    def validate(self, candles, probability):
        sides=technical_audits(candles)
        for side,audit in sides.items():
            policy=POLICIES[side]
            model_probability=None;error=None
            if self.model_name:
                try:
                    if self.model is None:
                        import laya_mlx
                        self.model=laya_mlx.load(self.model_name)
                    # Each direction gets its own explicit evidence and MLX inference.
                    result=self.model.predict(json.dumps({**audit,'gan_up_probability':probability,
                        'side_probability':probability if side=='UP' else 1-probability}),
                        {"audit":{"type":"choice","instructions":
                            f"Audit only ENTRY_{side}. Require the supplied directional checks, "
                            "technical_pass=true and current price and momentum confirmation. "
                            "Reject neutral or conflicting evidence. Approval of the opposite side "
                            "must never imply approval here. This is consistency, not profitability.",
                            "criteria":["LAYA_APPROVED","LAYA_REJECTED"]}})
                    model_probability=float(result['answers']['audit']['probabilities']['LAYA_APPROVED'])
                    if not math.isfinite(model_probability) or not 0<=model_probability<=1:
                        raise ValueError('Invalid LAYA probability')
                except Exception as exc:
                    error=str(exc);model_probability=None
            approved=bool(audit['technical_pass'] and (model_probability>policy.min_mlx if model_probability is not None else not self.model_name))
            audit.update(approved=approved,model_probability=model_probability,
                         model_connected=model_probability is not None,model_error=error,
                         status='LAYA_APPROVED' if approved and model_probability is not None else 'LAYA_REJECTED' if model_probability is not None else 'TECHNICAL_BASELINE',
                         engine='LAYA MLX + directional audit' if model_probability is not None else 'technical baseline · LAYA MLX not connected')
        self.load_error=next((a['model_error'] for a in sides.values() if a['model_error']),None)
        selected='UP' if probability>.5 else 'DOWN'
        # Compute experimental context AFTER both MLX calls. It cannot change their
        # prompts, scores or execution until a separate prospective comparison exists.
        context=market_context(candles[:-1],float(candles[-1]['close']))
        return {**sides[selected],'sides':sides,'market_context':context}


class QLearningAgent:
    def __init__(self): self.table={}
    def state(self,p,odds,score): return f'{POLICY_VERSION}:{int(p*10)}:{int(odds*10)}:{int(score*10)}'
    def decide(self,p,up,down,score,fee_rate=0):
        if not math.isfinite(p) or not 0<=p<=1:
            raise ValueError('Probability must be finite and between zero and one')
        # Independently price both binary outcomes; a rejected UP is not a DOWN signal.
        candidates={}
        for direction,prob,ask in [('UP',p,up),('DOWN',1-p,down)]:
            cost=ask*(1+fee_rate*(1-ask)) if math.isfinite(ask) else 0
            ev_side=prob/cost-1 if 0<cost<1 else -1
            policy=POLICIES[direction]
            eligible=signal_side(p)==direction
            candidates[direction]=dict(probability=prob,ask=ask,effective_price=cost,
                                       ev=ev_side,probability_pass=eligible,ev_pass=ev_side>policy.min_ev)
        side=signal_side(p)
        policy=POLICIES[side] if side!='WAIT' else POLICIES['UP']
        probability=p if side=='UP' else 1-p
        price=up if side=='UP' else down
        price=price*(1+fee_rate*(1-price))
        ev=probability/price-1 if 0<price<1 else -1
        fraction=min(.05,max(0,.5*(probability-price)/(1-price))) if 0<price<1 else 0
        state=self.state(p,price,score)
        q=self.table.setdefault(state,{'WAIT':0.,'UP':0.,'DOWN':0.})
        # Hard gates cannot be bypassed by exploration or Q-values.
        action=side if side!='WAIT' and score>policy.min_technical and ev>policy.min_ev and q[side]>=q['WAIT'] else 'WAIT'
        return dict(action=action,candidate=side,candidates=candidates,ev=ev,fraction=fraction,state=state,q=q.copy())
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
    candidate=signal_side(probability)
    policy=POLICIES[candidate] if candidate!='WAIT' else POLICIES['UP']
    d['q_permits']=candidate!='WAIT' and d['q'][candidate]>=d['q']['WAIT']
    mlp=audit.get('model_probability')
    validated=bool(audit.get('model_connected') and audit.get('approved') and
                   audit['score']>policy.min_technical and mlp is not None and mlp>policy.min_mlx and
                   audit.get('side')==candidate and audit.get('technical_pass',False))
    if not validated: d['action']='WAIT'
    d.update(profile='gan_laya',stake_usd=1.,fraction=0.,validated=validated,
             gan_probability=probability,laya_model_probability=mlp,
             directional_audit={k:audit.get(k) for k in ('side','policy_version','technical_pass','checks')})
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
    closing_price: float | None=None
    closing_time: float | None=None
    closing_source: str | None=None
    official_outcome: str | None=None
    directional_audit: dict=field(default_factory=dict)


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
            expected=signal_side(p)
            policy=POLICIES[expected] if expected!='WAIT' else POLICIES['UP']
            if not (decision.get('validated') and score>policy.min_technical and mlp is not None and mlp>policy.min_mlx
                    and decision['action']==expected and expected!='WAIT' and validator_status=='LAYA_APPROVED'
                    and decision['ev']>policy.min_ev and decision.get('directional_audit',{}).get('side')==expected
                    and decision.get('directional_audit',{}).get('technical_pass')): return
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
        self.trades.append(Position(len(self.trades)+1,cycle,side,price,stake,tokens,reference,decision['state'],score,now,condition_id=market['condition_id'] if market else '',market_slug=market['slug'] if market else '',fee=fee,validator_status=validator_status,profile=decision.get('profile','strategy'),entry_ev=decision['ev'],below_minimum=below_minimum,gan_probability=decision.get('gan_probability'),laya_model_probability=decision.get('laya_model_probability'),directional_audit=decision.get('directional_audit',{}))); self.save()
        return self.trades[-1]

    def record_close(self,cycle,price,closed_at,source='BINANCE'):
        if not math.isfinite(price) or price<=0 or abs(closed_at-(cycle+300))>.001:
            raise ValueError('Invalid completed candle close')
        changed=False
        for t in self.trades:
            if t.cycle==cycle and t.closing_price is None:
                t.closing_price=price;t.closing_time=closed_at;t.closing_source=source;changed=True
        if changed:self.save()
        return changed

    def resolve(self,condition,side):
        if side not in ('UP','DOWN'): raise ValueError('Invalid settlement side')
        changed=False
        for t in self.trades:
            if t.condition_id!=condition:continue
            if t.official_outcome is None:t.official_outcome=side;changed=True
            if t.status=='OPEN':self._settle_position(t,t.side==side)
        if changed:self.save()

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
            t.closing_price=closing;t.closing_time=cycle+300;t.closing_source='DEMO'
            self._settle_position(t,win)
    def snapshot(self):
        done=[t for t in self.trades if t.status!='OPEN']; profits=sum(max(t.pnl,0) for t in done); losses=-sum(min(t.pnl,0) for t in done)
        balance=self.cash+sum(t.stake for t in self.trades if t.status=='OPEN')
        peak=1000.; dd=0.
        for value in self.equity:
            peak=max(peak,value); dd=max(dd,(peak-value)/peak)
        return dict(cash=self.cash,balance=balance,pnl=balance-1000,win_rate=sum(t.status=='WON' for t in done)/len(done) if done else 0,total_trades=len(done),profit_factor=profits/losses if losses else None,max_drawdown=dd,equity=self.equity,trades=[asdict(t) for t in reversed(self.trades)],paused=self.paused)
