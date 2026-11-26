"""Offline publication audit. Frozen input series are never modified."""
from pathlib import Path
import json
import hashlib
import shutil
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1])); sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import reanalyze_informatica_returns as paired

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
OUT = BASE / 'publication_audit_v1'
SIGNAL = BASE / 'signal_risk_v1'
paired.RF = 0.0  # This audit passes excess returns, including the sampled RF.
SOURCES = {}

def read(path):
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path, index_col=0, parse_dates=True).loc[:'2025-12-31']

def metrics(r, rf):
    e = r.sub(rf, axis=0)
    wealth = (1+r).cumprod()
    peak = wealth.cummax().clip(lower=1)
    return pd.DataFrame({'cagr':wealth.iloc[-1]**(252/len(r))-1,
        'volatility':r.std()*np.sqrt(252), 'sharpe':e.mean()/e.std()*np.sqrt(252),
        'fixed_2pct_sharpe':(r.mean()-(1.02**(1/252)-1))/r.std()*np.sqrt(252),
        'max_drawdown':(wealth/peak-1).min()})

def comparisons(frame, rf, pairs, group, window, seed):
    e=frame.sub(rf, axis=0)
    result=[]
    for length in [5,21,63]:
        boot=paired.block_sharpes(e.to_numpy(),length,10000,seed+length)
        for a,b in pairs:
            ia,ib=frame.columns.get_loc(a),frame.columns.get_loc(b)
            diff=boot[:,ia]-boot[:,ib]
            se=float(diff.std(ddof=1))
            ci=np.quantile(diff,[.025,.975])
            result.append(dict(group=group,window=window,block=length,a=a,b=b,
                difference=float(np.sqrt(252)*(e[a].mean()/e[a].std()-e[b].mean()/e[b].std())),
                low=float(ci[0]),high=float(ci[1]),bootstrap_se=se,
                mde_80=(norm.ppf(.975)+norm.ppf(.8))*se,
                mde_80_bonferroni6=(norm.ppf(1-.05/12)+norm.ppf(.8))*se,
                **paired.hac_mean((frame[a]-frame[b]).to_numpy(),length)))
    return result

def dsr(frame, rf, group):
    unique=[]
    for name in frame:
        if not any(np.allclose(frame[name],frame[other],rtol=0,atol=1e-12) for other in unique):
            unique.append(name)
    e=frame[unique].sub(rf,axis=0)
    scores=e.mean()/e.std()
    dispersion=float(scores.std(ddof=1))
    x=e['bl_llm_tilt_pos'].to_numpy(); n=len(x)
    mu=x.mean(); sd=x.std(ddof=1); sr=mu/sd
    s=float(skew(x,bias=False)); k=float(kurtosis(x,fisher=False,bias=False))
    se=np.sqrt((1-s*sr+(k-1)*sr**2/4)/(n-1))
    influence=(x-mu)/sd-mu*((x-mu)**2-sd**2)/(2*sd**3)
    hac_se=paired.hac_mean(influence,21)['se_annualized']/252
    rows=[]
    for trials in [1,6,24,42,100]:
        threshold=0 if trials==1 else dispersion*((1-np.euler_gamma)*norm.ppf(1-1/trials)+np.euler_gamma*norm.ppf(1-1/(trials*np.e)))
        rows.append(dict(group=group,assumed_effective_trials=trials,observed_candidates=len(frame.columns),
            unique_candidates=len(unique),daily_sr=sr,annualized_threshold=threshold*np.sqrt(252),
            daily_candidate_sr_sd=dispersion,skewness=s,pearson_kurtosis=k,
            moment_se=se,hac_se=hac_se,dsr=float(norm.cdf((sr-threshold)/se)),
            hac_probability=float(norm.cdf((sr-threshold)/hac_se))))
    return rows,unique

