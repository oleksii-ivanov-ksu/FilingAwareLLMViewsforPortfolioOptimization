"""Offline matched controls; shared and frozen files are read-only."""
from pathlib import Path
import hashlib
import json
import logging
import sys
import shutil
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_all_prices, load_universe
from src.backtesting import engine
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior, build_view_matrices
from src.optimization.optimizer import tilt_weights
from scripts.v2.portfolio_protocol import posterior
from scripts.v2.reanalyze_informatica_returns import block_sharpes

OUT = ROOT/'data/v2/analysis/informatica_v5_gemini/matched_controls_v1'
ARMS = ['real', 'prior_only', 'equal_weight'] + [f'{family}_{i:03d}' for family in ['full_shuffle','eligible_shuffle'] for i in range(100)]


def permutation(group, date, family, seed, eligible, n):
    key=f'20261116|{group}|{date.date()}|{family}|{seed}'
    entropy=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big')
    rng=np.random.default_rng(entropy)
    return rng.choice(n,len(eligible),replace=False) if family=='full_shuffle' else rng.permutation(eligible)


def replay(prices, dates, targets):
    """Vectorize across arms while reproducing engine drift and trade costs."""
    daily=prices.pct_change().dropna()
    m=len(ARMS); n=prices.shape[1]
    current=np.full((m,n),1/n); out=[]; index=[]; weights=[]; costs=[]
    for i,date in enumerate(dates):
        if len(prices.loc[:date])<262: continue
        trade=engine.get_next_trading_day(date,prices)
        if trade is None: continue
        end=engine.get_next_trading_day(dates[i+1],prices) if i+1<len(dates) else prices.index[-1]
        if end is None: end=prices.index[-1]
        target=targets[date]
        target=current.copy() if target is None else target.copy()
        # EW does not require covariance and rebalances even when BL cannot.
        target[2]=np.full(n,1/n)
        turnover=np.abs(target-current).sum(axis=1)
        costs.append((str(date.date()),turnover))
        weights.append((str(date.date()),target.copy()))
        period=daily.loc[(daily.index>=trade)&(daily.index<end)]
        if period.empty: continue
        w=target.copy()
        for j,(dt,row) in enumerate(zip(period.index,period.to_numpy())):
            value=w@row
            if j==0:value=value-.001*turnover
            out.append(value);index.append(dt)
            w*=1+row;w/=w.sum(axis=1)[:,None]
        current=w
    return pd.DataFrame(out,index=index,columns=ARMS),weights,costs


