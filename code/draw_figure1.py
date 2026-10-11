"""Draw the inventory layers and stratified SR-Site study populations."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
R=Path(__file__).resolve().parents[1]
O=R/'figures';O.mkdir(exist_ok=True)
rows=list(csv.DictReader((R/'data/coverage_evidence_200.csv').open(encoding='utf-8-sig')))
assert len(rows)==200 and sum(r['project_letter']!='N' for r in rows)==55
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'svg.fonttype':'none','pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(6.2,5.75));fig.subplots_adjust(0,0,1,1)
ax.set(xlim=(0,6.2),ylim=(-.08,5.75));ax.axis('off')
ink='#18354A';blue='#226A8E';teal='#147D74';amber='#9D651E';gray='#626E77';pale='#EFF4F7'
def txt(x,y,t,**kw):ax.text(x,y,t,ha=kw.pop('ha','center'),va=kw.pop('va','center'),color=kw.pop('color',ink),**kw)
def arrow(a,b,color=gray,style='-',lw=1.3,rad=0):
 p=FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,linewidth=lw,color=color,linestyle=style,connectionstyle=f'arc3,rad={rad}',shrinkA=2,shrinkB=2,zorder=1);ax.add_patch(p)
def pill(x,y,w,h,t,color=blue,fill='white',weight='normal'):
 ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.035,rounding_size=0.06',facecolor=fill,edgecolor=color,linewidth=1.15,zorder=2));txt(x,y,t,fontweight=weight,zorder=3)
txt(.10,5.57,'a  Catalogue layers',ha='left',fontweight='bold')
txt(6.07,5.54,'Schematic relations',ha='right',fontsize=12,color=gray)
ys=[5.0,4.07,3.10]; xs=[2.40,3.84,5.30]
for y,label in zip(ys,['IFEP\ncategories','PFEP\nsource entries','SR-Site\ncatalogue']):txt(.12,y,label,ha='left',fontweight='bold')
for x,label in zip(xs,['i','j','k']):
 ax.add_patch(Circle((x,ys[0]),.21,facecolor='#E7F1F7',edgecolor=blue,linewidth=1.15,zorder=2));txt(x,ys[0],label,fontweight='bold')
for x,label in zip(xs,['a','b','c']):pill(x,ys[1],.70,.42,label,teal,'#EAF5F1',weight='bold')
for x,label in zip(xs,['Process','Variable','Initial\nstate']):pill(x,ys[2],1.13,.55,label,blue,pale)
for i,j in [(0,0),(0,1),(1,1),(1,2),(2,2)]:arrow((xs[i],ys[0]-.22),(xs[j],ys[1]+.24),blue,':',1.2)
for i,j in [(0,0),(1,0),(1,1),(2,1),(2,2)]:arrow((xs[i],ys[1]-.24),(xs[j],ys[2]+.30),teal,'-',1.35)
txt(3.9,4.54,'many-to-many indexing',fontsize=12,color=blue,bbox={'facecolor':'white','edgecolor':'none','pad':1.4})
txt(3.9,3.57,'many-to-many handling',fontsize=12,color=teal,bbox={'facecolor':'white','edgecolor':'none','pad':1.4})
ax.plot([.12,6.07],[2.65,2.65],color='#C5D0D7',lw=.8)
txt(.10,2.40,'b  Screening populations',ha='left',fontweight='bold')
pill(1.37,1.84,2.15,.50,'1,671 screened PFEPs',blue,pale)
pill(4.63,2.01,2.65,.45,'1,301 relevant',teal,'#EAF5F1')
pill(4.63,1.44,2.65,.44,'370 excluded',gray,'#F3F4F5')
arrow((2.49,1.90),(3.26,2.01),teal);arrow((2.49,1.74),(3.26,1.46),gray)
txt(4.63,2.42,'4,375 handling associations',fontsize=12,color=teal)
pill(1.34,.83,2.20,.47,'200 coverage decisions',blue,pale)
arrow((3.27,1.33),(2.50,.99),blue)
txt(4.62,.98,'166 applicability\n4 non-FEP',fontsize=12,color=gray)
arrow((4.63,1.20),(4.63,1.08),gray)
pill(1.44,.20,2.43,.40,'55 non-Project N',teal,'#EAF5F1',weight='bold')
pill(4.47,.20,2.95,.40,'145 Project N',amber,'#FBF2E7',weight='bold')
arrow((1.17,.58),(1.42,.46),teal);arrow((2.08,.58),(3.45,.46),amber)
for ext in ['svg','pdf','png']:
 fig.savefig(O/f'Figure_1_Branching_Documentary_Pathways.{ext}',dpi=300,facecolor='white',metadata={'Creator':''} if ext=='pdf' else None)
plt.close(fig)
