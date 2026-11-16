"""Recheck all saved sensitivity series without rerunning portfolio simulation."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'data/v2/analysis/dissertation_revision_20260914/portfolio_v1_sensitivity'
OUT = ROOT/'data/v2/analysis/informatica_revision/sensitivity_audit'


def main():
    OUT.mkdir(exist_ok=True)
    daily = pd.read_csv(SOURCE/'daily_returns.csv', index_col=0)
    summary = pd.read_csv(SOURCE/'summary.csv')
    rows = []
    for record in summary.to_dict('records'):
        x = daily[record['id']].dropna()
        cagr = np.expm1(np.log1p(x).mean()*252)
        sharpe = np.sqrt(252)*(x.mean()-np.expm1(np.log1p(.02)/252))/x.std(ddof=1)
        assert abs(sharpe-record['arithmetic_sharpe']) < 1e-10
        assert abs(cagr-record['cagr']) < 1e-10
        record['recomputed_sharpe'] = float(sharpe)
        record['recomputed_cagr'] = float(cagr)
        rows.append(record)
    result = pd.DataFrame(rows)
    match = {}
    for group in ['core', 'holdout']:
        original = pd.read_csv(ROOT/f'data/results/{group}/daily_returns.csv',index_col=0)
        x = daily[f'v1_{group}_legacy_tilt1.0_legacy'].dropna()
        error = float((x-original['bl_llm_tilt_pos'].reindex(x.index)).abs().max())
        assert error < 1e-10
        match[group] = error
    pivot = result.pivot(index=['group','mode','tilt'],columns='allocation',values='recomputed_sharpe')
    validation = {'configurations':len(result),'max_daily_difference_from_frozen':match,
        'max_sharpe_change_projection':float((pivot.projected-pivot.legacy).abs().max()),
        'max_sharpe_change_rounding':float((pivot.rounded-pivot.projected).abs().max()),
        'projected_violations':int(result.query("allocation == 'projected'").violating_rebalances.sum()),
        'rounded_violations':int(result.query("allocation == 'rounded'").violating_rebalances.sum()),
        'source_hashes':{f:hashlib.sha256((SOURCE/f).read_bytes()).hexdigest() for f in ['summary.csv','daily_returns.csv','manifest.json']},
        'supersedes':'Numerical claims in POINT2_V1_RESULT.md and old validation.json must not substitute for this direct CSV audit.'}
    result.to_csv(OUT/'all_36_scenarios.csv',index=False)
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    text='| Sample | Scale Q / Ω | Sharpe | CAGR % |\n|---|---|---|---|\n'
    for r in result.query("tilt == 1 and allocation == 'legacy'").to_dict('records'):
        mode={'legacy':'1 / 1','q_x4_only':'4 / 1','q_x4_omega_x16':'4 / 16'}[r['mode']]
        text+=f"| {r['group'].title()} | {mode} | {r['recomputed_sharpe']:.3f} | {r['recomputed_cagr']*100:.2f} |\n"
    (ROOT/'paper/informatica/tables/sensitivity.md').write_text(text)
    print(json.dumps(validation,indent=2),flush=True)


if __name__ == '__main__':
    main()
