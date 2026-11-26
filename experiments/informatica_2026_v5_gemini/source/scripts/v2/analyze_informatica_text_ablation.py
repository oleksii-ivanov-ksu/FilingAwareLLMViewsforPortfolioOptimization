"""Analyze all prespecified text-ablation contrasts; never issue model calls."""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_all_prices, load_universe
from scripts.v2.portfolio_protocol import posterior
from scripts.v2.analyze_informatica_portfolio_masking import allocate as previous_allocate
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior
from src.optimization.optimizer import tilt_weights

BASE = ROOT / 'data/v2/analysis/informatica_revision'
INPUT = BASE / 'text_ablation_preparation_v1'
RUN = BASE / 'text_ablation_grok43_v1'
ARMS = ['real_text', 'no_text', 'shuffled_text']
CONTRASTS = [('real_text', 'no_text'), ('real_text', 'shuffled_text'), ('shuffled_text', 'no_text')]


def allocate(cases, outputs, names, cov, prior, all_support=False):
    """No historical sentiment or confidence can enter the new allocation."""
    indices, q = [], []
    for c in cases:
        out = outputs[c['case_id']]
        if all_support or (out['confidence'] == 'medium' and out['view_bps'] > 0):
            indices.append(names.index(c['ticker']))
            q.append(out['view_bps'] / 10000)
    if not indices:
        return np.ones(len(names)) / len(names), indices
    p = np.eye(len(names))[indices]
    omega = np.full(len(indices), .03 ** 2)
    weights = tilt_weights(posterior(cov, prior, p, np.array(q), omega), tilt_strength=1.)
    assert np.isfinite(weights).all() and np.min(weights) >= 0
    np.testing.assert_allclose(weights.sum(), 1, atol=1e-12)
    return weights, indices


def weight_contrast(a, b):
    within_a = [float(np.abs(a[i] - a[j]).sum() / 2) for i, j in combinations(range(3), 2)]
    within_b = [float(np.abs(b[i] - b[j]).sum() / 2) for i, j in combinations(range(3), 2)]
    cross = np.abs(a[:, None, :] - b[None, :, :]).sum(2) / 2
    return {'mean_vector_distance': float(np.abs(a.mean(0) - b.mean(0)).sum() / 2),
            'within_a': within_a, 'within_b': within_b, 'cross_pairs': cross.tolist(),
            'mean_within_a': float(np.mean(within_a)), 'mean_within_b': float(np.mean(within_b)),
            'mean_cross': float(cross.mean()),
            'cross_minus_average_within': float(cross.mean() - (np.mean(within_a) + np.mean(within_b)) / 2)}