def main():
    if OUT.exists():raise SystemExit('Refusing to overwrite matched_controls_v1')
    OUT.mkdir(parents=True)
    protocol=ROOT/'docs/informatica/MATCHED_CONTROLS_PROTOCOL.md'
    shutil.copyfile(protocol,OUT/'protocol.md');shutil.copyfile(__file__,OUT/'run_snapshot.py')
    logging.disable(logging.CRITICAL)
    universe=load_universe(str(ROOT/'config/universe.yaml'))
    prices=load_all_prices(ROOT/'data/raw',universe['core']+universe['holdout'])
    views=engine.load_views_summary(ROOT/'data/v2/views_v2/views_summary.csv')
    dates=engine.generate_rebalance_dates(2006,2025,'quarterly')
    source_paths=[ROOT/'config/universe.yaml',ROOT/'data/v2/views_v2/views_summary.csv',protocol]
    source_paths += [ROOT/f'data/raw/{t}/prices.csv' for group in universe.values() for t in group]
    source_paths += [ROOT/p for p in ['src/backtesting/engine.py','src/optimization/black_litterman.py','src/optimization/covariance.py','src/optimization/optimizer.py','scripts/v2/portfolio_protocol.py']]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    results={};manifest=[]
    for group in ['core','holdout']:
        names=universe[group];px=prices[names];n=len(names);targets={};fallbacks=[]
        for date in dates:
            if len(px.loc[:date])<262 or engine.get_next_trading_day(date,px) is None:continue
            active=engine.get_active_views(views,names,date,120)
            chosen=[v for v in active if v.confidence=='medium' and v.view_bps>0]
            manifest.append({'group':group,'date':str(date.date()),'latest_count':len(active),'accepted_count':len(chosen),'latest':[{'ticker':v.ticker,'view_bps':float(v.view_bps),'confidence':v.confidence,'sigma':float(v.sigma)} for v in active]})
            try:cov=rolling_covariance(px,date,lookback=252)
            except ValueError as exc:
                if not str(exc).startswith('Not enough observations:'):raise
                targets[date]=None;fallbacks.append({'date':str(date.date()),'reason':str(exc)});continue
            prior=compute_prior(cov,np.ones(n)/n,delta=2.5)
            weights=np.full((len(ARMS),n),1/n)
            if chosen:
                p,q,omega=build_view_matrices(chosen,{t:i for i,t in enumerate(names)},n)
                mu=posterior(cov,prior,p,q,omega)
                weights[0]=tilt_weights(mu,tilt_strength=1.)
                weights[1]=tilt_weights(prior,tilt_strength=1.)
                original=engine._compute_strategy_weights(strategy='bl_llm_tilt_pos',prices=px,views_df=views,tickers=names,ticker_to_idx={t:i for i,t in enumerate(names)},rebal_date=date,n=n,delta=2.5,tau=.05,risk_aversion=2.5,max_weight=.1,lookback=252,max_staleness_days=120)
                np.testing.assert_allclose(weights[0],original,atol=1e-10,rtol=0)
                eligible=p.argmax(axis=1)
                for offset,family in [(3,'full_shuffle'),(103,'eligible_shuffle')]:
                    for seed in range(100):
                        idx=permutation(group,date,family,seed,eligible,n)
                        assert len(set(idx))==len(eligible)
                        if family=='eligible_shuffle':assert set(idx)==set(eligible)
                        pick=np.eye(n)[idx]
                        # Q/Omega never change: their joint multiset is preserved exactly.
                        weights[offset+seed]=tilt_weights(posterior(cov,prior,pick,q,omega),tilt_strength=1.)
            assert np.isfinite(weights).all() and (weights>=0).all()
            np.testing.assert_allclose(weights.sum(axis=1),1,atol=1e-12)
            targets[date]=weights
        frame,wh,costs=replay(px,dates,targets)
        frame=frame.loc[:'2025-12-31']
        frozen=pd.read_csv(ROOT/f'data/v2/analysis/informatica_v5_gemini/results/{group}/daily_returns.csv',index_col=0,parse_dates=True).loc[:'2025-12-31']
        assert frame.index.equals(frozen.index),(group,'date mismatch')
        errors={}
        for arm,column in [('real','bl_llm_tilt_pos'),('equal_weight','equal_weight')]:
            errors[arm]=float(np.max(np.abs(frame[arm]-frozen[column])))
            assert errors[arm]<1e-10,errors
        # Independently compare one new arm through the unmodified engine simulator.
        original_callback=engine._compute_strategy_weights
        def callback(**kw):
            value=targets[kw['rebal_date']]
            if value is None:raise ValueError('recorded covariance fallback')
            return value[3]
        engine._compute_strategy_weights=callback
        try:reference=engine.run_backtest(px,views,names,dates,strategy='bl_llm_tilt_pos')['daily_returns'].loc[:'2025-12-31']
        finally:engine._compute_strategy_weights=original_callback
        errors['new_arm_shared_engine']=float(np.max(np.abs(frame.iloc[:,3]-reference)))
        assert errors['new_arm_shared_engine']<1e-10
        frame.to_csv(OUT/f'{group}_daily_returns.csv')
        np.savez_compressed(OUT/f'{group}_targets.npz',dates=np.array([d for d,w in wh]),weights=np.stack([w for d,w in wh]),tickers=np.array(names),arms=np.array(ARMS))
        turnover=pd.DataFrame([v for d,v in costs],index=[d for d,v in costs],columns=ARMS)
        turnover.to_csv(OUT/f'{group}_turnover.csv')
        x=frame.to_numpy();rf=1.02**(1/252)-1;sh=np.sqrt(252)*(x.mean(0)-rf)/x.std(0,ddof=1)
        wealth=np.cumprod(1+x,axis=0);peak=np.maximum.accumulate(np.vstack([np.ones(len(ARMS)),wealth]),axis=0)[1:]
        reported_dates=[d for d,w in wh if engine.get_next_trading_day(pd.Timestamp(d),px)<=frame.index[-1]]
        relevant=[w for d,w in wh if d in reported_dates]
        concentration=np.mean([np.sum(w*w,axis=1) for w in relevant],axis=0)
        summary=pd.DataFrame({'arm':ARMS,'sharpe':sh,'cagr':wealth[-1]**(252/len(x))-1,'max_drawdown':np.min(wealth/peak-1,axis=0),'annualized_turnover':turnover.loc[reported_dates].sum().to_numpy()/(len(x)/252),'mean_target_hhi':concentration})
        summary.to_csv(OUT/f'{group}_summary.csv',index=False)
        controls={}
        for offset,family in [(3,'full_shuffle'),(103,'eligible_shuffle')]:
            values=sh[offset:offset+100]
            controls[family]={'median_sharpe':float(np.median(values)),'seed_percentiles_2_5_97_5':np.quantile(values,[.025,.975]).tolist(),'real_sharpe':float(sh[0]),'seeds_ge_real':int((values>=sh[0]).sum()),'conditional_rank_exceedance':float((1+(values>=sh[0]).sum())/101)}
        paired=np.column_stack([x[:,0],x[:,1],x[:,2],x[:,3:103].mean(1),x[:,103:].mean(1)])
        intervals={}
        for length in [5,21,63]:
            boot=block_sharpes(paired,length,10000,20261116+(0 if group=='core' else 1000)+length)
            actual=np.sqrt(252)*(paired.mean(0)-rf)/paired.std(0,ddof=1)
            intervals[str(length)]={name:{'difference':float(actual[0]-actual[i]),'ci95':np.quantile(boot[:,0]-boot[:,i],[.025,.975]).tolist()} for i,name in enumerate(['real','prior_only','equal_weight','full_shuffle_mean_series','eligible_shuffle_mean_series']) if i}
        results[group]={'days':len(frame),'start':str(frame.index[0].date()),'end':str(frame.index[-1].date()),'reproduction_max_abs_error':errors,'fallbacks':fallbacks,'controls':controls,'paired_sharpe_intervals':intervals}
        print(group,json.dumps(controls),flush=True)
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    (OUT/'date_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (OUT/'validation.json').write_text(json.dumps({'status':'PASS','arms_per_group':len(ARMS),'seeds_per_family':100,'sources_unchanged':True,'permutation_constraints':'asserted for every draw','reproduction':{k:v['reproduction_max_abs_error'] for k,v in results.items()}},indent=2)+'\n')
    print('PASS: matched controls saved',flush=True)


if __name__=='__main__':main()
