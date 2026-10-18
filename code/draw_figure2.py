#!/usr/bin/env python3
"""Draw documented FEP routes and report-supported assessment dependencies.

Source records: H 1.6.3 (PT12) and I 165 (PT13) in the SR-Site runtime archive.
The figure distinguishes archived relations, engineering dependencies described
in safety reports, and a proposed review workflow. It does not encode a newly
observed safety failure or a recovered PFEP-to-model-input relation.

Technical sources: SKB TR-10-47, Section 3.5.6; TR-11-01, Sections 12.2 and
12.6; TR-21-01, Sections 5.5.1, 8.3.2 and 10.3.9. See the manuscript caption.

Run: python draw_figure2.py --output-dir /path/to/figures
"""
from pathlib import Path
import argparse
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Ellipse, PathPatch
from matplotlib.path import Path as MplPath
from PIL import Image

W, H = 6.2, 5.5
C = {
    'ink': '#22323F', 'muted': '#52616D', 'line': '#66727E',
    'blue': '#315A73', 'blue_fill': '#EDF3F7', 'teal': '#257E83',
    'teal_fill': '#E8F3F1', 'purple': '#81609A', 'purple_fill': '#F4EFF8',
    'panel': '#F9FAFB', 'panel_border': '#D5DEE5', 'white': '#FFFFFF',
}
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 12,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'axes.linewidth': 0.7, 'savefig.facecolor': 'white',
})


