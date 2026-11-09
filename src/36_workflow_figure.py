"""Step 36: the workflow schematic (Figure 1).

Replaces the six-box chain drawn inside 11_referee_figures.py, which still
carried a baked-in "Figure 0" title and predated the uncertainty budget, the
Monte-Carlo propagation and the whole Greek application.

Four stages run left to right -- inputs, atlas construction, assessment,
application -- along one spine, with the comparison and ancillary layers
entering from a feeder band along the bottom so they do not cross the spine.
The three-scenario bracket is drawn as three rasters, since that bracket is
what distinguishes this product from an ordinary land-cover reclassification,
and each assessment and application box names the section that reports it, so
the figure doubles as a map of the paper. No title is drawn inside the image:
the caption carries it.

Outputs
  outputs/figures/fig0_workflow.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

import _env

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FIG = os.path.join(_env.OUTPUTS, "figures")

INK = "#1a1a1a"
EDGE = "#5a6670"
BAND = "#eef2f6"
C_IN = "#dce7f2"
C_BUILD = "#fbe3cc"
C_ASSESS = "#d9e8d3"
C_APPLY = "#cde5e1"
C_OUT = "#e7dcf0"
SCEN = [("lower", "#bdd7ec"), ("best", "#6ba3cb"), ("upper", "#2e6b9c")]

COL = [0.105, 0.355, 0.625, 0.886]
W = [0.185, 0.215, 0.215, 0.195]


def box(ax, x, y, w, h, text, fc, fs=7.5):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.010", fc=fc, ec=EDGE,
                                lw=0.9, zorder=3))
    lines = text.split("\n")
    step = min(0.040, (h - 0.028) / max(len(lines), 1))
    y0 = y + step * (len(lines) - 1) / 2
    for i, ln in enumerate(lines):
        ax.text(x, y0 - i * step, ln, ha="center", va="center", color=INK,
                fontsize=fs + (0.8 if i == 0 else 0),
                fontweight="bold" if i == 0 else "normal", zorder=4)


def arrow(ax, p0, p1, rad=0.0, lw=1.15, style=None):
    # above the boxes, so the heads are not hidden by the box they point at
    cs = style if style else "arc3,rad=%.2f" % rad
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=11,
                                 color=EDGE, lw=lw, zorder=5,
                                 connectionstyle=cs, shrinkA=3, shrinkB=4))


def main():
    fig, ax = plt.subplots(figsize=(13.2, 5.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for x, w, hd in zip(COL, W, ["Inputs", "Atlas construction",
                                 "Assessment", "Application"]):
        ax.add_patch(Rectangle((x - w / 2 - 0.016, 0.915), w + 0.032, 0.060,
                               fc=BAND, ec="none", zorder=1))
        ax.text(x, 0.945, hd, ha="center", va="center", fontsize=9.8,
                fontweight="bold", color=INK, zorder=4)

    # ------------------------------------------------------------- inputs
    box(ax, COL[0], 0.770, W[0], 0.125,
        "CORINE Land Cover 2018\n100 m, 44 Level-3 classes\nEPSG:3035", C_IN)
    box(ax, COL[0], 0.455, W[0], 0.110,
        "Administrative boundaries\nEurostat GISCO, GADM\n39 national polygons", C_IN)

    # -------------------------------------------------- atlas construction
    box(ax, COL[1], 0.770, W[1], 0.125,
        "Roughness look-up table\n44 classes → lower / best / upper\nfrom the hydraulic literature (Table A.1)",
        C_BUILD)

    # the three-scenario bracket
    sx, sy, sw, sh, gap = COL[1], 0.500, 0.055, 0.072, 0.012
    x0 = sx - (3 * sw + 2 * gap) / 2
    for i, (lab, c) in enumerate(SCEN):
        ax.add_patch(Rectangle((x0 + i * (sw + gap), sy - sh / 2), sw, sh,
                               fc=c, ec=EDGE, lw=0.8, zorder=3))
        ax.text(x0 + i * (sw + gap) + sw / 2, sy, lab, ha="center", va="center",
                fontsize=7.0, fontweight="bold", zorder=4,
                color="white" if i == 2 else INK)
    ax.text(sx, sy - 0.075, "Three co-registered pan-European\nManning's $n$ rasters, 100 m",
            ha="center", va="center", fontsize=7.5, color=INK, zorder=4)

    box(ax, COL[1], 0.250, W[1], 0.110,
        "Per-country extraction\nclip, statistics, provenance manifest\n39 states",
        C_BUILD)

    # --------------------------------------------------------- assessment
    box(ax, COL[2], 0.840, W[2], 0.118,
        "Cross-product consistency\nthree classifiers, seven regimes\ntwo regridding conventions  §4.4–4.7",
        C_ASSESS)
    box(ax, COL[2], 0.650, W[2], 0.108,
        "Uncertainty budget\ntable ≫ product > rule > grid\non one metric  §4.8", C_ASSESS)
    box(ax, COL[2], 0.440, W[2], 0.128,
        "Hydraulic propagation\nSFINCS 2-D, 721 simulations\ndeterministic and Monte-Carlo  §4.9–4.10",
        C_ASSESS)
    box(ax, COL[2], 0.235, W[2], 0.108,
        "Product extensions\nin-channel layer\ncanopy-density refinement  §4.13", C_ASSESS)

    # -------------------------------------------------------- application
    box(ax, COL[3], 0.690, W[3], 0.230,
        "Greece\nnational field  §4.11\nriver corridors and basins  §4.12\nfive floodplain landscapes  §4.14\nLakes Koronia and Volvi  §4.15",
        C_APPLY)
    box(ax, COL[3], 0.330, W[3], 0.145,
        "Open release\nper-country GeoTIFFs\nlook-up tables and code\nstudy-site KML", C_OUT)

    # ------------------------------------------------------- feeder band
    fb_x, fb_y, fb_w, fb_h = 0.300, 0.072, 0.560, 0.080
    ax.add_patch(FancyBboxPatch((fb_x - fb_w / 2, fb_y - fb_h / 2), fb_w, fb_h,
                                boxstyle="round,pad=0.010", fc=C_IN, ec=EDGE,
                                lw=0.9, zorder=3))
    ax.text(fb_x, fb_y + 0.016, "Comparison and ancillary layers", ha="center",
            va="center", fontsize=8.3, fontweight="bold", color=INK, zorder=4)
    ax.text(fb_x, fb_y - 0.016,
            "ESA WorldCover 2021 and CLCplus Backbone 2018 (10 m)  ·  "
            "HRL Tree Cover Density  ·  HydroRIVERS v1.0",
            ha="center", va="center", fontsize=7.4, color=INK, zorder=4)

    # ------------------------------------------------------------ arrows
    arrow(ax, (COL[0] + W[0] / 2, 0.770), (COL[1] - W[1] / 2, 0.770))
    arrow(ax, (COL[1], 0.705), (COL[1], 0.545))
    arrow(ax, (COL[1], 0.400), (COL[1], 0.307))
    arrow(ax, (COL[0] + W[0] / 2, 0.455), (COL[1] - W[1] / 2, 0.268), rad=-0.12)

    right2 = COL[1] + W[1] / 2
    left3 = COL[2] - W[2] / 2
    for y, rad in ((0.840, -0.16), (0.650, -0.08), (0.440, 0.04)):
        arrow(ax, (right2, 0.250), (left3, y), rad=rad)

    # feeder band into the two analyses that use those layers; the longer of
    # the two is routed as an elbow up the empty gap between the columns
    arrow(ax, (fb_x + fb_w / 2, 0.072), (left3, 0.215), rad=-0.10)
    arrow(ax, (0.500, 0.112), (left3, 0.840),
          style="angle,angleA=90,angleB=180,rad=12")

    right3 = COL[2] + W[2] / 2
    left4 = COL[3] - W[3] / 2
    arrow(ax, (right3, 0.650), (left4, 0.720), rad=-0.10)
    arrow(ax, (right3, 0.440), (left4, 0.650), rad=-0.10)
    arrow(ax, (right3, 0.235), (left4, 0.360), rad=-0.12)
    arrow(ax, (COL[3], 0.575), (COL[3], 0.403))

    out = os.path.join(FIG, "fig0_workflow.png")
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    fig.savefig(out, dpi=_env.FIGDPI)
    plt.close(fig)
    print("wrote", out, "at %d dpi" % _env.FIGDPI)


if __name__ == "__main__":
    main()
