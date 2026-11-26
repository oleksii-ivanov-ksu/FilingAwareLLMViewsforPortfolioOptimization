"""Standalone verifier for the GitHub publication-audit package."""
from pathlib import Path
import sys
import json
import hashlib
import numpy as np
import pandas as pd

P = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
sys.path.insert(0,str(P))
import analysis_source as audit

def read(name):
    return pd.read_csv(P/name,index_col=0,parse_dates=True)

def close(actual, expected):
    np.testing.assert_allclose(actual,expected,rtol=2e-9,atol=2e-11,equal_nan=True)

manifest=json.loads((P/'SHA256.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((P/name).read_bytes()).hexdigest()==digest,name
rf=read('risk_free.csv').RF
saved=pd.read_csv(P/'results/metrics.csv')
costs=pd.read_csv(P/'results/costs.csv')
saved_dsr=pd.read_csv(P/'results/dsr.csv')
saved_unc=pd.read_csv(P/'results/comparisons.csv')
for gi,g in enumerate(['core','holdout']):
    raw=read(f'results/{g}_original_returns.csv')
    extra=read(f'{g}_daily_returns.csv')
    rate=rf.reindex(raw.index);assert rate.notna().all()
    for family,frame in [('original',raw),('diagnostic',extra)]:
        actual=audit.metrics(frame,rate)
        expected=saved[(saved.group==g)&(saved.family==family)].set_index('strategy')
        close(actual.to_numpy(),expected.loc[actual.index,actual.columns].to_numpy())
    charges=read(f'results/{g}_charged_turnover.csv')
    z=np.load(P/f'{g}_targets.npz');dates=pd.to_datetime(z['dates'])
    executed=[i for i,d in enumerate(dates) if np.any((extra.index>d)&(extra.index<=(dates[i+1] if i+1<len(dates) else pd.Timestamp('2025-12-31'))))]
    for bp in [5,10,20]:
        actual=audit.metrics(extra+(.001-bp/10000)*charges,rate)
        expected=costs[(costs.group==g)&(costs.cost_bps==bp)].set_index('strategy')
        close(actual.to_numpy(),expected.loc[actual.index,actual.columns].to_numpy())
        close(charges.sum()/(len(extra)/252),expected.loc[extra.columns,'annual_l1_turnover'])
        close(np.mean(1/(z['weights'][executed]**2).sum(axis=2),axis=0),expected.loc[list(z['arms']),'mean_effective_holdings'])
    candidates=pd.concat([raw,read(f'results/{g}_candidate_returns.csv')],axis=1)
    actual,_=audit.dsr(candidates,rate,g);actual=pd.DataFrame(actual).drop(columns='group')
    close(actual,saved_dsr[saved_dsr.group==g][actual.columns])
    for wi,start in enumerate([raw.index[0],pd.Timestamp('2007-04-27')]):
        frame=raw.loc[start:];window=['full','common'][wi]
        actual=pd.DataFrame(audit.comparisons(frame,rate.reindex(frame.index),[(audit.paired.NAMES[a],audit.paired.NAMES[b]) for a,b,_ in audit.paired.CONTRASTS],g,window,20261116+gi*1000+wi*100))
        cols=actual.select_dtypes(include=np.number).columns
        close(actual[cols],saved_unc[(saved_unc.group==g)&(saved_unc.window==window)][cols])
    matched=read(f'{g}_matched_returns.csv.gz')
    expected_matched=read(f'results/{g}_matched_metrics.csv')
    actual_matched=audit.metrics(matched,rate)
    close(actual_matched.to_numpy(),expected_matched.loc[actual_matched.index,actual_matched.columns].to_numpy())
    ensemble=read(f'{g}_ensemble_returns.csv')
    for scheme in ['full_shuffle','eligible_shuffle']:
        close(matched.filter(like=scheme).mean(axis=1),ensemble[scheme+'_mean'])
    frame=pd.concat([extra,ensemble],axis=1)
    actual=pd.DataFrame(audit.comparisons(frame,rate,[('real',b) for b in ['equal_weight','prior_only','volatility_tilt','full_shuffle_mean','eligible_shuffle_mean']],g,'diagnostic',20262116+gi*100))
    cols=actual.select_dtypes(include=np.number).columns
    close(actual[cols],saved_unc[(saved_unc.group==g)&(saved_unc.window=='diagnostic')][cols])
    print(g+': metrics, costs, DSR and bootstrap/MDE reproduced',flush=True)
print(f'PASS: {len(manifest)} hashes; all publication-audit calculations reproduced offline.',flush=True)
