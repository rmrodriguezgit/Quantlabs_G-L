import { BrainCircuit, ShieldCheck, TowerControl, ChevronRight } from 'lucide-react';
import type { State } from './types';
export function PipelinePanel({ s, stale, dataAge }: {
    s: State;
    stale: boolean;
    dataAge: number;
}) {
    const a = s.account;
    const simple=s.profile==='edge_laya';
    return (<section className="panel signal">
    <div className="panelhead">
    <h2>Pipeline de inteligencia</h2>
    <span className="dot"/>
    </div>
    <div className="pipeline">
    <div>
    <BrainCircuit />
    <span>01 / GAN ESTIMATOR<small>{s.estimator}<small className="trade-profile">UP {(s.probability * 100).toFixed(1)}% · DOWN {((1 - s.probability) * 100).toFixed(1)}%{s.decision.candidates && ` · EV UP ${s.decision.candidates.UP.ev.toFixed(3)} / DOWN ${s.decision.candidates.DOWN.ev.toFixed(3)}`}</small>
    </small>
    <small>{s.gan_quality?.scenarios ? `${s.gan_quality.up_scenarios} / ${s.gan_quality.scenarios} escenarios UP · σ relativa ${s.gan_quality.std_ratio?.toFixed(2) ?? '—'}` : ''}</small>
    </span>
    <b className="pipeline-both">UP {(s.probability * 100).toFixed(1)}%<small>DOWN {((1 - s.probability) * 100).toFixed(1)}%</small>
    </b>
    </div>
    <div className="prob">
    <i style={{ width: `${s.probability * 100}%` }}/>
    </div>
    <div>
    <ShieldCheck />
    <span>02 / LAYA VALIDATOR<small>{simple ? 'Veto de consistencia ≥35%; indicadores informativos' : s.validator.model_connected ? `Concordancia técnica ${(s.validator.score * 100).toFixed(0)}% · aprobación MLX →` : 'MLX sin conectar'}</small>
    </span>
    <b className={s.validator.approved ? 'green' : ''}>{s.validator.model_probability != null ? `${(s.validator.model_probability * 100).toFixed(1)}%` : '—'}</b>
    </div>
    <div className="technical">
    <span>RSI {s.validator.rsi.toFixed(1)}</span>
    <span>EMA 9 / 21</span>
    <span>DELTA VOL.</span>
    </div>
    <div className="pipeline-directions">{(['UP', 'DOWN'] as const).map(side => { const audit = s.validator.sides?.[side]; return <span key={side}>LAYA {side}: {audit?.model_probability != null ? `${(audit.model_probability * 100).toFixed(1)}%` : '—'} · {audit?.approved ? (simple?'SIN VETO':'APROBADO') : 'WAIT'}</span>; })}</div>
    <div>
    <TowerControl />
    <span>{simple?'03 / EDGE · Q DIAGNÓSTICO':'03 / Q-LEARNING'}<small>EV {s.decision.ev.toFixed(3)} · {['exploratory', 'gan_laya','edge_laya'].includes(s.profile ?? '') ? 'Importe fijo $1' : `Kelly ${(s.decision.fraction * 100).toFixed(1)}%`}</small>
    </span>
    <b className="action">{s.decision.action}</b>
    </div>
    </div>
    <div className="decision">
    <span>04 / PAPER EXECUTION</span>
    <b>{a.paused ? 'PAUSADO' : s.decision.action === 'WAIT' ? 'ESPERANDO SEÑAL' : 'EVALUANDO ENTRADA'} <ChevronRight size={14}/>
    </b>
    </div>
    <div className="pipeline-explanation">
    <strong>{stale ? 'DATOS OBSOLETOS · ENTRADAS BLOQUEADAS' : s.decision.action === 'WAIT' ? 'WAIT: filtros pendientes' : 'ENTRADA PAPER'}</strong>
    <p>{(s.blockers?.length ? s.blockers.join(' · ') : s.reason)}</p>
    <small>Último dato BTC: hace {dataAge.toFixed(1)}s · Actualización {new Date(s.timestamp * 1000).toLocaleTimeString()}</small>{s.gan_quality && !s.gan_quality.healthy && <p className="red">{s.gan_quality.reason}</p>}</div>
    </section>);
}
