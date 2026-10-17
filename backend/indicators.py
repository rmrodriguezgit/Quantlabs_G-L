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


def trend_indicators(closed):
    """No partial candle, centered window or future pivot. SMA200 requires 200 bars."""
    closes=[float(c['close']) for c in closed]
    if not closes or not all(math.isfinite(x) and x>0 for x in closes):return {'available':False}
    def ema(values,n):
        x=values[0];out=[x]
        for v in values[1:]:x+=2/(n+1)*(v-x);out.append(x)
        return out
    fast=ema(closes,12);slow=ema(closes,26);macd=[a-b for a,b in zip(fast,slow)];signal=ema(macd,9)
    sma50=sum(closes[-50:])/50 if len(closes)>=50 else None
    sma200=sum(closes[-200:])/200 if len(closes)>=200 else None
    cross=None
    if len(closes)>=201:
        prev=sum(closes[-51:-1])/50-sum(closes[-201:-1])/200;cur=sma50-sma200
        cross='UP' if prev<=0<cur else 'DOWN' if prev>=0>cur else 'NONE'
    bb=None
    if len(closes)>=20:
        mid=sum(closes[-20:])/20;std=(sum((x-mid)**2 for x in closes[-20:])/20)**.5
        bb=dict(mid=mid,upper=mid+2*std,lower=mid-2*std,period=20,std=2)
    return dict(available=True,sma50=sma50,sma200=sma200,ma_cross=cross,
                trend='UP' if sma50 is not None and sma200 is not None and sma50>sma200 else 'DOWN' if sma50 is not None and sma200 is not None and sma50<sma200 else 'NEUTRAL',
                macd=macd[-1] if len(closes)>=26 else None,macd_signal=signal[-1] if len(closes)>=35 else None,
                bollinger=bb,closed_candles=len(closes),ema_seed='Primer cierre; warmup mínimo explícito')
