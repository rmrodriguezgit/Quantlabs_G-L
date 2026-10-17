"""Closed one-minute observations and causal remaining-horizon examples."""
import asyncio
import json
import math
import time
from pathlib import Path
import httpx
import numpy as np

FEATURES=['distance_to_open','elapsed','return_1m','return_3m','return_5m','return_15m','ema_gap','signed_volume_5m','volume_ratio','log_volatility','range_3m','spot_vs_ema9']

async def download_minutes(start,end,path):
    path=Path(path)
    if path.exists():return json.loads(path.read_text())
    limiter=asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=25) as client:
        async def chunk(begin):
            async with limiter:
                for retry in range(4):
                    try:
                        response=await client.get('https://api.binance.com/api/v3/klines',params={'symbol':'BTCUSDT','interval':'1m','startTime':begin*1000,'endTime':min(end,begin+60000)*1000-1,'limit':1000})
                        response.raise_for_status()
                        return response.json()
                    except (httpx.HTTPError,ValueError):
                        if retry==3:raise
                        await asyncio.sleep(1+retry)
        chunks=await asyncio.gather(*(chunk(t) for t in range(start,end,60000)))
    by_time={int(row[0]):row for rows in chunks for row in rows if start*1000<=int(row[0])<end*1000 and int(row[6])<end*1000}
    data=[by_time[t] for t in sorted(by_time)]
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))
    return data


def context(history,reference,price,elapsed_seconds):
    """All history rows MUST be completed before the current observation."""
    if len(history)<60 or not 0<=elapsed_seconds<300:raise ValueError('Invalid causal context')
    rows=history[-60:]
    if any(int(b[0])-int(a[0])!=60000 for a,b in zip(rows,rows[1:])):raise ValueError('Gap in minute context')
    close=np.array([float(r[4]) for r in rows]);volume=np.array([float(r[5]) for r in rows])
    returns=np.diff(np.log(close))
    vol=max(float(np.std(returns[-20:])),1e-6)
    def ema(n):
        v=float(close[0])
        for x in close[1:]:v+=2/(n+1)*(x-v)
        return v
    ema9,ema21=ema(9),ema(21)
    momentum=[math.log(close[-1]/close[-1-n])/(vol*math.sqrt(n)) for n in [1,3,5,15]]
    delta=sum(2*float(r[9])-float(r[5]) for r in rows[-5:])
    distance=math.log(price/reference)
    features=[distance/(vol*math.sqrt(5)),elapsed_seconds/300,*momentum,
              math.log(ema9/ema21)/(vol*math.sqrt(5)),delta/max(float(volume[-5:].sum()),1e-9),
              math.log(max(float(volume[-3:].mean()),1e-9)/max(float(volume[-20:].mean()),1e-9)),math.log(vol),
              math.log(max(float(r[2]) for r in rows[-3:])/min(float(r[3]) for r in rows[-3:]))/(vol*math.sqrt(3)),
              math.log(price/ema9)/(vol*math.sqrt(5))]
    horizon_scale=vol*math.sqrt((300-elapsed_seconds)/60)
    return np.asarray(features,dtype=np.float32),horizon_scale,distance


def build_examples(rows):
    by_time={int(row[0])//1000:i for i,row in enumerate(rows)}
    records=[]
    for cycle,index in by_time.items():
        if cycle%300 or index<60:continue
        window=rows[index:index+5]
        if len(window)!=5 or any(int(row[0])//1000!=cycle+j*60 for j,row in enumerate(window)):continue
        reference=float(window[0][1]);final=float(window[-1][4])
        for minute in range(5):
            cutoff=cycle+minute*60
            price=reference if minute==0 else float(window[minute-1][4])
            try:x,scale,distance=context(rows[index+minute-60:index+minute],reference,price,minute*60)
            except ValueError:continue
            records.append(dict(x=x,target=math.log(final/price)/scale,scale=scale,distance=distance,
                                label=float(final>=reference),cycle=cycle,cutoff=cutoff,label_time=cycle+300,
                                reference=reference,current=price,final=final))
    return records


def temporal_split(records):
    cycles=sorted({r['cycle'] for r in records})
    if len(cycles)<100:raise ValueError('Too few complete cycles for temporal evaluation')
    calibration_start=cycles[int(len(cycles)*.6)]
    test_start=cycles[int(len(cycles)*.8)]
    # A full 20-minute gap before each new segment prevents overlapping labels/windows.
    train=[r for r in records if r['label_time']<calibration_start-1200]
    calibration=[r for r in records if calibration_start<=r['cycle'] and r['label_time']<test_start-1200]
    test=[r for r in records if r['cycle']>=test_start]
    return train,calibration,test
