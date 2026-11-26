"""Per-date summary of the text-ablation and name-masking experiments on gemini-2.5-flash.

Combines the two original dates with the three added after review. For every date and group:
view-level change, its excess over repeat noise with a bootstrap interval over companies,
and weight-level distances next to the between-repeat distance. Offline; saved responses only.
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
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior
from scripts.v2.analyze_informatica_text_ablation import allocate as allocate_neutral, weight_contrast
from scripts.v2.analyze_informatica_portfolio_masking import allocate as allocate_masking, compare_weights

BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
SETS = [('llm_inputs_v1', '_gemini25flash_v1'), ('llm_inputs_extra_dates_v1', '_gemini25flash_extra_dates_v1')]
PAIRS = {'removal': ('ablation', 'real_text', 'no_text'), 'replacement': ('ablation', 'real_text', 'shuffled_text'), 'masking': ('masking', 'original', 'anonymized')}


def per_case(a, b):
    """a, b: cases x 3 repeats. Returns |mean difference| and excess of cross distance over repeat noise, per case."""
    wa = np.mean(np.stack([np.abs(a[:, i] - a[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    wb = np.mean(np.stack([np.abs(b[:, i] - b[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    cross = np.abs(a[:, :, None] - b[:, None, :]).mean((1, 2))
    return np.abs(a.mean(1) - b.mean(1)), cross - (wa + wb) / 2, (wa + wb) / 2


def ci(x, rng):
    idx = rng.integers(len(x), size=(5000, len(x)))
    return np.quantile(x[idx].mean(1), [.025, .975]).tolist()


def main():
    logging.disable(logging.CRITICAL)
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    rng = np.random.default_rng(20261125)
    rows = []; pooled = {}
    for prep, suffix in SETS:
        manifest = json.loads((BASE / prep / 'manifest.json').read_text())
        rec = {}
        for exp in ['ablation', 'masking']:
            for p in sorted((BASE / f'{exp}{suffix}').glob('[0-9][0-9][0-9][0-9]_*.json')):
                r = json.loads(p.read_text()); j = r['job']
                assert r['valid'] and not r['fatal'], p.name
                rec[exp, j['case_id'], j['condition'], j['repeat']] = r['parsed']
        for date in manifest['dates']:
            for group in ['core', 'holdout']:
                cases = [c for c in manifest['cases'] if c['date'] == date and c['group'] == group]
                names = universe[group]
                cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
                prior = compute_prior(cov, np.ones(50) / 50, 2.5)
                row = dict(date=date, group=group, cases=len(cases))
                for label, (exp, a, b) in PAIRS.items():
                    va = np.array([[rec[exp, c['case_id'], a, r]['view_bps'] for r in (1, 2, 3)] for c in cases])
                    vb = np.array([[rec[exp, c['case_id'], b, r]['view_bps'] for r in (1, 2, 3)] for c in cases])
                    absd, excess, noise = per_case(va, vb)
                    pooled.setdefault((date, label), []).append((absd, excess, noise))
                    alloc = allocate_neutral if exp == 'ablation' else allocate_masking
                    w = {arm: np.stack([alloc(cases, {c['case_id']: rec[exp, c['case_id'], arm, r] for c in cases}, names, cov, prior)[0] for r in (1, 2, 3)]) for arm in (a, b)}
                    if exp == 'ablation':
                        s = weight_contrast(w[a], w[b]); dist, wn, ex = s['mean_vector_distance'], (s['mean_within_a'] + s['mean_within_b']) / 2, s['cross_minus_average_within']
                    else:
                        s = compare_weights(w[a], w[b]); dist, wn, ex = s['mean_vector_one_way_distance'], (s['original_within_one_way'] + s['masked_within_one_way']) / 2, s['cross_minus_average_within']
                    row.update({f'{label}_view_abs_bps': float(absd.mean()), f'{label}_view_excess_bps': float(excess.mean()), f'{label}_view_excess_ci95': ci(excess, rng),
                                f'{label}_view_noise_bps': float(noise.mean()), f'{label}_weight_distance': float(dist), f'{label}_weight_between_repeats': float(wn), f'{label}_weight_excess': float(ex)})
                rows.append(row)
    by_date = []
    for (date, label), parts in sorted(pooled.items()):
        absd = np.concatenate([p[0] for p in parts]); excess = np.concatenate([p[1] for p in parts]); noise = np.concatenate([p[2] for p in parts])
        by_date.append(dict(date=date, contrast=label, cases=len(absd), view_abs_bps=float(absd.mean()), view_excess_bps=float(excess.mean()), view_excess_ci95=ci(excess, rng), view_noise_bps=float(noise.mean())))
    allc = {}
    for label in PAIRS:
        absd = np.concatenate([p[0] for (d, l), parts in pooled.items() if l == label for p in parts]); excess = np.concatenate([p[1] for (d, l), parts in pooled.items() if l == label for p in parts])
        allc[label] = dict(cases=len(absd), view_abs_bps=float(absd.mean()), view_excess_bps=float(excess.mean()), view_excess_ci95=ci(excess, rng))
    (BASE / 'llm_dates_analysis.json').write_text(json.dumps(dict(slices=rows, by_date=by_date, all_dates=allc), indent=2) + '\n')
    pd.set_option('display.width', 250)
    print(pd.DataFrame(by_date).round(2).to_string(index=False), flush=True)
    d = pd.DataFrame(rows)
    print(d[['date', 'group'] + [c for c in d.columns if 'weight' in c]].round(4).to_string(index=False), flush=True)
    print(json.dumps(allc, indent=1), flush=True)


if __name__ == '__main__':
    main()