def main():
    if OUT.exists(): raise SystemExit('Refusing to overwrite publication audit')
    OUT.mkdir(parents=True)
    factors=read(ROOT/'data/v2/analysis/csit_cost_audit/factors.csv')
    allmetrics=[]; uncertainty=[]; costs=[]; dsrs=[]; checks={}; gridmetrics=[]
    for gi,group in enumerate(['core','holdout']):
        raw=read(ROOT/'data/v2/analysis/informatica_v5_gemini/results'/group/'daily_returns.csv')[paired.NAMES]
        rf=factors.RF.reindex(raw.index); assert rf.notna().all()
        original=metrics(raw,rf); original['group']=group; original['family']='original'
        allmetrics.append(original.rename_axis('strategy').reset_index())
        for wi,start in enumerate([raw.index[0],pd.Timestamp('2007-04-27')]):
            fr=raw.loc[start:]
            uncertainty.extend(comparisons(fr,rf.reindex(fr.index),[(paired.NAMES[a],paired.NAMES[b]) for a,b,_ in paired.CONTRASTS],group,['full','common'][wi],20261116+gi*1000+wi*100))
            cm=metrics(fr,rf.reindex(fr.index)); cm['group']=group; cm['family']=['full','common'][wi]
            cm.rename_axis('strategy').to_csv(OUT/f'{group}_{["full","common"][wi]}_metrics.csv')
        extra=read(SIGNAL/f'{group}_daily_returns.csv')
        assert extra.index.equals(raw.index)
        assert np.max(np.abs(extra.real-raw.bl_llm_tilt_pos))<1e-12
        em=metrics(extra,rf); em['group']=group; em['family']='diagnostic'
        allmetrics.append(em.rename_axis('strategy').reset_index())
        matched=read(BASE/'matched_controls_v1'/f'{group}_daily_returns.csv')
        assert matched.index.equals(raw.index)
        mm=metrics(matched,rf); mm.rename_axis('strategy').to_csv(OUT/f'{group}_matched_metrics.csv')
        tests=extra.copy()
        for scheme in ['full_shuffle','eligible_shuffle']:
            tests[scheme+'_mean']=matched.filter(like=scheme).mean(axis=1)
        uncertainty.extend(comparisons(tests,rf,[('real',b) for b in ['equal_weight','prior_only','volatility_tilt','full_shuffle_mean','eligible_shuffle_mean']],group,'diagnostic',20262116+gi*100))
        turn=read(SIGNAL/f'{group}_turnover.csv')
        targetpath=SIGNAL/f'{group}_targets.npz'
        SOURCES[str(targetpath.relative_to(ROOT))]=hashlib.sha256(targetpath.read_bytes()).hexdigest()
        target=np.load(targetpath); dates=pd.to_datetime(target['dates']); arms=list(target['arms'])
        charge=pd.DataFrame(0.,index=extra.index,columns=extra.columns)
        executed=[]
        for i,date in enumerate(dates):
            end=dates[i+1] if i+1<len(dates) else pd.Timestamp('2025-12-31')
            interval=extra.index[(extra.index>date)&(extra.index<=end)]
            if len(interval):
                charge.loc[interval[0]]=turn.loc[date]
                executed.append(i)
        assert not charge.index.duplicated().any()
        charge.to_csv(OUT/f'{group}_charged_turnover.csv')
        for bp in [5,10,20]:
            net=extra+(.001-bp/10000)*charge
            if bp==10: assert np.array_equal(net.to_numpy(),extra.to_numpy())
            met=metrics(net,rf)
            for name,row in met.iterrows():
                ai=arms.index(name)
                costs.append(dict(group=group,strategy=name,cost_bps=bp,
                    annual_l1_turnover=float(charge[name].sum()/(len(extra)/252)),
                    annual_oneway_turnover=float(charge[name].sum()/(len(extra)/252)/2),
                    mean_effective_holdings=float(np.mean(1/(target['weights'][executed,ai,:]**2).sum(axis=1))),
                    executed_rebalances=len(executed),**row.to_dict()))
        unique=list(raw.columns)  # v5 gemini: the v1 sensitivity grid and DSR are not recomputed
        checks[group]={'days':len(raw),'unique_candidate_names':unique,'executed_rebalances':len(executed),
            'rf_missing':int(rf.isna().sum()),'10bp_identity':True}
        raw.to_csv(OUT/f'{group}_original_returns.csv')
        print(group,'complete',flush=True)
    pd.concat(allmetrics).to_csv(OUT/'metrics.csv',index=False)
    unc=pd.DataFrame(uncertainty)
    for window in ['full','common']:
        for length in [5,21,63]:
            keep=(unc.window==window)&(unc.block==length)
            unc.loc[keep,'p_holm']=paired.holm(unc.loc[keep,'p_raw'].to_numpy())
    unc.to_csv(OUT/'comparisons.csv',index=False)
    pd.DataFrame(costs).to_csv(OUT/'costs.csv',index=False)
    (OUT/'validation.json').write_text(json.dumps(checks,indent=2))
    (OUT/'source_hashes.json').write_text(json.dumps(SOURCES,indent=2))
    for path,digest in SOURCES.items(): assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    shutil.copy2(__file__,OUT/'run_snapshot.py')
    shutil.copy2(ROOT/'docs/informatica/PUBLICATION_AUDIT_PROTOCOL.md',OUT/'protocol.md')
    print('PASS: inputs unchanged, dates aligned, 10bp paths identical.',flush=True)

if __name__=='__main__': main()
