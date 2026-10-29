"""make ladder (R4 part): robustness, costs and the three O3.1 zoo rows (D4.1–D4.7; spec/prereg.yaml r4_zoo,
r4_evaluation; rules.yaml r4) on 1986–2019, development 1990–2019 scored. Every number is descriptive: "built rungs;
none promoted" (R2 walk seats L1, post-hoc chains seat L0, R3 not walked per O2.4). 2020+ is never touched (R5).

Committed (statistics only): reports/r4/{zoo.csv, costs.csv, loco.csv, decades.csv, rolling.csv, power.csv,
power_planning.csv, waterfall.csv, sensitivity.csv, dsr.csv, pbo.csv, facts.json}. Local only (gitignored, KF-derived
daily series): data/r4/books.parquet, data/r4/rolling.parquet. The base ladder is rebuilt with R2/R3's own functions
(`robust.build_core`) and checked bit for bit against data/r2 and data/r3 books before anything is computed on it.
"""

import hashlib
import json
import math
import pathlib
import time

import numpy as np
import pandas as pd
from quantkit import sizing
from quantkit.alloc.risk import max_div
from quantkit.stats import dsr, dsr_effective, effective_trials, pbo
from quantkit.stats.power import HEADER, periods_needed, power, power_table
from quantkit.vol import shuffle_blocks

from rspy import accounting, paths, regime, robust, rungs, volzoo
from rspy import evaluate as ev
from rspy.data import build

t0 = time.perf_counter()
timing = {}


def lap(k):
    timing[k] = round(time.perf_counter() - t0, 2)


R2, R3, R4 = (paths.rules()[k] for k in ("r2", "r3", "r4"))
PE = paths.prereg()["r4_evaluation"]
SC = [str(d) for d in R4["scored"]]
OUT = paths.REPORTS / "r4"
LOCAL = paths.data_dir() / "r4"
OUT.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)
ANN = 252
SP = paths.rules()["accounting"]["financing_spread_bp"]

# ---- the base ladder, checked against R2 / R3 -----------------------------------------------------------------------
panel = build.load()
# v1's grid first (D4.6), while this process is still small: the pool and the full book set never overlap (perf pass)
key = hashlib.sha256()
key.update(panel.loc["1986-01-02":SC[1]].to_numpy(np.float64).tobytes())
for f in sorted((paths.ROOT / "legacy").rglob("*.py")) + [paths.ROOT / "spec/rules.yaml", paths.ROOT / "src/rspy/robust.py",
                                                         paths.ROOT / "src/rspy/accounting.py",
                                                         paths.ROOT / "src/rspy/rungs.py",
                                                         paths.ROOT / "src/rspy/legacy_bridge.py"]:
    key.update(f.read_bytes())
gcache = paths.ROOT / ".cache" / "r4" / f"v1_grid_{key.hexdigest()[:20]}.parquet"
if gcache.exists():
    VG = pd.read_parquet(gcache).to_numpy()
else:
    VG = robust.v1_grid_net(paths.data_dir() / "panel.parquet", workers=1)  # perf pass: each loky worker is ~500 MB; 4 workers peaked at 2.36 GB summed, 2 at 1.78 GB
    gcache.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(VG, columns=[str(i) for i in range(VG.shape[1])]).to_parquet(gcache)
base = robust.build_core(panel)
inp, rows, dev = base.inp, base.rows, base.dev
idx = inp.index
c, rate, dt = inp.bill[dev], inp.mmy[dev], inp.dt[dev]
D = pd.DatetimeIndex(idx[dev])
RUNGS = list(PE["rungs"])
PAR = dict(PE["parents"])
facts = {"label": PE["label"]}
B1 = {r: robust.book(base, r) for r in RUNGS}
for tag, f, names in (("r2", "r2", ["L0", "L1", "L2", "L3", "L4", "L5", "L5-lev"]), ("r3", "r3", ["L6", "L7", "L8"])):
    old = paths.data_dir() / f / "books.parquet"
    if old.exists():
        o = pd.read_parquet(old)
        for r in names:
            facts[f"{r}_equals_{tag}_book"] = bool(np.array_equal(o[f"{r}_net"].to_numpy(), B1[r].net))
bad = [k for k, v in facts.items() if k.endswith("_book") and v is False]
if bad:
    raise RuntimeError(f"the rebuilt base ladder differs from the stored R2/R3 books: {bad}")
