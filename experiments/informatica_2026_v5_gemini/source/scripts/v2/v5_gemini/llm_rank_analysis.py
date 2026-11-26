"""Does the filing text change the ORDER of companies by view? (V5 review, section 5.2)

Spearman rank correlation of mean views (three repeats) between the own-text condition and
the no-text / other-company-text conditions, per date and group, next to the rank correlation
between repeated answers to the same prompt. Offline; saved responses only.
"""
from pathlib import Path
from itertools import combinations
import json
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
SETS = [('llm_inputs_v1', '_gemini25flash_v1'), ('llm_inputs_extra_dates_v1', '_gemini25flash_extra_dates_v1')]


def rho(a, b):
    return float(spearmanr(a, b).correlation)


def main():
    rows = []
    for prep, suffix in SETS:
        manifest = json.loads((BASE / prep / 'manifest.json').read_text()); rec = {}
        for p in sorted((BASE / f'ablation{suffix}').glob('[0-9][0-9][0-9][0-9]_*.json')):
            r = json.loads(p.read_text()); j = r['job']
            rec[j['case_id'], j['condition'], j['repeat']] = r['parsed']['view_bps']
        for date in manifest['dates']:
            for group in ['core', 'holdout']:
                cases = [c['case_id'] for c in manifest['cases'] if c['date'] == date and c['group'] == group]
                v = {a: np.array([[rec[c, a, r] for r in (1, 2, 3)] for c in cases], dtype=float) for a in ['real_text', 'no_text', 'shuffled_text']}
                m = {a: x.mean(1) for a, x in v.items()}
                within = np.mean([rho(v['real_text'][:, i], v['real_text'][:, j]) for i, j in combinations(range(3), 2)])
                top = lambda x: set(np.argsort(-x)[:max(1, len(x) // 5)])
                rows.append(dict(date=date, group=group, n=len(cases),
                                 rho_real_vs_no_text=rho(m['real_text'], m['no_text']),
                                 rho_real_vs_other_text=rho(m['real_text'], m['shuffled_text']),
                                 rho_between_repeats=float(within),
                                 top_quintile_kept_no_text=len(top(m['real_text']) & top(m['no_text'])) / len(top(m['real_text'])),
                                 top_quintile_kept_other_text=len(top(m['real_text']) & top(m['shuffled_text'])) / len(top(m['real_text']))))
    keys = [k for k in rows[0] if k not in ('date', 'group', 'n')]
    summary = {k: dict(mean=float(np.mean([r[k] for r in rows])), min=float(np.min([r[k] for r in rows])), max=float(np.max([r[k] for r in rows]))) for k in keys}
    (BASE / 'llm_rank_analysis.json').write_text(json.dumps(dict(slices=rows, summary=summary), indent=2) + '\n')
    for r in rows:
        print(r['date'], r['group'], {k: round(r[k], 3) for k in keys}, flush=True)
    print(json.dumps({k: {m: round(x, 3) for m, x in v.items()} for k, v in summary.items()}), flush=True)


if __name__ == '__main__':
    main()
