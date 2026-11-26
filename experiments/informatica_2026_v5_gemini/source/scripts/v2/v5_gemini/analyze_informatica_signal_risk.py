"""Offline, prespecified signal/risk diagnostics for the editorial Informatica V2."""
from pathlib import Path
import sys, json, hashlib, logging, shutil
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr, norm
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_all_prices, load_universe
from src.backtesting import engine
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior, build_view_matrices
from src.optimization.optimizer import tilt_weights
from scripts.v2.portfolio_protocol import posterior
from scripts.v2.reanalyze_informatica_returns import block_sharpes
from scripts.v2.v5_gemini import run_informatica_matched_controls as matched

BASE = ROOT/'data/v2/analysis/informatica_v5_gemini'
OUT = BASE/'signal_risk_v1'
ARMS = ['real', 'prior_only', 'equal_weight', 'beta_tilt', 'volatility_tilt', 'horizon_aligned']
RF = np.expm1(np.log1p(.02)/252)


def metrics(x):
    x = np.asarray(x)
    w = np.cumprod(1+x)
    peak = np.maximum.accumulate(np.r_[1., w])[1:]
    return dict(days=len(x), cagr=float(w[-1]**(252/len(x))-1),
                volatility=float(np.std(x,ddof=1)*np.sqrt(252)),
                sharpe=float(np.sqrt(252)*(x.mean()-RF)/x.std(ddof=1)),
                max_drawdown=float(np.min(w/peak-1)))


def hac_mean(x, lag=4, null=0.):
    x = pd.Series(x).dropna().to_numpy()
    if len(x)<8:
        return dict(n=len(x), mean=float(x.mean()) if len(x) else None, t=None, p=None, ci95=None)
    fit = sm.OLS(x,np.ones((len(x),1))).fit(cov_type='HAC',
          cov_kwds={'maxlags':lag,'use_correction':True},use_t=False)
    stat=float((fit.params[0]-null)/fit.bse[0])
    return dict(n=len(x),mean=float(fit.params[0]),t=stat, null=null,
                p=float(2*norm.sf(abs(stat))),ci95=fit.conf_int()[0].tolist())


def signals(px, views, group, dates):
    panel=[]; rows=[]; exclusions=[]
    for date in dates:
        end=(date.to_period('Q')+1).end_time.normalize()
        if end>pd.Timestamp('2025-12-31'): continue
        start_px=px.loc[:date].iloc[-1]; end_px=px.loc[:end].iloc[-1]
        assert px.loc[:date].index[-1]<=date<px.loc[:end].index[-1]<=end
        fwd=end_px/start_px-1
        available=views.loc[(views.view_date<=date)&views.ticker.isin(px.columns)]
        latest=available.groupby('ticker',sort=False).tail(1)
        latest=latest.loc[(date-latest.view_date).dt.days<=120].copy()
        latest['outcome']=latest.ticker.map(fwd)
        latest['relative_outcome']=latest.outcome-fwd.mean()
        missing=int(latest.outcome.isna().sum());latest=latest.dropna(subset=['outcome'])
        for r in latest.to_dict('records'):
            panel.append(dict(group=group,date=str(date.date()),outcome_end=str(end.date()),
                ticker=r['ticker'],view_date=str(r['view_date'].date()),view_bps=r['view_bps'],
                confidence=r['confidence'],outcome=r['outcome'],relative_outcome=r['relative_outcome']))
        for conf in ['all','low','medium','high']:
            a=latest if conf=='all' else latest.loc[latest.confidence==conf]
            valid=len(a)>=10 and a.view_bps.nunique()>1 and a.outcome.nunique()>1
            nonzero=a.loc[a.view_bps!=0];rank=a.view_bps.rank(method='average',pct=True)
            top=a.loc[rank>=.8];bottom=a.loc[rank<=.2]
            spread=float(top.outcome.mean()-bottom.outcome.mean()) if len(a)>=10 and a.view_bps.nunique()>=5 and len(top) and len(bottom) else np.nan
            rows.append(dict(group=group,date=str(date.date()),confidence=conf,n=len(a),
                ic=float(spearmanr(a.view_bps,a.outcome).statistic) if valid else np.nan,
                spread=spread,hit=float((np.sign(nonzero.view_bps)==np.sign(nonzero.outcome)).mean()) if len(nonzero) else np.nan,
                relative_hit=float((np.sign(nonzero.view_bps)==np.sign(nonzero.relative_outcome)).mean()) if len(nonzero) else np.nan,
                always_positive=float((nonzero.outcome>0).mean()) if len(nonzero) else np.nan,
                nonzero_n=len(nonzero),top_n=len(top),bottom_n=len(bottom),missing_outcomes=missing))
    frame=pd.DataFrame(rows);pd.DataFrame(panel).to_csv(OUT/f'{group}_signal_panel.csv',index=False)
    frame.to_csv(OUT/f'{group}_signal_by_date.csv',index=False)
    return {conf:{key:hac_mean(a[key],null=.5 if key in ['hit','relative_hit','always_positive'] else 0.) for key in ['ic','spread','hit','relative_hit','always_positive']}
            for conf,a in frame.groupby('confidence')}


