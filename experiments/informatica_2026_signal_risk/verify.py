"""Verify the shareable signal/risk archive without raw prices or API calls."""
from pathlib import Path
import json, hashlib, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm


def main():
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    manifest=json.loads((root/'SHA256.json').read_text())
    for name,digest in manifest.items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    d=root/'results'; summary=pd.read_csv(d/'performance.csv')
    factors=pd.read_csv(root/'factors.csv',index_col=0,parse_dates=True)
    regs=pd.read_csv(d/'factor_regressions.csv'); max_error=0.; rf=np.expm1(np.log1p(.02)/252)
    for group in ['core','holdout']:
        frame=pd.read_csv(d/f'{group}_daily_returns.csv',index_col=0,parse_dates=True)
        for arm in frame:
            x=frame[arm].to_numpy();wealth=np.cumprod(1+x);peak=np.maximum.accumulate(np.r_[1,wealth])[1:]
            values=[wealth[-1]**(252/len(x))-1,np.std(x,ddof=1)*np.sqrt(252),np.sqrt(252)*(x.mean()-rf)/x.std(ddof=1),np.min(wealth/peak-1)]
            saved=summary.loc[(summary.group==group)&(summary.arm==arm),['cagr','volatility','sharpe','max_drawdown']].iloc[0].to_numpy()
            np.testing.assert_allclose(values,saved,atol=1e-12)
        panel=pd.read_csv(d/f'{group}_signal_panel.csv'); bydate=pd.read_csv(d/f'{group}_signal_by_date.csv')
        for (date,conf),row in bydate.set_index(['date','confidence']).iterrows():
            a=panel.loc[panel.date==date]
            if conf!='all':a=a.loc[a.confidence==conf]
            if pd.notna(row.ic):
                actual=a.view_bps.rank().corr(a.outcome.rank());max_error=max(max_error,abs(actual-row.ic))
                assert abs(actual-row.ic)<1e-12
        accepted=pd.read_csv(d/f'{group}_accepted_views_ic.csv')
        for row in accepted.itertuples():
            a=panel.loc[(panel.date==row.date)&(panel.confidence=='medium')&(panel.view_bps>0)]
            assert len(a)==row.n and len(a)>=10
            assert abs(a.view_bps.rank().corr(a.outcome.rank())-row.ic)<1e-12
        np.testing.assert_allclose(frame.beta_tilt,frame.prior_only,atol=1e-12)
        t=np.load(d/f'{group}_targets.npz');np.testing.assert_allclose(t['weights'][:,1],t['weights'][:,3],atol=1e-12)
        full=pd.read_csv(root/f'{group}_full_shuffle_returns.csv',index_col=0,parse_dates=True)
        ff=frame.copy();ff['full_shuffle_mean']=full.mean(1)
        for arm in ['prior_only','beta_tilt','volatility_tilt','equal_weight','full_shuffle_mean']:ff['difference_'+arm]=ff.real-ff[arm]
        ff=pd.concat([ff,full],axis=1);f=factors.loc[ff.index];assert len(f)==len(ff)
        for row in regs.loc[regs.group==group].itertuples():
            cols=['Mkt-RF','SMB','HML','Mom'] if row.model=='FF3+Mom' else ['Mkt-RF','SMB','HML','RMW','CMA','Mom']
            x=sm.add_constant(f[cols]);y=ff[row.arm] if row.arm.startswith('difference_') else ff[row.arm]-f.RF
            fit=sm.OLS(y,x).fit(cov_type='HAC',cov_kwds={'maxlags':21,'use_correction':True},use_t=False)
            np.testing.assert_allclose([fit.params['const']*252,fit.pvalues['const'],fit.params['Mkt-RF']],[row.alpha_annual,row.alpha_p,row.beta_market],atol=1e-10)
    print(f'PASS: {len(manifest)} hashes; portfolio metrics, all defined ICs, beta/prior identity and {len(regs)} factor regressions. Max IC error {max_error:.3g}.',flush=True)


if __name__=='__main__':main()
