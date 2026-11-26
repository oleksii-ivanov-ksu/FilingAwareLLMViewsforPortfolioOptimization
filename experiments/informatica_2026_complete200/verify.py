"""Offline, independent recomputation from archived views and covariance inputs."""
from pathlib import Path
from itertools import combinations
from collections import Counter
import hashlib
import json
import numpy as np

BASE = Path(__file__).resolve().parent


def read(name):
    return json.loads((BASE / name).read_text())


def close(a, b):
    np.testing.assert_allclose(a, b, atol=1e-10, rtol=1e-10)


def weights(cases, outputs, inputs, mode, experiment):
    names = inputs['tickers']; indices = []; q = []; sigma = []
    for c in cases:
        out = outputs[c['case_id']]
        keep = (True if mode == 'all_support' else c['historical_selected'] if mode == 'frozen_support'
                else out['confidence'] == 'medium' and out['view_bps'] > 0)
        if keep:
            indices.append(names.index(c['ticker'])); q.append(out['view_bps']/10000)
            s = .03
            if experiment == 'masking' and c['sentiment'] in ['confident', 'concerned']:
                s *= .8
            sigma.append(s)
    if not indices:
        return np.ones(len(names))/len(names)
    cov = np.array(inputs['covariance']) * .05
    prior = np.array(inputs['prior'])
    p = np.eye(len(names))[indices]
    # Independent precision-space form of the BL update.
    precision = np.linalg.inv(cov)
    omega_inverse = np.diag(1 / np.square(sigma))
    mu = np.linalg.solve(precision + p.T @ omega_inverse @ p, precision @ prior + p.T @ omega_inverse @ q)
    if mu.std() < 1e-10:
        return np.ones(len(names))/len(names)
    w = np.clip((1 + (mu-mu.mean())/mu.std())/len(names), .005, .10)
    return w/w.sum()


def main():
    for name, digest in read('SHA256.json').items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest, name
    manifest = read('manifest.json'); cases = manifest['cases']; inputs = read('allocation_inputs.json')
    assert len(cases) == 200 and len({c['case_id'] for c in cases}) == 200
    for key in inputs:
        subset = [c for c in cases if c['date']+'_'+c['group'] == key]
        assert len(subset) == 50
        assert {c['case_id'] for c in subset} == {c['donor_case_id'] for c in subset}
        assert all(c['case_id'] != c['donor_case_id'] for c in subset)
    for experiment, count in [('content', 1800), ('masking', 1200)]:
        raw = read(experiment + '_records.json')
        assert len(raw) == len({r['generation_id'] for r in raw}) == count
        records = {(r['case_id'], r['condition'], r['repeat']): r for r in raw}
        assert len(records) == count
        targets = read(experiment + '_targets.json'); result = read(experiment + '_analysis.json')
        for key, entry in inputs.items():
            subset = [c for c in cases if c['date']+'_'+c['group'] == key]
            modes = ['end_to_end', 'all_support'] if experiment == 'content' else ['end_to_end', 'frozen_support']
            for mode in modes:
                target = targets[key+'_'+mode]
                arms = target['weights'] if experiment == 'content' else target
                for condition, expected in arms.items():
                    actual = []
                    for repeat in range(1, 4):
                        outputs = {c['case_id']: records[c['case_id'], condition, repeat] for c in subset}
                        actual.append(weights(subset, outputs, entry, mode, experiment))
                    close(actual, expected)
        rows = result['weight_contrasts'] if experiment == 'content' else result['slices']
        for row in rows:
            target = targets[row['date']+'_'+row['group']+'_'+row['mode']]
            arms = target['weights'] if experiment == 'content' else target
            a, b = (np.array(arms[row['a']]), np.array(arms[row['b']])) if experiment == 'content' else (np.array(arms['original']), np.array(arms['anonymized']))
            distance = abs(a.mean(0)-b.mean(0)).sum()/2
            cross = abs(a[:, None, :]-b[None, :, :]).sum(2).mean()/2
            within = [np.mean([abs(x[i]-x[j]).sum()/2 for i,j in combinations(range(3),2)]) for x in [a,b]]
            close(distance, row['mean_vector_distance' if experiment == 'content' else 'mean_vector_one_way_distance'])
            close(cross-np.mean(within), row['cross_minus_average_within'])
        if experiment == 'content':
            for arm, counts in result['confidence'].items():
                assert dict(Counter(r['confidence'] for r in raw if r['condition'] == arm)) == counts
            for row in result['view_contrasts']:
                subset = [c for c in cases if row['slice'] == 'all' or c['date']+'_'+c['group'] == row['slice']]
                a,b = [np.array([[records[c['case_id'],arm,r]['view_bps'] for r in range(1,4)] for c in subset]) for arm in [row['a'],row['b']]]
                close(abs(a.mean(1)-b.mean(1)).mean(), row['mean_absolute_mean_difference_bps'])
                close((a.mean(1)-b.mean(1)).mean(), row['signed_a_minus_b_bps'])
                within = [np.mean([abs(x[:,i]-x[:,j]) for i,j in combinations(range(3),2)]) for x in [a,b]]
                close(abs(a[:,:,None]-b[:,None,:]).mean()-np.mean(within), row['cross_minus_average_within_bps'])
                assert int((np.sign(a.mean(1)) != np.sign(b.mean(1))).sum()) == row['sign_category_changes']
                assert int((a.mean(1)*b.mean(1)<0).sum()) == row['strict_sign_reversals']
    new = [json.loads(p.read_text()) for p in (BASE/'responses').glob('*.json')]
    assert len(new) == 19 and all(r['valid'] and not r['fatal'] for r in new)
    close(sum(r['cost'] for r in new), read('validation.json')['repair_cost_usd'])
    assert sum(r['cost'] for r in new) <= .20
    print('PASS: hashes, 200 cases, 3,000 active responses, independent BL weight reconstruction, contrasts, confidence counts, 19-call repair cost.')


if __name__ == '__main__':
    main()