def regressions(frame,factors,group):
    data=frame.join(factors,how='inner'); assert len(data)==len(frame), 'Missing factor dates'
    records=[]
    for model,cols in [('FF3+Mom',['Mkt-RF','SMB','HML','Mom']),
                       ('FF5+Mom',['Mkt-RF','SMB','HML','RMW','CMA','Mom'])]:
        x=sm.add_constant(data[cols])
        for arm in frame.columns:
            y=data[arm] if arm.startswith('difference_') else data[arm]-data.RF
            fit=sm.OLS(y,x).fit(cov_type='HAC',cov_kwds={'maxlags':21,'use_correction':True},use_t=False)
            ci=fit.conf_int().loc['const']*252
            records.append(dict(group=group,model=model,arm=arm,n=len(y),alpha_annual=fit.params['const']*252,
                alpha_t=fit.tvalues['const'],alpha_p=fit.pvalues['const'],alpha_ci_low=ci.iloc[0],alpha_ci_high=ci.iloc[1],
                beta_market=fit.params['Mkt-RF'],r_squared=fit.rsquared,
                **{f'loading_{c}':fit.params[c] for c in cols}))
    return pd.DataFrame(records)


def main():
    if OUT.exists():raise SystemExit('Refusing overwrite of signal_risk_v1')
    OUT.mkdir(parents=True);logging.disable(logging.CRITICAL)
    protocol=ROOT/'docs/informatica/SIGNAL_RISK_PROTOCOL.md'
    shutil.copy2(protocol,OUT/'protocol.md');shutil.copy2(__file__,OUT/'run_snapshot.py')
    universe=load_universe(str(ROOT/'config/universe.yaml'))
    prices=load_all_prices(ROOT/'data/raw',universe['core']+universe['holdout'])
    views=engine.load_views_summary(ROOT/'data/v2/views_v2/views_summary.csv')
    dates=engine.generate_rebalance_dates(2006,2025,'quarterly')
    factor_path=ROOT/'data/v2/analysis/csit_cost_audit/factors.csv'
    factors=pd.read_csv(factor_path,index_col=0,parse_dates=True)
    paths=[protocol,Path(__file__),factor_path,ROOT/'data/v2/views_v2/views_summary.csv',ROOT/'config/universe.yaml']
    paths += [ROOT/f'data/raw/{t}/prices.csv' for names in universe.values() for t in names]
    paths += [ROOT/f'data/v2/analysis/informatica_v5_gemini/results/{g}/daily_returns.csv' for g in universe]
    paths += list((BASE/'matched_controls_v1').glob('*daily_returns.csv'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report={};reg=[];performance=[];periods=[];audit={}
    for group in ['core','holdout']:
        print('Running',group,flush=True)
        names=universe[group];px=prices[names];n=len(names);targets={};eligibility=[];horizon_error=0.
        signal=signals(px,views,group,dates)
        saved=pd.read_csv(BASE/f'matched_controls_v1/{group}_daily_returns.csv',index_col=0,parse_dates=True)
        for date in dates:
            if len(px.loc[:date])<262 or engine.get_next_trading_day(date,px) is None:continue
            active=engine.get_active_views(views,names,date,120)
            chosen=[v for v in active if v.confidence=='medium' and v.view_bps>0]
            eligibility.append(dict(date=str(date.date()),accepted=len(chosen)))
            try:cov=rolling_covariance(px,date,lookback=252)
            except ValueError as exc:
                if not str(exc).startswith('Not enough observations:'):raise
                targets[date]=None;continue
            prior=compute_prior(cov,np.ones(n)/n,delta=2.5)
            weights=np.full((len(ARMS),n),1/n);weights[1]=tilt_weights(prior)
            window=px.loc[:date].iloc[-253:].pct_change().dropna()
            market=window.mean(axis=1).to_numpy();a=window.to_numpy()
            beta=((a-a.mean(0))*(market-market.mean())[:,None]).sum(0)/np.sum((market-market.mean())**2)
            weights[3]=tilt_weights(beta);weights[4]=tilt_weights(a.std(0,ddof=1))
            if chosen:
                p,q,o=build_view_matrices(chosen,{t:i for i,t in enumerate(names)},n)
                weights[0]=tilt_weights(posterior(cov,prior,p,q,o))
                quarter=posterior(cov/4,prior/4,p,q,o)
                annual=posterior(cov,prior,p,4*q,4*o)
                np.testing.assert_allclose(annual,4*quarter,atol=1e-12)
                weights[5]=tilt_weights(quarter)
                horizon_error=max(horizon_error,float(np.max(np.abs(weights[5]-tilt_weights(annual)))))
            assert np.isfinite(weights).all() and (weights>=0).all()
            np.testing.assert_allclose(weights.sum(1),1,atol=1e-12)
            targets[date]=weights
        previous_arms=matched.ARMS;matched.ARMS=ARMS
        try:frame,wh,costs=matched.replay(px,dates,targets)
        finally:matched.ARMS=previous_arms
        frame=frame.loc[:'2025-12-31'];assert frame.index.equals(saved.index)
        errors={arm:float(np.max(np.abs(frame[arm]-saved[arm]))) for arm in ARMS[:3]}
        assert max(errors.values())<1e-10,errors
        original=engine._compute_strategy_weights
        def callback(**kw):
            w=targets[kw['rebal_date']]
            if w is None:raise ValueError('recorded covariance fallback')
            return w[3]
        engine._compute_strategy_weights=callback
        try:reference=engine.run_backtest(px,views,names,dates,strategy='bl_llm_tilt_pos')['daily_returns'].loc[:'2025-12-31']
        finally:engine._compute_strategy_weights=original
        errors['beta_shared_engine']=float(np.max(np.abs(frame.beta_tilt-reference)))
        assert errors['beta_shared_engine']<1e-10
        frame.to_csv(OUT/f'{group}_daily_returns.csv')
        np.savez_compressed(OUT/f'{group}_targets.npz',dates=np.array([d for d,w in wh]),weights=np.stack([w for d,w in wh]),arms=ARMS,tickers=names)
        pd.DataFrame([v for d,v in costs],index=[d for d,v in costs],columns=ARMS).to_csv(OUT/f'{group}_turnover.csv')
        factor_frame=frame.copy()
        full=saved.filter(regex='^full_shuffle_');factor_frame['full_shuffle_mean']=full.mean(1)
        for arm in ['prior_only','beta_tilt','volatility_tilt','equal_weight','full_shuffle_mean']:
            factor_frame['difference_'+arm]=frame.real-factor_frame[arm]
        reg.append(regressions(pd.concat([factor_frame,full],axis=1),factors,group))
        for arm in ARMS:
            r=frame[arm];m=metrics(r);ex=r-factors.loc[r.index,'RF']
            performance.append(dict(group=group,arm=arm,**m,sharpe_realized_rf=float(np.sqrt(252)*ex.mean()/ex.std(ddof=1))))
            for start,end in [('2006-01-01','2012-12-31'),('2013-01-01','2019-12-31'),('2020-01-01','2025-12-31')]:
                sub=r.loc[start:end];periods.append(dict(group=group,arm=arm,period=start[:4]+'–'+end[:4],actual_start=str(sub.index[0].date()),actual_end=str(sub.index[-1].date()),**metrics(sub)))
        rolling=np.sqrt(252)*(frame.rolling(756).mean()-RF)/frame.rolling(756).std()
        rolling.dropna().to_csv(OUT/f'{group}_rolling_sharpe_756.csv')
        pair=frame[['real','beta_tilt','volatility_tilt']].to_numpy();boot=block_sharpes(pair,21,10000,20261117+(group=='holdout'))
        actual=np.sqrt(252)*(pair.mean(0)-RF)/pair.std(0,ddof=1)
        contrasts={arm:dict(difference=float(actual[0]-actual[i]),ci95=np.quantile(boot[:,0]-boot[:,i],[.025,.975]).tolist()) for i,arm in enumerate(['real','beta_tilt','volatility_tilt']) if i}
        frozen=pd.read_csv(ROOT/f'data/v2/analysis/informatica_v5_gemini/results/{group}/daily_returns.csv',index_col=0,parse_dates=True).loc[:'2025-12-31']
        audit[group]={arm:metrics(frozen[arm]) for arm in frozen}
        report[group]=dict(signal=signal,reproduction_errors=errors,horizon_weight_error=horizon_error,
            eligibility=eligibility,paired_sharpe_intervals=contrasts)
    p=[report[g]['signal']['all']['ic']['p'] for g in ['core','holdout']]
    for g,adj in zip(['core','holdout'],multipletests(p,method='holm')[1]):report[g]['signal']['all']['ic']['p_holm_two']=float(adj)
    regs=pd.concat(reg,ignore_index=True)
    for model in regs.model.unique():
        mask=(regs.model==model)&(regs.arm=='difference_prior_only')
        regs.loc[mask,'alpha_p_holm_two']=multipletests(regs.loc[mask,'alpha_p'],method='holm')[1]
    regs.to_csv(OUT/'factor_regressions.csv',index=False)
    pd.DataFrame(performance).to_csv(OUT/'performance.csv',index=False)
    pd.DataFrame(periods).to_csv(OUT/'subperiods.csv',index=False)
    (OUT/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (OUT/'metric_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (OUT/'source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (OUT/'validation.json').write_text(json.dumps(dict(status='PASS',sources_unchanged=True,groups={g:report[g]['reproduction_errors'] for g in report}),indent=2)+'\n')
    print('PASS',OUT,flush=True)


if __name__=='__main__':main()
