"""Post hoc paired reanalysis; reads frozen v1 returns and writes separate outputs."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import norm

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/v2/analysis/informatica_revision/financial_reanalysis_v1'
NAMES=['bl_llm_tilt_pos','bl_llm_tilt','equal_weight','mvo','random_views','bl_llm']
CONTRASTS=[(0,2,'BL-Filing+ vs EW'),(0,3,'BL-Filing+ vs MVO'),(1,5,'BL-Filing vs BL-Filing MVO')]
RF=1.02**(1/252)-1

def sharpe(x):
    return np.sqrt(252)*(x.mean(axis=0)-RF)/x.std(axis=0,ddof=1)

def metrics(x):
    growth=np.cumprod(1+x,axis=0)
    peak=np.maximum.accumulate(np.vstack([np.ones(x.shape[1]),growth]),axis=0)[1:]
    cagr=growth[-1]**(252/len(x))-1
    vol=x.std(axis=0,ddof=1)*np.sqrt(252)
    return {name:{'cagr':float(cagr[i]),'volatility':float(vol[i]),'sharpe':float(sharpe(x)[i]),
                  'max_drawdown':float((growth/peak-1).min(axis=0)[i]),'total_return':float(growth[-1,i]-1),
                  'legacy_cagr_ratio':float((cagr[i]-.02)/vol[i])} for i,name in enumerate(NAMES)}

def hac_mean(d,lag):
    n=len(d);res=d-d.mean()
    longvar=float(res@res/n)
    for k in range(1,lag+1):
        longvar+=2*(1-k/(lag+1))*float(res[k:]@res[:-k]/n)
    se=np.sqrt(max(0,longvar)/n*n/(n-1))
    z=float(d.mean()/se) if se else 0.0
    return {'annualized_mean_difference':float(d.mean()*252),'se_annualized':float(se*252),
            'z':z,'p_raw':float(2*norm.sf(abs(z)))}

def holm(ps):
    order=np.argsort(ps);out=np.empty(len(ps));running=0
    for rank,i in enumerate(order):
        running=max(running,(len(ps)-rank)*ps[i]);out[i]=min(1,running)
    return out

def block_sharpes(x,length,draws,seed):
    # Sums and squares of circular blocks reproduce explicit resampling exactly.
    n,m=x.shape;full,rem=divmod(n,length)
    extended=np.vstack([x,x[:length]])
    sums=np.vstack([np.zeros(m),np.cumsum(extended,axis=0)])
    squares=np.vstack([np.zeros(m),np.cumsum(extended**2,axis=0)])
    starts=np.arange(n)
    bs=sums[starts+length]-sums[starts];bq=squares[starts+length]-squares[starts]
    rs=sums[starts+rem]-sums[starts];rq=squares[starts+rem]-squares[starts]
    rng=np.random.default_rng(seed);result=[]
    for offset in range(0,draws,200):
        size=min(200,draws-offset)
        indices=rng.integers(n,size=(size,full+(rem>0)))
        total=bs[indices[:,:full]].sum(axis=1);sq=bq[indices[:,:full]].sum(axis=1)
        if rem:
            total+=rs[indices[:,-1]];sq+=rq[indices[:,-1]]
        sd=np.sqrt(np.maximum(0,(sq-total**2/n)/(n-1)))
        result.append(np.sqrt(252)*(total/n-RF)/sd)
    return np.vstack(result)

def main():
    if OUT.exists():raise SystemExit('Refusing to overwrite reanalysis')
    OUT.mkdir(parents=True)
    source={};datasets={}
    for split in ['core','holdout']:
        path=ROOT/'data/results'/split/'daily_returns.csv'
        source[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open() as f:rows=list(csv.DictReader(f))
        dates=np.array([r['date'] for r in rows]);x=np.array([[float(r[k]) for k in NAMES] for r in rows])
        assert len(set(dates))==len(dates) and np.all(dates[:-1]<dates[1:]) and np.isfinite(x).all()
        datasets[split]=(dates,x)
    common=sorted(set(datasets['core'][0]) & set(datasets['holdout'][0]))
    report={'source_sha256':source,'protocol_sha256':hashlib.sha256((ROOT/'docs/informatica/FINANCIAL_REANALYSIS_PROTOCOL.md').read_bytes()).hexdigest(),
            'seed':20261116,'bootstrap_draws':10000,'rf_daily':RF,'contrasts':[c[2] for c in CONTRASTS],'windows':{}}
    for wi,window in enumerate(['through_2025','common_through_2025']):
        result={}
        for si,(split,(dates,raw)) in enumerate(datasets.items()):
            keep=dates<='2025-12-31'
            if wi:keep &= np.isin(dates,common)
            x=raw[keep];dt=dates[keep]
            item={'start':dt[0],'end':dt[-1],'days':len(x),'metrics':metrics(x),'uncertainty':{}}
            for length in [5,21,63]:
                seed=20261116+wi*1000+si*100+length
                boot=block_sharpes(x,length,10000,seed)
                contrasts=[]
                for a,b,label in CONTRASTS:
                    diff=boot[:,a]-boot[:,b]
                    contrasts.append({'contrast':label,'sharpe_difference':float(sharpe(x)[a]-sharpe(x)[b]),
                                      'sharpe_difference_ci95':np.quantile(diff,[.025,.975]).tolist(),
                                      'mean_return_test':hac_mean(x[:,a]-x[:,b],length)})
                item['uncertainty'][str(length)]={'seed':seed,'contrasts':contrasts}
            result[split]=item
            print(window,split,len(x),'complete',flush=True)
        for length in ['5','21','63']:
            tests=[c['mean_return_test'] for split in ['core','holdout'] for c in result[split]['uncertainty'][length]['contrasts']]
            for t,p in zip(tests,holm([t['p_raw'] for t in tests])):t['p_holm_six']=float(p)
        report['windows'][window]=result
    regimes=[('2006–2007','2006-01-01','2007-12-31'),('2008–2009','2008-01-01','2009-12-31'),
             ('2010–2013','2010-01-01','2013-12-31'),('2014–2019','2014-01-01','2019-12-31'),
             ('2020','2020-01-01','2020-12-31'),('2021–2022','2021-01-01','2022-12-31'),('2023–2025','2023-01-01','2025-12-31')]
    dates,x=datasets['core'];report['core_regimes']={}
    for label,start,end in regimes:
        subset=x[(dates>=start)&(dates<=end)]
        report['core_regimes'][label]={'days':len(subset),'metrics':metrics(subset)}
    common_result=report['windows']['common_through_2025']
    report['common_window_degradation']={k:(common_result['core']['metrics'][k]['sharpe']-common_result['holdout']['metrics'][k]['sharpe'])/abs(common_result['core']['metrics'][k]['sharpe']) for k in NAMES}
    (OUT/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (OUT/'protocol.md').write_bytes((ROOT/'docs/informatica/FINANCIAL_REANALYSIS_PROTOCOL.md').read_bytes())
    (OUT/'reanalysis.py').write_bytes(Path(__file__).read_bytes())

if __name__=='__main__':main()
