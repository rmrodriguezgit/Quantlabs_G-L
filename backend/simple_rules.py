"""Experimental paper policy: net edge + required MLX veto, stable for 3 ticks."""
import math

VERSION='edge-laya-v1'
MIN_EDGE=.04
MIN_LAYA=.35
MIN_REMAINING=20
MAX_REMAINING=240


def edge_decision(p,up,down,audit,fee_rate=0.,q_table=None):
    if not math.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid probability')
    if not math.isfinite(fee_rate) or fee_rate<0:raise ValueError('Invalid fee rate')
    candidates={}
    for side,prob,ask in [('UP',p,up),('DOWN',1-p,down)]:
        valid=math.isfinite(ask) and 0<ask<1
        cost=ask*(1+fee_rate*(1-ask)) if valid else None
        edge=prob-cost if cost is not None else None
        a=audit.get('sides',{}).get(side,{})
        mlp=a.get('model_probability')
        laya=bool(a.get('model_connected') and not a.get('model_error') and
                  mlp is not None and math.isfinite(mlp) and MIN_LAYA<=mlp<=1)
        edge_pass=edge is not None and edge+1e-12>=MIN_EDGE
        candidates[side]=dict(probability=prob,ask=ask,effective_price=cost,edge=edge,
            ev=prob/cost-1 if cost else -1.,probability_pass=True,ev_pass=edge_pass,
            edge_pass=edge_pass,laya_pass=laya,laya_probability=mlp,eligible=edge_pass and laya)
    ranked=sorted(candidates,key=lambda s:candidates[s]['edge'] if candidates[s]['edge'] is not None else -math.inf,reverse=True)
    eligible=[s for s in ranked if candidates[s]['eligible']]
    side=eligible[0] if eligible else ranked[0];c=candidates[side]
    state=f'{VERSION}:{side}:{int(p*10)}:{int((c["effective_price"] or 0)*10)}'
    q={'WAIT':0.,'UP':0.,'DOWN':0.}
    if q_table is not None:q=q_table.setdefault(state,q).copy()
    return dict(action=side if eligible else 'WAIT',candidate=side,candidates=candidates,
        edge=c['edge'],ev=c['ev'],fraction=0.,stake_usd=1.,profile='edge_laya',
        policy_version=VERSION,state=state,q=q,q_role='diagnostic_only',
        gan_probability=p,laya_model_probability=c['laya_probability'],validated=bool(eligible),
        confirmation_ticks=0)


class SignalConfirmation:
    def __init__(self):self.cycle=None;self.side=None;self.count=0;self.last=None;self.first=None
    def observe(self,cycle,side,now,eligible):
        if not eligible or side not in ('UP','DOWN'):
            self.__init__();return False
        continuation=self.cycle==cycle and self.side==side and self.last is not None and 0<now-self.last<=5
        self.count=self.count+1 if continuation else 1
        if not continuation:self.first=now
        self.cycle=cycle;self.side=side;self.last=now
        return self.count>=3 and now-self.first>=2


def execution_gates(now,cycle,market,data_at,models,healthy,paused,already,decision):
    side=decision.get('candidate');quote=(market or {}).get('quotes',{}).get(side,{})
    fresh=lambda stamp: isinstance(stamp,(int,float)) and math.isfinite(stamp) and -3<=now-stamp<=5
    c=decision.get('candidates',{}).get(side,{})
    return [dict(name='Mercado actual y cuotas reales frescas',ok=bool(market and market.get('slug')==f'btc-updown-5m-{cycle}' and fresh(market.get('timestamp')) and fresh(quote.get('timestamp')))),
        dict(name='BTC fresco y modelos conectados',ok=bool(models and fresh(data_at))),
        dict(name='GAN saludable',ok=bool(healthy)),
        dict(name='Ventana: 60–280s desde apertura',ok=MIN_REMAINING<=cycle+300-now<=MAX_REMAINING),
        dict(name='Edge neto ≥4 puntos porcentuales',ok=bool(c.get('edge_pass'))),
        dict(name='LAYA conectado, sin veto (≥35%)',ok=bool(c.get('laya_pass'))),
        dict(name='Motor activo, máximo una entrada por ciclo',ok=not paused and not already)]
