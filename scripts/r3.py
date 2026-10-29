"""make ladder (R3 part): the regime layer L6–L8, its descriptive rows and the zoo (D3.1–D3.6) on 1986–2019 (development
scored 1990–2019), evaluated through the ablation table only (owner O2.4: no promotion walk; the R2 walk verdict stands).

Committed (statistics only): reports/r3/{metrics.csv, lines.csv, ablation.csv, ablation_context.csv, crisis.csv,
crisis_exposure.csv, placebo.csv, crash.json, facts.json}. Local only (gitignored, KF-derived daily series):
data/r3/books.parquet. Parents L1, L3, L4, L5 are rebuilt with R2's functions (vol-zoo forecasts cached), so they
equal R2's books (checked against data/r2/books.parquet when present). The test window 2020+ is not run here (R5).
"""

import hashlib
import json
import math
import time

import numpy as np
import pandas as pd
from quantkit import state as qstate
from quantkit.alloc.risk import max_div
from quantkit.stats.multitest import adjust_pvalues

from rspy import evaluate as ev
from rspy import paths, regime, rungs, volzoo
from rspy.data import build

t0 = time.perf_counter()
R2 = paths.rules()["r2"]
R3 = paths.rules()["r3"]
SC = [str(d) for d in R3["scored"]]
OUT = paths.REPORTS / "r3"
LOCAL = paths.data_dir() / "r3"
OUT.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)

# ---- inputs and parents (R2 constructions) ------------------------------------------------------------------------
panel = build.load()
inp = rungs.Inputs.from_panel(panel, "1986-01-02", SC[1])
idx = inp.index
dev = np.asarray(idx >= pd.Timestamp(SC[0]))
rows = rungs.decision_rows(idx, R2["tranche"]["record"])
scored_rows = rows & dev
B = R2["band"]["width"]
years = range(1989, int(SC[1][:4]))
T = {"L0": rungs.l0_target(inp), "L1": rungs.l1_target(panel, inp), "L3": rungs.l3_target(inp, rows),
     "L4": rungs.l4_target(inp, rows)}
