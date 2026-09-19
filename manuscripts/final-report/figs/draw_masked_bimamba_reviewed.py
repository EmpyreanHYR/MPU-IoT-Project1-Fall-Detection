#!/usr/bin/env python3
"""Draw the audited MaskedBiMamba architecture with editable vector outputs.

Run: uv run --no-project --with matplotlib draw_masked_bimamba_reviewed.py
Evidence: code/src/fallbench/models.py, data.py and the main/fold_0/seed_42
resolved_config.yaml in the frozen 2026-09-16 results. No model weights or
experimental results are synthesized by this drawing script.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 14,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'mathtext.fontset': 'dejavusans',
})
fig, ax = plt.subplots(figsize=(14.6, 8.1))
fig.subplots_adjust(left=0.008, right=.992, top=.985, bottom=.012)
ax.set_xlim(0,14.4); ax.set_ylim(0,8.0); ax.axis('off')
INK='#213547'; GRAY='#536471'; LINE='#8997A3'
BLUE='#EAF3FB'; TEAL='#E8F5F2'; AMBER='#FFF3D9'; PURPLE='#F1ECFA'; WHITE='#FFFFFF'

def text(x,y,s,size=14,weight='normal',color=INK,ha='center',va='center',**kw):
    return ax.text(x,y,s,fontsize=size,fontweight=weight,color=color,ha=ha,va=va,**kw)

def box(x,y,w,h,s,fill=BLUE,size=14,edge=LINE,dashed=False,lw=1.3):
    p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.015,rounding_size=0.07',
                     facecolor=fill,edgecolor=edge,linewidth=lw,
                     linestyle=(0,(4,3)) if dashed else '-')
    ax.add_patch(p)
    text(x+w/2,y+h/2,s,size=size,linespacing=1.33)
    return p

def arrow(a,b,color=INK,lw=1.5,style='-',connectionstyle='arc3,rad=0',head=13):
    p=FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=head,
                      linewidth=lw,color=color,linestyle=style,
                      connectionstyle=connectionstyle,shrinkA=2,shrinkB=2)
    ax.add_patch(p)
    return p

def path(points,color=INK,lw=1.5,style='-',head=True):
    for a,b in zip(points[:-2],points[1:-1]):
        ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=lw,linestyle=style)
    if head: arrow(points[-2],points[-1],color=color,lw=lw,style=style)
    else: ax.plot([points[-2][0],points[-1][0]],[points[-2][1],points[-1][1]],color=color,lw=lw,linestyle=style)

def panel(x,y,w,h,title):
    p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012,rounding_size=.10',
                     facecolor='#FBFCFE',edgecolor='#BFC9D1',linewidth=1.1)
    ax.add_patch(p)
    text(x+.18,y+h-.27,title,size=16,weight='bold',ha='left')

# (a) End-to-end network. Shapes omit the batch dimension.
panel(.12,5.60,14.16,2.26,'(a)  Full MaskedBiMamba: 1 s window, T = 30 samples')
y=6.22; h=.98
blocks=[
    (.30,1.61,'Pose input X\n12 × (x, y, c)\n30 × 36',BLUE,13.5),
    (2.14,1.52,'Frame masking\np = 0.15\nTRAIN ONLY',AMBER,13.5),
    (3.90,1.80,'Linear 36 → 64\n+ learned position\n30 × 64',BLUE,13.5),
    (5.94,1.82,'4-head attention\n+ residual + LN\n30 × 64',BLUE,13.5),
    (8.00,2.13,'Bidirectional Mamba\nfusion + LN (b)\n30 × 64',PURPLE,13.5),
    (10.37,1.67,'Quality-weighted\npooling (c)\n64',TEAL,13.5),
    (12.28,1.68,'Linear 64 → 2\nfall / non-fall\nlogits',BLUE,13.5),
]
for x,w,s,c,sz in blocks: box(x,y,w,h,s,c,size=sz,dashed=(c==AMBER))
for left,right in zip(blocks,blocks[1:]): arrow((left[0]+left[1],y+h/2),(right[0],y+h/2),head=11)
text(.31,5.89,'x and y: per-frame min–max normalization; c: joint confidence. Batch dimension omitted.',size=12.4,ha='left',color=GRAY)

# (b) Expanded bidirectional core.
panel(.12,.75,8.08,4.62,'(b)  Independent forward and backward Mamba stacks')
text(.36,4.71,'Both stacks: 2 residual layers; d_model = 64, d_state = 16, d_conv = 4, expand = 2',
     size=12.1,ha='left',color=GRAY)
box(.37,2.71,.80,1.02,'H',WHITE,size=16)
# Forward route.
box(1.57,3.77,2.10,.66,'Residual Mamba × 2',PURPLE,size=13.2)
box(4.02,3.77,1.53,.66,'Forward F\n30 × 64',WHITE,size=13)
path([(1.17,3.22),(1.37,3.22),(1.37,4.10),(1.57,4.10)],head=True)
arrow((3.67,4.10),(4.02,4.10))
# Reverse route.
box(1.50,2.03,.99,.72,'Reverse\ntime',WHITE,size=12.8)
box(2.80,2.03,2.10,.72,'Residual Mamba × 2',PURPLE,size=13.2)
box(5.21,2.03,1.03,.72,'Restore\ntime',WHITE,size=12.8)
path([(1.17,3.22),(1.36,3.22),(1.36,2.39),(1.50,2.39)])
arrow((2.49,2.39),(2.80,2.39)); arrow((4.90,2.39),(5.21,2.39))
# Combine aligned directional features.
box(6.62,2.20,1.31,1.97,'Concat\n64 + 64\n↓\nLinear\n128 → 64\n↓\nLayerNorm',PURPLE,size=12.7)
path([(5.55,4.10),(6.16,4.10),(6.16,3.79),(6.62,3.79)])
arrow((6.24,2.39),(6.62,2.39))
# Residual definition and non-causality note.
text(.40,1.57,r'Each residual layer:  $U^{(l+1)} = U^{(l)} + \mathrm{Mamba}_l(U^{(l)})$',size=13.8,ha='left')
text(.40,1.11,'Reverse outputs are realigned before fusion; both directions use the complete window.',
     size=12.2,ha='left',color=GRAY)

# (c) Quality branch and exact pooling operator.
panel(8.43,.75,5.85,4.62,'(c)  Quality gate and temporal pooling')
box(8.67,3.88,5.35,.66,'qₜ = [mean joint c, fraction c ≥ 0.2, box confidence]',TEAL,size=12.5)
box(8.67,2.72,2.36,.78,'Gate MLP\n3 → 32 → 1\nReLU, then sigmoid',TEAL,size=13.3)
box(11.43,2.72,2.59,.78,'Scalar weight aₜ\nclamp minimum 10⁻⁶\n30 × 1 per window',TEAL,size=13.3)
path([(11.34,3.88),(11.34,3.69),(9.85,3.69),(9.85,3.50)])
arrow((11.03,3.11),(11.43,3.11))
box(8.67,1.45,5.35,.86,r'$\mathbf{z}=\frac{\sum_t a_t\mathbf{h}_t}{\sum_t a_t}\ \in\ \mathbb{R}^{64}$',TEAL,size=19)
arrow((12.73,2.72),(12.73,2.31))
text(8.70,1.11,'qₜ bypasses the training-time pose mask.',size=12.7,ha='left',color=GRAY)

# A concise note distinguishes zero input from dropping sequence positions.
text(.24,.37,'Masking zeroes the full 36-D pose vector independently per frame; at least one frame is retained. It is disabled for evaluation.',
     size=12.7,ha='left',color=GRAY)

for suffix in ('pdf','svg','png'):
    dest = OUT / f'masked_bimamba_architecture_reviewed.{suffix}'
    fig.savefig(dest, dpi=300, facecolor='white')
    print(dest)
plt.close(fig)
