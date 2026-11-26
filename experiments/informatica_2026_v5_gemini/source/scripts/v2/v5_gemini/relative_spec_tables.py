"""What Tables 3-5 of V5 look like if LLM views enter BL relative to the prior.

Relative specification: q_i = prior_i / 4 + view_i, with prior and covariance on a quarterly
scale (as in reviewer_checks.py, part A). Offline: saved views, saved experiment responses.

  1  portfolios: positive-view and both-sign variants, the no-LLM control, EW, and the two
     permutation schemes (100 seeds each) under the relative specification;
  2  text-ablation and name-masking weight distances on the five dates under the relative
     specification, next to the between-repeat distance.
"""
from pathlib import Path
from itertools import combinations
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
from src.reasoning.calibration import calibrate_uncertainty
from src.reasoning.schemas import Confidence
from scripts.v2.portfolio_protocol import posterior
from scripts.v2 import reanalyze_informatica_returns as paired
from scripts.v2.v5_gemini import run_informatica_matched_controls as matched

BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
OUT = BASE / 'relative_spec_v1'
FIXED = ['real_absolute', 'prior_only', 'equal_weight', 'rel_pos', 'rel_all']
ARMS = FIXED + [f'{fam}_{i:03d}' for fam in ['full_shuffle', 'eligible_shuffle'] for i in range(100)]
paired.RF = 0.0


def rel_weights(cov, prior, idx, q, omega, n):
    p = np.eye(n)[idx]
    return tilt_weights(posterior(cov / 4, prior / 4, p, prior[idx] / 4 + q, omega), tilt_strength=1.)


def portfolios(prices, views, universe, dates, factors):
    out = {}
    for group in ['core', 'holdout']:
        names = universe[group]; px = prices[names]; n = len(names); targets = {}
        for date in dates:
            if len(px.loc[:date]) < 262 or engine.get_next_trading_day(date, px) is None:
                continue
            active = engine.get_active_views(views, names, date, 120)
            chosen = [v for v in active if v.confidence == 'medium' and v.view_bps > 0]
            medium = [v for v in active if v.confidence == 'medium']
            try:
                cov = rolling_covariance(px, date, lookback=252)
            except ValueError:
                targets[date] = None
                continue
            prior = compute_prior(cov, np.ones(n) / n, delta=2.5)
            w = np.full((len(ARMS), n), 1 / n)
            w[1] = tilt_weights(prior, tilt_strength=1.)
            imap = {t: i for i, t in enumerate(names)}
            if medium:
                p2, q2, o2 = build_view_matrices(medium, imap, n)
                w[4] = rel_weights(cov, prior, p2.argmax(axis=1), q2, o2, n)
            if chosen:
                p, q, om = build_view_matrices(chosen, imap, n)
                idx = p.argmax(axis=1)
                w[0] = tilt_weights(posterior(cov, prior, p, q, om), tilt_strength=1.)
                w[3] = rel_weights(cov, prior, idx, q, om, n)
                for offset, family in [(5, 'full_shuffle'), (105, 'eligible_shuffle')]:
                    for seed in range(100):
                        new = matched.permutation(group, date, family, seed, idx, n)
                        w[offset + seed] = rel_weights(cov, prior, np.asarray(new), q, om, n)
            else:
                w[5:] = w[1]
            targets[date] = w
        previous = matched.ARMS; matched.ARMS = ARMS
        try:
            frame, wh, costs = matched.replay(px, dates, targets)
        finally:
            matched.ARMS = previous
        frame = frame.loc[:'2025-12-31']
        rf = factors.RF.reindex(frame.index); e = frame.sub(rf, axis=0)
        sharpe = e.mean() / e.std() * np.sqrt(252)
        wealth = (1 + frame).cumprod(); peak = wealth.cummax().clip(lower=1)
        cagr = wealth.iloc[-1] ** (252 / len(frame)) - 1
        turn = pd.DataFrame([v for d, v in costs], index=[d for d, v in costs], columns=ARMS)
        reported = [d for d, w_ in wh if engine.get_next_trading_day(pd.Timestamp(d), px) <= frame.index[-1]]
        eff = np.mean([1 / (w_ ** 2).sum(axis=1) for d, w_ in wh if d in reported], axis=0)
        res = {}
        for i, arm in enumerate(FIXED):
            res[arm] = dict(cagr=float(cagr[arm]), volatility=float(frame[arm].std() * np.sqrt(252)), sharpe=float(sharpe[arm]),
                            max_drawdown=float((wealth[arm] / peak[arm] - 1).min()),
                            annual_turnover=float(turn.loc[reported, arm].sum() / (len(frame) / 252)), effective_holdings=float(eff[i]))
        perms = {}
        for fam in ['eligible_shuffle', 'full_shuffle']:
            s = sharpe.filter(like=fam).to_numpy(); real = float(sharpe['rel_pos'])
            perms[fam] = dict(median=float(np.median(s)), p05=float(np.quantile(s, .05)), p95=float(np.quantile(s, .95)), runs_at_or_above_real=int((s >= real).sum()))
        cols = FIXED
        boot = paired.block_sharpes(e[cols].to_numpy(), 21, 10000, 20261126 + (group == 'holdout'))
        diffs = {}
        for a, b in [('rel_pos', 'prior_only'), ('rel_pos', 'equal_weight'), ('rel_all', 'prior_only'), ('rel_pos', 'rel_all')]:
            ia, ib = cols.index(a), cols.index(b)
            test = paired.hac_mean((frame[a] - frame[b]).to_numpy(), 21)
            diffs[f'{a}_minus_{b}'] = dict(sharpe_difference=float(sharpe[a] - sharpe[b]), ci95=np.quantile(boot[:, ia] - boot[:, ib], [.025, .975]).tolist(),
                                           mean_return_difference=test['annualized_mean_difference'], p_raw=test['p_raw'])
        out[group] = dict(performance=res, permutations=perms, differences=diffs)
        frame[FIXED].to_csv(OUT / f'{group}_returns.csv')
        print(group, json.dumps({k: {m: round(x, 4) for m, x in v.items()} for k, v in res.items()}), flush=True)
        print(group, json.dumps(perms), flush=True)
    return out


