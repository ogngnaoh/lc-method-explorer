"""Render static presentation figures from frozen evidence; no model fitting."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/figures'
RUN = ROOT / 'reports/experiments/mcmrt-v3-compound-v1'
TEAL, INK, MUTED, PALE = '#00857b', '#24332f', '#586b65', '#edf6f3'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':13,'text.color':INK,
 'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
 'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})

def save(fig, name):
    for ext in ('png','svg'):
        fig.savefig(OUT/f'{name}.{ext}',dpi=180,facecolor='white')
    plt.close(fig)

def canvas(title, subtitle, height=4.8):
    fig=plt.figure(figsize=(12,height),facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,12),ylim=(0,height));ax.axis('off')
    ax.add_patch(Rectangle((.45,height-.34),.55,.07,color=TEAL))
    ax.text(.45,height-.86,title,fontsize=24,weight='bold')
    ax.text(.45,height-1.27,subtitle,fontsize=12,color=MUTED)
    return fig,ax

def box(ax,x,y,w,h,title,body):
    ax.add_patch(Rectangle((x,y),w,h,facecolor=PALE,edgecolor='none'))
    ax.text(x+.2,y+h-.37,title,weight='bold',fontsize=16)
    ax.text(x+.2,y+h-.77,body,fontsize=12,linespacing=1.6,va='top')

def arrow(ax,a,b):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=16,color=TEAL,lw=2))

fig,ax=canvas('A molecule. A window. A shortlist.', 'LC Method Explorer  /  prediction under 30 recorded methods')
box(ax,.45,1.25,3.35,1.75,'01  Describe','Molecular structure\nColumn, solvents and gradient\nRecorded temperature')
box(ax,4.3,1.25,3.15,1.75,'02  Predict','Estimate retention time\nfor each supported method\nusing the frozen model')
box(ax,7.95,1.25,3.6,1.75,'03  Rank','Compare with the target window\nRank all 30 candidates\nInspect method settings')
arrow(ax,(3.86,2.1),(4.24,2.1));arrow(ax,(7.51,2.1),(7.89,2.1))
ax.text(.45,.57,'Measured outcomes are revealed after ranking. A window hit does not establish separation quality.',fontsize=12,color=MUTED)
save(fig,'workflow')

fig,ax=canvas('Keep compound groups together', 'All measurements for a group stay in the same partition.',5.5)
box(ax,.45,1.7,3.1,2,'341 groups','343 source compounds\n10,073 measured retention times\n30 known methods')
box(ax,4.15,2.75,3.15,1.15,'Development','272 groups / 8,026 rows')
box(ax,4.15,1.15,3.15,1.15,'Final holdout','69 groups / 2,047 rows')
box(ax,7.9,2.75,3.65,1.15,'Select and freeze','Five grouped validation folds')
box(ax,7.9,1.15,3.65,1.15,'Evaluate once','70 compounds, unseen in fitting')
arrow(ax,(3.55,3.3),(4.1,3.3));arrow(ax,(3.55,2),(4.1,1.7))
arrow(ax,(7.3,3.3),(7.85,3.3));arrow(ax,(7.3,1.7),(7.85,1.7))
arrow(ax,(9.7,2.72),(9.7,2.33))
ax.text(.45,.48,'Group separation is not scaffold separation. The evaluated holdout is closed to further tuning.',fontsize=12,color=MUTED)
save(fig,'evaluation')

sel=json.loads((RUN/'selection.json').read_text())
metrics=json.loads((RUN/'holdout/metrics.json').read_text())
keys=['median','rf_leaf1','xgb_depth5']
fig,axes=plt.subplots(1,2,figsize=(12,5.6))
fig.subplots_adjust(left=.08,right=.97,top=.76,bottom=.28,wspace=.36)
fig.text(.045,.92,'Better prediction, modest ranking gain',fontsize=24,weight='bold')
fig.text(.045,.845,'Frozen compound-group evaluation  /  XGBoost selected before holdout',fontsize=12,color=MUTED)
x=np.arange(3);w=.32
for dx,values,color,label in [(-w/2,[next(c['mae_min'] for c in sel['candidates'] if c['candidate']==k) for k in keys],'#a7bdb6','Development'),(w/2,[metrics['models'][k]['retention']['mae_min'] for k in keys],TEAL,'Holdout')]:
 bars=axes[0].bar(x+dx,values,w,color=color,label=label)
 axes[0].bar_label(bars,fmt='%.2f',padding=4,fontsize=11)
axes[0].set_xticks(x,['Median','Random\nForest','XGBoost']);axes[0].set(ylabel='Mean absolute error (min)',ylim=(0,6))
axes[0].legend(frameon=False,fontsize=11,loc='upper right')
rankkeys=['median','fixed','rf_leaf1','xgb_depth5']
vals=[100*metrics['models'][k]['ranking']['overall']['top1_hit_rate'] for k in rankkeys]
bars=axes[1].bar(range(4),vals,color=['#a7bdb6','#405d58','#6c9589',TEAL],width=.6)
axes[1].bar_label(bars,labels=[f'{v:.1f}%' for v in vals],padding=4,fontsize=11)
axes[1].set_xticks(range(4),['Median','Fixed\nrule','Random\nForest','XGBoost']);axes[1].set(ylabel='Top recommendation in window (%)',ylim=(0,100))
fig.text(.08,.12,'70 holdout compounds / 2,047 observations',fontsize=11,color=MUTED)
fig.text(.56,.12,'67 complete panels × 4 windows = 268 cases',fontsize=11,color=MUTED)
fig.text(.045,.045,'14 negative XGBoost predictions remain scored. Ranking gains do not establish laboratory time savings.',fontsize=12,color=MUTED)
save(fig,'results_summary')
print('Rendered workflow, evaluation and results summary as PNG + SVG.')
