"""Generate paper assets from saved, separately audited results."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]
PAPER=ROOT/'paper/informatica'
DATA=ROOT/'data/v2/analysis/informatica_revision'
NAMES=['bl_llm_tilt_pos','bl_llm_tilt','equal_weight','mvo','random_views','bl_llm']
LABELS=['BL-Filing+','BL-Filing','EW','MVO','Random Views','BL-Filing MVO']

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'

def savefig(name):
    for ext in ['png','pdf','svg']:
        plt.savefig(PAPER/'figures'/f'{name}.{ext}',dpi=300,bbox_inches='tight')
    plt.close()

def main():
    r=json.loads((DATA/'financial_reanalysis_v1/results.json').read_text())
    pilot=json.loads((DATA/'grok43_replication_v1/analysis.json').read_text())
    for split in ['core','holdout']:
        m=r['windows']['through_2025'][split]['metrics']
        rows=[[label,f"{m[k]['cagr']*100:.2f}",f"{m[k]['volatility']*100:.2f}",f"{m[k]['sharpe']:.3f}",f"{m[k]['max_drawdown']*100:.1f}"] for k,label in zip(NAMES,LABELS)]
        (PAPER/'tables'/f'{split}_performance.md').write_text(table(['Strategy','CAGR %','Vol. %','Sharpe','Max DD %'],rows))
    rows=[]
    for split in ['core','holdout']:
        for c in r['windows']['through_2025'][split]['uncertainty']['21']['contrasts']:
            lo,hi=c['sharpe_difference_ci95'];t=c['mean_return_test']
            rows.append([split.title(),c['contrast'],f"{c['sharpe_difference']:.3f}",f'[{lo:.3f}, {hi:.3f}]',f"{t['annualized_mean_difference']*100:.2f}",f"{t['p_holm_six']:.3f}"])
    (PAPER/'tables/paired_comparisons.md').write_text(table(['Sample','Contrast','ΔSharpe','95% CI','Δmean p.p./yr','Holm p'],rows))
    rows=[]
    for k,label in zip(NAMES,LABELS):
        a=r['windows']['common_through_2025']['core']['metrics'][k]['sharpe'];b=r['windows']['common_through_2025']['holdout']['metrics'][k]['sharpe']
        rows.append([label,f'{a:.3f}',f'{b:.3f}',f"{r['common_window_degradation'][k]*100:.1f}"])
    (PAPER/'tables/common_window.md').write_text(table(['Strategy','Core','Holdout','Relative change %'],rows))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(3.2,4.1));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    texts=['SEC filing + date\nHTML → structured facts','Facts + estimates + prices\n→ view_bps, confidence, rationale','Latest eligible views\n→ P, Q, Ω → BL posterior','Posterior z-scores\n→ clipped and normalized weights']
    for i,text in enumerate(texts):
        y=.79-i*.235
        ax.add_patch(FancyBboxPatch((.02,y),.96,.18,boxstyle='round,pad=.01',facecolor='white',edgecolor='black'))
        ax.text(.5,y+.09,text,ha='center',va='center',fontsize=9)
        if i<3:ax.annotate('',xy=(.5,y-.05),xytext=(.5,y),arrowprops={'arrowstyle':'->','color':'black'})
    savefig('fig1_pipeline')
    fig,axes=plt.subplots(2,1,figsize=(3.25,4.7))
    styles=['-',(0,(6,3)),(0,(1,2)),(0,(6,2,1,2)),(0,(3,2)),(0,(6,2,1,2,1,2))]
    markers=['o','s','^','D','v','X']
    for ax,split in zip(axes,['core','holdout']):
        with (ROOT/'data/results'/split/'daily_returns.csv').open() as f:rows=list(csv.DictReader(f))
        rows=[x for x in rows if x['date']<='2025-12-31'];dates=[datetime.fromisoformat(x['date']) for x in rows]
        for j,(k,label) in enumerate(zip(NAMES,LABELS)):
            y=np.cumprod([1+float(x[k]) for x in rows])
            ax.plot(dates,y,label=label,ls=styles[j],color='black',lw=1.0,
                    marker=markers[j],markevery=(j*40,500),markersize=4,
                    markerfacecolor='white',markeredgewidth=.75)
        ax.set_title(split.title());ax.set_yscale('log');ax.set_ylabel('Wealth (start = 1)');ax.grid(alpha=.2)
        ax.set_xticks([datetime(y,1,1) for y in [2008,2012,2016,2020,2024]])
        ax.set_xticklabels(['2008','2012','2016','2020','2024'],fontsize=8)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=7,ncol=2,loc='upper center',
               handlelength=3.5,columnspacing=1.2,frameon=False,numpoints=2)
    fig.tight_layout(rect=(0,0,1,.86));savefig('fig2_wealth')
    fig,ax=plt.subplots(figsize=(3.25,3.3));ys=[];labels=[]
    for si,split in enumerate(['core','holdout']):
        for i,c in enumerate(r['windows']['through_2025'][split]['uncertainty']['21']['contrasts']):
            y=5-(si*3+i);v=c['sharpe_difference'];lo,hi=c['sharpe_difference_ci95']
            ax.errorbar(v,y,xerr=[[v-lo],[hi-v]],fmt='o' if si==0 else 's',color='black',capsize=3)
            labels.append(split.title()+': '+['+ vs EW','+ vs MVO','all vs BL-MVO'][i]);ys.append(y)
    ax.set_yticks(ys,labels,fontsize=7);ax.axvline(0,color='.5',ls=':');ax.set_xlabel('Difference in arithmetic Sharpe');ax.grid(axis='x',alpha=.2);fig.tight_layout();savefig('fig3_intervals')
    fig,ax=plt.subplots(figsize=(3.2,3.2));a=[c['original_mean'] for c in pilot['cases']];b=[c['anonymized_mean'] for c in pilot['cases']]
    ax.scatter(a,b,facecolor='white',edgecolor='black',s=20);lo=min(a+b)-15;hi=max(a+b)+15
    ax.plot([lo,hi],[lo,hi],color='.4',ls='--');ax.set(xlim=(lo,hi),ylim=(lo,hi),xlabel='Original mean view (bps)',ylabel='Masked mean view (bps)');ax.grid(alpha=.2);fig.tight_layout();savefig('fig4_masking')
    print('Generated 4 figures in PNG/PDF/SVG and four result tables.',flush=True)

if __name__=='__main__':main()
