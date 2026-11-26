"""Random Views ensemble at the scale of the gemini views (61.4 bps), for Tables 2 and 4 of V5.

The shared engine draws random views from N(0, 84.5 bps); that value is the spread of the v1
(Grok) views. The spread of the gemini-2.5-flash views is 61.4 bps. The shared engine is not
modified: N(0, s) is s times a standard normal draw, so the same draws are rescaled by
61.4 / 84.5 on their way into the BL posterior. With a factor of 1 the script reproduces the
saved 84.5 bps run (checked on seed 0 before the ensemble starts).

Offline: saved views and prices only, no API calls.
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

BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
OUT = BASE / 'random_views_matched_scale_v1'
ENGINE_BPS = 84.5
MATCHED_BPS = 61.4
SEEDS = 100
_posterior = engine.black_litterman_posterior


def set_scale(bps):
    factor = bps / ENGINE_BPS
    engine.black_litterman_posterior = lambda cov, prior, p, q, omega, tau: _posterior(cov, prior, p, np.asarray(q) * factor, omega, tau)


def run(px, views, names, dates, seed, rf):
    r = engine.run_backtest(px, views, names, dates, strategy='random_views', placebo_seed=seed)['daily_returns'].loc[:'2025-12-31']
    e = r - rf.reindex(r.index)
    wealth = (1 + r).cumprod(); peak = wealth.cummax().clip(lower=1)
    return r, dict(cagr=float(wealth.iloc[-1] ** (252 / len(r)) - 1), volatility=float(r.std() * np.sqrt(252)),
                   sharpe=float(e.mean() / e.std() * np.sqrt(252)), max_drawdown=float((wealth / peak - 1).min()))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    views = engine.load_views_summary(ROOT / 'data/v2/views_v2/views_summary.csv')
    dates = engine.generate_rebalance_dates(2006, 2025, 'quarterly')
    rf = pd.read_csv(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv', index_col=0, parse_dates=True).RF
    saved = json.loads((BASE / 'reviewer_checks_v1/random_views_ensemble.json').read_text())
    out = dict(engine_bps=ENGINE_BPS, matched_bps=MATCHED_BPS, seeds=SEEDS, view_std_bps=float(pd.read_csv(ROOT / 'data/v2/views_v2/views_summary.csv').view_bps.std()))
    for group in ['core', 'holdout']:
        names = universe[group]; px = prices[names]
        set_scale(ENGINE_BPS)
        check = run(px, views, names, dates, 0, rf)[1]['sharpe']
        assert abs(check - saved[group]['seed0_sharpe']) < 1e-9, (group, check, saved[group]['seed0_sharpe'])
        print(group, 'seed 0 at 84.5 bps reproduces the saved run:', round(check, 6), flush=True)
        set_scale(MATCHED_BPS)
        rows = []; seed0 = None
        for seed in range(SEEDS):
            r, m = run(px, views, names, dates, seed, rf)
            rows.append(m)
            if seed == 0:
                seed0 = r
            if seed % 25 == 24:
                print(group, seed + 1, flush=True)
        seed0.rename('random_views_61_4_seed0').to_csv(OUT / f'{group}_seed0_returns.csv')
        d = pd.DataFrame(rows)
        d.to_csv(OUT / f'{group}_runs.csv', index_label='seed')
        out[group] = {c: dict(median=float(d[c].median()), p05=float(d[c].quantile(.05)), p95=float(d[c].quantile(.95)), seed0=float(d[c].iloc[0])) for c in d.columns}
        out[group]['saved_84_5'] = {k: v for k, v in saved[group].items() if not isinstance(v, list)}
        print(group, json.dumps({c: {k: round(v, 4) for k, v in out[group][c].items()} for c in d.columns}), flush=True)
    engine.black_litterman_posterior = _posterior
    (OUT / 'ensemble.json').write_text(json.dumps(out, indent=2) + '\n')
    print('saved', OUT / 'ensemble.json', flush=True)


if __name__ == '__main__':
    main()