def draw(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(W, H), facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, W), ylim=(0, H)); ax.axis('off')
    label_boxes = []

    def txt(x, y, s, size=12, color=None, weight='normal', ha='center', va='center', z=5, **kw):
        return ax.text(x, y, s, fontsize=size, color=color or C['ink'],
                       fontweight=weight, ha=ha, va=va, zorder=z,
                       linespacing=1.08, **kw)

    def panel(x, y, w, h):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.01,rounding_size=0.08',
            edgecolor=C['panel_border'], facecolor=C['panel'], linewidth=0.7, zorder=0))

    def node(cx, cy, w, h, label, selected=False, engineering=False, size=12, weight='normal'):
        edge = C['teal'] if engineering else C['blue']
        fill = C['teal_fill'] if engineering else C['blue_fill'] if selected else C['white']
        patch = FancyBboxPatch((cx-w/2, cy-h/2), w, h,
            boxstyle='round,pad=0.025,rounding_size=0.055',
            edgecolor=edge, facecolor=fill, linewidth=1.15 if selected or engineering else 0.8,
            zorder=3)
        ax.add_patch(patch)
        text = txt(cx, cy, label, size=size, weight=weight)
        label_boxes.append((label, text, (cx-w/2,cy-h/2,w,h)))
        return patch

    def arrow(start, end, kind='stored', connectionstyle='arc3,rad=0', lw=1.25, mutation=9, z=2):
        color = C['line'] if kind=='stored' else C['teal'] if kind=='report' else C['purple']
        style = (0, (3.5, 2.5)) if kind=='review' else '-'
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=mutation,
            color=color, linewidth=lw, linestyle=style, connectionstyle=connectionstyle,
            shrinkA=0, shrinkB=0, zorder=z))

    panel(.23, 3.77, 5.82, 1.57)
    panel(.23, 1.14, 5.82, 2.46)

    # A: one archived association and a report-supported branching influence.
    txt(.39, 5.14, 'A  Thermal effects and impurity chemistry', weight='bold', ha='left')
    node(.86, 4.59, 1.02, .77, 'H 1.6.3\nThermal\neffects')
    node(2.35, 4.59, 1.05, .77, 'Bu13\nImpurity\nalteration', selected=True)
    arrow((1.40,4.59),(1.79,4.59))
    txt(1.61,4.90,'SKB',size=12,color=C['muted'])
    ax.add_patch(Ellipse((3.94,4.59),1.27,.74,facecolor=C['teal_fill'],edgecolor=C['teal'],linewidth=1.15,zorder=3))
    txt(3.94,4.59,'Buffer\nchemistry')
    arrow((2.90,4.59),(3.27,4.59),'report')
    for y,label in [(4.92,'Corrosion'),(4.59,'Retention'),(4.26,'Swelling')]:
        arrow((4.59,4.59),(4.93,y),'report')
        txt(5.52,y,label)
    txt(.41,3.97,'Indirect influence on safety functions',ha='left',color=C['teal'])

    # B: all four imported references are retained. Only the I058 branch is
    # expanded. C09 belongs to the separate galvanic branch, not the
    # report-supported erosion-to-sulphide-corrosion dependency shown at right.
    txt(.39,3.39,'B  Interfaces, buffer loss and corrosion assessment',weight='bold',ha='left')
    node(.86,2.65,1.02,.58,'I 165\nInterfaces')
    endpoints=[(3.06,'I 126  Galvanic',False),(2.69,'I 058  Colloids',True),
               (2.32,'I 061  Concrete',False),(1.95,'I 273  Models',False)]
    x_left, x_trunk = 1.71, 1.50
    ax.plot([1.40,x_trunk],[2.65,2.65],color=C['line'],linewidth=1.25,zorder=2)
    ax.plot([x_trunk,x_trunk],[1.95,3.06],color=C['line'],linewidth=1.25,zorder=2)
    for y,label,sel in endpoints:
        arrow((x_trunk,y),(x_left-.055,y))
        node(2.48,y,1.54,.29,label,selected=sel,size=12)
    txt(.86,1.93,'Imported\nsource\npointers',size=12,color=C['muted'])

    node(4.97,2.69,1.72,.72,'Bu18\nMontmorillonite\ncolloid release',selected=True)
    arrow((3.29,2.69),(4.065,2.69))
    txt(3.68,2.97,'SKB',size=12,color=C['muted'])
    txt(3.68,2.29,'Fit\nqualified',size=12,color=C['muted'])

    # Physical influences are explained by the reports. The loss of buffer
    # can affect Buff1; the chosen advection cases enter the Can1 assessment.
    node(4.11,1.65,1.05,.76,'Buff1\nLimit\nadvection',engineering=True)
    node(5.47,1.65,1.04,.76,'Can1\nCorrosion\nbarrier',engineering=True)
    arrow((4.67,2.30),(4.20,2.08),'report',connectionstyle='arc3,rad=0.12')
    txt(5.30,2.17,'Mass loss',size=12,color=C['teal'])
    arrow((4.67,1.65),(4.90,1.65),'report')

    # A shared review workflow returns changed assumptions to both source
    # aspects and treatment scope. It is a proposed check, not an archive edge.
    review = FancyBboxPatch((.34,.32),2.58,.57,boxstyle='round,pad=0.025,rounding_size=0.06',
        facecolor=C['purple_fill'],edgecolor=C['purple'],linewidth=.85,zorder=3)
    change = FancyBboxPatch((3.45,.32),2.53,.57,boxstyle='round,pad=0.025,rounding_size=0.06',
        facecolor=C['white'],edgecolor=C['purple'],linewidth=.85,zorder=3)
    ax.add_patch(review);ax.add_patch(change)
    txt(1.63,.605,'Review source aspects\nand target scope',size=12,color=C['purple'])
    txt(4.715,.605,'Changed material or\nmodel assumptions',size=12,color=C['purple'])
    arrow((3.39,.605),(2.98,.605),'review')
    # Loop outside the panels, with two explicit arrowheads to the source nodes.
    verts=[(.30,.605),(.10,.605),(.10,4.59),(.30,4.59)]
    codes=[MplPath.MOVETO,MplPath.LINETO,MplPath.LINETO,MplPath.LINETO]
    ax.add_patch(PathPatch(MplPath(verts,codes),facecolor='none',edgecolor=C['purple'],
                          linewidth=1.0,linestyle=(0,(3.5,2.5)),zorder=2))
    arrow((.10,4.59),(.30,4.59),'review',lw=1.0,mutation=8)
    arrow((.10,2.65),(.30,2.65),'review',lw=1.0,mutation=8)

    # Compact visual key; the manuscript note defines the evidentiary meaning.
    for x,lab,kind in [(.34,'Stored relation','stored'),(2.42,'Safety report','report'),(4.28,'Review feedback','review')]:
        arrow((x,.105),(x+.28,.105),kind,lw=1.1,mutation=7)
        txt(x+.35,.105,lab,size=12,ha='left',color=C['muted'])

    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    warnings=[]
    for label,text,(x,y,w,h) in label_boxes:
        bb=text.get_window_extent(renderer)
        left,bottom=ax.transData.transform((x,y))
        right,top=ax.transData.transform((x+w,y+h))
        if bb.x0<left-1 or bb.x1>right+1 or bb.y0<bottom-1 or bb.y1>top+1:
            warnings.append(label.replace('\n',' / '))
    if warnings:
        raise RuntimeError('Node label exceeds its box: '+', '.join(warnings))
    base=output_dir/'Figure_2_Documentary_Pathways'
    png_bytes = BytesIO()
    fig.savefig(png_bytes, format='png', dpi=450)
    png_bytes.seek(0)
    with Image.open(png_bytes) as check_image:
        check_image.load()
    base.with_suffix('.png').write_bytes(png_bytes.getvalue())
    fig.savefig(base.with_suffix('.svg'),metadata={'Title':'Documentary routes, safety dependencies and assessment updates'})
    fig.savefig(base.with_suffix('.pdf'),metadata={'Title':'Documentary routes, safety dependencies and assessment updates','Author':'','Creator':'','Producer':'','CreationDate':None,'ModDate':None})
    plt.close(fig)
    return [str(base.with_suffix(s)) for s in ['.png','.svg','.pdf']]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    for result in draw(args.output_dir): print(result)
