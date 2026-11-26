"""Offline check: how much the confidence part of the BL-Filing+ filter matters.

Same saved v1 views, prices, BL settings, tilting rule, costs and Sharpe
definition as the published BL-Filing+ series. Only the view filter differs.
No API calls. Shared and frozen files are read-only.
"""
from pathlib import Path
import json
import logging
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_all_prices, load_universe
from src.backtesting import engine
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior, build_view_matrices
from src.optimization.optimizer import tilt_weights
from scripts.v2.portfolio_protocol import posterior

OUT = ROOT / 'data/v2/analysis/informatica_v5_gemini/confidence_filter_check_v1'
FILTERS = {
    'medium_positive': lambda v: v.confidence == 'medium' and v.view_bps > 0,   # published BL-Filing+
    'all_conf_positive': lambda v: v.view_bps > 0,
    'medium_both_signs': lambda v: v.confidence == 'medium',                     # published BL-Filing
    'all_conf_both_signs': lambda v: True,
}
ARMS = list(FILTERS) + ['equal_weight']
EW = ARMS.index('equal_weight')


def replay(prices, dates, targets):
    """Same drift, trade timing and cost rule as run_informatica_matched_controls.replay."""
    daily = prices.pct_change().dropna()
    m, n = len(ARMS), prices.shape[1]
    current = np.full((m, n), 1 / n)
    out, index = [], []
    for i, date in enumerate(dates):
        if len(prices.loc[:date]) < 262:
            continue
        trade = engine.get_next_trading_day(date, prices)
        if trade is None:
            continue
        end = engine.get_next_trading_day(dates[i + 1], prices) if i + 1 < len(dates) else prices.index[-1]
        if end is None:
            end = prices.index[-1]
        target = targets[date]
        target = current.copy() if target is None else target.copy()
        target[EW] = np.full(n, 1 / n)
        turnover = np.abs(target - current).sum(axis=1)
        period = daily.loc[(daily.index >= trade) & (daily.index < end)]
        if period.empty:
            continue
        w = target.copy()
        for j, (dt, row) in enumerate(zip(period.index, period.to_numpy())):
            value = w @ row
            if j == 0:
                value = value - .001 * turnover
            out.append(value)
            index.append(dt)
            w *= 1 + row
            w /= w.sum(axis=1)[:, None]
        current = w
    return pd.DataFrame(out, index=index, columns=ARMS)


def metrics(r, rf):
    e = r.sub(rf, axis=0)
    wealth = (1 + r).cumprod()
    peak = wealth.cummax().clip(lower=1)
    return pd.DataFrame({
        'cagr': wealth.iloc[-1] ** (252 / len(r)) - 1,
        'sharpe': e.mean() / e.std() * np.sqrt(252),
        'max_drawdown': (wealth / peak - 1).min(),
    })


def main():
    if OUT.exists():
        raise SystemExit('Refusing to overwrite confidence_filter_check_v1')
    OUT.mkdir(parents=True)
    logging.disable(logging.CRITICAL)
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    views = engine.load_views_summary(ROOT / 'data/v2/views_v2/views_summary.csv')
    dates = engine.generate_rebalance_dates(2006, 2025, 'quarterly')
    factors = pd.read_csv(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv', index_col=0, parse_dates=True)
    report = {}
    for group in ['core', 'holdout']:
        names = universe[group]
        px = prices[names]
        n = len(names)
        idx = {t: i for i, t in enumerate(names)}
        targets, accepted = {}, {k: [] for k in FILTERS}
        for date in dates:
            if len(px.loc[:date]) < 262 or engine.get_next_trading_day(date, px) is None:
                continue
            active = engine.get_active_views(views, names, date, 120)
            try:
                cov = rolling_covariance(px, date, lookback=252)
            except ValueError as exc:
                if not str(exc).startswith('Not enough observations:'):
                    raise
                targets[date] = None
                continue
            prior = compute_prior(cov, np.ones(n) / n, delta=2.5)
            weights = np.full((len(ARMS), n), 1 / n)
            for k, (name, keep) in enumerate(FILTERS.items()):
                chosen = [v for v in active if keep(v)]
                accepted[name].append(len(chosen))
                if chosen:
                    p, q, omega = build_view_matrices(chosen, idx, n)
                    weights[k] = tilt_weights(posterior(cov, prior, p, q, omega), tilt_strength=1.)
            assert np.isfinite(weights).all() and (weights >= 0).all()
            np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-12)
            targets[date] = weights
        frame = replay(px, dates, targets).loc[:'2025-12-31']
        frozen = pd.read_csv(ROOT / f'data/v2/analysis/informatica_v5_gemini/results/{group}/daily_returns.csv', index_col=0, parse_dates=True).loc[:'2025-12-31']
        assert frame.index.equals(frozen.index), (group, 'date mismatch')
        errors = {}
        for arm, column in [('medium_positive', 'bl_llm_tilt_pos'), ('medium_both_signs', 'bl_llm_tilt'), ('equal_weight', 'equal_weight')]:
            if column in frozen.columns:
                errors[arm] = float(np.max(np.abs(frame[arm] - frozen[column])))
        rf = factors.RF.reindex(frame.index)
        assert rf.notna().all()
        table = metrics(frame, rf)
        table['mean_accepted_views'] = [float(np.mean(accepted[a])) if a in accepted else np.nan for a in table.index]
        frame.to_csv(OUT / f'{group}_daily_returns.csv')
        table.to_csv(OUT / f'{group}_metrics.csv')
        report[group] = {'max_abs_error_vs_frozen': errors, 'metrics': table.round(6).to_dict(orient='index')}
        print(group, 'max abs error vs frozen series:', errors, flush=True)
        print(table.round(4).to_string(), flush=True)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