def view_contrast(a, b):
    """n cases × 3 repeats; descriptive averages only, no pseudoreplicated tests."""
    ma, mb = a.mean(1), b.mean(1)
    wa = np.mean(np.stack([np.abs(a[:, i] - a[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    wb = np.mean(np.stack([np.abs(b[:, i] - b[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    cross = np.abs(a[:, :, None] - b[:, None, :]).mean((1, 2))
    return {'cases': len(a), 'mean_a_bps': float(ma.mean()), 'mean_b_bps': float(mb.mean()),
            'signed_a_minus_b_bps': float((ma - mb).mean()),
            'mean_absolute_mean_difference_bps': float(np.abs(ma - mb).mean()),
            'sign_category_changes': int((np.sign(ma) != np.sign(mb)).sum()),
            'strict_sign_reversals': int((ma * mb < 0).sum()),
            'within_a_bps': float(wa.mean()), 'within_b_bps': float(wb.mean()),
            'cross_bps': float(cross.mean()), 'cross_minus_average_within_bps': float((cross - (wa + wb) / 2).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-check', action='store_true')
    args = ap.parse_args()
    manifest = json.loads((INPUT / 'manifest.json').read_text())
    cases = manifest['cases']
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    records, hashes, ids = {}, {}, []
    cost = 0.
    if not args.self_check:
        for p in sorted(RUN.glob('[0-9][0-9][0-9][0-9]_*.json')):
            record = json.loads(p.read_text())
            j = record['job']
            key = (j['case_id'], j['condition'], j['repeat'])
            assert key not in records and record['valid'] and not record['fatal'], p.name
            records[key] = record['parsed']
            hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
            ids.append(record['response']['id'])
            cost += record['cost']
        assert len(records) == len(ids) == len(set(ids)) == 1791
        assert cost <= 10
    views, weights, contrasts, targets, maxerror = [], [], [], {}, 0.
    if args.self_check:
        a = np.array([[.75, .25]] * 3)
        b = np.array([[.25, .75]] * 3)
        assert weight_contrast(a, b)['mean_vector_distance'] == .5
        assert weight_contrast(a, b)['cross_minus_average_within'] == .5
        assert weight_contrast(a, a)['mean_vector_distance'] == 0
    else:
        subsets = [('all', cases)] + [(date + '_' + group, [c for c in cases if c['date'] == date and c['group'] == group]) for date in manifest['dates'] for group in ['core', 'holdout']]
        for label, subset in subsets:
            arm = {a: np.array([[records[c['case_id'], a, r]['view_bps'] for r in range(1, 4)] for c in subset]) for a in ARMS}
            for a, b in CONTRASTS:
                views.append({'slice': label, 'a': a, 'b': b, **view_contrast(arm[a], arm[b])})
    for date in manifest['dates']:
        for group in ['core', 'holdout']:
            subset = [c for c in cases if c['date'] == date and c['group'] == group]
            names = universe[group]
            cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
            prior = compute_prior(cov, np.ones(50) / 50, 2.5)
            historical = {c['case_id']: json.loads((ROOT / c['source_view']).read_text())['view'] for c in subset}
            neutral_cases = [{**c, 'sentiment': 'neutral'} for c in subset]
            reference, accepted = previous_allocate(neutral_cases, historical, names, cov, prior)
            tested, selected = allocate(subset, historical, names, cov, prior)
            np.testing.assert_allclose(reference, tested, atol=1e-12)
            assert accepted == selected
            maxerror = max(maxerror, float(np.abs(reference - tested).max()))
            for mode in ['end_to_end', 'all_support']:
                arm = {}
                for condition in ARMS:
                    arrays, counts = [], []
                    for repeat in range(1, 4):
                        outputs = historical if args.self_check else {c['case_id']: records[c['case_id'], condition, repeat] for c in subset}
                        w, accepted = allocate(subset, outputs, names, cov, prior, mode == 'all_support')
                        arrays.append(w)
                        counts.append(len(accepted))
                    arm[condition] = np.stack(arrays)
                    weights.append({'date': date, 'group': group, 'mode': mode, 'condition': condition,
                                    'accepted_counts': counts, 'hhi': (arm[condition] ** 2).sum(1).tolist(),
                                    'max_weights': arm[condition].max(1).tolist()})
                for a, b in CONTRASTS:
                    stats = weight_contrast(arm[a], arm[b])
                    if args.self_check:
                        assert stats['mean_vector_distance'] == stats['cross_minus_average_within'] == 0
                    contrasts.append({'date': date, 'group': group, 'mode': mode, 'a': a, 'b': b, **stats})
                targets[date + '_' + group + '_' + mode] = {'tickers': names, 'weights': {a: v.tolist() for a, v in arm.items()}}
    if args.self_check:
        result = {'status': 'PASS', 'neutral_reference_max_error': maxerror, 'synthetic_distance_verified': True, 'identical_inputs_identical_weights': True, 'four_slices_verified': True}
        (RUN / 'analysis_self_check.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        return
    confidence = {a: dict(Counter(records[c['case_id'], a, r]['confidence'] for c in cases for r in range(1, 4))) for a in ARMS}
    result = {'complete_calls': len(records), 'unique_generation_ids': len(set(ids)), 'cases': len(cases), 'cost_usd': cost,
              'confidence': confidence, 'view_contrasts': views, 'weight_contrasts': contrasts, 'weight_summaries': weights,
              'scope': 'Four dependent slices; fixed one-permutation placebo; neutral Omega across arms; descriptive sensitivity, not utility or temporal-validity proof.'}
    for name, obj in [('analysis.json', result), ('targets.json', targets), ('response_hashes.json', hashes)]:
        (RUN / name).write_text(json.dumps(obj, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['complete_calls', 'unique_generation_ids', 'cases', 'cost_usd', 'confidence']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