def distances(prices, universe):
    sets = [('llm_inputs_v1', '_gemini25flash_v1'), ('llm_inputs_extra_dates_v1', '_gemini25flash_extra_dates_v1')]
    pairs = {'removal': ('ablation', 'real_text', 'no_text'), 'replacement': ('ablation', 'real_text', 'shuffled_text'), 'masking': ('masking', 'original', 'anonymized')}
    rows = []
    for prep, suffix in sets:
        manifest = json.loads((BASE / prep / 'manifest.json').read_text()); rec = {}
        for exp in ['ablation', 'masking']:
            for p in sorted((BASE / f'{exp}{suffix}').glob('[0-9][0-9][0-9][0-9]_*.json')):
                r = json.loads(p.read_text()); j = r['job']
                rec[exp, j['case_id'], j['condition'], j['repeat']] = r['parsed']
        for date in manifest['dates']:
            for group in ['core', 'holdout']:
                cases = [c for c in manifest['cases'] if c['date'] == date and c['group'] == group]
                names = universe[group]; n = len(names)
                cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
                prior = compute_prior(cov, np.ones(n) / n, 2.5)
                row = dict(date=date, group=group)

                def alloc(exp, arm, rep):
                    idx, q, om = [], [], []
                    for c in cases:
                        o = rec[exp, c['case_id'], arm, rep]
                        if o['confidence'] == 'medium' and o['view_bps'] > 0:
                            idx.append(names.index(c['ticker'])); q.append(o['view_bps'] / 10000)
                            om.append(.03 ** 2 if exp == 'ablation' else calibrate_uncertainty(Confidence.MEDIUM, sentiment=c['sentiment']) ** 2)
                    if not idx:
                        return tilt_weights(prior, tilt_strength=1.)
                    return rel_weights(cov, prior, np.array(idx), np.array(q), np.array(om), n)
                for label, (exp, a, b) in pairs.items():
                    wa = np.stack([alloc(exp, a, r) for r in (1, 2, 3)]); wb = np.stack([alloc(exp, b, r) for r in (1, 2, 3)])
                    within = np.mean([np.abs(x[i] - x[j]).sum() / 2 for x in (wa, wb) for i, j in combinations(range(3), 2)])
                    row[f'{label}_distance'] = float(np.abs(wa.mean(0) - wb.mean(0)).sum() / 2)
                    row[f'{label}_between_repeats'] = float(within)
                rows.append(row)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    views = engine.load_views_summary(ROOT / 'data/v2/views_v2/views_summary.csv')
    dates = engine.generate_rebalance_dates(2006, 2025, 'quarterly')
    factors = pd.read_csv(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv', index_col=0, parse_dates=True)
    rows = distances(prices, universe)
    (OUT / 'distances.json').write_text(json.dumps(rows, indent=2) + '\n')
    pd.set_option('display.width', 220)
    print(pd.DataFrame(rows).sort_values(['date', 'group']).round(4).to_string(index=False), flush=True)
    res = portfolios(prices, views, universe, dates, factors)
    (OUT / 'portfolios.json').write_text(json.dumps(res, indent=2) + '\n')
    for g in res:
        print(g, json.dumps({k: {m: (round(x, 4) if isinstance(x, float) else [round(y, 4) for y in x]) for m, x in v.items()} for k, v in res[g]['differences'].items()}), flush=True)


if __name__ == '__main__':
    main()
