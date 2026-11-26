"""Analyze full matched portfolio slices, with a no-call historical self-check."""
from pathlib import Path
from itertools import combinations
from collections import Counter
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.run_backtest import load_all_prices,load_universe
from src.backtesting import engine
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior
from src.optimization.optimizer import tilt_weights
from src.reasoning.calibration import calibrate_uncertainty
from src.reasoning.schemas import Confidence
from scripts.v2.portfolio_protocol import posterior
BASE=ROOT/'data/v2/analysis/informatica_revision'
INPUT=BASE/'portfolio_masking_preparation_v1'
RUN=BASE/'portfolio_masking_grok43_v1'


def allocate(cases,outputs,names,cov,prior,frozen=False):
    accepted=[];q=[];omega=[]
    for c in cases:
        out=outputs[c['case_id']]
        if frozen:
            saved=json.loads((ROOT/c['source_view']).read_text())['view']
            keep=saved['confidence']=='medium' and saved['view_bps']>0
        else:keep=out['confidence']=='medium' and out['view_bps']>0
        if not keep:continue
        accepted.append(names.index(c['ticker']));q.append(out['view_bps']/10000)
        omega.append(calibrate_uncertainty(Confidence.MEDIUM,sentiment=c['sentiment'])**2)
    if not q:return np.ones(len(names))/len(names),accepted
    p=np.eye(len(names))[accepted]
    w=tilt_weights(posterior(cov,prior,p,np.array(q),np.array(omega)),tilt_strength=1.)
    return w,accepted


def compare_weights(a,b):
    """All distances are one-way reallocated capital: half the L1 distance."""
    within_a=np.array([np.abs(a[i]-a[j]).sum()/2 for i,j in combinations(range(3),2)])
    within_b=np.array([np.abs(b[i]-b[j]).sum()/2 for i,j in combinations(range(3),2)])
    cross=np.abs(a[:,None,:]-b[None,:,:]).sum(2)/2
    return {'mean_vector_one_way_distance':float(np.abs(a.mean(0)-b.mean(0)).sum()/2),
        'original_within_one_way':float(within_a.mean()),'masked_within_one_way':float(within_b.mean()),
        'cross_one_way':float(cross.mean()),'cross_minus_average_within':float(cross.mean()-(within_a.mean()+within_b.mean())/2),
        'original_mean_hhi':float((a*a).sum(1).mean()),'masked_mean_hhi':float((b*b).sum(1).mean()),
        'original_mean_max_weight':float(a.max(1).mean()),'masked_mean_max_weight':float(b.max(1).mean()),
        'hypothetical_cross_reallocation_charge_fraction':float(.001*2*cross.mean())}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--self-check',action='store_true');args=ap.parse_args()
    manifest=json.loads((INPUT/'manifest.json').read_text());universe=load_universe(str(ROOT/'config/universe.yaml'))
    prices=load_all_prices(ROOT/'data/raw',universe['core']+universe['holdout']);views=engine.load_views_summary(ROOT/'data/views/views_summary.csv')
    records={};ids=[];cost=0.;invalid=[];hashes={}
    if not args.self_check:
        for p in sorted(RUN.glob('[0-9][0-9][0-9][0-9]_*.json')):
            r=json.loads(p.read_text());j=r['job'];key=(j['case_id'],j['condition'],j['repeat']);assert key not in records
            records[key]=r;cost+=r['cost'];hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
            if not r['valid'] or r['fatal']:invalid.append(key)
            ids.append(r.get('response',{}).get('id'))
        assert len(records)==1194, f'Incomplete: {len(records)}/1194'
        assert not invalid, f'Invalid records, explicit analysis amendment needed: {invalid}'
        assert len(set(ids))==1194 and None not in ids
    rows=[];targets={};maxerror=0.
    for date in manifest['dates']:
        for group in ['core','holdout']:
            cases=[c for c in manifest['cases'] if c['date']==date and c['group']==group]
            names=universe[group];px=prices[names];dt=pd.Timestamp(date)
            cov=rolling_covariance(px,dt,lookback=252);prior=compute_prior(cov,np.ones(50)/50,2.5)
            historical={c['case_id']:json.loads((ROOT/c['source_view']).read_text())['view'] for c in cases}
            baseline,_=allocate(cases,historical,names,cov,prior)
            expected=engine._compute_strategy_weights(strategy='bl_llm_tilt_pos',prices=px,views_df=views,tickers=names,ticker_to_idx={t:i for i,t in enumerate(names)},rebal_date=dt,n=50,delta=2.5,tau=.05,risk_aversion=2.5,max_weight=.1,lookback=252,max_staleness_days=120)
            error=float(np.max(np.abs(baseline-expected)));assert error<1e-10;maxerror=max(maxerror,error)
            for mode,frozen in [('end_to_end',False),('frozen_support',True)]:
                arm={};sets={};counts={}
                for condition in ['original','anonymized']:
                    arm[condition]=[];sets[condition]=[];counts[condition]=Counter()
                    for repeat in range(1,4):
                        outputs=historical if args.self_check else {c['case_id']:records[c['case_id'],condition,repeat]['parsed'] for c in cases}
                        w,accepted=allocate(cases,outputs,names,cov,prior,frozen)
                        arm[condition].append(w);sets[condition].append(set(accepted));counts[condition].update(x['confidence'] for x in outputs.values())
                    arm[condition]=np.stack(arm[condition]);assert np.isfinite(arm[condition]).all();np.testing.assert_allclose(arm[condition].sum(1),1,atol=1e-12)
                stats=compare_weights(arm['original'],arm['anonymized'])
                stats['accepted_counts_original']=[len(x) for x in sets['original']];stats['accepted_counts_masked']=[len(x) for x in sets['anonymized']]
                stats['mean_cross_selected_symmetric_difference']=float(np.mean([len(a^b) for a in sets['original'] for b in sets['anonymized']]))
                stats['confidence_counts']={k:dict(v) for k,v in counts.items()}
                rows.append({'date':date,'group':group,'mode':mode,**stats})
                targets[date+'_'+group+'_'+mode]=arm
                if args.self_check:
                    assert stats['mean_vector_one_way_distance']==0
                    assert stats['cross_minus_average_within']==0
    if args.self_check:
        result={'status':'PASS','slices':4,'historical_target_max_error':maxerror,'identical_input_zero_distance':True}
        (RUN/'analysis_self_check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return
    transitions=Counter()
    for c in manifest['cases']:
        for i in range(1,4):
            for j in range(1,4):
                a=records[c['case_id'],'original',i]['parsed']['confidence'];b=records[c['case_id'],'anonymized',j]['parsed']['confidence'];transitions[a+' -> '+b]+=1
    result={'complete_calls':1194,'cases':199,'unique_generation_ids':len(set(ids)),'cost_usd':cost,'slices':rows,'confidence_transitions_all_cross_pairs':dict(transitions),'interpretation':'Four dependent descriptive slices; narrow explicit-identity intervention; no temporal-leakage or performance claim.'}
    (RUN/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    (RUN/'targets.json').write_text(json.dumps({k:{c:v.tolist() for c,v in d.items()} for k,d in targets.items()},indent=2)+'\n')
    (RUN/'response_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
