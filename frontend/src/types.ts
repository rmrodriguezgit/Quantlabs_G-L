import type { MarketContext } from './IndicatorContext';
import type { MarketOdds } from './binaryMarket';
import type { SideAudit } from './DirectionalPanel';
import type { ResearchReport } from './ResearchPanel';
export type Trade = {
    id: number;
    timestamp: number;
    side: string;
    reference?: number;
    closing_price?: number | null;
    closing_time?: number | null;
    closing_source?: string | null;
    official_outcome?: string | null;
    cycle: number;
    price: number;
    stake: number;
    status: string;
    pnl: number;
    laya_score: number;
    validator_status?: string;
    market_slug?: string;
    fee?: number;
    profile?: string;
    entry_ev?: number;
    below_minimum?: boolean;
    gan_probability?: number | null;
    laya_model_probability?: number | null;
};
export type State = {
    timestamp: number;
    mode: string;
    profile?: string;
    cycle: number;
    remaining: number;
    price: number;
    reference: number;
    probability: number;
    estimator: string;
    error: string | null;
    reason: string;
    odds: MarketOdds;
    validator: {
        market_context?: MarketContext;
        sides?: Record<string, SideAudit>;
        score: number;
        rsi: number;
        engine: string;
        approved: boolean;
        model_connected: boolean;
        model_probability: number | null;
    };
    decision: {
        action: string;
        ev: number;
        fraction: number;
        candidate?: string;
        candidates?: Record<string, {
            probability: number;
            ev: number;
            probability_pass: boolean;
            ev_pass: boolean;
        }>;
    };
    account: {
        cash: number;
        balance: number;
        pnl: number;
        win_rate: number;
        total_trades: number;
        profit_factor: number | null;
        max_drawdown: number;
        equity: number[];
        trades: Trade[];
        paused: boolean;
    };
    candles: {
        close: number;
    }[];
    gates: {
        name: string;
        ok: boolean;
    }[];
    events: {
        timestamp: number;
        kind: string;
        message: string;
    }[];
    model_ready: boolean;
    data_updated_at?: number | null;
    gan_quality?: {
        healthy: boolean;
        reason: string;
        std_ratio?: number;
        up_scenarios?: number;
        scenarios?: number;
        trained_at?: number;
    };
    blockers?: string[];
    model_error?: string;
    signal_note?: string;
    research?: ResearchReport;
    research_error?: string | null;
};
