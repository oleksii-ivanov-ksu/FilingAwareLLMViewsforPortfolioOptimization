"""Analyze frozen paired pilot, counting documents rather than calls."""
import json
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/v2/analysis/informatica_revision/grok43_replication_v1'

def main():
    files = sorted(OUT.glob('[0-9][0-9][0-9]_*.json'))
    records = [json.loads(p.read_text()) for p in files if '.attempt' not in p.name]
    grouped = defaultdict(lambda: defaultdict(list))
    confidence = defaultdict(Counter)
    invalid = []
    for r in records:
        job = r['job']
        if r.get('valid'):
            grouped[job['case_id']][job['condition']].append(r['parsed']['view_bps'])
            confidence[job['condition']][r['parsed']['confidence']] += 1
        else:
            invalid.append(job)
    rows = []
    for cid in sorted(grouped):
        g = grouped[cid]
        if len(g['original']) != 3 or len(g['anonymized']) != 3:
            continue
        a, b = np.array(g['original']), np.array(g['anonymized'])
        wa = np.mean([abs(x-y) for x,y in combinations(a,2)])
        wb = np.mean([abs(x-y) for x,y in combinations(b,2)])
        cross = np.abs(a[:,None]-b).mean()
        d = b.mean()-a.mean()
        rows.append({'case_id':cid, 'original_mean':float(a.mean()), 'anonymized_mean':float(b.mean()),
                     'signed_change':float(d), 'absolute_change':float(abs(d)),
                     'sign_changed':int(np.sign(a.mean()) != np.sign(b.mean())),
                     'original_repeat_distance':float(wa), 'anonymized_repeat_distance':float(wb),
                     'cross_distance':float(cross), 'cross_minus_within':float(cross-(wa+wb)/2)})
    metrics = {}
    if rows:
        rng = np.random.default_rng(20261116)
        indices = rng.integers(0,len(rows),size=(10000,len(rows)))
        for k in ('signed_change','absolute_change','sign_changed','original_repeat_distance',
                  'anonymized_repeat_distance','cross_distance','cross_minus_within'):
            v = np.array([r[k] for r in rows])
            metrics[k] = {'mean':float(v.mean()),'ci95':np.quantile(v[indices].mean(axis=1),[.025,.975]).tolist()}
        rho = spearmanr([r['original_mean'] for r in rows],[r['anonymized_mean'] for r in rows]).statistic
        metrics['spearman'] = float(rho) if np.isfinite(rho) else None
    result = {'completed_jobs':len(records),'planned_jobs':300,'complete_run':len(records)==300,
              'valid_jobs':sum(bool(r.get('valid')) for r in records), 'complete_cases':len(rows),
              'missing_or_incomplete_cases':50-len(rows),'invalid_jobs':invalid,
              'reported_cost_usd':sum(r.get('cost',0) for r in records),
              'confidence_counts_all_valid_calls':dict(confidence), 'metrics':metrics,'cases':rows,
              'interpretation':'Diagnostic sample; current-model replication; not proof against temporal leakage.'}
    (OUT/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','invalid_jobs')},indent=2))

if __name__ == '__main__':
    main()