net = {r: b.net[dev] for r, b in B1.items()}
line = {r: ev.line(B1[r].net, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"][dev] for r in RUNGS}
for r, v in line.items():
    if not np.isfinite(v).all():
        raise RuntimeError(f"{r}: the ex-ante line is not finite on every development row")
lap("v1_grid_and_base")

# ---- O3.1 zoo rows (D4.1, D4.2) -------------------------------------------------------------------------------------------
keep_ov = {k: robust.overlay_keep(base.panel, inp, k) for k in ("spread", "bollinger")}
TZ = {"v1_spread_overlay_on_L5": regime.gate(base.T["L5"], keep_ov["spread"]),
      "v1_bollinger_overlay_on_L5": regime.gate(base.T["L5"], keep_ov["bollinger"])}
G = robust.gbm_predict(base, n_jobs=1)
sig = {h: robust.gbm_sigma(base, G["log_sigma_gbm"], h) for h in (R4["gbm"]["haircut"], 0.0)}
TZ["gbm_risk_sizing"] = robust.gbm_target(base, sig[R4["gbm"]["haircut"]])
TZ["gbm_risk_sizing_raw"] = robust.gbm_target(base, sig[0.0])
ZB = {k: robust.book(base, k, v) for k, v in TZ.items()}
for k, kp in keep_ov.items():
    facts[f"{k}_share_dev_days_spy_to_cash"] = float((kp[dev, 0] == 0).mean())
    facts[f"{k}_share_dev_days_tlt_to_cash"] = float((kp[dev, 1] == 0).mean())
lz = 0.5 * np.log(ANN * base.s5.reindex(idx).to_numpy())
pg = G["log_sigma_gbm"]
ok = dev & np.isfinite(pg)
facts["gbm"] = {"n_usable_rows": G["n_usable"], "n_splits": G["n_splits"], "first_prediction": G["first_pred"],
                "dev_rows_without_prediction_use_sigma_zoo": G["dropped_dev_rows"],
                "corr_log_sigma_gbm_vs_zoo_dev": float(np.corrcoef(pg[ok], lz[ok])[0, 1]),
                "mean_log_gap_gbm_minus_zoo_dev": float(np.mean(pg[ok] - lz[ok])),
                "fit_cv_flags": {k: v for k, v in G["flags"].items() if np.ndim(v) == 0}}
zrows = []
for k, b in ZB.items():
    x = b.net[dev]
    ln = ev.line(b.net, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"][dev]
    m = ev.metrics(x, c, b.turnover[dev], b.cost[dev], b.financing[dev])
    for ref_name, y in (("L5 (parent)", net["L5"]), ("SPY+T-bills line", ln)):
        zrows.append({"row": k, "reference": ref_name, "sharpe": m["sharpe_excess"], "vol": m["vol"],
                      "turnover_pa": m["turnover_pa"], "cost_pa": m["cost_pa"], **ev.ablation_row(x, y, c, rate, dt)})
zoo = pd.DataFrame(zrows)
zoo.to_csv(OUT / "zoo.csv", index=False, float_format="%.10g")
lap("zoo")

# ---- robustness on the built rungs (D4.4) ---------------------------------------------------------------------------------
COST = {"1x": {}, "2x": {"cost_mult": 2.0}, "3x": {"cost_mult": 3.0}, "f75": {"stress_bp": R4["costs"]["financing_extra_bp"]}}
BK = {r: {k: (B1[r] if k == "1x" else robust.book(base, r, **kw)) for k, kw in COST.items()} for r in RUNGS}


def refs(r):
    cm = PE["comparisons"]
    out = [PAR[r]] if r in PAR else []
    out += [x for x in (cm[r] if r in cm else cm["all"]) if x != r and x not in out]
    return out


def ref_series(ref, r, k="1x"):
    return line[r] if ref == "line" else BK[ref][k].net[dev]


crows, wrows = [], []
kw0 = rungs.acc_kw()
for r in RUNGS:
    for k, kw in COST.items():
        b = BK[r][k]
        x = b.net[dev]
        g = np.abs(b.held).sum(axis=1)
        m = ev.metrics(x, c, b.turnover[dev], b.cost[dev], b.financing[dev], g[dev])
        bs = accounting.run(base.T[r], inp.R, inp.bill, inp.mmy, inp.dt, cost_rates=kw0["cost_rates"] * np.array([1.0, 0.0]),
                            spread=kw0["spread"], stress_spread=kw.get("stress_bp", 0.0) * 1e-4,
                            cost_mult=kw.get("cost_mult", 1.0), band=None if r in robust.UNBANDED else base.band,
                            index=idx)
        sl = lambda bk: type(bk)(*(getattr(bk, f)[dev] if f != "index" else bk.index[dev]  # noqa: E731
                                   for f in ("index", "held", "gross", "cash", "financing", "cost", "net", "turnover",
                                             "traded")))
        wrows.append({"rung": r, "book": k, **robust.waterfall(sl(b), sl(bs), c)})
        for ref in refs(r):
            y = ref_series(ref, r, k)
            row = {"rung": r, "book": k, "reference": ref, "sharpe": m["sharpe_excess"], "cagr": m["cagr"],
                   "vol": m["vol"], "max_dd": m["max_dd"], "turnover_pa": m["turnover_pa"], "cost_pa": m["cost_pa"],
                   "financing_pa": m["financing_pa"], "cdar95": m["cdar95"], "max_gross": float(g[dev].max())}
            if k == "1x":
                try:
                    row |= ev.ablation_row(x, y, c, rate, dt)
                except ValueError as err:  # L0 vs its own line: the line at SPY's own vol is ~SPY (LW moments degenerate)
                    row |= {"dsharpe": ev.pair(x, y, c, rate, dt)[0], "note": f"no interval: {err}"}
            else:
                row["dsharpe"] = ev.pair(x, y, c, rate, dt, spread_bp=SP + (75 if k == "f75" else 0))[0]
            crows.append(row)
for r in RUNGS:  # E4.6: a book that never borrows is untouched by the financing stress, bit for bit
    facts[f"{r}_f75_net_equals_1x"] = bool(np.array_equal(BK[r]["f75"].net, B1[r].net))
costs = pd.DataFrame(crows)
costs.to_csv(OUT / "costs.csv", index=False, float_format="%.10g")
pd.DataFrame(wrows).to_csv(OUT / "waterfall.csv", index=False, float_format="%.10g")
lap("costs_waterfall")

pos = ev.crisis_positions(D)
PAIRS = [(r, ref) for r in RUNGS for ref in refs(r)]
matched = {}
for r, ref in PAIRS:
    x = net[r]
    matched[(r, ref)] = ev.rescale(ref_series(ref, r), c, float(np.std(x - c, ddof=1)) * math.sqrt(ANN), rate, dt,
                                   spread_bp=SP)
lrows, drows = [], []
T_ = len(c)
for (r, ref), ym in matched.items():
    x = net[r]
    full = ev.sr(x - c) - ev.sr(ym - c)
    for k, p in pos.items():
        kp = np.setdiff1d(np.arange(T_), p)
        d_ = ev.sr(x[kp] - c[kp]) - ev.sr(ym[kp] - c[kp])
        lrows.append({"rung": r, "reference": ref, "dropped": k, "dsharpe_full": full, "dsharpe_dropped": d_,
                      "change": d_ - full, "sign_flip": bool(np.sign(d_) != np.sign(full))})
    for a, z in PE["decades"]:
        p = np.flatnonzero((D >= pd.Timestamp(str(a))) & (D <= pd.Timestamp(str(z))))
        drows.append({"rung": r, "reference": ref, "decade": f"{str(a)[:4]}s",
                      "dsharpe": ev.sr(x[p] - c[p]) - ev.sr(ym[p] - c[p])})
for r in RUNGS:
    for a, z in PE["decades"]:
        p = np.flatnonzero((D >= pd.Timestamp(str(a))) & (D <= pd.Timestamp(str(z))))
        b = B1[r]
        m = ev.metrics(net[r][p], c[p], b.turnover[dev][p], b.cost[dev][p], b.financing[dev][p])
        drows.append({"rung": r, "reference": None, "decade": f"{str(a)[:4]}s", "sharpe": m["sharpe_excess"],
                      "cagr": m["cagr"], "vol": m["vol"], "max_dd": m["max_dd"]})
pd.DataFrame(lrows).to_csv(OUT / "loco.csv", index=False, float_format="%.10g")
pd.DataFrame(drows).to_csv(OUT / "decades.csv", index=False, float_format="%.10g")

W = R4["rolling_sessions"]


def roll_sr(e):
    s = pd.Series(e)
    return (s.rolling(W, min_periods=W).mean() / s.rolling(W, min_periods=W).std(ddof=1) * math.sqrt(ANN)).to_numpy()


roll = {f"{r}_sr": roll_sr(net[r] - c) for r in RUNGS}
rrows = []
for r in RUNGS:
    v = roll[f"{r}_sr"]
    v = v[np.isfinite(v)]
    rrows.append({"rung": r, "reference": None, "stat": "excess_sharpe", "n_windows": len(v), "share_pos": float((v > 0).mean()),
                  "min": float(v.min()), "median": float(np.median(v)), "max": float(v.max())})
for (r, ref), ym in matched.items():
    dv = roll_sr(net[r] - c) - roll_sr(ym - c)
    roll[f"{r}_vs_{ref}_dsr"] = dv
    v = dv[np.isfinite(dv)]
    rrows.append({"rung": r, "reference": ref, "stat": "dsharpe_matched_once", "n_windows": len(v),
                  "share_pos": float((v > 0).mean()), "min": float(v.min()), "median": float(np.median(v)),
                  "max": float(v.max())})
pd.DataFrame(rrows).to_csv(OUT / "rolling.csv", index=False, float_format="%.10g")

prow = []
P_ = R4["power"]
for (r, ref), ym in matched.items():
    x, y = net[r] - c, ym - c
    s1, s2 = ev.sr(x) / math.sqrt(ANN), ev.sr(y) / math.sqrt(ANN)
    rho = float(np.corrcoef(x, y)[0, 1])
    need = periods_needed(s1, s2, rho, P_["target"], P_["alpha"]) / ANN
    prow.append({"rung": r, "reference": ref, "dsharpe": (s1 - s2) * math.sqrt(ANN), "rho": rho,
                 "power_at_30y": power(s1, s2, rho, len(x), P_["alpha"]),
                 "years_needed": need, "years_needed_label": "inf (measured edge <= 0)" if not np.isfinite(need) else
                 f"{need:.1f}", "header": HEADER, "label": PE["power"]["label"]})
pd.DataFrame(prow).to_csv(OUT / "power.csv", index=False, float_format="%.10g")
pt = power_table(sr_base=ev.sr(net["L5"] - c), alpha=P_["alpha"], target=P_["target"])
pt["header"] = pt.attrs.get("header", HEADER)
pt.to_csv(OUT / "power_planning.csv", index=False, float_format="%.10g")
lap("loco_decades_rolling_power")

# ---- sensitivity (D4.5): one factor at a time vs the registered rung -----------------------------------------------------------
S = R4["sensitivity"]
srows, sens_net = [], {}


def sens(core, tag, names, factor, value):
    for r in names:
        b = robust.book(core, r)
        x = b.net[dev]
        sens_net[f"{r}@{tag}"] = x
        ln = ev.line(b.net, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"][dev]
        m = ev.metrics(x, c, b.turnover[dev], b.cost[dev], b.financing[dev])
        row = {"variant": f"{r}@{tag}", "rung": r, "factor": factor, "value": value, "sharpe": m["sharpe_excess"],
               "cagr": m["cagr"], "vol": m["vol"], "max_dd": m["max_dd"], "cdar95": m["cdar95"],
               "turnover_pa": m["turnover_pa"], "cost_pa": m["cost_pa"],
               "registered_sharpe": ev.sr(net[r] - c), "registered_turnover_pa": float(B1[r].turnover[dev].mean() * ANN),
               "dsharpe_vs_line": ev.pair(x, ln, c, rate, dt)[0]}
        row |= {f"vs_registered_{k}": v for k, v in ev.ablation_row(x, net[r], c, rate, dt).items()}
        srows.append(row)
    return core


MAT_RUNGS = PE["sensitivity"]["maturity"]["rungs"]
BC_RUNGS = PE["sensitivity"]["band_pp"]["rungs"]
for mty in S["maturities"]:
    cm_ = sens(robust.build_core(panel, maturity=mty), f"{mty}y", MAT_RUNGS, "maturity_years", mty)
    l6, l5 = robust.book(cm_, "L6").net[dev], robust.book(cm_, "L5").net[dev]
    for row in ev.crisis_matched(l6, l5, c, rate, dt, pos):
        if row["crisis"] == "bonds_1994":
            facts[f"L6_minus_L5_matched_1994_{mty}y"] = row["diff_matched"]
for row in ev.crisis_matched(net["L6"], net["L5"], c, rate, dt, pos):
    if row["crisis"] == "bonds_1994":
        facts["L6_minus_L5_matched_1994_25y"] = row["diff_matched"]
for w in S["band_widths"]:
    sens(robust.build_core(panel, band=w, l1=False), f"band{w * 100:g}pp", BC_RUNGS, "band_pp", w * 100)
sens(robust.build_core(panel, quarterly=True, l1=False), "quarterly", BC_RUNGS, "calendar", "quarterly")
sensitivity = pd.DataFrame(srows)
sensitivity.to_csv(OUT / "sensitivity.csv", index=False, float_format="%.10g")
facts["n_sensitivity_books"] = len(srows)
lap("sensitivity")

# ---- the DSR trial pool (D4.6): every registered row with a series + v1's grid on permitted data ---------------------------
pool = {}  # name -> development excess returns


def add(name, x_net):
    pool[name] = np.asarray(x_net, np.float64) - c


for r in ("L1", "L2", "L3", "L4", "L5", "L5-lev"):
    add(r, net[r])
spy = np.full((len(idx), 2), np.nan)
spy[0] = (1.0, 0.0)
r0 = pd.Series(np.log1p(inp.R[:, 0]), idx)
F0 = volzoo.forecasts(r0)
yrs = range(1989, int(SC[1][:4]))
T2u = rungs.vol_target(spy, volzoo.stitched(F0, robust.picks_cached(F0, r0, yrs)), idx, R2["L2u"]["target_vol"],
                       R2["L2u"]["cap"])
add("L2-u", rungs.book(T2u, inp).net[dev])
add("L4b", rungs.book(rungs.l4b_target(inp, rows), inp, band=base.band).net[dev])
F4 = volzoo.forecasts(base.r4)
for mname in F4:
    add(f"L5_vol_{mname}", rungs.book(rungs.vol_target(base.T["L4"], F4[mname], idx, R2["L5"]["target_vol"],
                                                       R2["L5"]["cap"]), inp, band=base.band).net[dev])
for o in R2["tranche"]["offsets"]:
    if o == R2["tranche"]["record"]:
        continue
    dec = rungs.decision_rows(idx, o)
    t3, t4 = rungs.l3_target(inp, dec), rungs.l4_target(inp, dec)
    t5 = rungs.vol_target(t4, base.s5, idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
    for r, tg in (("L3", t3), ("L4", t4), ("L5", t5)):
        add(f"{r}@offset{o}", rungs.book(tg, inp, band=base.band).net[dev])
for r in ("L6", "L6-63", "L6-th-0.2", "L6-th+0.2", "L7", "L7-on-L5", "L7-63", "L8"):
    add(r, robust.book(base, r).net[dev])
rt = base.rt
ov = rt["overlay"]
L3c = R3["L8"]
plc = sizing.overlay(rt["x7"], L3c["target"], rule="fixed", mult=shuffle_blocks(ov.mult, block=L3c["judge"]["block"],
                                                                              seed=L3c["judge"]["seed"]),
                     sigma=np.full(len(rt["x7"]), L3c["sigma"]), cap=L3c["cap"])
pool["L8_placebo"] = np.nan_to_num(plc.returns, nan=0.0)  # excess already (judge's same-close placebo; row 0 = 0)
Z = regime.zoo_targets(inp, rows, base.T["L5"], band=base.band, years=yrs)
for k_, tg in Z["targets"].items():
    add(k_, rungs.book(tg, inp, band=base.band).net[dev])
md = np.full(inp.R.shape, np.nan)
for t in np.flatnonzero(rows & np.isfinite(base.T["L4"][:, 0])):
    win = inp.R[t - 62:t + 1]
    md[t] = max_div(win, cov=np.cov(win.T, ddof=1))
add("max_div", rungs.book(md, inp, band=base.band).net[dev])
pc = R3["placebo"]
GATES = {"L6": ("L5", base.keep["corr126"]), "L7": ("L6", base.keep["trend"]), "hmm_gate": ("L5", Z["keep"]["hmm"]),
         "jump_gate": ("L5", Z["keep"]["jump"])}
for gname, (pname, kp) in GATES.items():
    for blk in (pc["block_months"], pc["sensitivity_block_months"]):
        tg = regime.gate(base.T[pname], regime.shuffle_decisions(kp, rows, dev, block=blk, seed=pc["seed"]))
        add(f"{gname}_placebo_b{blk}", rungs.book(tg, inp, band=base.band).net[dev])
for k_, b in ZB.items():
    add(k_, b.net[dev])
for k_, x in sens_net.items():
    add(k_, x)
n_registered_pool = len(pool)

grid = robust.v1_grid()
sel = rungs._legacy().v1_params()
jsel = [i for i, g in enumerate(grid) if all(np.isclose(g[k], sel[k]) for k in sel.index)]
facts["v1_grid_selected_column_equals_L1"] = bool(np.array_equal(VG[:, jsel[0]], net["L1"]))
for j in range(VG.shape[1]):
    pool[f"v1_grid_{j:03d}"] = VG[:, j] - c
lap("pool")

names = list(pool)
P = np.column_stack([pool[k] for k in names])
const = [k for k, v in pool.items() if np.std(v) == 0]
if const:
    raise RuntimeError(f"constant trial series: {const}")
eff = effective_trials(P, rho_star=R4["dsr"]["rho_star"], seed=R4["dsr"]["seed"])
is_grid = np.array([k.startswith("v1_grid_") for k in names])
eff_ng = effective_trials(P[:, ~is_grid], rho_star=R4["dsr"]["rho_star"], seed=R4["dsr"]["seed"])
vr = pd.read_csv(paths.REPORTS / "variants.csv")
vr = vr[~vr["phase"].isin(["R5"])]  # R4's register as of R4 (R5 rows are counted in R5's own test DSR)
raw_n = int(vr.loc[vr["counted_in_dsr"] == "yes", "n_configs"].sum())
sel_only = 1  # walk_chains_O2.3 (D4.6 amendment 3)
sr_pp = P.mean(axis=0) / P.std(axis=0, ddof=1)
best = names[int(np.argmax(sr_pp))]
targets = {r: net[r] - c for r in RUNGS} | {f"best_in_pool ({best})": pool[best]}
dsr_rows = []
for k, x in targets.items():
    for tag, e_ in (("headline (n_eff + 1)", {**eff, "n_eff": eff["n_eff"] + sel_only}),
                    ("without v1 grid", {**eff_ng, "n_eff": eff_ng["n_eff"] + sel_only})):
        d = dsr_effective(x, e_)
        dsr_rows.append({"rung": k, "pool": tag, "dsr": d["dsr"], "psr": d["psr"], "sr_ann": d["sr_ann"],
                         "sr0_ann": d["sr0_ann"], "n_used": d["n_eff"], "k_cut": d["k_cut"], "k_gap": d["k_gap"]})
    d = dsr(x, raw_n, sr_pp)
    dsr_rows.append({"rung": k, "pool": f"raw N = {raw_n} (variants.csv register count; the pool holds {P.shape[1]} series)", "dsr": d["dsr"], "psr": d["psr"], "sr_ann": d["sr_ann"],
                     "sr0_ann": d["sr0_ann"], "n_used": raw_n, "k_cut": None, "k_gap": None})
pd.DataFrame(dsr_rows).to_csv(OUT / "dsr.csv", index=False, float_format="%.10g")
facts["dsr_pool"] = {"n_raw_columns": int(P.shape[1]), "n_registered_series": n_registered_pool,
                     "n_v1_grid": int(VG.shape[1]), "n_unique": eff["n_unique"], "n_eff": eff["n_eff"],
                     "k_cut": eff["k_cut"], "k_gap": eff["k_gap"], "k_cut_sens": eff["k_cut_sens"],
                     "participation_ratio": eff["participation_ratio"], "li_ji": eff["li_ji"], "path": eff["path"],
                     "n_used_headline": eff["n_eff"] + sel_only, "n_eff_without_v1_grid": eff_ng["n_eff"],
                     "raw_n_variants_csv": raw_n, "best_in_pool": best,
                     "sr_pp_var_ddof1": float(np.var(sr_pp, ddof=1)), "n_sessions": int(P.shape[0])}  # R5 D5.4: the raw-N companion's trial variance
lap("dsr")

# ---- PBO (D4.7) ------------------------------------------------------------------------------------------------------------
PB = PE["pbo"]
alias = {"jump_model_gate": "jump_gate"}


def dedupe(cols):
    keep_, seen, dropped = [], {}, []
    for k in cols:
        h = hashlib.sha256(pool[k].tobytes()).hexdigest()
        if h in seen:
            dropped.append(f"{k} == {seen[h]}")
        else:
            seen[h] = k
            keep_.append(k)
    return keep_, dropped


prim, drop_p = dedupe([alias.get(k, k) for k in PB["primary_pool"]])
sec_cols = ["L1", "L2", "L2-u", "L3", "L4", "L5", "L5-lev", "L6", "L6-63", "L6-th-0.2", "L6-th+0.2", "L7", "L7-on-L5",
            "L7-63", "L8"] + list(sens_net) + [alias.get(k, k) for k in PB["primary_pool"]]
pool["L0"] = net["L0"] - c
sec, drop_s = dedupe(list(dict.fromkeys(["L0"] + sec_cols)))  # each id once (L5 is a rung and in the zoo list)


def dedupe_tol(cols, tol=1e-12):
    """Descriptive companion (not the registered rule): drop a column within `tol` (max abs) of one already kept, e.g.
    max_div vs L4b (≈ 1e-15 apart: two-asset identity, floating-point weights)."""
    keep_, dropped = [], []
    for k in cols:
        hit = next((j for j in keep_ if np.max(np.abs(pool[k] - pool[j])) <= tol), None)
        if hit is None:
            keep_.append(k)
        else:
            dropped.append(f"{k} ~ {hit} (max abs {np.max(np.abs(pool[k] - pool[hit])):.1e})")
    return keep_, dropped


prim_tol, drop_pt = dedupe_tol(prim)
pbo_rows = []
for tag, cols, dropped in (("primary (zoo)", prim, drop_p), ("secondary (rungs + sensitivity + zoo)", sec, drop_s),
                           ("primary, near-duplicates dropped (1e-12; descriptive)", prim_tol, drop_pt)):
    M = np.column_stack([pool[k] for k in cols])
    for s_ in [PB["blocks"]] + list(PB["descriptive_blocks"]):
        o = pbo(M, blocks=s_)
        pbo_rows.append({"pool": tag, "blocks": s_, "pbo": o["pbo"], "n_splits": o["n_splits"],
                         "logit_median": o["logit_median"], "n_strategies": len(cols), "dropped_duplicates": "; ".join(dropped),
                         "role": "primary" if (tag == "primary (zoo)" and s_ == PB["blocks"]) else "descriptive",
                         "dsr_pool_series": eff["n_raw"], "register_n": raw_n})
pd.DataFrame(pbo_rows).to_csv(OUT / "pbo.csv", index=False, float_format="%.10g")
lap("pbo")

# ---- facts and local series ---------------------------------------------------------------------------------------------------
facts["timing_s"] = timing | {"total": round(time.perf_counter() - t0, 2)}
(OUT / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True, default=float))
loc = {"bill": inp.bill[dev], "spy_proxy": inp.R[dev, 0], "tlt_proxy": inp.R[dev, 1]}
for r in RUNGS:
    loc[f"{r}_net"] = net[r]
    loc[f"{r}_line"] = line[r]
    loc[f"{r}_w_spy"], loc[f"{r}_w_tlt"] = B1[r].held[dev, 0], B1[r].held[dev, 1]
for k, b in ZB.items():
    loc[f"{k}_net"] = b.net[dev]
pd.DataFrame(loc, index=D).to_parquet(LOCAL / "books.parquet")
pd.DataFrame(roll, index=D).to_parquet(LOCAL / "rolling.parquet")
pathlib.Path(LOCAL / "README").write_text("R4 local series (KF-derived, gitignored; scripts/r4.py)\n")

pd.set_option("display.width", 220)
print(zoo[["row", "reference", "dsharpe", "lo", "hi", "p_one_sided", "cdar_ratio", "turnover_pa"]].round(3).to_string(index=False))
print(costs.pivot_table(index=["rung", "reference"], columns="book", values="dsharpe").round(3).to_string())
print(pd.DataFrame(dsr_rows).round(3).to_string(index=False))
print(pd.DataFrame(pbo_rows)[["pool", "blocks", "pbo", "n_strategies", "dropped_duplicates"]].to_string(index=False))
print(sensitivity[["variant", "sharpe", "registered_sharpe", "vs_registered_dsharpe", "turnover_pa",
                   "registered_turnover_pa"]].round(3).to_string(index=False))
print("facts:", json.dumps({k: v for k, v in facts.items() if k != "timing_s"}, default=float)[:1500])
print(f"r4: {time.perf_counter() - t0:.1f} s", timing)
