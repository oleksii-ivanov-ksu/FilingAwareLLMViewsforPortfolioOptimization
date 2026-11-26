"""Recompute extension statistics from portable saved returns/target arrays."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.v2.reanalyze_informatica_returns import block_sharpes
BASE=ROOT/'data/v2/analysis/informatica_revision'


def main():
    folder=BASE/'matched_controls_v1';report=json.loads((folder/'results.json').read_text())
    table='| Sample | Control | Difference | 95% interval |\n|---|---|---|---|\n'
    for group in ['core','holdout']:
        frame=pd.read_csv(folder/f'{group}_daily_returns.csv',index_col=0)
        x=frame.to_numpy();rf=1.02**(1/252)-1
        s=np.sqrt(252)*(x.mean(0)-rf)/x.std(0,ddof=1)
        summary=pd.read_csv(folder/f'{group}_summary.csv')
        np.testing.assert_allclose(s,summary.sharpe,atol=1e-12,rtol=1e-10)
        growth=np.cumprod(1+x,axis=0);peak=np.maximum.accumulate(np.vstack([np.ones(x.shape[1]),growth]),axis=0)[1:]
        np.testing.assert_allclose(growth[-1]**(252/len(x))-1,summary.cagr,atol=1e-12)
        np.testing.assert_allclose((growth/peak-1).min(0),summary.max_drawdown,atol=1e-12)
        t=np.load(folder/f'{group}_targets.npz');keep=t['dates']<frame.index[-1]
        np.testing.assert_allclose((t['weights'][keep]**2).sum(2).mean(0),summary.mean_target_hhi,atol=1e-12)
        turnover=pd.read_csv(folder/f'{group}_turnover.csv',index_col=0)
        np.testing.assert_allclose(turnover.loc[t['dates'][keep]].sum().to_numpy()/(len(x)/252),summary.annualized_turnover,atol=1e-12)
        paired=np.column_stack([x[:,0],x[:,1],x[:,2],x[:,3:103].mean(1),x[:,103:].mean(1)])
        sh=np.sqrt(252)*(paired.mean(0)-rf)/paired.std(0,ddof=1)
        for length in [5,21,63]:
            boot=block_sharpes(paired,length,10000,20261116+(0 if group=='core' else 1000)+length)
            for i,name in enumerate(['real','prior_only','equal_weight','full_shuffle_mean_series','eligible_shuffle_mean_series']):
                if i==0:continue
                saved=report[group]['paired_sharpe_intervals'][str(length)][name]
                np.testing.assert_allclose(saved['difference'],sh[0]-sh[i],atol=1e-12)
                ci=np.quantile(boot[:,0]-boot[:,i],[.025,.975]);np.testing.assert_allclose(saved['ci95'],ci,atol=1e-10)
                if length==21 and name!='equal_weight':
                    label={'prior_only':'Prior','full_shuffle_mean_series':'Full','eligible_shuffle_mean_series':'Eligible'}[name]
                    table+=f'| {group.title()} | {label} | {sh[0]-sh[i]:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] |\n'
    (ROOT/'paper/informatica/tables/matched_controls.md').write_text(table)
    fig, axes = plt.subplots(2, 1, figsize=(3.4, 3.5), sharex=True)
    for ax, group in zip(axes, ['core', 'holdout']):
        values = pd.read_csv(folder/f'{group}_summary.csv').set_index('arm').sharpe
        ax.boxplot([values.iloc[3:103], values.iloc[103:203]], vert=False, positions=[1,2], widths=.45,
                   whis=(2.5,97.5), showfliers=True, patch_artist=True,
                   boxprops={'facecolor':'white','edgecolor':'black'}, medianprops={'color':'black'},
                   flierprops={'marker':'.','markersize':2,'markeredgecolor':'gray'})
        ax.axvline(values['real'],color='black',linestyle='-',label='Real views')
        ax.axvline(values['prior_only'],color='gray',linestyle='--',label='Prior only')
        ax.set_yticks([1,2],['Full shuffle','Eligible only'],fontsize=8)
        ax.set_title(group.title(),fontsize=9);ax.tick_params(axis='x',labelsize=8)
        ax.grid(axis='x',alpha=.2);ax.spines[['top','right']].set_visible(False)
    axes[-1].set_xlabel('Arithmetic Sharpe',fontsize=8)
    axes[0].legend(fontsize=7,loc='lower left',frameon=False)
    fig.tight_layout()
    for ext in ['png','pdf','svg']:fig.savefig(ROOT/f'paper/informatica/figures/fig5_matched_controls.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)
    masking=BASE/'portfolio_masking_grok43_v1'
    if (masking/'analysis.json').exists():
        analysis=json.loads((masking/'analysis.json').read_text());targets=json.loads((masking/'targets.json').read_text())
        table='| Slice | Mean shift % | Within % | Excess % |\n|---|---|---|---|\n'
        for row in analysis['slices']:
            key=row['date']+'_'+row['group']+'_'+row['mode'];a=np.array(targets[key]['original']);b=np.array(targets[key]['anonymized'])
            within_a=sum(np.abs(a[i]-a[j]).sum()/2 for i,j in [(0,1),(0,2),(1,2)])/3
            within_b=sum(np.abs(b[i]-b[j]).sum()/2 for i,j in [(0,1),(0,2),(1,2)])/3
            mean_shift=np.abs(a.mean(0)-b.mean(0)).sum()/2;cross=np.abs(a[:,None]-b[None,:]).sum(2).mean()/2
            excess=cross-(within_a+within_b)/2
            for k,v in [('mean_vector_one_way_distance',mean_shift),('original_within_one_way',within_a),('masked_within_one_way',within_b),('cross_one_way',cross),('cross_minus_average_within',excess)]:np.testing.assert_allclose(row[k],v,atol=1e-12)
            if row['mode']=='end_to_end':table+=f"| {row['group'].title()} {row['date'][:4]} | {mean_shift*100:.2f} | {(within_a+within_b)/2*100:.2f} | {excess*100:.2f} |\n"
        (ROOT/'paper/informatica/tables/portfolio_masking.md').write_text(table)
    print('PASS: extension statistics and tables reproduced',flush=True)


if __name__=='__main__':main()
