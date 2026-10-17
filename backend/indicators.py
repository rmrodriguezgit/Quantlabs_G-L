"""Closed-candle context only. ATR is volatility, not a directional vote."""
import math


def market_context(closed,price,period=14,lookback=50):
    unavailable=dict(available=False,mode='SHADOW',reason='Se requieren OHLC de al menos 15 velas cerradas',atr=None,fibonacci=None)
    if len(closed)<period+1:return unavailable
    try:
        rows=[]
        for c in closed:
            o,h,l,x=(float(c[k]) for k in ('open','high','low','close'))
            if not all(math.isfinite(v) and v>0 for v in (o,h,l,x)) or h<max(o,x) or l>min(o,x) or h<l:
                return {**unavailable,'reason':'OHLC inválido; no se aproxima el rango con apertura/cierre'}
            rows.append((o,h,l,x))
        if not math.isfinite(price) or price<=0:return unavailable
    except (KeyError,TypeError,ValueError):return unavailable
    ranges=[max(b[1]-b[2],abs(b[1]-a[3]),abs(b[2]-a[3])) for a,b in zip(rows,rows[1:])]
    atr=sum(ranges[:period])/period
    for tr in ranges[period:]:atr=(atr*(period-1)+tr)/period
    recent=rows[-lookback:]
    high=max(x[1] for x in recent);low=min(x[2] for x in recent)
    hi=max(i for i,x in enumerate(recent) if x[1]==high);lo=max(i for i,x in enumerate(recent) if x[2]==low)
    fib=None
    if high>low and hi!=lo:
        swing='UP' if lo<hi else 'DOWN'
        levels=[dict(ratio=r,price=high-r*(high-low) if swing=='UP' else low+r*(high-low)) for r in (0.,.236,.382,.5,.618,.786,1.)]
        nearest={}
        for side in ('UP','DOWN'):
            ahead=[v['price'] for v in levels if v['price']>price] if side=='UP' else [v['price'] for v in levels if v['price']<price]
            level=(min(ahead) if side=='UP' else max(ahead)) if ahead else None
            nearest[side]=dict(level=level,distance_atr=abs(level-price)/atr if level is not None and atr>0 else None)
        fib=dict(swing=swing,lookback=len(recent),high=high,low=low,levels=levels,nearest=nearest,
                 anchors='Extremos OHLC de las últimas 50 velas cerradas; orden por índice de vela',
                 note='50% es un nivel convencional, no una razón Fibonacci')
    return dict(available=True,mode='SHADOW',reason=None,
                atr=dict(period=period,value=atr,percent=atr/rows[-1][3]*100,method='Wilder',timeframe='5m',closed_candles=len(rows)),
                fibonacci=fib,fibonacci_reason=None if fib else 'Sin extremos temporalmente ordenables; no se supone el orden dentro de una vela',
                note='Contexto descriptivo, sin votos ni cambios en GAN, LAYA, Q o entradas; no prueba ventaja')
