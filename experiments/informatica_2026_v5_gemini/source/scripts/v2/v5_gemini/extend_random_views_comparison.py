"""Author-requested eight-contrast extension; no frozen inputs are modified."""
from pathlib import Path
import json
import hashlib
import shutil
import numpy as np
import pandas as pd
from scipy.stats import norm
import audit_informatica_publication as audit
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1])); sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import reanalyze_informatica_returns as paired

ROOT = Path(__file__).resolve().parents[3]
OUT = audit.BASE / 'random_views_comparison_v1'

def main():
    if OUT.exists():
        raise SystemExit('Refusing to overwrite completed extension')
    OUT.mkdir(parents=True)
    factors = audit.read(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv')
    pairs = [(paired.NAMES[a], paired.NAMES[b]) for a,b,_ in paired.CONTRASTS]
    pairs.append(('bl_llm_tilt_pos','random_views'))
    rows = []
    for gi,group in enumerate(['core','holdout']):
        raw = audit.read(ROOT/'data/v2/analysis/informatica_v5_gemini/results'/group/'daily_returns.csv')[paired.NAMES]
        rf = factors.RF.reindex(raw.index)
        assert rf.notna().all()
        for wi,start in enumerate([raw.index[0],pd.Timestamp('2007-04-27')]):
            fr = raw.loc[start:]
            rows.extend(audit.comparisons(fr,rf.reindex(fr.index),pairs,group,
                         ['full','common'][wi],20261116+gi*1000+wi*100))
        print(group,'complete',flush=True)
    result = pd.DataFrame(rows).drop(columns='mde_80_bonferroni6')
    result['mde_80_bonferroni8'] = (norm.ppf(1-.05/16)+norm.ppf(.8))*result.bootstrap_se
    for window in ['full','common']:
        for block in [5,21,63]:
            ix = (result.window==window)&(result.block==block)
            assert ix.sum()==8
            result.loc[ix,'p_holm'] = paired.holm(result.loc[ix,'p_raw'].to_numpy())
    old = pd.read_csv(audit.OUT/'comparisons.csv')
    keys = ['group','window','block','a','b']
    joined = result.merge(old,on=keys,suffixes=('_new','_old'))
    assert len(joined)==36
    checks = ['difference','low','high','bootstrap_se','p_raw','annualized_mean_difference']
    for col in checks:
        assert np.allclose(joined[col+'_new'],joined[col+'_old'],rtol=1e-10,atol=1e-12),col
    result.to_csv(OUT/'comparisons.csv',index=False)
    primary = result[(result.window=='full')&(result.block==21)].copy()
    primary.to_csv(OUT/'primary_table.csv',index=False)
    for path,digest in audit.SOURCES.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    (OUT/'source_hashes.json').write_text(json.dumps(audit.SOURCES,indent=2))
    (OUT/'validation.json').write_text(json.dumps({'existing_rows_reproduced':36,
        'family_size':8,'draws':10000,'input_hashes_unchanged':True,
        'pointwise_intervals':True,'new_model_calls':0},indent=2))
    shutil.copy2(__file__,OUT/'run_snapshot.py')
    shutil.copy2(ROOT/'docs/informatica/RANDOM_VIEWS_COMPARISON_PROTOCOL.md',OUT/'protocol.md')
    plot(primary)
    print(primary[['group','a','b','difference','low','high','annualized_mean_difference','p_raw','p_holm']].to_string(index=False),flush=True)

def plot(frame):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','pdf.fonttype':42})
    labels={'bl_llm_tilt_pos':'BL-Filing+','bl_llm_tilt':'BL-Filing',
            'equal_weight':'EW','mvo':'MVO','bl_llm':'BL-Filing MVO','random_views':'Random Views'}
    fig,ax=plt.subplots(figsize=(6.7,4.4))
    for i,row in enumerate(frame.itertuples()):
        ax.errorbar(row.difference,7-i,xerr=[[row.difference-row.low],[row.high-row.difference]],
                    fmt='o' if row.group=='core' else 's',color='#265b86' if row.group=='core' else '#b04a19',
                    capsize=4,markersize=6,lw=1.7)
    ax.set_yticks(range(8),list(reversed([f'{r.group.title()}: {labels[r.a]} − {labels[r.b]}' for r in frame.itertuples()])),fontsize=9)
    ax.axvline(0,color='.45',ls='--',lw=1)
    ax.grid(axis='x',alpha=.2); ax.set_axisbelow(True)
    ax.set_xlabel('Sharpe difference (realized daily RF)',fontsize=10)
    ax.set_ylim(-.6,7.6)
    fig.tight_layout()
    for ext in ['png','svg','pdf']:
        fig.savefig(OUT/f'fig3_intervals_eight.{ext}',dpi=300,facecolor='white')
    plt.close(fig)

if __name__=='__main__':
    main()
