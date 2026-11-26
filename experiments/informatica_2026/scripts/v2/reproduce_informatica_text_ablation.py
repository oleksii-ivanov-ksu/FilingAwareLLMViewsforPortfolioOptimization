"""Portable reproduction from minimal response records and saved weights."""
from pathlib import Path
from itertools import combinations
from collections import Counter
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'data/v2/analysis/informatica_revision/text_ablation_grok43_v1'


def close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)


def main():
    minimal = json.loads((RUN / 'minimal_records.json').read_text())
    expected = json.loads((RUN / 'analysis.json').read_text())
    records = {(r['case_id'], r['condition'], r['repeat']): r for r in minimal['records']}
    assert len(records) == len(minimal['records']) == expected['complete_calls'] == 1791
    close(sum(r['cost'] for r in records.values()), expected['cost_usd'])
    for arm, counts in expected['confidence'].items():
        assert dict(Counter(r['confidence'] for r in records.values() if r['condition'] == arm)) == counts
    for c in expected['view_contrasts']:
        cases = [r for r in minimal['cases'] if c['slice'] == 'all' or r['date'] + '_' + r['group'] == c['slice']]
        a, b = [np.array([[records[r['case_id'], arm, i]['view_bps'] for i in range(1, 4)] for r in cases]) for arm in [c['a'], c['b']]]
        ma, mb = a.mean(1), b.mean(1)
        within = [np.mean([abs(w[:, i] - w[:, j]) for i, j in combinations(range(3), 2)]) for w in [a, b]]
        cross = abs(a[:, :, None] - b[:, None, :]).mean()
        close([ma.mean(), mb.mean(), (ma-mb).mean(), abs(ma-mb).mean(), *within, cross, cross-np.mean(within)],
              [c[k] for k in ['mean_a_bps','mean_b_bps','signed_a_minus_b_bps','mean_absolute_mean_difference_bps','within_a_bps','within_b_bps','cross_bps','cross_minus_average_within_bps']])
        assert int((np.sign(ma) != np.sign(mb)).sum()) == c['sign_category_changes']
        assert int((ma * mb < 0).sum()) == c['strict_sign_reversals']
    targets = json.loads((RUN / 'targets.json').read_text())
    for c in expected['weight_contrasts']:
        target = targets[c['date']+'_'+c['group']+'_'+c['mode']]['weights']
        a, b = np.array(target[c['a']]), np.array(target[c['b']])
        wa, wb = [[abs(w[i]-w[j]).sum()/2 for i,j in combinations(range(3),2)] for w in [a,b]]
        cross = abs(a[:,None,:]-b[None,:,:]).sum(2)/2
        close(abs(a.mean(0)-b.mean(0)).sum()/2, c['mean_vector_distance'])
        close(wa,c['within_a']);close(wb,c['within_b']);close(cross,c['cross_pairs'])
        close(cross.mean()-(np.mean(wa)+np.mean(wb))/2,c['cross_minus_average_within'])
    for c in expected['weight_summaries']:
        target = np.array(targets[c['date']+'_'+c['group']+'_'+c['mode']]['weights'][c['condition']])
        close((target*target).sum(1),c['hhi']);close(target.max(1),c['max_weights'])
        cases = [r for r in minimal['cases'] if r['date']==c['date'] and r['group']==c['group']]
        for repeat in range(1,4):
            outputs=[records[r['case_id'],c['condition'],repeat] for r in cases]
            count=len(outputs) if c['mode']=='all_support' else sum(r['confidence']=='medium' and r['view_bps']>0 for r in outputs)
            assert count==c['accepted_counts'][repeat-1]
    lines=['| Slice | No summaries % | Shuffled summaries % |','|---|---:|---:|']
    for date in ['2015-09-30','2025-09-30']:
        for group in ['core','holdout']:
            rows=[r for r in expected['weight_contrasts'] if r['mode']=='end_to_end' and r['a']=='real_text' and r['date']==date and r['group']==group]
            values={r['b']:100*r['mean_vector_distance'] for r in rows}
            lines.append(f"| {group.capitalize()} {date[:4]} | {values['no_text']:.2f} | {values['shuffled_text']:.2f} |")
    (ROOT/'paper/informatica/tables/text_ablation.md').write_text('\n'.join(lines)+'\n')
    print('PASS: 1791 minimal responses, 15 view contrasts, 24 weight contrasts, confidence/selection summaries and Table 5.',flush=True)


if __name__=='__main__':
    main()
