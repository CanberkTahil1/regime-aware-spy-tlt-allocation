"""R2 evaluation (D2.4, D2.5, D2.8): window metrics, the L0-line, the four-part promotion walk and timing luck.

Promotion (D2.4; prereg `promotion_rule`). Adapted from naive-vs-optimal `src/nvo/evaluate.py:344-440` and
`src/nvo/bench.py:43-51` @ 290cf2c (COPIED.md), with the advisor's departures: no `no_worse` / `crisis_return` gates, no
−0.03 floor (every leg is "no loss"), the CDaR-only step continues the walk, daily grid.
- quantkit part: `Ladder.promote` on daily bill-excess returns over the development window, each rung multiplied by
  one constant k_r = 0.10 / σ(excess) (√252) (Sharpe and the LW test unchanged; the MCS is on vol-matched returns);
  the 2× cost book scaled by the same k_r. Gives the Sharpe effect (≥ 0.05), the one-sided LW test, robustness (2× and
  Sharpe inside each development crisis) and the prefix 90% MCS.
- rspy legs: the incumbent rescaled ex post to the candidate's excess vol (`rescale`, financed above 1× at mmy + 25 bp,
  +75 bp in the stress leg); CDaR route: CDaR-95 (compounded, `quantkit.stats.drawdown.cdar`) of the candidate ≤ 0.85 ×
  the matched incumbent's; legs: 2× costs, +75 bp financing, each leave-one-crisis-out sample: ΔSharpe ≥ 0 (both
  routes) and, for the CDaR route, CDaR below the matched incumbent's.
- promoted = quantkit test ∧ robust ∧ MCS ∧ ((Sharpe effect ∧ legs) ∨ (CDaR route ∧ legs)). A CDaR-only promotion
  (quantkit stopped there) continues with a fresh pre-registered `Ladder` on [that rung, the remaining rungs].
Timing: statistics of finished development series; nothing dated after `knowledge_date` (quantkit refuses).
L0-line (D2.8): `quantkit.bench.vol_matched` ex ante, window 63, lag 1, financed above w = 1 at the rung's own lagged
money-market yield + 25 bp (dt calendar/360); the ex-post line descriptive.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd
from quantkit import bench as qbench
from quantkit.costs.financing import accrual
from quantkit.ladder import STOPPED, Ladder
from quantkit.stats import drawdown as qdd
from quantkit.stats import sharpe
from quantkit.stats.sharpe_diff import sharpe_diff_lw

from rspy import accounting, paths

ANN = 252


def sr(x) -> float:
    return float(sharpe(np.asarray(x, np.float64), ann=ANN))


def cdar95(x) -> float:
    return float(abs(qdd.cdar(np.asarray(x, np.float64), alpha=0.95)))


def metrics(net, bill, turnover=None, cost=None, fin=None, gross=None) -> dict:
    x, c = np.asarray(net, np.float64), np.asarray(bill, np.float64)
    n = len(x)
    e = x - c
    out = {"n": n, "cagr": float(np.prod(1 + x) ** (ANN / n) - 1), "vol": float(x.std(ddof=1) * math.sqrt(ANN)),
           "sharpe_excess": sr(e), "sortino": accounting.sortino(e), "max_dd": float(qdd.max_dd(x)),
           "cdar95": cdar95(x), "net_pa": float(x.mean() * ANN), "bill_pa": float(c.mean() * ANN)}
    for k, v in (("turnover_pa", turnover), ("cost_pa", cost), ("financing_pa", fin)):
        if v is not None:
            out[k] = float(np.mean(v) * ANN)
    if gross is not None:
        out["avg_gross"] = float(np.mean(gross))
    return out


# ---- the line --------------------------------------------------------------------------------------------------------
def line(net, hi20, bill, mmy, dt, mode: str = "ex_ante") -> dict:
    lc = paths.rules()["r2"]["line"]
    fin = {"rate": np.asarray(mmy, np.float64), "spread": paths.rules()["accounting"]["financing_spread_bp"] * 1e-4,
           "dt": np.asarray(dt, np.float64)}
    kw = {"window": lc["window"], "lag": lc["lag"]} if mode == "ex_ante" else {}
    return qbench.vol_matched(net, hi20, bill, mode=mode, financing=fin, ann=ANN, **kw)


def lw(x, y, *, seed: int = 0, draws: int = 1000, block: int = 21) -> dict:
    """Annualised ΔSharpe(x − y) of excess returns with the LW interval and one-sided p (H1: x > y)."""
    o = sharpe_diff_lw(np.asarray(x, np.float64), np.asarray(y, np.float64), block=block, draws=draws, seed=seed)
    a = math.sqrt(ANN)
    return {"dsharpe": o["diff"] * a, "lo": o["ci"][0] * a, "hi": o["ci"][1] * a, "p_one_sided": o["p_one_sided"]}


# ---- promotion ---------------------------------------------------------------------------------------------------------
def rescale(s, c, target_vol: float, rate, dt, *, spread_bp: float) -> np.ndarray:
    """s at `target_vol` (annualised excess vol), ex post; above k = 1 the borrowed notional pays rate + spread only
    (nvo bench.rescale, with this repo's per-row dt = calendar days / 360)."""
    s, c = np.asarray(s, np.float64), np.asarray(c, np.float64)
    k = target_vol / (np.std(s - c, ddof=1) * math.sqrt(ANN))
    fin = accrual(np.full(len(s), k), np.asarray(rate, np.float64), spread=spread_bp / 1e4, dt=np.asarray(dt))
    return k * s + max(1.0 - k, 0.0) * c - fin


def pair(x, y, c, rate, dt, spread_bp: float = 25.0) -> tuple[float, float, float]:
    """(ΔSharpe of x vs y matched to x's excess vol, CDaR-95 of x, CDaR-95 of matched y)."""
    ym = rescale(y, c, float(np.std(np.asarray(x) - c, ddof=1)) * math.sqrt(ANN), rate, dt, spread_bp=spread_bp)
    return sr(np.asarray(x) - c) - sr(ym - c), cdar95(x), cdar95(ym)


def crisis_positions(dates: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    out = {}
    for k, v in paths.prereg()["crisis_windows"].items():
        a, z = pd.Period(str(v["start"]), "M").start_time, pd.Period(str(v["end"]), "M").end_time
        p = np.flatnonzero((dates >= a) & (dates <= z))
        if len(p):
            out[k] = p
    return out


def legs(cand: dict, inc: dict, c, rate, dt, pos: dict) -> dict:
    """cand / inc: {"1x", "2x", "f75"} net return arrays (development rows)."""
    ds, cd_s, cd_b = pair(cand["1x"], inc["1x"], c, rate, dt)
    stress = {"cost_2x": pair(cand["2x"], inc["2x"], c, rate, dt),
              "financing_75": pair(cand["f75"], inc["f75"], c, rate, dt, spread_bp=100.0)}
    T = len(c)
    loco = {}
    for k, p in pos.items():
        keep = np.setdiff1d(np.arange(T), p)
        loco[k] = pair(cand["1x"][keep], inc["1x"][keep], c[keep], rate[keep], dt[keep])
    cd_change = cd_s / cd_b - 1.0 if cd_b > 0 else (0.0 if cd_s == 0 else math.inf)
    route_cdar = bool(cd_change <= -0.15)
    sharpe_ok = lambda v: v[0] >= 0  # noqa: E731
    cdar_ok = lambda v: v[0] >= 0 and v[1] < v[2]  # noqa: E731
    leg = {r: {"cost_2x": f(stress["cost_2x"]), "financing_75": f(stress["financing_75"]),
               "loco": all(f(v) for v in loco.values())} for r, f in (("sharpe", sharpe_ok), ("cdar", cdar_ok))}
    return {"dsharpe_matched": float(ds), "cdar_cand": cd_s, "cdar_inc_matched": cd_b, "cdar_change": float(cd_change),
            "route_cdar": route_cdar, "legs": leg, "dsharpe_2x": float(stress["cost_2x"][0]),
            "dsharpe_f75": float(stress["financing_75"][0]), "loco_dsharpe": {k: float(v[0]) for k, v in loco.items()}}


def ladder(name: str, rungs) -> Ladder:
    pr = paths.prereg()["promotion_rule"]
    dev = paths.prereg()["windows"]["development"]
    win = []
    for v in paths.prereg()["crisis_windows"].values():
        a, z = pd.Period(str(v["start"]), "M"), pd.Period(str(v["end"]), "M")
        if z.end_time <= pd.Timestamp(dev["end"]) + pd.Timedelta(days=1):
            win.append((a.start_time.date().isoformat(), z.end_time.date().isoformat()))
    return Ladder(name=name, rungs=tuple(rungs), metric="sharpe", test="lw",
                  min_effect=float(pr["min_effect"]["delta_sharpe"]), mean_block=float(pr["mean_block"]),
                  stress_windows=tuple(win), cost_mults=(1.0, 2.0), alpha=float(pr["alpha"]),
                  mcs_size=1.0 - float(pr["mcs"]["level"]), reps=int(pr["reps"]), seed=int(pr["seed"]), ann=float(ANN))


def walk(books: dict, c, rate, dt, dates: pd.DatetimeIndex, *, prereg_path, register_path, name: str = "r2_core") -> dict:
    """books {rung: {"1x", "2x", "f75"}} on the development rows, in walk order. Returns the steps and the winner."""
    pr = paths.prereg()["promotion_rule"]
    order = list(books)
    pos = crisis_positions(dates)
    kd = str(pr["knowledge_date"])
    steps, ladders = [], []
    start = 0
    while start < len(order) - 1:
        sub = order[start:]
        lad = ladder(name if start == 0 else f"{name}_from_{sub[0]}", sub)
        lad.preregister(prereg_path)
        ladders.append({"name": lad.name, "rungs": sub, "spec_hash": lad.spec_hash()})
        data = {}
        for r in sub:
            k = 0.10 / (np.std(books[r]["1x"] - c, ddof=1) * math.sqrt(ANN))
            data[r] = {1.0: k * (books[r]["1x"] - c), 2.0: k * (books[r]["2x"] - c)}
        q = lad.promote(data, dates=dates, prereg=prereg_path, register=register_path, knowledge_date=kd,
                        phase="R2")
        cont = None
        for st in q["steps"]:
            if st["status"] == STOPPED:
                break
            lg = legs(books[st["rung"]], books[st["incumbent"]], c, rate, dt, pos)
            p = st["parts"]
            base = p["test"] and p["robust"] and p["mcs"]
            via_sharpe = p["effect"] and all(lg["legs"]["sharpe"].values())
            via_cdar = lg["route_cdar"] and all(lg["legs"]["cdar"].values())
            ok = bool(base and (via_sharpe or via_cdar))
            steps.append({"rung": st["rung"], "incumbent": st["incumbent"], "ladder": lad.name, "quantkit": st,
                          "rspy": lg, "route": "sharpe" if (base and via_sharpe) else ("cdar" if ok else None),
                          "promoted": ok})
            if not ok:
                return {"steps": steps, "winner": st["incumbent"], "ladders": ladders, "mcs_all": q["mcs"]}
            if st["status"] != "promoted":  # CDaR-only promotion: quantkit stopped here; continue from this rung
                cont = order.index(st["rung"])
                break
        if cont is None:
            return {"steps": steps, "winner": q["winner"], "ladders": ladders, "mcs_all": q["mcs"]}
        start = cont
    return {"steps": steps, "winner": order[start], "ladders": ladders, "mcs_all": {}}


def chains(built) -> dict[str, list[str]]:
    """Post-hoc parent chains (owner O2.3; prereg `walk_chains`), each cut at its first rung not built yet (L6–L8 join in
    R3). A comparison row (L1) is never a parent: refuses a chain that contains one."""
    pr = paths.prereg()["promotion_rule"]
    out = {}
    for k, ch in pr["walk_chains"].items():
        if set(ch) & set(pr["comparison_rows"]):
            raise ValueError(f"chain {k} contains a comparison row ({pr['comparison_rows']}): never a parent")
        cut = next((i for i, r in enumerate(ch) if r not in built), len(ch))
        out[k] = list(ch[:cut])
    return out


def as_ladder(lad: Ladder, **kw) -> Ladder:
    return dataclasses.replace(lad, **kw)
