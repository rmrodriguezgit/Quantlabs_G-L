import { Activity } from 'lucide-react';
import type { State } from './types';
import { money } from './format';
export function TradeHistory({ s, uiNow, filter, setFilter }: {
    s: State;
    uiNow: number;
    filter: string;
    setFilter: (value: string) => void;
}) {
    const a = s.account;
    return (<section className="panel history">
    <div className="panelhead">
    <h2>Histórico de operaciones <span className="count">{a.trades.length}</span>
    </h2>
    <select aria-label="Filtrar operaciones" value={filter} onChange={e => setFilter(e.target.value)}>
    <option value="ALL">Todas las operaciones</option>
    <option value="OPEN">Abiertas</option>
    <option value="WON">Ganadas</option>
    <option value="LOST">Perdidas</option>
    </select>
    </div>
    <p className="model-note">Referencia y cierre: misma vela BTCUSDT de Binance. El resultado oficial de Polymarket usa Chainlink TWAP y puede diferir de esta comparación spot.</p>
    <div className="tablewrap">
    <table>
    <thead>
    <tr>{['HORA LOCAL', 'POSICIÓN / PERFIL', 'BTC REF. (BINANCE)', 'BTC CIERRE (BINANCE)', 'Δ BTC', 'CUOTA', 'INVERSIÓN', 'LAYA / TÉCNICO', 'RESULTADO', 'PNL'].map(x => <th key={x}>{x}</th>)}</tr>
    </thead>
    <tbody>{a.trades.filter(t => filter === 'ALL' || t.status === filter).map(t => <tr key={t.id}>
        <td>{new Date(t.timestamp * 1000).toLocaleString()}</td>
        <td className={t.side === 'UP' ? 'green' : 'red'}>{t.side}<small className="trade-profile">{t.profile === 'gan_laya' ? 'GAN + LAYA' : t.profile === 'exploratory' ? 'EXPLORATORIA' : 'ESTRATEGIA'}{t.below_minimum ? ' · BAJO MÍNIMO REAL' : ''}</small>
        </td>
        <td title="Apertura BTC de Binance guardada para este ciclo; no es el TWAP oficial de Chainlink">{t.reference != null && Number.isFinite(t.reference) ? money(t.reference) : '—'}</td>
        <td title="Cierre histórico de la vela Binance de esta operación; el resultado oficial usa Chainlink TWAP">{t.closing_price != null ? money(t.closing_price) : uiNow < t.cycle + 300 ? 'En curso' : 'Pendiente de dato'}{t.closing_time != null && <small className="trade-profile">{new Date(t.closing_time * 1000).toLocaleTimeString()} · {t.closing_source}</small>}</td>
        <td className={t.closing_price != null && t.reference != null ? (t.closing_price >= t.reference ? 'green' : 'red') : ''}>{t.closing_price != null && t.reference != null ? `${t.closing_price >= t.reference ? '+' : ''}${money(t.closing_price - t.reference)}` : '—'}</td>
        <td>{money(t.price)}</td>
        <td title={`Tasas: ${money(t.fee ?? 0)}`}>{money(t.stake)}</td>
        <td>{t.gan_probability != null && <small className="trade-profile">GAN UP {(t.gan_probability * 100).toFixed(1)}% · MLX {((t.laya_model_probability ?? 0) * 100).toFixed(1)}%</small>}{(t.laya_score * 100).toFixed(0)}% técnico / {t.validator_status === 'LAYA_APPROVED' ? 'MLX APROBADO' : t.validator_status === 'LAYA_REJECTED' ? 'MLX RECHAZADO' : 'BASELINE'}</td>
        <td>{t.status === 'OPEN' ? 'ABIERTA' : t.status === 'WON' ? 'GANÓ' : 'PERDIÓ'}{t.official_outcome && <small className="trade-profile">OFICIAL: {t.official_outcome}</small>}</td>
        <td className={t.pnl >= 0 ? 'green' : 'red'}>{money(t.pnl)}</td>
        </tr>)}</tbody>
    </table>{!a.trades.length && <div className="empty">
        <Activity size={22}/>
        <p>El motor está observando el mercado.</p>
        <small>{s.profile === 'exploratory' ? 'La primera entrada se registra con una cotización válida y modelos listos.' : 'Las operaciones aparecerán cuando se cumplan todos los filtros dentro de la ventana.'}</small>
        </div>}</div>
    </section>);
}
