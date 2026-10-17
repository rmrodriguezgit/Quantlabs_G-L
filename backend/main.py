"""Local paper trader: public reads only, strict execution gates, durable account."""
import asyncio
import time
import os
import math
import random
import logging
import json
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from .engine import PaperTradingEngine, LayaMLXValidator, exploratory_decision, gan_laya_decision
from .market import LiveMarket

log=logging.getLogger('laya')
MODE=os.getenv('LAYA_MODE','demo')
if MODE not in ('demo','live'): raise ValueError('LAYA_MODE must be demo or live')
PROFILE=os.getenv('LAYA_EXECUTION','strategy')
if PROFILE not in ('strategy','exploratory','gan_laya'): raise ValueError('Unknown execution profile')
if PROFILE in ('exploratory','gan_laya') and MODE!='live': raise ValueError('Exploratory fills require live market data')
ACCOUNT_KEY=f'{MODE}-exploratory' if PROFILE in ('exploratory','gan_laya') else MODE
DATA=Path(__file__).parent/'data'
engine=PaperTradingEngine(DATA/f'{ACCOUNT_KEY}.json')
validator=LayaMLXValidator()
gan=None
state=dict(timestamp=time.time(),mode=MODE,profile=PROFILE,cycle=0,remaining=300,price=0,reference=1,probability=.5,estimator='Inicializando modelos…',validator=dict(score=0,rsi=50,engine='Inicializando',approved=False,model_connected=False,model_probability=None),decision=dict(action='WAIT',ev=0,fraction=0),reason='Conectando datos y modelos',odds=dict(up=0,down=0,source='SIN DATOS',available=False),account=engine.snapshot(),candles=[],error=None,gates=[],events=[],model_ready=False,data_updated_at=None,gan_quality={},blockers=['Inicializando motor'])
events=[]

def event(message,kind='INFO'):
    item=dict(timestamp=time.time(),kind=kind,message=message)
    events.insert(0,item); del events[100:]
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/f'{ACCOUNT_KEY}-events.jsonl').open('a') as f: f.write(json.dumps(item)+'\n')
    log.info('%s: %s',kind,message)


def execution_gates(now,cycle,p,audit,decision,market,models,paused,already):
    remaining=cycle+300-now
    return [
        dict(name='Datos y cuotas frescos',ok=market and now-market['timestamp']<=5),
        dict(name='GAN y LAYA MLX listos',ok=models),
        dict(name='Ventana 00:30 → 00:15',ok=15<=remaining<=30),
        dict(name='Probabilidad >58% UP / <42% DOWN',ok=p>.58 or p<.42),
        dict(name='Concordancia técnica >70% y LAYA aprobado',ok=audit['score']>.7 and audit['approved']),
        dict(name='EV neto >+0.05 y Q-policy permite entrada',ok=decision['ev']>.05 and decision['action']!='WAIT'),
        dict(name='Motor activo y ciclo sin entrada',ok=not paused and not already),
    ]


def exploratory_gates(now,cycle,market,models,paused,already):
    return [
        dict(name='Cuotas reales frescas (máx. 5s)',ok=bool(market and now-market['timestamp']<=5)),
        dict(name='GAN y LAYA cargados (señal informativa)',ok=bool(models)),
        dict(name='Ciclo activo con más de 5s restantes',ok=cycle<=now<cycle+295),
        dict(name='Motor activo y máximo una entrada por ciclo',ok=not paused and not already),
    ]


async def load_models():
    global gan
    try:
        from .gan import GANEstimator
        gan=await asyncio.to_thread(GANEstimator)
        event('GAN inicializada en '+gan.device)
    except Exception as exc:
        event('GAN no disponible: '+str(exc),'ERROR')
    if MODE=='live' and validator.model_name:
        try:
            import laya_mlx
            state['reason']='Descargando/cargando checkpoint LAYA MLX…'
            validator.model=await asyncio.to_thread(laya_mlx.load,validator.model_name)
            event('Checkpoint LAYA MLX cargado')
        except Exception as exc:
            validator.load_error=str(exc); event('LAYA no disponible: '+str(exc),'ERROR')


