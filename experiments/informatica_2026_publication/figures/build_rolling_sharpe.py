from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/Users/oleksii_ivanov/Projects/university/FilingAwareLLMViewsforPortfolioOptimization');D=R/'data/v2/analysis/informatica_revision/signal_risk_v1';O=R/'paper/informatica/v2_evaluation/figures'
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
f,axes=plt.subplots(2,1,figsize=(7,5.4),sharex=True,sharey=True)
for ax,g in zip(axes,['core','holdout']):
 d=pd.read_csv(D/f'{g}_rolling_sharpe_756.csv',index_col=0,parse_dates=True)
 for k,l,c,ls in [('real','BL-Filing+','#0072B2','-'),('equal_weight','EW','#222222','--'),('beta_tilt','Beta / prior-only','#D55E00','-.'),('volatility_tilt','Volatility tilt','#009E73',':')]:
  ax.plot(d.index,d[k],label=l,color=c,ls=ls,lw=1.4 if k=='real' else 1.)
 ax.axhline(0,color='.5',lw=.5);ax.set_title(g.title(),loc='left',fontsize=10);ax.set_ylabel('Rolling Sharpe');ax.grid(axis='y',alpha=.2)
h,l=axes[0].get_legend_handles_labels();f.legend(h,l,loc='upper center',ncol=4,frameon=False,fontsize=8);f.tight_layout(rect=(0,0,1,.94))
for ext in ['png','pdf','svg']:f.savefig(O/f'figS3_rolling_sharpe.{ext}',dpi=300)
