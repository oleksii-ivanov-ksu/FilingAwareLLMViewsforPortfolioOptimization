"""Offline checks requested by the V5 review (2026-11-25). No API calls; saved inputs are read-only.

A  view scale: how often an accepted positive view lies below the prior return of its stock,
   and portfolios in which the view is entered relative to the prior (q = prior + view),
   on a quarterly scale;
B  permutation ranges and ranks for Table 5;
C  Random Views as a 100-seed ensemble;
D  CAPM and four-factor loadings for BL-Filing+, the no-LLM control and EW;
E  Table 1 on the 90 annotated filings, with bootstrap intervals over filings.
"""
from pathlib import Path
import json
import logging
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_all_prices, load_universe
from src.backtesting import engine
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior, build_view_matrices
from src.optimization.optimizer import tilt_weights
from scripts.v2.portfolio_protocol import posterior
from scripts.v2 import reanalyze_informatica_returns as paired
from scripts.v2.v5_gemini import run_informatica_matched_controls as matched
from scripts.v2.v5_gemini.event_matching import match_events, MATCH_THRESHOLD

BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
OUT = BASE / 'reviewer_checks_v1'
OUT_TABLE1 = BASE / 'table1_all_filings_v1'
ARMS = ['real', 'prior_only', 'equal_weight', 'rel_pos', 'rel_all']
paired.RF = 0.0  # excess returns are passed explicitly


def perf(frame, rf):
    e = frame.sub(rf, axis=0)
    wealth = (1 + frame).cumprod()
    peak = wealth.cummax().clip(lower=1)
    return pd.DataFrame({'cagr': wealth.iloc[-1] ** (252 / len(frame)) - 1, 'volatility': frame.std() * np.sqrt(252),
                         'sharpe': e.mean() / e.std() * np.sqrt(252), 'max_drawdown': (wealth / peak - 1).min()})


def scale_and_relative(prices, views, universe, dates, factors):
    out = {}
    for group in ['core', 'holdout']:
        names = universe[group]; px = prices[names]; n = len(names); targets = {}; rows = []; bounds = []
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
            idx_map = {t: i for i, t in enumerate(names)}
            if chosen:
                p, q, om = build_view_matrices(chosen, idx_map, n)
                idx = p.argmax(axis=1)
                mu = posterior(cov, prior, p, q, om)
                w[0] = tilt_weights(mu, tilt_strength=1.)
                z_prior = (prior - prior.mean()) / prior.std(); z_post = (mu - mu.mean()) / mu.std()
                rows.append(dict(date=str(date.date()), accepted=len(chosen),
                                 q_below_annual_prior=int((q < prior[idx]).sum()),
                                 q_below_quarter_prior=int((q < prior[idx] / 4).sum()),
                                 posterior_below_prior=int((mu[idx] < prior[idx]).sum()),
                                 weight_below_control=int((w[0][idx] < w[1][idx]).sum()),
                                 z_lowered=int((z_post[idx] < z_prior[idx]).sum()),
                                 mean_q=float(q.mean()), mean_prior_viewed=float(prior[idx].mean())))
                # views relative to the prior, everything on a quarterly scale
                w[3] = tilt_weights(posterior(cov / 4, prior / 4, p, prior[idx] / 4 + q, om), tilt_strength=1.)
            if medium:
                p2, q2, om2 = build_view_matrices(medium, idx_map, n)
                idx2 = p2.argmax(axis=1)
                w[4] = tilt_weights(posterior(cov / 4, prior / 4, p2, prior[idx2] / 4 + q2, om2), tilt_strength=1.)
            bounds.append((float(w[0].min()), float(w[0].max())))
            targets[date] = w
        previous = matched.ARMS; matched.ARMS = ARMS
        try:
            frame, wh, costs = matched.replay(px, dates, targets)
        finally:
            matched.ARMS = previous
        frame = frame.loc[:'2025-12-31']
        saved = pd.read_csv(BASE / f'matched_controls_v1/{group}_daily_returns.csv', index_col=0, parse_dates=True)
        for arm in ARMS[:3]:
            assert float(np.max(np.abs(frame[arm] - saved[arm]))) < 1e-10, (group, arm)
        rf = factors.RF.reindex(frame.index)
        e = frame.sub(rf, axis=0)
        boot = paired.block_sharpes(e.to_numpy(), 21, 10000, 20261125 + (group == 'holdout'))
        actual = (e.mean() / e.std() * np.sqrt(252)).to_numpy()
        diffs = {}
        for a, b in [('rel_pos', 'prior_only'), ('rel_all', 'prior_only'), ('rel_pos', 'real'), ('rel_pos', 'equal_weight'), ('rel_all', 'equal_weight')]:
            ia, ib = ARMS.index(a), ARMS.index(b)
            diffs[f'{a}_minus_{b}'] = dict(difference=float(actual[ia] - actual[ib]), ci95=np.quantile(boot[:, ia] - boot[:, ib], [.025, .975]).tolist())
        d = pd.DataFrame(rows); tot = int(d.accepted.sum())
        frame.to_csv(OUT / f'{group}_relative_views_returns.csv')
        out[group] = dict(accepted_view_dates=tot,
                          share_q_below_annual_prior=float(d.q_below_annual_prior.sum() / tot),
                          share_q_below_quarter_prior=float(d.q_below_quarter_prior.sum() / tot),
                          share_posterior_below_prior=float(d.posterior_below_prior.sum() / tot),
                          share_weight_below_control=float(d.weight_below_control.sum() / tot),
                          share_standardized_score_lowered=float(d.z_lowered.sum() / tot),
                          mean_view=float(np.average(d.mean_q, weights=d.accepted)),
                          mean_annual_prior_of_viewed=float(np.average(d.mean_prior_viewed, weights=d.accepted)),
                          weight_bounds_after_normalization=dict(min=min(b[0] for b in bounds), max=max(b[1] for b in bounds)),
                          performance=perf(frame, rf).round(6).to_dict('index'), sharpe_differences=diffs)
        print('A', group, json.dumps({k: v for k, v in out[group].items() if k.startswith('share') or k.startswith('mean')}), flush=True)
    return out