async def loop():
    global state
    rng=random.Random(21);price=65000.;previous=None;last_train=None;probability=.5;last_resolution=0;last_log=0
    candles=[]
    if MODE=='demo':
        for _ in range(200):
            close=price*math.exp(rng.gauss(0,.001));candles.append(dict(open=price,close=close,volume=rng.uniform(10,100)));price=close
    # Loading runs in a separate thread so the dashboard remains available.
    model_task=asyncio.create_task(load_models())
    try:
        async with httpx.AsyncClient(timeout=8,headers={'User-Agent':'LAYA-Paper-Research/1.0'}) as client:
            live=LiveMarket(client)
            while True:
                tick=time.monotonic();now=time.time();cycle=int(now//300)*300
                try:
                    market=None;quote_error=None
                    if MODE=='live':
                        # Data updates continue even when a model is still downloading.
                        candles,current,cycle=await live.btc();price=current['close'];reference=current['open']
                        try: market=await live.quotes(cycle)
                        except Exception as exc: quote_error=str(exc)
                        # Pending positions survive restart and wait for official results.
                        if now-last_resolution>10:
                            last_resolution=now
                            for condition in {t.condition_id for t in engine.trades if t.status=='OPEN' and t.condition_id and t.cycle+300<now}:
                                try:
                                    winner=await live.winner(condition)
                                    if winner:
                                        engine.resolve(condition,winner);event('Liquidación oficial: '+winner+' / '+condition[:14])
                                except Exception as exc: event('Resolución pendiente: '+str(exc),'WARNING')
                    else:
                        price*=math.exp(rng.gauss(0,.00007));reference=candles[-1]['close'] if previous!=cycle else state['reference']
                        if previous is not None and previous!=cycle:
                            engine.settle(previous,price);candles.append(dict(open=state['reference'],close=price,volume=rng.uniform(10,100)));candles=candles[-200:]
                        current=dict(open=reference,close=price,volume=0.)
                        up=.5+.08*math.sin(now/70)
                        market=dict(up=up,down=1-up,source='SINTÉTICAS · DEMO',timestamp=time.time())
                    previous=cycle
                    if gan is not None and model_task.done():
                        if last_train!=cycle:
                            await asyncio.to_thread(gan.train,[math.log(c['close']/c['open']) for c in candles]);last_train=cycle
                        probability=await asyncio.to_thread(gan.predict,math.log(price/reference),max(0,cycle+300-time.time())) if gan.ready else .5
                    elif MODE=='demo':
                        returns=[math.log(c['close']/c['open']) for c in candles]
                        probability=sum(rng.choice(returns)>0 for _ in range(1000))/1000
                    audit=dict(score=0,rsi=50,approved=False,model_connected=False,model_probability=None,engine='Modelo cargando')
                    if model_task.done():
                        # On load failure do not retry a large checkpoint every second.
                        if validator.load_error and validator.model is None:
                            audit['model_error']=validator.load_error
                        else: audit=await asyncio.to_thread(validator.validate,candles+[current],probability)
                    now=time.time();remaining=max(0,cycle+300-now)
                    gan_quality=gan.quality.copy() if gan else {'healthy':False,'reason':'GAN no disponible'}
                    decision=engine.agent.decide(probability,market['up'],market['down'],audit['score'],market.get('fee_rate',0)) if market else dict(action='WAIT',ev=0,fraction=0)
                    models=bool(gan and gan.ready and audit['model_connected']) if MODE=='live' else model_task.done()
                    already=cycle<=engine.blocked_through_cycle or any(t.cycle==cycle for t in engine.trades)
                    if PROFILE=='exploratory':
                        if market: decision=exploratory_decision(probability,market['up'],market['down'],market.get('fee_rate',0))
                        gates=exploratory_gates(now,cycle,market,models,engine.paused,already)
                    elif PROFILE=='gan_laya':
                        if market: decision=gan_laya_decision(engine.agent,probability,market['up'],market['down'],audit,market.get('fee_rate',0))
                        gates=exploratory_gates(now,cycle,market,models,engine.paused,already)
                        gates[1]['name']='GAN y LAYA MLX conectados'
                        gates.extend([
                            dict(name='GAN UP >58% / DOWN <42%',ok=probability>.58 or probability<.42),
                            dict(name='Concordancia técnica >70%',ok=audit['score']>.7),
                            dict(name='Aprobación LAYA MLX >70%',ok=bool(audit.get('model_connected') and (audit.get('model_probability') or 0)>.7 and audit['approved'])),
                            dict(name='EV neto >0.05',ok=decision['ev']>.05),
                            dict(name='Política Q permite la dirección GAN',ok=decision.get('q_permits',False)),
                        ])
                    else:
                        gates=execution_gates(now,cycle,probability,audit,decision,market,models,engine.paused,already)
                    if MODE=='live':
                        gates.insert(2,dict(name='GAN con dispersión y media válidas',ok=bool(gan and gan_quality.get('healthy'))))
                    blockers=[g['name'] for g in gates if not g['ok']]
                    # Inference can cross a boundary; recheck wall clock before any fill.
                    valid=all(g['ok'] for g in gates) and int(now//300)*300==cycle
                    recommendation=decision['action']
                    if valid:
                        trade=engine.enter(cycle,now,reference,decision,audit['score'],market['up'],market['down'],market if MODE=='live' else None,audit.get('status','TECHNICAL_BASELINE'))
                        if trade: event(f'ENTRY_{trade.side} PAPER {PROFILE.upper()} · {trade.stake:.2f} USD · cuota {trade.price:.4f} · LAYA {audit.get("status","N/A")} · EV {decision["ev"]:.3f} · ciclo {cycle}', 'ENTRY')
                        reason='Entrada simulada registrada' if trade else 'Sin fill: liquidez o saldo insuficientes para $1'
                        if trade is None: decision['action']='WAIT'
                    else:
                        reason='WAIT · '+(' | '.join(blockers) if blockers else 'ciclo vencido')
                        decision['action']='WAIT'
                    decision['recommendation']=recommendation
                    if now-last_log>=15:
                        event(f"{decision['action']} · P(UP)={probability:.3f} · EV={decision['ev']:.3f} · {reason}",'SIGNAL');last_log=now
                    odds={**market,'available':True} if market else {**state['odds'],'available':False,'source':'POLYMARKET NO DISPONIBLE'}
                    state=dict(timestamp=now,mode=MODE,profile=PROFILE,cycle=cycle,remaining=remaining,price=price,reference=reference,probability=probability,estimator='GAN experimental / 1000 escenarios / horizonte restante' if gan else 'Bootstrap DEMO' if MODE=='demo' else 'GAN no disponible',validator=audit,decision=decision,reason=reason,odds=odds,account=engine.snapshot(),candles=candles[-60:],error=quote_error,events=events.copy(),gates=gates,model_ready=models,model_error=validator.load_error,resolution_note='Chainlink TWAP 60s · Liquidación oficial Polymarket' if MODE=='live' else 'Resolución demo',data_updated_at=current.get('timestamp',now),gan_quality={**gan_quality,'up_scenarios':gan.last_up_scenarios if gan else 0,'scenarios':gan.last_scenario_count if gan else 0},blockers=blockers,signal_note='Probabilidad experimental de spot Binance; no calibrada para TWAP Chainlink')
                except Exception as exc:
                    # Expected feed interruptions must not flood the server with tracebacks.
                    if time.time()-last_log>=15:
                        event('Datos no disponibles: '+str(exc),'WARNING');last_log=time.time()
                    state={**state,'timestamp':time.time(),'remaining':max(0,cycle+300-time.time()),'error':str(exc),'reason':'Datos no disponibles: ejecución bloqueada','decision':{'action':'WAIT','ev':0,'fraction':0},'odds':{**state['odds'],'available':False},'blockers':['Datos no disponibles: '+str(exc)],'gates':[],'account':engine.snapshot(),'events':events.copy()}
                await asyncio.sleep(max(.05,1-(time.monotonic()-tick)))
    finally:
        model_task.cancel()
        try: await model_task
        except asyncio.CancelledError: pass


@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(loop())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    engine.save()

app=FastAPI(title='LAYA Paper Trader',lifespan=lifespan)
@app.get('/api/state')
async def get_state(): return state
@app.get('/api/health')
async def health(): return {'ok':bool(state['candles']) and not state.get('error'),'mode':MODE,'paper_only':True,'profile':PROFILE,'models_ready':state['model_ready']}
@app.post('/api/pause')
async def pause(): engine.paused=not engine.paused; return {'paused':engine.paused}
@app.websocket('/ws')
async def stream(ws:WebSocket):
    await ws.accept()
    try:
        while True: await ws.send_json(state); await asyncio.sleep(1)
    except (WebSocketDisconnect,RuntimeError): pass

build=Path(__file__).parents[1]/'frontend'/'dist'
if build.exists(): app.mount('/',StaticFiles(directory=build,html=True),name='dashboard')
