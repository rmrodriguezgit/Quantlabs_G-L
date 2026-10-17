type Variant={key:string;label:string;trades:number;win_rate:number|null;pnl:number|null;profit_factor:number|null;max_drawdown:number|null;entry_rate:number|null;below_minimum:number;stress_trades:number;stress_pnl:number|null};
type Offline={metrics:Record<string,{brier:number;accuracy:number}>;segments:{test:{cycles:number}};promoted:boolean};
export type ResearchReport={offline?:Offline;cohort:string;observations:number;fresh_observations:number;since:number|null;samples:number;resolved:number;pending:number;brier:number|null;brier_reference:number;variants:Variant[];calibration:{low:number;high:number;count:number;predicted:number|null;actual:number|null}[];blockers:{reason:string;count:number}[];protocol:string;stress_note:string;evidence:string};
const pct=(n:number|null)=>n===null?'—':`${(n*100).toFixed(1)}%`;
const usd=(n:number|null)=>n===null?'—':n.toLocaleString('en-US',{style:'currency',currency:'USD'});
export function ResearchPanel({report,error}:{report?:ResearchReport;error?:string|null}){
 if(!report)return null;
 return <section className="panel research" aria-label="Evaluación prospectiva de señales">
  <div className="panelhead"><h2>Laboratorio de señales <span className="count">PROSPECTIVO</span></h2><a className="export-signals" href="/api/research/signals.csv?limit=10000" download>Exportar señales CSV ↗</a></div>
  {error&&<div className="error">{error}</div>}
  {report.offline&&<article className="model-note"><h3>Entrenamiento condicional WGAN-GP · Evaluación offline</h3><p>30 días históricos · {report.offline.segments.test.cycles} velas de prueba separadas · Candidato sin promover a ejecución.</p><div className="tablewrap"><table><thead><tr><th>MODELO</th><th>BRIER ↓</th><th>ACIERTO DIRECCIONAL</th></tr></thead><tbody>{[['conditional_calibrated','GAN condicional calibrada'],['diffusion','Referencia estadística'],['legacy_retrained','GAN anterior reentrenada']].map(([key,label])=><tr key={key}><td>{label}</td><td>{report.offline!.metrics[key].brier.toFixed(4)}</td><td>{pct(report.offline!.metrics[key].accuracy)}</td></tr>)}</tbody></table></div><p>La nueva GAN no superó la referencia. Estos aciertos mezclan cinco momentos por vela; no son win rate ni rentabilidad. Etiquetas Binance, sin cuotas históricas ni liquidación oficial. Se requieren nuevas pruebas prospectivas.</p></article>}
  <div className="research-metrics">
   <div><small>OBSERVACIONES / FRESCAS</small><strong>{report.observations.toLocaleString()} <span>/ {report.fresh_observations.toLocaleString()}</span></strong></div>
   <div><small>VELAS CON SEÑAL FIJA</small><strong>{report.samples}</strong></div>
   <div><small>RESUELTAS / PENDIENTES</small><strong>{report.resolved} <span>/ {report.pending}</span></strong></div>
   <div><small>BRIER GAN · MENOR ES MEJOR</small><strong>{report.brier===null?'—':report.brier.toFixed(4)}</strong><small>Referencia P=50%: {report.brier_reference.toFixed(2)}</small></div>
  </div>
  <p className="model-note">{report.protocol}</p>
  <div className="tablewrap"><table><thead><tr>{['VARIANTE SHADOW','OPERACIONES','ENTRADAS / VELAS','WIN RATE','PNL NETO $1','PROFIT FACTOR','DRAWDOWN','ESTRÉS +$0.01 / TOKEN'].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>
   {report.variants.map(v=><tr key={v.key}><td>{v.label}</td><td>{v.trades}</td><td>{pct(v.entry_rate)}</td><td>{pct(v.win_rate)}</td><td className={v.pnl!==null?(v.pnl>=0?'green':'red'):''}>{usd(v.pnl)}</td><td>{v.profit_factor?.toFixed(2)??'—'}</td><td>{pct(v.max_drawdown)}</td><td>{usd(v.stress_pnl)}<small className="trade-profile">{v.stress_trades} operaciones · {v.below_minimum} bajo mínimo real en base</small></td></tr>)}
  </tbody></table></div>
  {!report.resolved&&<p className="research-empty">Aún no hay señales fijas con resultado oficial. Se recopilan datos nuevos; no se reconstruyen resultados pasados.</p>}
  <div className="research-details"><article><h3>Probabilidad estimada vs. resultado</h3><p>Una observación por vela resuelta. Descriptivo; el modelo aún no está calibrado.</p><div className="reliability">{report.calibration.map((bin,i)=><div key={i} title={`Predicción media: ${pct(bin.predicted)}; frecuencia UP: ${pct(bin.actual)}; n=${bin.count}`}><span>{Math.round(bin.low*100)}–{Math.round(bin.high*100)}%</span><b>{bin.count?`${pct(bin.actual)} UP`:'Sin datos'}</b><small>n={bin.count} · pred. {pct(bin.predicted)}</small></div>)}</div></article>
  <article><h3>Qué bloquea las entradas</h3><p>Frecuencia en snapshots; no son casos independientes ni probabilidades de pérdida.</p><div className="blocker-counts">{report.blockers.slice(0,8).map(b=><div key={b.reason}><span>{b.reason}</span><b>{b.count.toLocaleString()}</b></div>)}</div></article></div>
  <p className="model-note">{report.evidence} {report.stress_note}</p><p className="model-note">Cohorte: {report.cohort} · Desde {report.since?new Date(report.since*1000).toLocaleString():'el próximo dato'} · CSV: últimas 10,000 observaciones. El histórico completo permanece en SQLite local.</p>
 </section>
}
