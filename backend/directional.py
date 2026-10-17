"""Versioned directional consistency rules; thresholds are not profit-calibrated."""
from dataclasses import asdict, dataclass
import math

POLICY_VERSION='directional-v1'

@dataclass(frozen=True)
class SidePolicy:
    side: str
    min_probability: float=.58
    min_technical: float=.7
    min_mlx: float=.7
    min_ev: float=.05

# Independently addressable policies. Keep numeric thresholds equal until future
# out-of-sample evidence supports an asymmetry, rather than fitting two losses.
POLICIES={side:SidePolicy(side) for side in ('UP','DOWN')}


def signal_side(p):
    if p>POLICIES['UP'].min_probability:return 'UP'
    if p<round(1-POLICIES['DOWN'].min_probability,10):return 'DOWN'
    return 'WAIT'


def technical_audits(candles):
    if len(candles)<22:raise ValueError('Directional audit needs at least 22 candles')
    closes=[float(c['close']) for c in candles]
    if not all(math.isfinite(x) and x>0 for x in closes):raise ValueError('Invalid BTC prices')
    changes=[b-a for a,b in zip(closes[-15:-1],closes[-14:])]
    gain=sum(max(x,0) for x in changes)/len(changes)
    loss=sum(max(-x,0) for x in changes)/len(changes)
    rsi=100-100/(1+gain/loss) if loss else (100 if gain else 50)
    def ema(n):
        value=closes[0]
        for close in closes[1:]:value+=2/(n+1)*(close-value)
        return value
    fast,slow=ema(9),ema(21)
    delta=sum(float(c.get('delta',(1 if c['close']>c['open'] else -1 if c['close']<c['open'] else 0)*c['volume'])) for c in candles[-5:])
    if not math.isfinite(delta):raise ValueError('Invalid signed volume')
    momentum=closes[-1]-closes[-2]
    output={}
    for side,policy in POLICIES.items():
        sign=1 if side=='UP' else -1
        checks=[dict(key='rsi',label='RSI >50' if side=='UP' else 'RSI <50',ok=sign*(rsi-50)>0),
                dict(key='ema',label='EMA9 > EMA21' if side=='UP' else 'EMA9 < EMA21',ok=sign*(fast-slow)>0),
                dict(key='volume',label='Delta volumen >0' if side=='UP' else 'Delta volumen <0',ok=sign*delta>0),
                dict(key='price',label='BTC sobre EMA9 y EMA21' if side=='UP' else 'BTC bajo EMA9 y EMA21',ok=sign*(closes[-1]-fast)>0 and sign*(closes[-1]-slow)>0),
                dict(key='momentum',label='Último cambio BTC positivo' if side=='UP' else 'Último cambio BTC negativo',ok=sign*momentum>0)]
        score=sum(c['ok'] for c in checks)/len(checks)
        # Current price and momentum must confirm; lagged averages alone cannot approve.
        technical_pass=score>policy.min_technical and checks[3]['ok'] and checks[4]['ok']
        output[side]=dict(side=side,policy_version=POLICY_VERSION,policy=asdict(policy),checks=checks,
                          score=score,technical_pass=technical_pass,rsi=rsi,ema_fast=fast,ema_slow=slow,
                          delta_volume=delta,price=closes[-1],momentum=momentum)
    return output
