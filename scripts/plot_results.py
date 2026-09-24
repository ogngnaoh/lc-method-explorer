"""Create scientific figures from saved results; never fit or select models."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'config/experiment.json').read_text())
run=ROOT/'reports/experiments'/config['experiment_id']
selection=json.loads((run/'selection.json').read_text())
result=json.loads((run/'holdout/metrics.json').read_text())
selected=result['deployment_model']
selected_label={'baseline':'Method median','random_forest':'Random Forest','xgboost':'XGBoost'}[
    next(f for f,n in selection['best_by_family'].items() if n==selected)]
names=[selection['best_by_family'][f] for f in ['baseline','random_forest','xgboost']]
labels=['Method median','Random Forest','XGBoost']
colors=['#94a3b8','#405d58','#00857b']
destination=ROOT/'reports/figures'
destination.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.titleweight':'bold','figure.facecolor':'white','savefig.facecolor':'white'})

fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
mae=[result['models'][n]['retention']['mae_min'] for n in names]
axes[0].bar(labels,mae,color=colors,width=.6)
for i,value in enumerate(mae):axes[0].text(i,value+.08,f'{value:.2f}',ha='center')
axes[0].set(ylabel='Mean absolute error (min)',title='Unseen-compound holdout',ylim=(0,max(mae)*1.2))
pred=pd.read_csv(run/f'holdout/{selected}_predictions.csv')
axes[1].scatter(pred.rt_min,pred.prediction_min,s=10,alpha=.28,color='#00857b',edgecolors='none',rasterized=True)
limit=max(pred.rt_min.max(),pred.prediction_min.max())*1.04
axes[1].plot([0,limit],[0,limit],color='#64748b',linestyle='--',linewidth=1)
axes[1].set(xlabel='Measured retention (min)',ylabel='Predicted retention (min)',title=f'{selected_label} (selected in development)',xlim=(0,limit),ylim=(min(0,pred.prediction_min.min()),limit))
base=pd.read_csv(run/'holdout/median_by_method.csv').set_index('method_id')
chosen=pd.read_csv(run/f'holdout/{selected}_by_method.csv').set_index('method_id')
axes[2].plot(range(1,31),base.mae_min,'o-',markersize=3,color='#94a3b8',label='Method median')
axes[2].plot(range(1,31),chosen.mae_min,'o-',markersize=3,color='#00857b',label='Selected model')
axes[2].set(xlabel='Method number',ylabel='Mean absolute error (min)',title='Error varies by method')
axes[2].legend(frameon=False)
fig.suptitle('Retention-time prediction | 70 held-out compounds, 30 known methods',fontsize=15)
for ext in ['png','svg']:fig.savefig(destination/f'retention_evaluation.{ext}',dpi=170)
plt.close(fig)

windows=[f'{a}-{b}' for a,b in config['windows_min']]
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
x=np.arange(len(windows));width=.23
for offset,name,label,color in [(-1,'median','Method median','#94a3b8'),(0,'fixed','Fixed-method ranking','#405d58'),(1,selected,'Selected model','#00857b')]:
    scores=result['models'][name]['ranking']['by_window']
    axes[0].bar(x+offset*width,[100*scores[w]['top1_hit_rate'] for w in windows],width=width,label=label,color=color)
    axes[1].bar(x+offset*width,[scores[w]['mean_excess_distance_min'] for w in windows],width=width,label=label,color=color)
feasible=[100*result['models'][selected]['ranking']['by_window'][w]['feasible_rate'] for w in windows]
axes[0].plot(x,feasible,'kD--',markersize=4,label='Any measured method succeeds',linewidth=1)
axes[0].set(ylabel='Top recommendation in window (%)',ylim=(0,105),title='Does the selected method meet the target?')
axes[1].set(ylabel='Mean excess window distance (min)',title='Distance penalty versus best measured method')
for ax in axes:ax.set_xticks(x,[w.replace('-','–') for w in windows]);ax.set_xlabel('Target window (min)')
axes[0].legend(fontsize=8,frameon=False,loc='upper left')
n=result['models'][selected]['ranking']['overall']['compounds']
fig.suptitle(f'Condition recommendations | {n} complete-panel holdout compounds',fontsize=15)
for ext in ['png','svg']:fig.savefig(destination/f'recommendation_evaluation.{ext}',dpi=170)
plt.close(fig)
print('Saved retention and recommendation figures from frozen evaluation artifacts.')