def permutation_table():
    out = {}
    for group in ['core', 'holdout']:
        mm = pd.read_csv(BASE / f'publication_audit_v1/{group}_matched_metrics.csv', index_col=0)
        real = float(mm.loc['real', 'sharpe']); out[group] = {'real': real}
        for scheme in ['eligible_shuffle', 'full_shuffle']:
            s = mm.filter(like=scheme, axis=0).sharpe.to_numpy()
            out[group][scheme] = dict(median=float(np.median(s)), p05=float(np.quantile(s, .05)), p95=float(np.quantile(s, .95)),
                                      runs_at_or_above_real=int((s >= real).sum()), empirical_p=float((1 + (s >= real).sum()) / 101))
    return out


def random_views_ensemble(prices, views, universe, dates, factors):
    out = {}
    for group in ['core', 'holdout']:
        names = universe[group]; px = prices[names]; sh = []; cg = []
        for seed in range(100):
            r = engine.run_backtest(px, views, names, dates, strategy='random_views', placebo_seed=seed)['daily_returns'].loc[:'2025-12-31']
            e = r - factors.RF.reindex(r.index)
            sh.append(float(e.mean() / e.std() * np.sqrt(252))); cg.append(float((1 + r).prod() ** (252 / len(r)) - 1))
            if seed % 25 == 24:
                print('C', group, seed + 1, flush=True)
        sh = np.array(sh); cg = np.array(cg)
        out[group] = dict(sharpe_median=float(np.median(sh)), sharpe_p05=float(np.quantile(sh, .05)), sharpe_p95=float(np.quantile(sh, .95)),
                          cagr_median=float(np.median(cg)), cagr_p05=float(np.quantile(cg, .05)), cagr_p95=float(np.quantile(cg, .95)),
                          seed0_sharpe=float(sh[0]), sharpes=sh.tolist(), cagrs=cg.tolist())
    return out


