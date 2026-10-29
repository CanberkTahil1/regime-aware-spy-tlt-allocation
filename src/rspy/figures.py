"""Headline figures via `quantkit.viz.headline` (owner O2.1): growth of $1 with drawdown underneath, crisis shading, the
inset table (CAGR, excess Sharpe over H.15 bills, max DD, worst year). Written to the gitignored
reports/figures_local/Rn/ only (owner O1.1: curves traced from KF/Yahoo/Cboe-derived series are never committed).

- `NAMES`: the readable line names the owner fixed (rung id → label); the first line passed is the emphasised one.
- `SHORT`: the chart labels (owner O2.2: readable abbreviations, full names in the footer key). viz.headline v0.19.2
  raises when "<name>  $<end>" leaves the figure (any label over ~17 characters, measured 2026-10-28); room for longer
  labels is an optional quantkit Q15 carry-over (reports/quantkit_carryovers.md). `save_headline` prints the key.
- `crises(start, end)`: the pre-registered crisis windows (spec/prereg.yaml) that overlap [start, end], labelled.
- `save_headline(lines, rf, out, name, **kw)`: `viz.headline` → out/name.svg + out/name.png (300 dpi); returns its table.
Timing: a picture of finished series (no signal). Numbers: quantkit computes the table from the same series.
"""

from __future__ import annotations

import pathlib
import textwrap

import pandas as pd
from quantkit import viz

from rspy import paths

NAMES = {"L0": "SPY", "L1": "v1 legacy", "L2": "Vol-targeted SPY", "L3": "60/40", "L4": "Inverse-vol SPY/TLT",
         "L5": "Inverse-vol + vol target", "L0-line": "SPY+T-bills at matched vol"}
SHORT = {"v1 legacy": "v1", "Vol-targeted SPY": "VT SPY", "Inverse-vol SPY/TLT": "InvVol",
         "Inverse-vol + vol target": "InvVol+VT", "SPY+T-bills at matched vol": "SPY+bills"}
CRISIS_LABELS = {"bonds_1994": "1994 bonds", "dotcom": "Dot-com", "gfc": "GFC", "euro_2011": "Euro 2011",
                 "china_2015": "China 2015", "q4_2018": "Q4 2018", "covid": "Covid", "infl_2022": "2022 inflation"}
FOOTER = ("SPY = SPY proxy (Ken French Hi 20, value-weighted, daily); TLT = " + paths.rules()["bonds"]["label"]
          + "; T-bills = H.15 3-month. Net of costs and financing (charter accounting).")


def crises(start, end) -> list:
    a, z = pd.Timestamp(start), pd.Timestamp(end)
    w = {}
    for k, v in paths.prereg()["crisis_windows"].items():
        s, e = pd.Period(str(v["start"]), "M").start_time, pd.Period(str(v["end"]), "M").end_time.normalize()
        if s <= z and e >= a:
            w[k] = (max(s, a), min(e, z))
    return viz.crisis_windows_from(w, {k: CRISIS_LABELS[k] for k in w})


def save_headline(lines: dict[str, pd.Series], rf: pd.Series, out: pathlib.Path, name: str, *, tier: str, title: str,
                  subtitle: str, footer: str = FOOTER, crisis=None) -> dict:
    idx = next(iter(lines.values())).index
    key = [f"{SHORT[n]} = {n}" for n in lines if n in SHORT]
    lines = {SHORT.get(n, n): v for n, v in lines.items()}
    if key:
        footer = footer + " Key: " + "; ".join(key) + "."
    footer = "\n".join(textwrap.wrap(footer, 150))  # viz.headline raises on a footer line wider than the figure
    h = viz.headline(lines, rf, tier=tier, crises=crises(idx[0], idx[-1]) if crisis is None else crisis, title=title,
                     subtitle=subtitle, footer=footer, data_cut=str(idx[-1].date()))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.svg").write_text(h.svg())
    (out / f"{name}.png").write_bytes(h.png())
    return h.table


# ---- R2 matplotlib figures: the R1 scripts' palette (dataviz reference slots, validated in R1) --------------------------
BLUE, ORANGE, AQUA, YELLOW, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
INK, INK2, MUTED, GRID, BASE, SURF, NEUTRAL = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#52514e"
RC = {"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
      "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
      "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
      "axes.titleweight": "bold", "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2}


def save(fig, out: pathlib.Path, name: str) -> None:
    import matplotlib.pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({"svg.hashsalt": "rspy"}):  # deterministic SVG ids and no date: a rerun leaves no diff
        fig.savefig(out / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
        fig.savefig(out / f"{name}.png", dpi=160, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
