"""Binary-contract math and bounded paper risk. No probability is certified alpha."""
import math
from functools import lru_cache
from .simple_rules import edge_decision

VERSION = 'quant-risk-v1'
SLIPPAGE = .005  # Conservative half-cent per token, both entry and early exit.
MIN_RR = 2.
RISK_HORIZON = 100
MAX_RUIN = .0001


def binary_terms(p, ask, rate, slippage=SLIPPAGE):
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (p,ask,rate,slippage)):
        return None
    price=ask+slippage
    if not 0<=p<=1 or not 0<ask<=price<1 or rate<0 or slippage<0:return None
    cost=price*(1+rate*(1-price))
    if not 0<cost<1:return None
    reward=1/cost-1
    return dict(probability=p,ask=ask,fill_price=price,cost_per_token=cost,
                reward=reward,loss=1.,rr=reward,ev=p*reward-(1-p),edge=p-cost,
                half_kelly=max(0.,.5*(p-cost)/(1-cost)),slippage_per_token=slippage)


@lru_cache(maxsize=512)
def ruin_probability(capital, stake, p, reward, horizon=RISK_HORIZON):
    """Exact finite-horizon first-passage DP for constant $ stake and iid binary payoff.

    Ruin = cannot fund the NEXT stake. It is not drawdown and not a long-run promise.
    The loss-only bound often makes it zero over 100 $1 trades on a $1000 account.
    """
    if not all(math.isfinite(x) for x in (capital,stake,p,reward)) or stake<=0 or capital<0 or not 0<=p<=1 or reward<0 or not 0<=horizon<=1000:
        raise ValueError('Invalid ruin inputs')
    if capital<stake:return 1.
    if capital-horizon*stake>=stake:return 0.
    paths={0:1.};ruin=0.
    for n in range(1,horizon+1):
        nxt={}
        for wins,mass in paths.items():
            for w,weight in ((wins,mass*(1-p)),(wins+1,mass*p)):
                equity=capital+stake*(w*reward-(n-w))
                if equity<stake-1e-10:ruin+=weight
                else:nxt[w]=nxt.get(w,0.)+weight
        paths=nxt
    return min(1.,max(0.,ruin))


def risk_assessment(account, terms, atr, spot, now):
    cash=account['cash'];balance=account['balance'];trades=account.get('trades',[])
    opened=sum(t['stake'] for t in trades if t['status']=='OPEN')
    done=[t for t in trades if t['status']!='OPEN']
    day=int(now//86400)*86400  # Explicit UTC calendar day; persisted timestamps.
    today=sum(t['pnl'] for t in done if (t.get('exit_time') or t.get('settled_at') or t['cycle']+300)>=day)
    start=balance-today
    atr_valid=isinstance(atr,(int,float)) and math.isfinite(atr) and atr>0 and math.isfinite(spot) and spot>0
    fraction=max(.005,min(.01,.01/(max(1.,atr/spot/.001)))) if atr_valid else 0.
    budget=balance*fraction
    kelly_budget=balance*min(.02,terms['half_kelly']) if terms else 0.
    ruin=ruin_probability(round(max(0.,cash),8),1.,terms['probability'],terms['reward']) if terms else None
    checks=[dict(name='EV terminal neto >0 y R/R ≥2',ok=bool(terms and terms['ev']>0 and terms['rr']+1e-12>=MIN_RR)),
        dict(name='ATR cerrado válido para gestión',ok=atr_valid),
        dict(name='$1 dentro del presupuesto ATR y Half-Kelly',ok=cash>=1 and min(budget,kelly_budget)>=1),
        dict(name='Exposición total ≤2% del capital',ok=opened+1<=max(0,balance)*.02),
        dict(name='Pérdida diaria UTC más exposición ≤2%',ok=max(0,-today)+opened+1<=max(0,start)*.02),
        dict(name='Drawdown realizado más exposición ≤5%',ok=max(0,account.get('max_drawdown',0))+(opened+1)/max(balance,1)<.05),
        dict(name='Ruina modelada a 100 trades <0.01%',ok=ruin is not None and ruin<MAX_RUIN)]
    return dict(version=VERSION,checks=checks,allowed=all(c['ok'] for c in checks),stake=1.,
                risk_fraction=fraction,risk_budget=budget,kelly_budget=kelly_budget,open_risk=opened,
                daily_pnl=today,daily_start=start,ruin=ruin,ruin_horizon=RISK_HORIZON,
                ruin_definition='No poder financiar el siguiente $1; iid, cuota y tamaño constantes; no garantía ni drawdown',
                atr=atr if atr_valid else None,stop_distance=2*atr if atr_valid else None,
                take_distance=4*atr if atr_valid else None,terms=terms,
                note='EV y R/R de mantener hasta resolución. Las salidas ATR pueden cambiar su distribución. P GAN no calibrada para Chainlink.')


def quant_decision(p, up, down, audit, rate, account, spot, now, q_table=None):
    # Filter both sides BEFORE ranking: rejecting an expensive UP must not hide DOWN.
    d=edge_decision(p,up,down,audit,rate,q_table)
    atr=(audit.get('market_context',{}).get('atr') or {}).get('value')
    risks={}
    for side,prob,ask in [('UP',p,up),('DOWN',1-p,down)]:
        terms=binary_terms(prob,ask,rate)
        r=risk_assessment(account,terms,atr,spot,now);risks[side]=r
        c=d['candidates'][side]
        c.update(edge=terms['edge'] if terms else None,ev=terms['ev'] if terms else -1,
                 rr=terms['rr'] if terms else None,effective_price=terms['cost_per_token'] if terms else None,
                 edge_pass=bool(terms and terms['edge']>=.04-1e-12))
        c['eligible']=c['edge_pass'] and c['laya_pass'] and r['allowed']
    ranked=sorted(d['candidates'],key=lambda s:d['candidates'][s]['edge'] if d['candidates'][s]['edge'] is not None else -math.inf,reverse=True)
    side=next((s for s in ranked if d['candidates'][s]['eligible']),ranked[0]);c=d['candidates'][side]
    d.update(action=side if c['eligible'] else 'WAIT',candidate=side,profile='quant_laya',
             edge=c['edge'],ev=c['ev'],laya_model_probability=c['laya_probability'],validated=c['eligible'],
             state=f'{VERSION}:{side}:{int(p*10)}',risk=risks[side],side_risks=risks,risk_version=VERSION,
             entry_spot=spot)
    return d


def performance(trades):
    """Per-trade excess returns (rf=0); deliberately not annualized irregular trades."""
    done=[t for t in trades if t['status']!='OPEN'];returns=[t['pnl']/t['stake'] for t in done if t['stake']>0]
    n=len(returns);mean=sum(returns)/n if n else 0.
    std=(sum((x-mean)**2 for x in returns)/(n-1))**.5 if n>1 else 0.
    downside=(sum(min(0.,x)**2 for x in returns)/n)**.5 if n else 0.
    return dict(n=n,sharpe=mean/std if n>=2 and std>0 else None,
        sortino=mean/downside if n>=2 and downside>0 else None,
        mean_return=mean if n else None,win_rate=sum(t['pnl']>0 for t in done)/len(done) if done else None,
        convention='Por operación, sin anualizar; rf=0, Sortino objetivo=0; datos insuficientes → —')