def loadings(factors):
    rows = []
    for group in ['core', 'holdout']:
        frame = pd.read_csv(BASE / f'signal_risk_v1/{group}_daily_returns.csv', index_col=0, parse_dates=True)
        f = factors.reindex(frame.index)
        for arm in ['real', 'prior_only', 'equal_weight']:
            y = frame[arm] - f.RF
            for model, cols in [('CAPM', ['Mkt-RF']), ('FF3+Mom', ['Mkt-RF', 'SMB', 'HML', 'Mom'])]:
                fit = sm.OLS(y, sm.add_constant(f[cols])).fit(cov_type='HAC', cov_kwds={'maxlags': 21})
                rows.append(dict(group=group, arm=arm, model=model, alpha_annual=float(fit.params['const'] * 252), alpha_p=float(fit.pvalues['const']),
                                 r2=float(fit.rsquared), **{c: float(fit.params[c]) for c in cols}))
    return rows


def table1():
    gold = {}
    for f in (ROOT / 'data/v2/gold_standard').glob('[0-9]*.json'):
        d = json.loads(f.read_text())
        gold[d['id']] = d
    ids = sorted(gold); counts = {}; processed = {}
    for folder in sorted((ROOT / 'data/v2/model_selection').iterdir()):
        if not folder.is_dir():
            continue
        c = {i: [0, len(gold[i]['events']), 0] for i in ids}  # matched, annotated, extracted
        done = 0
        for f in folder.glob('[0-9]*.json'):
            rec = json.loads(f.read_text())
            if rec['doc_id'] not in gold or not rec.get('facts'):
                continue  # a filing the model failed on counts as no events found
            done += 1
            ev = rec['facts'].get('key_events', [])
            m = match_events(ev, gold[rec['doc_id']]['events'], MATCH_THRESHOLD)
            c[rec['doc_id']][0] = len(m); c[rec['doc_id']][2] = len(ev)
        counts[folder.name] = np.array([c[i] for i in ids], dtype=float); processed[folder.name] = done
    rng = np.random.default_rng(20261125); draws = rng.integers(len(ids), size=(5000, len(ids)))

    def stats(a):
        tp, g, e = a[..., 0].sum(-1), a[..., 1].sum(-1), a[..., 2].sum(-1)
        r = tp / g; p = np.divide(tp, e, out=np.zeros_like(tp), where=e > 0)
        f1 = np.divide(2 * p * r, p + r, out=np.zeros_like(r), where=(p + r) > 0)
        return r, p, f1
    out = {}; boot_f1 = {}
    for model, a in counts.items():
        r, p, f1 = stats(a); br, bp, bf = stats(a[draws]); boot_f1[model] = bf
        out[model] = dict(filings=len(ids), processed=processed[model], tp=int(a[:, 0].sum()), gold=int(a[:, 1].sum()), extracted=int(a[:, 2].sum()), recall=float(r), precision=float(p), f1=float(f1),
                          recall_ci95=np.quantile(br, [.025, .975]).tolist(), precision_ci95=np.quantile(bp, [.025, .975]).tolist(), f1_ci95=np.quantile(bf, [.025, .975]).tolist())
    g = 'google_gemini-2.5-flash'
    for model in counts:
        if model != g:
            d = boot_f1[g] - boot_f1[model]
            out[model]['gemini_minus_this_f1'] = dict(difference=out[g]['f1'] - out[model]['f1'], ci95=np.quantile(d, [.025, .975]).tolist(), share_gemini_higher=float((d > 0).mean()))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    only = sys.argv[1:] or ['A', 'B', 'C', 'D', 'E']
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    views = engine.load_views_summary(ROOT / 'data/v2/views_v2/views_summary.csv')
    dates = engine.generate_rebalance_dates(2006, 2025, 'quarterly')
    factors = pd.read_csv(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv', index_col=0, parse_dates=True)
    jobs = {'A': ('view_scale', lambda: scale_and_relative(prices, views, universe, dates, factors)), 'B': ('permutations', permutation_table),
            'C': ('random_views_ensemble', lambda: random_views_ensemble(prices, views, universe, dates, factors)),
            'D': ('factor_loadings', lambda: loadings(factors)), 'E': ('table1', table1)}
    for key in only:
        name, fn = jobs[key]
        folder = OUT_TABLE1 if key == 'E' else OUT
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{name}.json').write_text(json.dumps(fn(), indent=2) + '\n')
        print('saved', name, flush=True)


if __name__ == '__main__':
    main()
