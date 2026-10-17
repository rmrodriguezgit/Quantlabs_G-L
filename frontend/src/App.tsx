import {SimpleRulesPanel} from './SimpleRulesPanel';
import {buildBranch} from './buildInfo';
import { Chart } from './Chart';
import { money } from './format';
import { PipelinePanel } from './PipelinePanel';
import { TradeHistory } from './TradeHistory';
import { useTrader } from './useTrader';
import React, { useEffect, useState } from 'react';
import { Activity, BrainCircuit, Pause, Play, Radio, TowerControl, Wallet } from 'lucide-react';
import './style.css';
import { IndicatorContext } from './IndicatorContext';
import { BinaryMarketPanel } from './BinaryMarketPanel';
import { DirectionalPanel } from './DirectionalPanel';
import { ResearchPanel } from './ResearchPanel';
import { version as appVersion } from '../package.json';
export default function App() {
    const [uiNow, setUiNow] = useState(Date.now() / 1000);
    useEffect(() => { const ticker = setInterval(() => setUiNow(Date.now() / 1000), 1000); return () => clearInterval(ticker); }, []);
    const { s, setS, connected } = useTrader();
    const [filter, setFilter] = useState('ALL');
    if (!s)
        return <div className="loading">
        <Activity />
        <h2>Quantlabs G&amp;L</h2>
        <small>LAYA · v{appVersion}</small>
        <p>Conectando con el motor local…</p>
        <small>Inicia ./start.sh para conectar el backend.</small>
        </div>;
    const simple=s.profile==='edge_laya';
    const a = s.account;
    const dataAge = Math.max(0, uiNow - (s.data_updated_at ?? s.timestamp));
    const stale = !connected || !s.data_updated_at || dataAge > 8 || !!s.error;
    const countdown = Math.max(0, s.cycle + 300 - uiNow);
    return <div className="shell">
    <aside>
    <div className="logo" title="Quantlabs G&L">
    <img src="/quantlabs-mark.svg" alt="Quantlabs G&L"/>
    </div>
    <Activity className="selected"/>
    <BrainCircuit />
    <Wallet />
    <TowerControl />
    <div className="asidefoot">5m</div>
    </aside>
    <main>
    <header>
    <div className="brand-lockup">
    <img className="brand-mark" src="/quantlabs-mark.svg" alt="" aria-hidden="true"/>
    <div className="brand-copy">
    <strong>Quantlabs <span>G&amp;L</span>
    </strong>
    <div className="engine-version">
    <b>LAYA</b>
    <small>v{appVersion}</small><small className="build-branch" title="Rama de esta compilación" aria-label={`Branch ${buildBranch}`}>{buildBranch}</small>
    </div>
    </div>
    </div>
    <div className="status">
    <i className={connected && !stale ? 'online' : 'stale'}/>{!connected ? 'RECONECTANDO' : stale ? 'DATOS NO DISPONIBLES' : `LIVE · ${new Date(s.timestamp * 1000).toLocaleTimeString()}`}<b>{simple ? 'EDGE + LAYA EXP. / PAPER $1' : s.profile === 'gan_laya' ? 'GAN + LAYA / PAPER $1' : s.profile === 'exploratory' ? 'SIMULACIÓN / REAL QUOTES' : `${s.mode.toUpperCase()} / PAPER`}</b>
    </div>
    </header>
    <div className="heading">
    <div>
    <div className="eyebrow">AUTONOMOUS RESEARCH / BTC–USD</div>
    <h1>Una señal. Cuatro filtros.</h1>
    <p>Predicción, validación y ejecución simulada en ciclos de 5 minutos.</p>
    </div>
    <button onClick={async () => { const r = await fetch('/api/pause', { method: 'POST' }); const d = await r.json(); setS({ ...s, account: { ...a, paused: d.paused } }); }}>{a.paused ? <Play size={15}/> : <Pause size={15}/>} {a.paused ? 'Reanudar motor' : 'Pausar entradas'}</button>
    </div>
    <div className="notice">
    <Radio size={15}/>
    <span>{s.mode === 'demo' ? 'ENTORNO DEMO · Precios y cuotas sintéticos. Rendimiento sin valor predictivo.' : simple ? 'EXPERIMENTO · Edge neto ≥4 puntos · LAYA veto ≥35% · 3 lecturas · $1 · cuenta independiente.' : s.profile === 'gan_laya' ? 'GAN + LAYA · Cuotas reales · $1 por ciclo · P(GAN)>58% UP / <42% DOWN · LAYA y concordancia >70%.' : s.profile === 'exploratory' ? 'SIMULACIÓN EXPLORATORIA · Cuotas reales · $1 por ciclo · Sin exigir ventana, EV ni aprobación LAYA.' : 'PAPER LIVE · BTC Binance + asks Polymarket. Entradas automáticas sujetas a todos los filtros.'}</span>
    <span className="right">SIN FONDOS REALES</span>
    </div>{(s.error || s.model_error) && <div className="error">{s.error || s.model_error}</div>}<section className="metrics">{[[simple ? 'Bankroll experimental Edge + LAYA' : s.profile === 'gan_laya' ? 'Bankroll paper GAN + LAYA' : s.profile === 'exploratory' ? 'Bankroll exploratorio' : 'Bankroll', money(a.balance), 'Capital contable · coste de posiciones'], ['PnL realizado', money(a.pnl), `${(a.pnl / 10).toFixed(2)}% desde el inicio`], ['Win rate', `${(a.win_rate * 100).toFixed(1)}%`, `${a.total_trades} liquidadas · ${a.trades.filter(t => t.status === 'OPEN').length} abiertas`], ['Profit factor', a.profit_factor?.toFixed(2) ?? '—', `Drawdown máx. ${(a.max_drawdown * 100).toFixed(2)}%`]].map(([label, value, note]) => <article key={label}>
        <label>{label}</label>
        <strong>{value}</strong>
        <small>{note}</small>
        </article>)}</section>
    <div className="grid">
    <section className="panel market">
    <div className="panelhead">
    <h2>
    <span className="btc">₿</span> Bitcoin <small>BTC / USD</small>
    </h2>
    <span className="tag">5 MIN</span>
    </div>
    <div className="price">{s.price ? money(s.price) : '—'} <small className={s.price >= s.reference ? 'green' : 'red'}>{((s.price / s.reference - 1) * 100).toFixed(3)}%</small>
    </div>
    <Chart values={[...s.candles.map(c => c.close), s.price]}/>
    <div className="chartfoot">
    <span>ÚLTIMAS 60 VELAS</span>
    <span>Apertura Binance {s.price ? money(s.reference) : '—'}</span>
    </div>
    <div className="cycle">
    <div>
    <small>CIERRE DEL CICLO</small>
    <strong>{String(Math.floor(countdown / 60)).padStart(2, '0')}<span>:</span>{String(Math.floor(countdown % 60)).padStart(2, '0')}</strong>
    </div>
    <div className="cycletext">
    <span>{simple ? 'Edge + LAYA: ventana 01:00 → 04:40 del ciclo' : s.profile === 'gan_laya' ? 'GAN + LAYA: máximo una entrada por ciclo' : s.profile === 'exploratory' ? 'Entrada exploratoria: una por ciclo' : 'Ventana de entrada: 00:30 → 00:15'}</span>
    <div className="track">
    <i style={{ width: `${Math.min(100, (300 - countdown) / 3)}%` }}/>
    </div>
    <small>{s.reason}</small>
    </div>
    </div>
    </section>
    <PipelinePanel s={s} stale={stale} dataAge={dataAge}/>
    <section className="panel equity">
    <div className="panelhead">
    <h2>Curva de equidad</h2>
    <small>USD / DESDE INICIO</small>
    </div>
    <div className="equityvalue">{money(a.balance)} <span className="green">{a.pnl >= 0 ? '+' : ''}{money(a.pnl)}</span>
    </div>
    <Chart values={a.equity}/>
    <div className="chartfoot">
    <span>INICIO · $1,000.00</span>
    <span>{a.equity.length - 1} liquidaciones</span>
    </div>
    </section>
    <BinaryMarketPanel snapshot={s} now={uiNow} connected={connected}/>
    </div>
    <IndicatorContext context={s.validator.market_context} stale={stale || Math.floor(uiNow / 300) * 300 !== s.cycle}/>
    {simple?<SimpleRulesPanel s={s}/>:<DirectionalPanel sides={s.validator.sides} probability={s.probability} candidates={s.decision.candidates}/>}
    <section className="live-grid">
    <article className="panel">
    <div className="panelhead">
    <h2>{simple ? 'Controles de ejecución experimental' : s.profile === 'gan_laya' ? 'Validación GAN + LAYA para entradas de $1' : s.profile === 'exploratory' ? 'Controles de simulación exploratoria' : 'Filtros de entrada en tiempo real'}</h2>
    <small>{s.model_ready ? 'MODELOS LISTOS' : 'MODELOS INICIALIZANDO'}</small>
    </div>
    <div className="gates">{s.gates.map(g => <div key={g.name}>
        <i className={g.ok ? 'pass' : 'pending'}>{g.ok ? '✓' : '·'}</i>
        <span>{g.name}</span>
        <b>{g.ok ? 'PASS' : 'WAIT'}</b>
        </div>)}</div>
    <p className="model-note">{simple ? 'Reglas edge-laya-v1: indicadores como contexto; Q diagnóstico. Las cuotas y la resolución siguen siendo oficiales; sin fallback sintético. Cuenta paper independiente.' : s.profile === 'gan_laya' ? 'La dirección procede de la GAN. Se exigen concordancia técnica y aprobación real MLX >70%, EV neto >0.05 y tamaño fijo de $1 con tasas. Las filas exploratorias anteriores no se reclasifican como validadas.' : s.profile === 'exploratory' ? 'Estas operaciones ejercitan el simulador y no cuentan como señales aprobadas. Importe total fijo de $1 con tasas. Se elige la cuota menor disponible; se permiten fracciones paper por debajo del mínimo real, identificadas en la tabla. Sin exigir aprobación de la señal.' : ''} {s.signal_note}</p>
    <p className="model-note">La liquidación live espera el resultado oficial de Polymarket. La referencia del gráfico es spot Binance.</p>
    </article>
    <article className="panel">
    <div className="panelhead">
    <h2>Señales y ejecuciones</h2>
    <small>ACTUALIZACIÓN 1s</small>
    </div>
    <div className="event-log" aria-live="polite">{s.events.slice(0, 15).map((e, i) => <div key={`${e.timestamp}-${i}`}>
        <time>{new Date(e.timestamp * 1000).toLocaleTimeString()}</time>
        <b className={e.kind === 'ENTRY' ? 'green' : ''}>{e.kind}</b>
        <span>{e.message}</span>
        </div>)}{!s.events.length && <p>Cargando fuentes y modelos…</p>}</div>
    </article>
    </section>
    <ResearchPanel report={s.research} error={s.research_error}/>
    <TradeHistory s={s} uiNow={uiNow} filter={filter} setFilter={setFilter}/>
    <footer>
    <span>LAYA RESEARCH ENGINE <i /> PAPER TRADING ONLY</span>
    <span>{simple ? 'EDGE + VETO LAYA · EXPERIMENTO $1' : s.profile === 'gan_laya' ? 'GAN + LAYA VALIDADOS · $1 TOTAL POR ENTRADA' : s.profile === 'exploratory' ? 'SIMULACIÓN EXPLORATORIA · $1 por ciclo · CUENTA SEPARADA' : 'GAN experimental · Half-Kelly · Máx. 5% por entrada'}</span>
    </footer>
    </main>
    </div>;
}
;