r4 = rungs.log_book_returns(rungs.book(T["L4"], inp, band=B))
F4 = volzoo.forecasts(r4)
s5 = volzoo.stitched(F4, volzoo.select(F4, r4, years))
T["L5"] = rungs.vol_target(T["L4"], s5, idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
band = {r: B for r in ("L3", "L4", "L5")}
facts = {}


def check_keep(name, k):
    regime.check_coverage(name, k, scored_rows)


# ---- L6 (D3.1), L7 (D3.2), L8 (D3.3) and the descriptive rows: one tested code path (regime.targets) ----------------
RT = regime.targets(inp, rows, dev, T["L5"], band=B)
keep, g = RT["keep"], RT["g"]
for k_, v in keep.items():
    check_keep(k_, v)
T.update(RT["targets"])
for r in RT["targets"]:
    band[r] = B
c = inp.bill[dev]
x7, ov = RT["x7"], RT["overlay"]
jd = regime.crash_judge(x7)
crash = {"on": jd["on"], "sharpe": jd["sharpe"],
         "candidate": {k: jd["candidate"][k] for k in ("p_one_sided", "p", "p_uncentred")},
         "placebo": {k: jd["placebo"][k] for k in ("p_one_sided", "p", "p_uncentred")},
         "share_dev_days_g_below_1": float((ov.mult < 1).mean()), "min_g": float(ov.mult.min()),
         "max_dd_overlay_nav_excess": float(1 - (ov.nav / np.maximum.accumulate(ov.nav)).min()),
         "note": "judge is same-close (e_t earns r_{t+1}) on L7 excess returns; the L8 book adds the one-session lag "
                 "and costs (D3.3)"}
t_core = time.perf_counter() - t0

# ---- zoo (D3.6) ---------------------------------------------------------------------------------------------------------
zc = R3["zoo"]
gd = zc["gate_defaults"]
hmm = regime.cached("hmm", lambda r: qstate.hmm_regime(r, **gd), inp.R[:, 0], key=gd)
jm = regime.cached("jump", lambda r: qstate.jump_regime(r, **gd), inp.R[:, 0], key=gd)
keep["hmm"] = regime.state_keep(hmm, rows, lambda s: s > 0.5)
keep["jump"] = regime.state_keep(jm, rows, lambda s: s == 1)
check_keep("hmm", keep["hmm"])
check_keep("jump", keep["jump"])
T["hmm_gate"] = regime.gate(T["L5"], keep["hmm"])
T["jump_gate"] = regime.gate(T["L5"], keep["jump"])
mc = zc["min_cdar"]
mkw = {"window": mc["window"], "alpha": mc["alpha"], "floor": mc["floor"]}
Wm = regime.cached("min_cdar", lambda R: regime.min_cdar_weights(R, rows, **mkw), inp.R,
                   key={**mkw, "rows": hashlib.sha256(rows.tobytes()).hexdigest()})
rm = rungs.log_book_returns(rungs.book(Wm, inp, band=B))
Fm = volzoo.forecasts(rm)
Lm = volzoo.losses(Fm, rm)
ym = [y for y in years if int(Lm.loc[:f"{y}-12-31"].dropna().shape[0]) >= 252]
pm = volzoo.select(Fm, rm, ym)
T["min_cdar"] = rungs.vol_target(Wm, volzoo.stitched(Fm, pm), idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
band["hmm_gate"] = band["jump_gate"] = band["min_cdar"] = B
facts["min_cdar_first_pick_year_end"] = min(pm) if pm else None
facts["min_cdar_vol_default_until"] = f"{min(pm) + 1}-01-01 (ewma_slow before the first pick; disclosed)" if pm else None
facts["min_cdar_first_target"] = str(idx[np.isfinite(T["min_cdar"][:, 0])][0].date())
md = 0.0
for t in np.flatnonzero(rows & np.isfinite(T["L4"][:, 0])):
    win = inp.R[t - 62:t + 1]
    md = max(md, float(np.abs(max_div(win, cov=np.cov(win.T, ddof=1)) - T["L4"][t]).max()))
facts["max_div_minus_L4_max_abs"] = md
t_zoo = time.perf_counter() - t0

# ---- books ----------------------------------------------------------------------------------------------------------------
books = {r: rungs.book(tg, inp, band=band.get(r)) for r, tg in T.items()}
for r in ("L5", "L6", "L7", "L8"):
    for m_ in (2.0, 3.0):
        books[f"{r}@{m_:.0f}x"] = rungs.book(T[r], inp, band=B, cost_mult=m_)
for r in ("L1", "L3", "L5"):
    old = paths.data_dir() / "r2" / "books.parquet"
    if old.exists():
        facts[f"{r}_equals_r2_book"] = bool(np.array_equal(pd.read_parquet(old)[f"{r}_net"].to_numpy(), books[r].net))
first = {r: idx[np.isfinite(T[r][:, 0])][0] for r in T}
late = {r: str(d.date()) for r, d in first.items() if d >= pd.Timestamp(SC[0]) and r != "min_cdar"}
if late:
    raise RuntimeError(f"rungs without a decision before the scored window: {late}")
rate, dt = inp.mmy[dev], inp.dt[dev]
vol_ = lambda s_: float(np.std(s_, ddof=1) * math.sqrt(252))  # noqa: E731
D = pd.DatetimeIndex(idx[dev])
net = {r: b.net[dev] for r, b in books.items()}
mrows = []
for r, b in books.items():
    gr = np.abs(b.held).sum(axis=1)
    mrows.append({"rung": r, **ev.metrics(b.net[dev], c, b.turnover[dev], b.cost[dev], b.financing[dev], gr[dev])})
pd.DataFrame(mrows).to_csv(OUT / "metrics.csv", index=False, float_format="%.10g")
line = {r: ev.line(books[r].net, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"][dev]
        for r in ("L5", "L6", "L7", "L8")}
for r, v in line.items():
    if not np.isfinite(v).all():
        raise RuntimeError(f"{r}: the ex-ante line is not finite on every development row")
pd.DataFrame([{"rung": r, "line_vol": vol_(v), "line_cagr": ev.metrics(v, c)["cagr"], "line_cdar95": ev.cdar95(v),
               "line_max_dd": ev.metrics(v, c)["max_dd"]} for r, v in line.items()]).to_csv(
    OUT / "lines.csv", index=False, float_format="%.10g")
t_books = time.perf_counter() - t0

# ---- ablation table (D3.5) --------------------------------------------------------------------------------------------
MAIN = [("L6", "L5", "correlation regime -> TLT to cash"), ("L7", "L6", "per-asset trend (Faber 10m)"),
        ("L8", "L7", "crash rule (dd brake)")]
DESC = [("L6-63", "L5", "correlation regime, 63-day"), ("L6-th-0.2", "L5", "correlation regime, threshold -0.2"),
        ("L6-th+0.2", "L5", "correlation regime, threshold +0.2"), ("L7-on-L5", "L5", "trend without the correlation layer"),
        ("L7-63", "L6-63", "trend on the 63-day correlation rung"), ("hmm_gate", "L5", "zoo: HMM gate, SPY to cash"),
        ("jump_gate", "L5", "zoo: jump-model gate, SPY to cash"), ("min_cdar", "L5", "zoo: min-CDaR in place of inverse vol")]
abl = []
for child, parent, layer in MAIN + DESC:
    refs = {"parent": parent, "60/40 (L3)": "L3", "v1 (L1)": "L1", "SPY+T-bills line": None} if (child, parent, layer) in MAIN \
        else {"parent": parent}
    x = net[child]
    if child == "min_cdar":  # zoo row: compared on the rows where it is invested (warm-up ends 1989-01)
        assert first["min_cdar"] < pd.Timestamp(SC[0])
    for ref_name, ref in refs.items():
        y = line[child] if ref is None else net[ref]
        abl.append({"child": child, "layer": layer, "role": "rung" if (child, parent, layer) in MAIN else "descriptive",
                    "reference": ref_name, "reference_rung": ref or f"L0-line({child})",
                    **ev.ablation_row(x, y, c, rate, dt)})
abl = pd.DataFrame(abl)
abl["holm_p"] = adjust_pvalues(abl["p_one_sided"].to_numpy(), "holm")
abl["n_family"] = len(abl)
abl.to_csv(OUT / "ablation.csv", index=False, float_format="%.10g")
ctx = []  # R2's layers with the same intervals, for the "what each layer added" chart (not in the Holm family)
for child, parent, layer in [("L3", "L0", "add bonds 60/40"), ("L4", "L3", "risk weighting"),
                             ("L5", "L4", "portfolio vol target")]:
    ctx.append({"child": child, "layer": layer, "role": "context (R2, seen)", "reference": "parent",
                "reference_rung": parent, **ev.ablation_row(net[child], net[parent], c, rate, dt)})
pd.DataFrame(ctx).to_csv(OUT / "ablation_context.csv", index=False, float_format="%.10g")
t_abl = time.perf_counter() - t0

# ---- crisis windows at matched risk (owner: 1994, GFC, Q4 2018; all six computed) --------------------------------------
pos = ev.crisis_positions(D)
cr = []
for child, refs in [("L6", ["L5", "L3", "L0"]), ("L7", ["L6", "L3", "L0"]), ("L8", ["L7", "L3", "L0"]),
                    ("L7-on-L5", ["L5"]), ("L6-63", ["L5"])]:
    for ref in refs:
        for row in ev.crisis_matched(net[child], net[ref], c, rate, dt, pos):
            cr.append({"child": child, "reference": ref, "owner_window": row["crisis"] in
                       paths.prereg()["r3_evaluation"]["crisis_owner"], **row})
pd.DataFrame(cr).to_csv(OUT / "crisis.csv", index=False, float_format="%.10g")
ex = []
for r in ("L3", "L5", "L6", "L7", "L8"):
    h = books[r].held[dev]
    for k_, p in pos.items():
        ex.append({"rung": r, "crisis": k_, "w_spy": float(h[p, 0].mean()), "w_tlt": float(h[p, 1].mean()),
                   "w_cash": float(np.maximum(1 - h[p].sum(axis=1), 0).mean()),
                   "share_days_tlt_zero": float((h[p, 1] == 0).mean()), "share_days_spy_zero": float((h[p, 0] == 0).mean())})
pd.DataFrame(ex).to_csv(OUT / "crisis_exposure.csv", index=False, float_format="%.10g")

# ---- gate placebos (D3.4) -------------------------------------------------------------------------------------------------
pc = R3["placebo"]
GATES = {"L6": ("L5", T["L5"], keep["corr126"]), "L7": ("L6", T["L6"], keep["trend"]),
         "hmm_gate": ("L5", T["L5"], keep["hmm"]), "jump_gate": ("L5", T["L5"], keep["jump"])}
pl = []
for gname, (pname, ptarget, k) in GATES.items():
    x, y = net[gname], net[pname]
    gate_t = ev.ablation_row(x, y, c, rate, dt, draws=1)  # LW part only matters here (draws=1 for the dd part)

    def plc_net(block, seed, ptarget=ptarget, k=k):
        return rungs.book(regime.gate(ptarget, regime.shuffle_decisions(k, rows, dev, block=block, seed=seed)), inp,
                          band=B).net[dev]

    p0 = ev.ablation_row(plc_net(pc["block_months"], pc["seed"]), y, c, rate, dt, draws=1)
    p6 = ev.ablation_row(plc_net(pc["sensitivity_block_months"], pc["seed"]), y, c, rate, dt, draws=1)
    dist = np.array([ev.pair(plc_net(pc["block_months"], s), y, c, rate, dt)[0]
                     for s in range(pc["seeds_distribution"][0], pc["seeds_distribution"][1] + 1)])
    pl.append({"gate": gname, "parent": pname, "dsharpe_gate": gate_t["dsharpe"], "p_gate": gate_t["p_one_sided"],
               "dsharpe_placebo_seed0": p0["dsharpe"], "p_placebo_seed0": p0["p_one_sided"],
               "beats_placebo": bool(gate_t["p_one_sided"] < 0.05 and p0["p_one_sided"] >= 0.05),
               "percentile_among_100_seeds": float((dist < gate_t["dsharpe"]).mean() * 100),
               "placebo_dsharpe_median": float(np.median(dist)), "placebo_dsharpe_p05": float(np.quantile(dist, 0.05)),
               "placebo_dsharpe_p95": float(np.quantile(dist, 0.95)),
               "dsharpe_placebo_block6_seed0": p6["dsharpe"], "p_placebo_block6_seed0": p6["p_one_sided"]})
pd.DataFrame(pl).to_csv(OUT / "placebo.csv", index=False, float_format="%.10g")
t_plc = time.perf_counter() - t0

# ---- facts --------------------------------------------------------------------------------------------------------------------
gated = rungs.carry(keep["corr126"])[dev, 1] == 0
facts["L6_share_dev_days_tlt_gated"] = float(gated.mean())
facts["L6_vol_dev"], facts["L5_vol_dev"] = vol_(net["L6"]), vol_(net["L5"])
facts["L6_vol_gated_days"], facts["L5_vol_same_days"] = vol_(net["L6"][gated]), vol_(net["L5"][gated])
tr = rungs.carry(keep["trend"])[dev]
facts["trend_share_dev_days_spy_out"], facts["trend_share_dev_days_tlt_out"] = float((tr[:, 0] == 0).mean()), float(
    (tr[:, 1] == 0).mean())
facts["L7_share_dev_days_tlt_zero_target"] = float((T["L7"][dev, 1] == 0).mean())
facts["hmm_share_dev_decisions_turbulent"] = float((keep["hmm"][scored_rows, 0] == 0).mean())
facts["jump_share_dev_decisions_turbulent"] = float((keep["jump"][scored_rows, 0] == 0).mean())
facts["n_scored_decision_rows"] = int(scored_rows.sum())
facts["holm_family_size"] = len(abl)
facts["timing_s"] = {"core_targets": round(t_core, 2), "zoo": round(t_zoo - t_core, 2), "books": round(t_books - t_zoo, 2),
                     "ablation": round(t_abl - t_books, 2), "crisis_placebo": round(t_plc - t_abl, 2),
                     "total": round(time.perf_counter() - t0, 2)}
(OUT / "crash.json").write_text(json.dumps(crash, indent=1, default=float))
(OUT / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True, default=float))

# ---- local daily books for the curve figures (gitignored) ---------------------------------------------------------------------
loc = {"bill": inp.bill, "spy_proxy": inp.R[:, 0], "tlt_proxy": inp.R[:, 1], "corr126": regime.corr(inp, 126),
       "corr126_gate": rungs.carry(keep["corr126"])[:, 1], "trend_spy": rungs.carry(keep["trend"])[:, 0],
       "trend_tlt": rungs.carry(keep["trend"])[:, 1], "L8_g": g}
for r in ("L0", "L1", "L3", "L5", "L6", "L7", "L8"):
    loc[f"{r}_net"] = books[r].net
    loc[f"{r}_w_spy"], loc[f"{r}_w_tlt"] = books[r].held[:, 0], books[r].held[:, 1]
for r, v in line.items():
    loc[f"{r}_line"] = np.r_[np.full((~dev).sum(), np.nan), v]
pd.DataFrame(loc, index=idx).to_parquet(LOCAL / "books.parquet")

pd.set_option("display.width", 200)
print(pd.DataFrame(mrows).set_index("rung")[["cagr", "vol", "sharpe_excess", "max_dd", "cdar95", "turnover_pa"]]
      .round(4).to_string())
print(abl[["child", "reference", "dsharpe", "lo", "hi", "p_one_sided", "holm_p", "cdar_ratio", "cdar_lo", "cdar_hi",
           "maxdd_ratio"]].round(3).to_string(index=False))
print(pd.DataFrame(cr).query("owner_window")[["child", "reference", "crisis", "child_return", "parent_matched_return",
                                              "diff_matched"]].round(4).to_string(index=False))
print(pd.DataFrame(pl).round(3).to_string(index=False))
print("judge:", json.dumps(crash, default=float)[:400])
print("facts:", json.dumps(facts, default=float))
print(f"r3: {time.perf_counter() - t0:.1f} s")
