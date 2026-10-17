import {useState} from 'react';
import {marketView,payoff,type BinarySnapshot} from './binaryMarket';
const usd=(n:number|null)=>n===null?'—':n.toLocaleString('en-US',{style:'currency',currency:'USD'});
const askPrice=(n:number|null)=>n===null?'—':n.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:4});
const percent=(n:number|null)=>n===null?'—':`${(n*100).toFixed(1)}%`;
export function BinaryMarketPanel({snapshot:s,now,connected}:{snapshot:BinarySnapshot;now:number;connected:boolean}){
 const [side,setSide]=useState<'UP'|'DOWN'>('UP');const[stake,setStake]=useState(1);
 const v=marketView(s,now,connected);const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;
 const clock=(time:number)=>new Date(time*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
 const date=new Date(v.cycle*1000).toLocaleDateString();const book=s.odds.quotes?.[side];
 const rate=s.mode==='demo'?0:s.odds.fee_rate;
 const selectedAsk=side==='UP'?v.up:v.down;const result=payoff(stake,selectedAsk,rate,book?.size);
 const selectedP=side==='UP'?v.pUp:v.pDown;
 const ev=selectedAsk!==null&&selectedP!==null&&rate!==undefined?selectedP/(selectedAsk*(1+rate*(1-selectedAsk)))-1:null;
 return <section className="panel payoff binary-market" aria-label="Mercado binario BTC 5m actual">
  <div className="panelhead"><h2>Mercado binario · BTC 5m</h2><small>{s.mode==='demo'?'DEMO':v.up!==null||v.down!==null?'CUOTAS LIVE':'SIN CUOTAS FRESCAS'}</small></div>
  <div className="binary-window"><strong>{date} · {clock(v.cycle)} → {clock(v.cycle+300)}</strong><small>{zone} · Ventana actual</small><span>{v.sameCycle?`Cierra en ${String(Math.floor(v.remaining/60)).padStart(2,'0')}:${String(Math.floor(v.remaining%60)).padStart(2,'0')}`:'Sincronizando nuevo ciclo…'}</span></div>
  <div className="binary-prices"><div><small>Referencia BTC · apertura {s.mode==='demo'?'demo':'Binance'}</small><strong>{usd(v.reference)}</strong></div><div><small>BTC actual · {s.mode==='demo'?'demo':'Binance'}</small><strong>{usd(v.price)}</strong></div><div><small>Δ frente a referencia</small><strong className={v.delta!==null&&v.delta>=0?'green':'red'}>{v.delta===null?'—':`${v.delta>=0?'+':''}${usd(v.delta)} (${v.deltaPct!.toFixed(3)}%)`}</strong></div></div>
  <p className="model-note">{s.mode==='demo'?'Precios y cuotas sintéticos.':'La referencia Binance no es la referencia oficial Chainlink de Polymarket; este feed no proporciona esa referencia oficial.'}</p>
  {v.identity&&s.odds.question&&<p className="binary-question">{s.odds.question}</p>}
  <div className="odds">{(['UP','DOWN'] as const).map(k=>{const p=k==='UP'?v.pUp:v.pDown;const ask=k==='UP'?v.up:v.down;return <button key={k} className={side===k?'active '+k.toLowerCase():k.toLowerCase()} aria-pressed={side===k} aria-label={`Seleccionar ${k} para calculadora paper`} onClick={()=>setSide(k)}><span>{k}<b>{askPrice(ask)}</b><small>Compra ask / token</small><small>Probabilidad GAN: {percent(p)}</small>{ask===null&&<small>Sin vendedores o cuota obsoleta</small>}</span></button>})}</div>
  {!v.modelFresh&&<p className="model-note">Probabilidades no disponibles: esperando datos y GAN válidos del ciclo actual.</p>}
  <p className="model-note">La probabilidad GAN es experimental; el ask es una cuota de compra, no otra predicción del modelo.</p>
  <div className="market-source">{s.mode!=='demo'&&v.identity&&s.odds.slug?<a href={`https://polymarket.com/event/${s.odds.slug}`} target="_blank" rel="noreferrer">Abrir mercado BTC 5m actual ↗</a>:'Esperando identificación del mercado actual'}</div>
  <p className="model-note">BTC: {s.data_updated_at?clock(s.data_updated_at):'—'} · Cuotas: {s.odds.timestamp?clock(s.odds.timestamp):'—'}{!v.btcFresh?' · BTC no actualizado':''}</p>
  <div className="calculator"><label htmlFor="binary-stake">Calcular inversión simulada · {side}</label><div className="input"><span>USD</span><input id="binary-stake" type="number" min="0" max="1000000" step="0.01" value={stake} onChange={e=>{const n=Number(e.target.value);setStake(Number.isFinite(n)?Math.min(1000000,Math.max(0,n)):0)}}/></div>
   <div><small>Tokens / pago si acierta</small><b>{result?`${result.tokens.toFixed(4)} / ${usd(result.tokens)}`:'—'}</b></div>
   <div><small>Tasas incluidas en el importe</small><b>{usd(result?.fee??null)}</b></div>
   <div><small>Beneficio si acierta / pérdida si falla</small><b>{result?`${usd(result.win)} / −${usd(result.loss)}`:'—'}</b></div>
   <div><small>EV neto estimado · {side}</small><b>{ev===null?'—':`${(ev*100).toFixed(1)}%`}</b></div>
   {s.mode!=='demo'&&result&&!result.depthEnough&&<p className="red">Tamaño visible insuficiente para simular este importe al mejor ask.</p>}
   {result&&book&&result.tokens<book.min_size&&<p className="model-note">BAJO MÍNIMO REAL · Fracción permitida solo en paper trading.</p>}
   <small>Esta calculadora no envía órdenes ni cambia el tamaño del bot: las entradas de los perfiles GAN + LAYA y Edge + LAYA siguen siendo de $1.</small>
  </div>
 </section>
}
