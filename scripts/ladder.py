"""make ladder (R2): L0–L5 + L4b, L5-lev, L2-u and the vol-zoo rows on 1986–2019 (development scored 1990–2019), the
L0-line, the pre-registered promotion walk L1 → L5 (D2.4), the post-hoc parent-chain walk and every rung vs L1 (owner
O2.3), timing luck (D2.5).

Committed (statistics only): reports/r2/{metrics.csv, lines.csv, ablation.csv, crisis.csv, timing_luck.csv,
volzoo.json, ladder.json, ladder_chains.json, vs_l1.csv, crisis_matched.csv (post-hoc, O2.4), facts.json, ladder_prereg.jsonl (append-only, written before any book is built)}.
Local only (gitignored, KF-derived daily series): data/r2/books.parquet, data/r2/register.csv (rebuilt each run).
The test window 2020+ is not run here (R5).
"""

import json
import math
import time

import numpy as np
import pandas as pd
from quantkit import costs as qcosts
from quantkit.trade import tranche as qtr

from rspy import evaluate as ev
from rspy import paths, rungs, volzoo
from rspy.data import build

t0 = time.perf_counter()
R2 = paths.rules()["r2"]
PR = paths.prereg()["promotion_rule"]
SC = [str(d) for d in R2["scored"]]  # yaml dates → ISO strings
OUT = paths.REPORTS / "r2"
LOCAL = paths.data_dir() / "r2"
OUT.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)
PREREG = OUT / "ladder_prereg.jsonl"
REGISTER = LOCAL / "register.csv"
REGISTER.unlink(missing_ok=True)
WALK = list(PR["walk"])
ev.ladder("r2_core", WALK).preregister(PREREG)  # before any book exists (quantkit refuses a changed spec later)
CHAINS = ev.chains({"L0", "L2", "L3", "L4", "L5"})  # post-hoc (O2.3): registered before this run's books
for k, ch in CHAINS.items():
    ev.ladder(f"r2_chain_{k}", ch).preregister(PREREG)

# ---- inputs and targets (rungs docstring: one line per transform) ---------------------------------------------------
panel = build.load()
inp = rungs.Inputs.from_panel(panel, "1986-01-02", SC[1])
idx = inp.index
dev = np.asarray(idx >= pd.Timestamp(SC[0]))
rows = rungs.decision_rows(idx, R2["tranche"]["record"])
B = R2["band"]["width"]
band = {r: B for r in R2["band"]["rungs"]}
T = {"L0": rungs.l0_target(inp), "L1": rungs.l1_target(panel, inp), "L2": rungs.l2_target(inp),
     "L3": rungs.l3_target(inp, rows), "L4": rungs.l4_target(inp, rows), "L4b": rungs.l4b_target(inp, rows)}

