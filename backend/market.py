"""Read-only public market adapters. No wallet or order-submission API."""
import asyncio
import json
import math
import time
from datetime import datetime


def array(value):
    return json.loads(value) if isinstance(value, str) else value


def epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def validate_market(market, cycle):
    expected = f'btc-updown-5m-{cycle}'
    if market.get('slug') != expected:
        raise ValueError('Mercado incorrecto: slug no coincide con el ciclo')
    if abs(epoch(market['endDate']) - cycle - 300) > 1:
        raise ValueError('La fecha de cierre no coincide con el ciclo 5m')
    start = market.get('eventStartTime')
    if not start or abs(epoch(start)-cycle)>1:
        raise ValueError('No se puede verificar el inicio del mercado')
    if set(array(market['outcomes'])) != {'Up', 'Down'}:
        raise ValueError('Resultados del mercado no compatibles')
    if market.get('closed') or not market.get('acceptingOrders') or not market.get('enableOrderBook'):
        raise ValueError('Mercado cerrado o sin libro de órdenes')
    if 'chain.link' not in market.get('resolutionSource', ''):
        raise ValueError('Fuente de resolución desconocida')
    if market.get('version','v1') != 'v1':
        raise ValueError('Versión Polymarket no soportada por este adaptador')
    if market.get('feesEnabled'):
        schedule=market.get('feeSchedule',{})
        if schedule.get('exponent')!=1 or not isinstance(schedule.get('rate'),(int,float)):
            raise ValueError('Comisiones desconocidas; no se simulan fills')
    return market


def read_book(book, token, condition, now):
    if book.get('asset_id')!=token or book.get('market')!=condition:
        raise ValueError('El libro no corresponde al token/mercado')
    timestamp=float(book['timestamp'])/1000
    if not -3 <= now-timestamp <= 12:
        raise ValueError('Libro de órdenes obsoleto')
    asks=sorted((float(x['price']),float(x['size'])) for x in book['asks'] if float(x['size'])>0)
    if not asks: return None  # An outcome without sellers cannot receive a fill.
    if any(not (0<p<=1 and math.isfinite(size) and size>0) for p,size in asks):
        raise ValueError('Libro sin asks válidos')
    p,size=asks[0]
    return dict(price=p,size=size,timestamp=timestamp,min_size=float(book['min_order_size']))


class LiveMarket:
    def __init__(self, client):
        self.client=client;self.cached=None;self.cached_at=0
    async def get(self,url,params=None):
        r=await self.client.get(url,params=params);r.raise_for_status();return r.json()
    async def btc(self):
        raw=await self.get('https://api.binance.com/api/v3/klines',{'symbol':'BTCUSDT','interval':'5m','limit':201,'endTime':int(time.time()*1000)})
        now=time.time();current=raw[-1]; cycle=int(now//300)*300
        if int(current[0])//1000!=cycle:
            raise ValueError('La vela Binance no corresponde al ciclo actual')
        end=int(time.time()*1000)
        trades=await self.get('https://api.binance.com/api/v3/aggTrades',{'symbol':'BTCUSDT','startTime':end-10000,'endTime':end,'limit':1000})
        if not trades or not -3<=time.time()-float(trades[-1]['T'])/1000<=5:
            raise ValueError('Última operación BTC obsoleta o ausente')
        price=float(trades[-1]['p'])
        candles=[dict(open=float(c[1]),close=float(c[4]),volume=float(c[5]),delta=2*float(c[9])-float(c[5])) for c in raw[:-1]]
        live=dict(open=float(current[1]),close=price,volume=float(current[5]),delta=2*float(current[9])-float(current[5]),timestamp=float(trades[-1]['T'])/1000)
        return candles,live,cycle
    async def quotes(self,cycle):
        if not self.cached or self.cached['slug']!=f'btc-updown-5m-{cycle}' or time.time()-self.cached_at>15:
            markets=await self.get('https://gamma-api.polymarket.com/markets',{'slug':f'btc-updown-5m-{cycle}'})
            if not markets: raise ValueError('Mercado BTC 5m todavía no disponible')
            self.cached=validate_market(markets[0],cycle);self.cached_at=time.time()
        m=self.cached
        labels=array(m['outcomes']);tokens=array(m['clobTokenIds'])
        if len(tokens)!=2:raise ValueError('Tokens binarios inválidos')
        response=await self.client.post('https://clob.polymarket.com/books',json=[{'token_id':t} for t in tokens])
        response.raise_for_status()
        by_token={b['asset_id']:b for b in response.json()}
        books=[by_token[t] for t in tokens]
        quotes={label.upper():read_book(book,token,m['conditionId'],time.time()) for label,token,book in zip(labels,tokens,books)}
        quotes={side:q for side,q in quotes.items() if q is not None}
        if not quotes: raise ValueError('Ningún resultado tiene vendedores')
        return dict(up=quotes.get('UP',{}).get('price',0),down=quotes.get('DOWN',{}).get('price',0),source='POLYMARKET · ASKS EN VIVO',quotes=quotes,slug=m['slug'],condition_id=m['conditionId'],question=m['question'],resolution=m['resolutionSource'],fee_rate=float(m.get('feeSchedule',{}).get('rate',0)) if m.get('feesEnabled') else 0,timestamp=time.time())
    async def candle_close(self,cycle):
        if cycle%300 or time.time()<cycle+300:
            raise ValueError('La ventana BTC todavía no ha cerrado')
        rows=await self.get('https://api.binance.com/api/v3/klines',{
            'symbol':'BTCUSDT','interval':'5m','startTime':cycle*1000,
            'endTime':(cycle+300)*1000-1,'limit':1})
        if len(rows)!=1 or int(rows[0][0])!=cycle*1000 or int(rows[0][6])!=(cycle+300)*1000-1:
            raise ValueError('El cierre histórico no corresponde a la ventana solicitada')
        price=float(rows[0][4])
        if not math.isfinite(price) or price<=0:raise ValueError('Cierre BTC inválido')
        return dict(price=price,closed_at=cycle+300,source='BINANCE')

    async def winner(self,condition):
        m=await self.get(f'https://clob.polymarket.com/markets/{condition}')
        if m.get('condition_id')!=condition or not m.get('closed'):
            return None
        winners=[t['outcome'].upper() for t in m.get('tokens',[]) if t.get('winner') is True]
        # Never infer resolution from last price, elapsed time or spot BTC.
        return winners[0] if len(winners)==1 and winners[0] in ('UP','DOWN') else None
