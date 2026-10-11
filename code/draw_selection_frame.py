#!/usr/bin/env python3
"""Draw the report-page frame and the separate purposive passage register.

The page counts come from external_review_selection_accounting.csv. A proportional
bar partitions the 184 nonblank pages into disjoint groups: 83 keyword matches,
3 required summary-context pages, and 98 remaining indexed pages. A dashed locator
relation connects 42 passage records to their 26 source pages within the keyword
group. It does not represent an exhaustive passage selection or a PRISMA flow.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path as MplPath


def draw(accounting: Path, output: Path):
    with accounting.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    total = lambda field: sum(int(row[field]) for row in rows)
    n_reports = len(rows)
    physical = total("physical_pdf_pages")
    framed = total("frame_pages_including_blank")
    blank = total("frame_blank_pages")
    nonblank = framed - blank
    keyword = total("keyword_retrieved_pages")
    context = total("additional_context_pages")
    retrieved = keyword + context
    remaining = nonblank - retrieved
    locator_pages = total("pages_locating_selected_passages")
    passages = total("selected_passages")
    assert (n_reports, physical, framed, blank, nonblank, keyword, context,
            remaining, retrieved, locator_pages, passages) == (
                3, 256, 185, 1, 184, 83, 3, 98, 86, 26, 42)

    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 12,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "text.color": "#17303D", "axes.unicode_minus": False,
        "savefig.facecolor": "white", "savefig.edgecolor": "white",
    })
    fig = plt.figure(figsize=(6.2, 4.45), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 6.2), ylim=(0, 4.45))
    ax.axis("off")

    ink = "#254D60"
    gray = "#727D83"
    keyword_fill = "#D7E9F2"
    context_fill = "#68A995"
    context_ink = "#276B55"
    register_ink = "#655578"
    line_width = 1.05

    def label(x, y, text, ha="center", color=None, weight="normal", **kwargs):
        return ax.text(x, y, text, ha=ha, va="center", fontsize=12,
                       color=color or ink, fontweight=weight, linespacing=1.13,
                       **kwargs)

    def box(x, y, w, h, text, edge=ink, fill="white"):
        patch = FancyBboxPatch((x, y), w, h,
                               boxstyle="round,pad=0.01,rounding_size=0.05",
                               lw=line_width, ec=edge, fc=fill)
        ax.add_patch(patch)
        label(x+w/2, y+h/2, text, color=edge)
        return patch

    def arrow(points, color=ink, dashed=False, width=line_width, head=8):
        path = MplPath(points, [MplPath.MOVETO] + [MplPath.LINETO] * (len(points)-1))
        patch = FancyArrowPatch(path=path, arrowstyle="-|>", mutation_scale=head,
                                lw=width, ec=color, fc=color,
                                linestyle=(0, (3.2, 2.6)) if dashed else "solid",
                                capstyle="round", joinstyle="round")
        ax.add_patch(patch)
        return patch

    top_y, top_h, top_w = 3.68, 0.62, 1.66
    top_x = [0.24, 2.27, 4.30]
    box(top_x[0], top_y, top_w, top_h, f"{n_reports} reports\n{physical} PDF pages")
    box(top_x[1], top_y, top_w, top_h, f"Defined frame\n{framed} pages")
    box(top_x[2], top_y, top_w, top_h, f"Nonblank frame\n{nonblank} pages")
    arrow([(top_x[0]+top_w+0.03, top_y+top_h/2), (top_x[1]-0.03, top_y+top_h/2)])
    arrow([(top_x[1]+top_w+0.03, top_y+top_h/2), (top_x[2]-0.03, top_y+top_h/2)])

    # Scope removal and blank-page removal remain explicit, without suggesting
    # that the 71 pages outside the defined ranges were substantive exclusions.
    arrow([(top_x[0]+top_w/2, top_y-0.02), (top_x[0]+top_w/2, 3.46)], color=gray, head=6)
    label(top_x[0]+top_w/2, 3.28, f"{physical-framed} outside frame", color=gray)
    arrow([(top_x[1]+top_w/2, top_y-0.02), (top_x[1]+top_w/2, 3.46)], color=gray, head=6)
    label(top_x[1]+top_w/2, 3.28, f"{blank} blank page", color=gray)

    # Exact widths express mutually exclusive page counts, rather than a
    # distribution of favorable/critical statements.
    bx, by, bw, bh = 0.24, 2.45, 5.72, 0.62
    kw = bw * keyword / nonblank
    cw = bw * context / nonblank
    rw = bw - kw - cw
    ax.add_patch(Rectangle((bx, by), kw, bh, facecolor=keyword_fill,
                           edgecolor=ink, linewidth=line_width))
    ax.add_patch(Rectangle((bx+kw, by), cw, bh, facecolor=context_fill,
                           edgecolor=context_ink, linewidth=line_width))
    ax.add_patch(Rectangle((bx+kw+cw, by), rw, bh, facecolor="#F0F2F3",
                           edgecolor=gray, linewidth=line_width))
    label(bx+kw/2, by+bh/2, f"{keyword} keyword\nmatches")
    label(bx+kw+cw+rw/2, by+bh/2, f"{remaining} other pages\nretained in index", color="#47535A")
    # Connect the nonblank count to a bracket over the whole partition, rather
    # than to one component of the bar.
    ax.plot([bx, bx, bx+bw, bx+bw], [3.10, 3.15, 3.15, 3.10],
            color=ink, lw=line_width, solid_capstyle="round")
    arrow([(top_x[2]+top_w/2, top_y-0.02),
           (top_x[2]+top_w/2, 3.18)])

    # Bracket the keyword pages and additional context pages into the retrieval
    # frame. The page register remains separate from the passage register.
    union_right = bx + kw + cw
    union_mid = (bx + union_right) / 2
    ax.plot([bx, bx, union_right, union_right], [2.40, 2.29, 2.29, 2.40],
            color=context_ink, lw=line_width, solid_capstyle="round")
    arrow([(union_mid, 2.29), (union_mid, 2.06)], color=context_ink)
    box(0.24, 1.42, union_right-0.24, 0.59,
        f"{keyword} + {context} = {retrieved} pages\nin retrieval frame",
        edge=context_ink, fill="#EFF6F2")

    # Leader for the deliberately small context segment (3/184).
    context_mid = bx + kw + cw/2
    ax.plot([context_mid, context_mid, 3.20], [by-0.015, 2.40, 2.40],
            color=context_ink, lw=line_width)
    label(3.31, 2.23, f"{context} additional pages\nfrom required context",
          ha="left", color=context_ink)

    register_x, register_y, register_w, register_h = 3.65, 0.70, 2.31, 0.65
    box(register_x, register_y, register_w, register_h,
        f"{passages} purposively selected\npassage records",
        edge=register_ink, fill="#F5F2F7")
    relation_y = register_y + register_h/2
    # Arrow direction runs from records to their source locations. It does not
    # connect the retrieval-frame box to a purported final included sample.
    arrow([(register_x-0.02, relation_y), (0.085, relation_y),
           (0.085, by+bh/2), (bx-0.025, by+bh/2)],
          color=register_ink, dashed=True, head=8)
    label(1.91, relation_y, f"Locators on {locator_pages}\nmatched pages",
          color=register_ink,
          bbox={"facecolor":"white", "edgecolor":"none", "pad":2.6})

    # Compact line key; qualifications belong in the separate Word note.
    arrow([(0.28, 0.28), (0.69, 0.28)], head=7)
    label(0.82, 0.28, "Page counts", ha="left")
    arrow([(3.20, 0.28), (3.65, 0.28)], color=register_ink, dashed=True, head=7)
    label(3.79, 0.28, "Source locators", ha="left", color=register_ink)

    output.mkdir(parents=True, exist_ok=True)
    basename = output / "Figure_S1_Review_Page_Frame"
    for suffix in ("svg", "pdf", "png"):
        # Do not crop: the exact 6.2-inch width is the intended print size.
        fig.savefig(basename.with_suffix("." + suffix), dpi=300)
    plt.close(fig)
    print(f"Saved {basename}.[svg,pdf,png] at 6.2 × 4.45 inches, 12-point text.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    draw(args.accounting, args.output)


if __name__ == "__main__":
    main()