years = range(1989, int(SC[1][:4]))
bk4 = rungs.book(T["L4"], inp, band=B)
r4 = rungs.log_book_returns(bk4)
F4 = volzoo.forecasts(r4)
picks4 = volzoo.select(F4, r4, years)
s5 = volzoo.stitched(F4, picks4)
w4 = rungs.carry(T["L4"])
T["L5"] = rungs.vol_target(T["L4"], s5, idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
T["L5-lev"] = rungs.vol_target(T["L4"], s5, idx, R2["L5-lev"]["target_vol"], R2["L5-lev"]["cap"])
for m in F4:
    T[f"L5_vol_{m}"] = rungs.vol_target(T["L4"], F4[m], idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
    band[f"L5_vol_{m}"] = B
r0 = pd.Series(np.log1p(inp.R[:, 0]), idx)
F0 = volzoo.forecasts(r0)
picks0 = volzoo.select(F0, r0, years)
spy = np.full((len(idx), 2), np.nan)
spy[0] = (1.0, 0.0)
T["L2-u"] = rungs.vol_target(spy, volzoo.stitched(F0, picks0), idx, R2["L2u"]["target_vol"], R2["L2u"]["cap"])
t_targets = time.perf_counter() - t0

# ---- books: 1x, 2x, 3x costs and +75 bp financing ---------------------------------------------------------------------
books = {}
for r, tg in T.items():
    b = band.get(r)
    books[r] = {"1x": rungs.book(tg, inp, band=b), "2x": rungs.book(tg, inp, band=b, cost_mult=2.0),
                "3x": rungs.book(tg, inp, band=b, cost_mult=3.0), "f75": rungs.book(tg, inp, band=b, stress_bp=75.0)}
t_books = time.perf_counter() - t0

c, rate, dt, hi = inp.bill[dev], inp.mmy[dev], inp.dt[dev], inp.R[dev, 0]
D = pd.DatetimeIndex(idx[dev])

# ---- metrics, lines, beyond 60/40 -----------------------------------------------------------------------------------------
mrows, lrows = [], []
for r, bk in books.items():
    for k, b in bk.items():
        g = np.abs(b.held).sum(axis=1)
        mrows.append({"rung": r, "book": k, **ev.metrics(b.net[dev], c, b.turnover[dev], b.cost[dev],
                                                          b.financing[dev], g[dev])})
    x = bk["1x"].net
    la = ev.line(x, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)
    lp = ev.line(x[dev], hi, c, rate, dt, mode="ex_post")
    ln = la["returns"][dev]
    if not np.isfinite(ln).all():
        raise RuntimeError(f"{r}: the ex-ante line is not finite on every development row")
    t_ = ev.lw(x[dev] - c, ln - c)
    lrows.append({"rung": r, "line_vol": float(np.std(ln, ddof=1) * math.sqrt(252)),
                  "rung_vol": float(np.std(x[dev], ddof=1) * math.sqrt(252)), "line_sharpe": ev.sr(ln - c),
                  "rung_sharpe": ev.sr(x[dev] - c), "dsharpe_vs_line": t_["dsharpe"], "lo": t_["lo"], "hi": t_["hi"],
                  "p_one_sided": t_["p_one_sided"], "line_cagr": ev.metrics(ln, c)["cagr"],
                  "line_max_dd": ev.metrics(ln, c)["max_dd"], "line_cdar95": ev.cdar95(ln),
                  "dsharpe_vs_line_ex_post": ev.sr(x[dev] - c) - ev.sr(lp["returns"] - c),
                  "line_max_weight": float(np.nanmax(la["weight"][dev])),
                  "dsharpe_vs_L3_matched": ev.pair(x[dev], books["L3"]["1x"].net[dev], c, rate, dt)[0]})
    lrows[-1]["beyond_6040"] = bool(lrows[-1]["dsharpe_vs_L3_matched"] >= PR["beyond_6040"]["delta_sharpe_vs_vol_matched_L3"])
    if r == "L0":
        line_books = {}
    line_books[r] = la["returns"]
metrics = pd.DataFrame(mrows)
lines = pd.DataFrame(lrows)
metrics.to_csv(OUT / "metrics.csv", index=False, float_format="%.10g")
lines.to_csv(OUT / "lines.csv", index=False, float_format="%.10g")

# ---- ablation: what each layer added (matched-vol pairs, descriptive) ------------------------------------------------
abl = []
for name, a, b in [("v1 (L1 vs L0)", "L1", "L0"), ("vol target on SPY, v1 style (L2 vs L0)", "L2", "L0"),
                   ("vol target on SPY, 10% (L2-u vs L0)", "L2-u", "L0"), ("add bonds 60/40 (L3 vs L0)", "L3", "L0"),
                   ("risk weighting (L4 vs L3)", "L4", "L3"), ("portfolio vol target (L5 vs L4)", "L5", "L4"),
                   ("leverage to 1.5x (L5-lev vs L5)", "L5-lev", "L5")]:
    ds, cs, cb = ev.pair(books[a]["1x"].net[dev], books[b]["1x"].net[dev], c, rate, dt)
    abl.append({"layer": name, "rung": a, "parent": b, "dsharpe_matched": ds, "cdar_rung": cs, "cdar_parent_matched": cb,
                "cdar_change": cs / cb - 1.0})
pd.DataFrame(abl).to_csv(OUT / "ablation.csv", index=False, float_format="%.10g")

# ---- crisis windows (descriptive) ---------------------------------------------------------------------------------------
pos = ev.crisis_positions(D)
crows = []
for r in ["L0", "L1", "L2", "L3", "L4", "L5", "L5-lev", "L2-u"]:
    x = books[r]["1x"].net[dev]
    for k, p in pos.items():
        crows.append({"rung": r, "crisis": k, "start": str(D[p[0]].date()), "end": str(D[p[-1]].date()),
                      "return": float(np.prod(1 + x[p]) - 1), "max_dd": float(ev.qdd.max_dd(x[p]))})
pd.DataFrame(crows).to_csv(OUT / "crisis.csv", index=False, float_format="%.10g")

# ---- promotion walk (development rows) -----------------------------------------------------------------------------------
wb = {r: {k: books[r][k].net[dev] for k in ("1x", "2x", "f75")} for r in WALK}
res = ev.walk(wb, c, rate, dt, D, prereg_path=PREREG, register_path=REGISTER)
res_chains = {}
for k, ch in CHAINS.items():  # post-hoc (O2.3): same rule, same books, parents only
    cb = {r: {kk: books[r][kk].net[dev] for kk in ("1x", "2x", "f75")} for r in ch}
    res_chains[k] = {"chain": ch, **ev.walk(cb, c, rate, dt, D, prereg_path=PREREG, register_path=REGISTER,
                                            name=f"r2_chain_{k}")}

# ---- in-crisis return at matched vol (POST-HOC descriptive, owner O2.4; cannot change any verdict) ------------------
tested = {(st["rung"], st["incumbent"]) for w in [res, *res_chains.values()] for st in w["steps"]}
pairs = list(dict.fromkeys([*zip(WALK[1:], WALK[:-1], strict=True)]
                           + [p_ for ch in CHAINS.values() for p_ in zip(ch[1:], ch[:-1], strict=True)]))
cm = []
for ch_, pa_ in pairs:
    for row in ev.crisis_matched(books[ch_]["1x"].net[dev], books[pa_]["1x"].net[dev], c, rate, dt, pos):
        cm.append({"child": ch_, "parent": pa_, "tested_in_a_walk": (ch_, pa_) in tested, **row})
pd.DataFrame(cm).to_csv(OUT / "crisis_matched.csv", index=False, float_format="%.10g")

# ---- every rung vs L1 (comparison row, descriptive; O2.3) --------------------------------------------------------------
x1 = books["L1"]["1x"].net[dev]
v1rows = []
for r in ["L0", "L2", "L2-u", "L3", "L4", "L5", "L5-lev"]:
    x = books[r]["1x"].net[dev]
    ds, cs, cb_ = ev.pair(x, x1, c, rate, dt)
    t_ = ev.lw(x - c, x1 - c)
    v1rows.append({"rung": r, "dsharpe_vs_L1_matched": ds, "dsharpe_vs_L1": t_["dsharpe"], "lo": t_["lo"],
                   "hi": t_["hi"], "p_one_sided": t_["p_one_sided"], "cdar_rung": cs, "cdar_L1_matched": cb_,
                   "cdar_change": cs / cb_ - 1.0})
pd.DataFrame(v1rows).to_csv(OUT / "vs_l1.csv", index=False, float_format="%.10g")
t_walk = time.perf_counter() - t0

# ---- timing luck (D2.5): 21 offsets for L3, L4, L5 on the development rows --------------------------------------------
offsets = R2["tranche"]["offsets"]
rates = rungs.acc_kw()["cost_rates"]
cost = qcosts.Proportional(rates)


def post_trade(bk) -> np.ndarray:
    """quantkit's W_t (weights after the trade at close t) = the weights carried into row t + 1."""
    return np.vstack([bk.held[1:], bk.held[-1:]])


def rule_for(r):
    def rule(mask):
        tr_ = np.flatnonzero(mask)
        dec = np.zeros(len(idx), bool)
        dec[tr_[tr_ >= 1] - 1] = True
        if r == "L3":
            tg = rungs.l3_target(inp, dec)
        elif r == "L4":
            tg = rungs.l4_target(inp, dec)
        else:
            tg = rungs.vol_target(rungs.l4_target(inp, dec), s5, idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
        return post_trade(rungs.book(tg, inp, band=B))
    return rule


tl_rows, facts = [], {}
per = idx.to_period("M")
sessions = pd.Series(1, index=idx).groupby(per).size()
collisions = {o: int((sessions.loc[sessions.index >= pd.Period(SC[0][:7], "M")] < o + 1).sum()) for o in offsets}
for r in R2["tranche"]["rungs"]:
    tr = qtr.tranche(rule_for(r), idx, offsets)
    facts[f"{r}_record_equals_offset0_book"] = bool(np.array_equal(tr["books"][0], post_trade(books[r]["1x"])))
    sl = {"W": tr["W"][dev], "books": {o: w[dev] for o, w in tr["books"].items()}, "dates": D}
    tl = qtr.timing_luck(sl, inp.R[dev], cost=cost)
    for o in offsets:
        st = tl["offsets"][o]
        tl_rows.append({"rung": r, "offset": o, "rtl": tl["rtl"][o], "short_month_collisions": collisions[o],
                        **{k: v for k, v in st.items() if np.ndim(v) == 0}})
    tl_rows.append({"rung": r, "offset": "tranched", "rtl": tl["rtl_mean"], "short_month_collisions": None,
                    **{k: v for k, v in tl["tranched"].items() if np.ndim(v) == 0}})
pd.DataFrame(tl_rows).to_csv(OUT / "timing_luck.csv", index=False, float_format="%.10g")
t_tl = time.perf_counter() - t0

# ---- vol zoo record and the D2.2 limitation diagnostic --------------------------------------------------------------------
(OUT / "volzoo.json").write_text(json.dumps({"L5 (series: L4 book)": picks4, "L2-u (series: SPY proxy)": picks0,
                                             "spec_hashes": {m: F4.attrs.get("spec_hash") for m in F4}},
                                            indent=1, default=float))
hl = R2["vol_zoo"]["models"]["ewma_slow"]["halflife"]
Rf = pd.DataFrame(inp.R, index=idx)
e00 = (Rf[0] ** 2).ewm(halflife=hl).mean()
e11 = (Rf[1] ** 2).ewm(halflife=hl).mean()
e01 = (Rf[0] * Rf[1]).ewm(halflife=hl).mean()
wc = pd.DataFrame(w4, index=idx)
v_cur = wc[0] ** 2 * e00 + wc[1] ** 2 * e11 + 2 * wc[0] * wc[1] * e01
v_book = (r4**2).ewm(halflife=hl).mean().reindex(idx)
ratio = np.sqrt(v_book / v_cur).loc[SC[0]:].dropna()
facts["limitation_ewma60_vol_book_over_current_weights"] = {"median": float(ratio.median()),
                                                            "p05": float(ratio.quantile(0.05)),
                                                            "p95": float(ratio.quantile(0.95))}

# ---- facts ------------------------------------------------------------------------------------------------------------------------
ok4 = np.isfinite(T["L4"][:, 0])
facts["L4b_minus_L4_max_abs"] = float(np.abs(T["L4b"][ok4] - T["L4"][ok4]).max())
tg5 = T["L5"][dev]
fin5 = np.isfinite(tg5[:, 0])
facts["L5_share_days_at_cap"] = float((np.abs(tg5[fin5].sum(axis=1) - R2["L5"]["cap"]) < 1e-12).mean())
facts["L5_mean_target_gross"] = float(tg5[fin5].sum(axis=1).mean())
facts["L2_share_days_above_1x"] = float((books["L2"]["1x"].held[dev, 0] > 1).mean())
facts["line_first_finite_scored"] = str(D[np.isfinite(line_books["L0"][dev])][0].date())
facts["walk_winner"] = res["winner"]
facts["chain_winners"] = {k: v["winner"] for k, v in res_chains.items()}
facts["timing_s"] = {"targets_and_zoo": round(t_targets, 2), "books": round(t_books - t_targets, 2),
                     "metrics_lines_walk": round(t_walk - t_books, 2), "timing_luck": round(t_tl - t_walk, 2),
                     "total": round(time.perf_counter() - t0, 2)}
js = lambda o: o.tolist() if hasattr(o, "tolist") else float(o)  # noqa: E731
(OUT / "ladder.json").write_text(json.dumps(res, indent=1, default=js))
(OUT / "ladder_chains.json").write_text(json.dumps({"label": "POST-HOC (owner O2.3, charter amendment 5822b28)",
                                                    "chains": res_chains}, indent=1, default=js))
(OUT / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True, default=float))

# ---- local daily books for the curve figures (gitignored) -------------------------------------------------------------------
loc = {"bill": inp.bill, "mmy": inp.mmy, "dt": inp.dt, "spy_proxy": inp.R[:, 0], "tlt_proxy": inp.R[:, 1]}
for r in ["L0", "L1", "L2", "L3", "L4", "L5", "L5-lev", "L2-u"]:
    b = books[r]["1x"]
    loc[f"{r}_net"] = b.net
    loc[f"{r}_w_spy"], loc[f"{r}_w_tlt"] = b.held[:, 0], b.held[:, 1]
    loc[f"{r}_line"] = line_books[r]
pd.DataFrame(loc, index=idx).to_parquet(LOCAL / "books.parquet")

show = metrics[metrics.book == "1x"].set_index("rung")[["cagr", "vol", "sharpe_excess", "max_dd", "cdar95", "turnover_pa"]]
print(show.round(4).to_string())
print(lines.set_index("rung")[["dsharpe_vs_line", "lo", "hi", "p_one_sided", "beyond_6040"]].round(3).to_string())
for s in res["steps"]:
    print(s["rung"], "vs", s["incumbent"], "promoted" if s["promoted"] else "failed", s["route"],
          s["quantkit"]["reasons"], {k: v for k, v in s["rspy"]["legs"].items()})
for k, v in res_chains.items():
    for s in v["steps"]:
        print(f"[post-hoc chain {k}]", s["rung"], "vs", s["incumbent"], "promoted" if s["promoted"] else "failed",
              s["route"], s["quantkit"]["reasons"])
    print(f"[post-hoc chain {k}] winner:", v["winner"])
print(pd.DataFrame(v1rows).set_index("rung")[["dsharpe_vs_L1", "lo", "hi", "p_one_sided", "dsharpe_vs_L1_matched",
                                            "cdar_change"]].round(3)
      .to_string())
print("[post-hoc O2.4] in-crisis return at matched vol (tested steps):")
print(pd.DataFrame(cm).query("tested_in_a_walk")[["child", "parent", "crisis", "child_return",
      "parent_matched_return", "loses_matched", "dsharpe_in_window"]].round(4).to_string(index=False))
print("winner:", res["winner"], "| facts:", json.dumps(facts, default=float)[:600])
print(f"ladder: {time.perf_counter() - t0:.1f} s")
