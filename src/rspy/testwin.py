"""R5 test-window run (spec/prereg.yaml r5_test, rules.yaml r5; D5.1–D5.6): the frozen ladder built once over
1986-01-02 → the test end, the test rows 2020-01-02 → 2026-09-30 scored. Every number is descriptive and cannot change
a development verdict (labelled "seen by owner in v1, disclosed").

One line per transform (value at t uses data ≤ t):
- `build(panel, end)` (D5.1): `robust.build_core(end=end)` (the R2/R3 functions, unchanged) for L0–L8, L5-lev; L2-u
  as R2 (SPY's own vol-zoo forecast); every book continuous from 1986 (positions carried into 2020); vol-zoo picks for
  year-ends 1989 .. end year − 1 (`require_picks`: a pick for every test year, never the silent default); the owner's
  post-hoc 10-year row = `build_core(maturity=10, end=end)` L5–L7. `dev_identity` checks every extended book's rows
  ≤ 2019-12-31 against a development-only rebuild (and, for the real run, data/r2, data/r3) bit for bit;
- lines: `evaluate.line` (ex ante, window 63, lag 1) on each full book, sliced to the test rows;
- matching (D5.2): inputs sliced to the test rows FIRST, then `evaluate.ablation_row` / `pair` / `crisis_matched`
  rescale the reference once to the child's test-window excess vol; k = the child's excess vol / the reference's;
- `family_rows` (D5.3): the 24 registered (child, reference) rows; Holm over all of them; `headline` answers the three
  README questions (point ≥ +0.05 and Holm p < 0.05 within a question's rows); power at the test length from the
  development point Sharpes and correlation (quantkit `stats.power.power`, optimistic iid); sign agreement vs the
  development ΔSharpe of the same pair (matched on development);
- `dsr_rows` (D5.4): headline `dsr_effective` with N 5 on R4's single development cluster (null variance 1/(T − 1));
  raw-N companion `dsr` with N 751 and V = max(V_dev, 1/(T − 1)) (`trial_var`);
- crisis panels (COVID, 2022): in-window cumulative return of each rung, its ex-ante line and its parent matched on the
  whole test window (k includes the crises; in-crisis vols are not matched), and mean SPY / TLT / cash weights.
- `placebos` (D5.8, descriptive): the L6 correlation keep, the L7 trend keep and the L8 multiplier shuffled on the
  TEST rows only (R3 machinery: `regime.shuffle_decisions`, blocks of 12 month-end decisions; L8: `quantkit.vol.
  shuffle_blocks` of g in 21-row blocks, the R4 L8_placebo analog), seeds 0–99; per gate: the gate's percentile among
  the seeds and the placebo median / p05 / p95 of (i) ΔSharpe vs its parent (matched) and (ii) the matched cumulative
  return in COVID and 2022. No p-value, no "beats" verdict (≈ 7 blocks: coarse); one-directional (it can only
  qualify a claim);
- `synthetic_panel(seed)`: the dry run's data (D5.5): seeded t(5) equity and bond returns on business days, an AR(1)
  3-month discount rate turned into bill / mmy / dt by the D1.1 rule. A code check, never evidence.
Complexity: build O(T·N) per book + three cold vol-zoo series (GARCH refits every 21 rows); the evaluation is
O(draws·T_test) per matched row (≈ 45 rows × 3 bootstraps of 1,000 on 1,695 rows).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from quantkit.stats import dsr, dsr_effective
from quantkit.stats.multitest import adjust_pvalues
from quantkit.stats.power import power
from quantkit.vol import shuffle_blocks

from rspy import evaluate as ev
from rspy import paths, regime, robust, rungs, volzoo

ANN = 252
OFFICIAL = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"]
DESCRIPTIVE = ["L5-lev", "L2-u"]
TEN = ["L5", "L6", "L7"]


def spec() -> dict:
    return paths.prereg()["r5_test"]


def rules() -> dict:
    return paths.rules()["r5"]


# ---- the dry run's data -------------------------------------------------------------------------------------------------
def synthetic_panel(seed: int = 0, start: str = "1985-06-03", end: str = "2026-09-30") -> pd.DataFrame:
    """Seeded synthetic panel with the real panel's columns (code check only; never evidence)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    T = len(idx)
    z = rng.standard_t(5, size=(T, 2)) / math.sqrt(5 / 3)
    rho = -0.2
    eq = 0.0003 + 0.011 * z[:, 0]
    bd = 0.0002 + 0.008 * (rho * z[:, 0] + math.sqrt(1 - rho**2) * z[:, 1])
    d = np.empty(T)
    d[0] = 0.05
    e = rng.normal(0, 0.0004, T)
    for t in range(1, T):
        d[t] = max(0.0, d[t - 1] + 0.002 * (0.03 - d[t - 1]) + e[t])
    dl = np.r_[d[0], d[:-1]]  # rate dated <= the previous session (D1.1)
    days = np.r_[1, np.diff(idx.values).astype("timedelta64[D]").astype(np.int64)]  # unit-independent (review R5 M1)
    P = 1 - dl * 91 / 360
    p = pd.DataFrame({"hi20": eq, "tlt25": bd, "tlt10": 0.45 * bd, "tlt20": 0.85 * bd, "tlt30": 1.1 * bd,
                      "bill": P ** (-days / 91) - 1, "mmy": (1 / P - 1) * 360 / 91, "dt": days / 360,
                      "disc_used": dl}, index=idx)
    p.index.name = "date"
    return p


# ---- D5.1 ------------------------------------------------------------------------------------------------------------------
def require_picks(picks: dict, first_year: int, last_year: int) -> None:
    """A vol-zoo pick (year-end y − 1) must exist for every scored year y (D5.1 amendment 2)."""
    miss = [y for y in range(first_year, last_year + 1) if (y - 1) not in picks]
    if miss:
        raise RuntimeError(f"no vol-zoo pick for scored years {miss}: volzoo.stitched would fall back silently")


def build(panel: pd.DataFrame, end: str) -> dict:
    R2 = paths.rules()["r2"]
    core = robust.build_core(panel, end=end)
    inp, idx = core.inp, core.inp.index
    t0, t1 = (pd.Timestamp(str(d)) for d in rules()["scored"])
    require_picks(core.picks, t0.year, idx[-1].year)
    r0 = pd.Series(np.log1p(inp.R[:, 0]), idx)
    F0 = volzoo.forecasts(r0)
    p0 = robust.picks_cached(F0, r0, range(1989, int(end[:4])))
    require_picks(p0, t0.year, idx[-1].year)
    spy = np.full((len(idx), 2), np.nan)
    spy[0] = (1.0, 0.0)
    T = {r: core.T[r] for r in OFFICIAL + ["L5-lev"]}
    T["L2-u"] = rungs.vol_target(spy, volzoo.stitched(F0, p0), idx, R2["L2u"]["target_vol"], R2["L2u"]["cap"])
    cost = {"1x": {}, "2x": {"cost_mult": 2.0}, "3x": {"cost_mult": 3.0},
            "f75": {"stress_bp": paths.rules()["r4"]["costs"]["financing_extra_bp"]}}

    def bk(name, **kw):
        if name == "L2-u":  # R2: unbanded (band dict had no L2-u)
            return rungs.book(T[name], inp, **kw)
        return robust.book(core, name, T[name], **kw)

    books = {r: {k: bk(r, **kw) for k, kw in cost.items()} if r in OFFICIAL + ["L5-lev"] else {"1x": bk(r)}
             for r in T}
    core10 = robust.build_core(panel, maturity=rules()["maturity_10y"], end=end, l1=False)
    require_picks(core10.picks, t0.year, idx[-1].year)
    books10 = {r: robust.book(core10, r) for r in TEN}
    return {"core": core, "core10": core10, "T": T, "books": books, "books10": books10, "picks": core.picks,
            "picks_spy": p0, "picks10": core10.picks}


def dev_identity(B: dict, dev_only: dict) -> dict:
    """{name: bool}: rows ≤ 2019-12-31 of each extended 1× book (and the targets) equal the development-only build's."""
    n = len(dev_only["idx"])
    out = {}
    for r, d in dev_only["net"].items():
        out[f"{r}_net"] = bool(np.array_equal(B["books"][r]["1x"].net[:n], d))
    for r, d in dev_only["held"].items():
        out[f"{r}_held"] = bool(np.array_equal(B["books"][r]["1x"].held[:n], d))
    out["index"] = bool(B["core"].inp.index[:n].equals(dev_only["idx"]))
    out["picks_1989_2018"] = {y: B["picks"][y]["pick"] for y in dev_only["picks"]} == \
        {y: v["pick"] for y, v in dev_only["picks"].items()}
    return out


def dev_only_books(panel: pd.DataFrame) -> dict:
    """The development-only rebuild (R4's `build_core` at its default end; vol zoo cached) for `dev_identity`."""
    R2 = paths.rules()["r2"]
    core = robust.build_core(panel)
    inp, idx = core.inp, core.inp.index
    r0 = pd.Series(np.log1p(inp.R[:, 0]), idx)
    F0 = volzoo.forecasts(r0)
    spy = np.full((len(idx), 2), np.nan)
    spy[0] = (1.0, 0.0)
    t2u = rungs.vol_target(spy, volzoo.stitched(F0, robust.picks_cached(F0, r0, range(1989, idx[-1].year))), idx,
                           R2["L2u"]["target_vol"], R2["L2u"]["cap"])
    net, held = {}, {}
    for r in OFFICIAL + ["L5-lev", "L2-u"]:
        b = rungs.book(t2u, inp) if r == "L2-u" else robust.book(core, r)
        net[r], held[r] = b.net, b.held
    return {"idx": idx, "net": net, "held": held, "picks": core.picks}


# ---- D5.3 ------------------------------------------------------------------------------------------------------------------
def family_rows() -> list[tuple[str, str, str]]:
    """[(child, reference, kind)] in registration order; kind ∈ {parent, rung, line}."""
    out = []
    for child, refs in spec()["family"]["rows"].items():
        for ref in refs:
            if ref.startswith("parent "):
                out.append((child, ref.split()[1], "parent"))
            elif ref == "line":
                out.append((child, "line", "line"))
            else:
                out.append((child, ref, "rung"))
    if len(out) != spec()["family"]["n_rows"]:
        raise RuntimeError(f"family has {len(out)} rows, prereg says {spec()['family']['n_rows']}")
    return out


QUESTIONS = {"L2": "beat plain vol-targeted SPY (L2)", "L3": "beat 60/40 (L3)",
             "line": "beat SPY + T-bills at matched risk (line)"}


def headline(fam: pd.DataFrame, min_effect: float = 0.05, alpha: float = 0.05) -> dict:
    """D5.3 amendment 2: per question, yes iff some row has point ≥ min_effect and Holm p < alpha."""
    out = {}
    for ref, q in QUESTIONS.items():
        rows = fam[fam.reference == ref]
        hit = rows[(rows.dsharpe >= min_effect) & (rows.holm_p < alpha)]
        raw = rows[(rows.dsharpe >= min_effect) & (rows.p_one_sided < alpha)]
        out[q] = {"answer": "yes" if len(hit) else "not shown in the test window",
                  "rows": rows.child.tolist(), "holm_hits": hit.child.tolist(), "raw_flags": raw.child.tolist(),
                  "best": None if rows.empty else {
                      "child": rows.loc[rows.dsharpe.idxmax(), "child"], "dsharpe": float(rows.dsharpe.max())}}
    return out


# ---- D5.4 ------------------------------------------------------------------------------------------------------------------
def trial_var(v_dev: float, T: int) -> tuple[float, str]:
    null = 1.0 / (T - 1)
    return (v_dev, "V_dev (development pool)") if v_dev > null else (null, "null 1/(T-1)")


def dsr_rows(x_excess: np.ndarray, n_head: int, n_raw: int, v_dev: float, k_gap: int) -> list[dict]:
    x = np.asarray(x_excess, np.float64)
    V, which = trial_var(v_dev, len(x))
    head = dsr_effective(x, {"n_eff": n_head, "cluster_sr": [], "k_cut": 1, "k_gap": k_gap})
    a = math.sqrt(V / 2.0)  # two trial Sharpes ±a have ddof-1 variance V
    raw = dsr(x, n_raw, None if which.startswith("null") else np.array([-a, a]))
    return [{"pool": f"headline (N = {n_head}: R4 n_eff 3 + 1 selection-only + 1 post-hoc 10y row)", "dsr": head["dsr"],
             "psr": head["psr"], "sr_ann": head["sr_ann"], "sr0_ann": head["sr0_ann"], "n_used": n_head,
             "trial_var": head["var"], "trial_var_source": "null 1/(T-1) (one development cluster)"},
            {"pool": f"raw N = {n_raw} (variants.csv counted)", "dsr": raw["dsr"], "psr": raw["psr"],
             "sr_ann": raw["sr_ann"], "sr0_ann": raw["sr0_ann"], "n_used": n_raw, "trial_var": raw["var"],
             "trial_var_source": which}]


# ---- v1 vs v2 -------------------------------------------------------------------------------------------------------------
STEP_NAMES = {"S0": "v1 as committed (own Yahoo/Cboe data, own accounting)", "S1": "+ trade at t+1",
              "S2": "+ cash at bills, financing above 1x", "S3": "+ charter costs on true traded turnover",
              "S4": "+ excess-return Sharpe / standard Sortino", "S5": "+ no shorts", "S6": "+ VIX -> realised vol",
              "S7": "+ permitted data (KF Hi 20, GSW 25y, H.15) = L1"}
V1_COLS = ["cagr", "vol", "sharpe_excess", "max_dd", "turnover_pa", "cost_pa", "financing_pa"]


def v1_vs_v2(metrics: pd.DataFrame, recon: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(side by side, corrections): v1 as committed (R1 S0, v1's own test 2020-01 -> 2025-12, seen) and the R1
    corrections S0 -> S7 one at a time, copied from reports/r1/reconciliation.csv; then v1 corrected (L1) and the v2
    rungs on the R5 test window. S0's Sharpe is the excess Sharpe column of the same row (R1 computed both)."""
    r1 = recon[recon.window == "test"].set_index("step")
    rows = [{"row": "v1 as committed (S0)", "rung": "S0", "window": f"{r1.loc['S0', 'start']} .. {r1.loc['S0', 'end']}",
             "data": "Yahoo SPY/TLT + Cboe VIX (v1's local file)", "accounting": "v1 (same close, 0% cash, no financing)",
             "source": "reports/r1/reconciliation.csv (seen)", **{k: float(r1.loc["S0", k]) for k in V1_COLS}}]
    m = metrics[metrics.book == "1x"].set_index("rung")
    t0, t1 = (str(d) for d in rules()["scored"])
    for r, name in (("L1", "v1 corrected (L1)"), ("L0", "SPY proxy (L0)"), ("L3", "60/40 (L3)"),
                    ("L5", "inverse-vol + vol target (L5)"), ("L6", "+ correlation regime (L6)"), ("L7", "+ trend (L7)"),
                    ("L8", "+ crash rule (L8)"), ("L5-line", "SPY + T-bills at L5's vol (line)")):
        rows.append({"row": name, "rung": r, "window": f"{t0} .. {t1}",
                     "data": "SPY proxy (KF Hi 20); " + paths.rules()["bonds"]["label"] + "; H.15 bills",
                     "accounting": "charter (t+1, bills, financing, true-turnover costs)", "source": "reports/r5",
                     **{k: float(m.loc[r, k]) if k in m.columns and pd.notna(m.loc[r, k]) else None for k in V1_COLS}})
    side = pd.DataFrame(rows)
    cor = []
    prev = None
    for st in STEP_NAMES:
        v = r1.loc[st]
        cor.append({"step": st, "correction": STEP_NAMES[st], "window": f"{v.start} .. {v.end}",
                    **{k: float(v[k]) for k in ("cagr", "sharpe_excess", "max_dd", "turnover_pa")},
                    "d_cagr": None if prev is None else float(v.cagr - prev.cagr),
                    "d_sharpe_excess": None if prev is None else float(v.sharpe_excess - prev.sharpe_excess)})
        prev = v
    return side, pd.DataFrame(cor).assign(source="reports/r1/reconciliation.csv (R1; v1's own test 2020-2025, seen)")


# ---- D5.8 placebos ------------------------------------------------------------------------------------------------------
def placebos(B: dict, ts: np.ndarray, c, rate, dt, pos: dict, net: dict) -> pd.DataFrame:
    core = B["core"]
    pz = spec()["placebo_descriptive"]
    seeds = range(pz["seeds"][0], pz["seeds"][1] + 1)
    T, rows = core.T, core.rows
    g = core.rt["g"]

    def tg_for(gate, seed):
        if gate == "L6":
            return regime.gate(T["L5"], regime.shuffle_decisions(core.keep["corr126"], rows, ts,
                                                                 block=pz["block_months"], seed=seed))
        if gate == "L7":
            return regime.gate(T["L6"], regime.shuffle_decisions(core.keep["trend"], rows, ts,
                                                                 block=pz["block_months"], seed=seed))
        gs = g.copy()
        gs[ts] = shuffle_blocks(g[ts], block=pz["l8_block_rows"], seed=seed)
        return T["L7"] * gs[:, None]

    par = {"L6": "L5", "L7": "L6", "L8": "L7"}
    out = []
    for gate, parent in par.items():
        y = net[parent]

        def stats(x, y=y):
            ds = ev.pair(x, y, c, rate, dt)[0]
            cm = {r["crisis"]: r["diff_matched"] for r in ev.crisis_matched(x, y, c, rate, dt, pos)}
            return ds, cm

        g_ds, g_cm = stats(net[gate])
        dist = [stats(robust.book(core, gate, tg_for(gate, s)).net[ts]) for s in seeds]
        ds = np.array([d for d, _ in dist])
        row = {"gate": gate, "parent": parent, "n_seeds": len(ds), "n_test_decisions": int((rows & ts).sum()),
               "block_months": pz["block_months"], "dsharpe_gate": g_ds,
               "gate_percentile_dsharpe": float((ds < g_ds).mean() * 100), "placebo_dsharpe_median": float(np.median(ds)),
               "placebo_dsharpe_p05": float(np.quantile(ds, 0.05)), "placebo_dsharpe_p95": float(np.quantile(ds, 0.95))}
        for k in pos:
            v = np.array([cm[k] for _, cm in dist])
            row |= {f"{k}_gate_minus_parent": g_cm[k], f"{k}_gate_percentile": float((v < g_cm[k]).mean() * 100),
                    f"{k}_placebo_median": float(np.median(v)), f"{k}_placebo_p05": float(np.quantile(v, 0.05)),
                    f"{k}_placebo_p95": float(np.quantile(v, 0.95)),
                    f"{k}_inside_placebo_p05_p95": bool(np.quantile(v, 0.05) <= g_cm[k] <= np.quantile(v, 0.95))}
        out.append(row)
    return pd.DataFrame(out).assign(label=pz["label"], caveat=pz["caveat"], tier="disclosed-reuse")


# ---- the evaluation ----------------------------------------------------------------------------------------------------------
def _vol(x) -> float:
    return float(np.std(x, ddof=1) * math.sqrt(ANN))


def evaluate(B: dict, *, r4_dsr: pd.DataFrame | None = None, r4_k_gap: int = 3,
             recon: pd.DataFrame | None = None) -> dict:
    """Every R5 table (DataFrames), the facts and the local daily books, from `build`'s output."""
    core = B["core"]
    inp, idx = core.inp, core.inp.index
    t0, t1 = (pd.Timestamp(str(d)) for d in rules()["scored"])
    ts = np.asarray((idx >= t0) & (idx <= t1))
    dv = np.asarray((idx >= pd.Timestamp("1990-01-02")) & (idx <= pd.Timestamp("2019-12-31")))
    if not ts.any() or idx[ts][0] != t0 or idx[ts][-1] != t1:
        raise RuntimeError(f"test rows {idx[ts][0] if ts.any() else None} .. {idx[ts][-1] if ts.any() else None} "
                           f"!= the registered window {t0.date()} .. {t1.date()}")
    c, rate, dt = inp.bill[ts], inp.mmy[ts], inp.dt[ts]
    cd, rated, dtd = inp.bill[dv], inp.mmy[dv], inp.dt[dv]
    D = pd.DatetimeIndex(idx[ts])
    books = B["books"]
    full = {r: b["1x"].net for r, b in books.items()}
    net = {r: v[ts] for r, v in full.items()}
    line_full = {r: ev.line(full[r], inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"] for r in full}
    line = {r: v[ts] for r, v in line_full.items()}
    for r, v in line.items():
        if not np.isfinite(v).all():
            raise RuntimeError(f"{r}: the ex-ante line is not finite on every test row")
    lab = {"tier": "disclosed-reuse", "label": spec()["label"], "tlt_leg": paths.rules()["bonds"]["label"]}
    out, facts = {}, {"n_test_rows": int(ts.sum()), "test_first": str(D[0].date()), "test_last": str(D[-1].date())}

    # metrics (1× and stress books, the lines, the 10-year row)
    m = []
    for r, bk in books.items():
        for k, b in bk.items():
            g = np.abs(b.held).sum(axis=1)
            m.append({"rung": r, "book": k, "role": "official" if r in OFFICIAL else "descriptive",
                      **ev.metrics(b.net[ts], c, b.turnover[ts], b.cost[ts], b.financing[ts], g[ts])})
    for r, v in line.items():
        m.append({"rung": f"{r}-line", "book": "1x", "role": "benchmark (ex ante line at the rung's vol)",
                  **ev.metrics(v, c)})
    for r, b in B["books10"].items():
        g = np.abs(b.held).sum(axis=1)
        m.append({"rung": f"{r}@10y", "book": "1x", "role": "POST-HOC sensitivity (owner), not QA'd vs an ETF",
                  **ev.metrics(b.net[ts], c, b.turnover[ts], b.cost[ts], b.financing[ts], g[ts])})
    out["metrics"] = pd.DataFrame(m).assign(**lab)

    # family (D5.3) with matching (D5.2)
    fam = []
    for child, ref, kind in family_rows():
        x = net[child]
        y = line[child] if kind == "line" else net[ref]
        yd = line_full[child][dv] if kind == "line" else full[ref][dv]
        xd = full[child][dv]
        row = ev.ablation_row(x, y, c, rate, dt)
        vx = _vol(x - c)
        k = vx / _vol(y - c)
        ym = ev.rescale(y, c, vx, rate, dt, spread_bp=paths.rules()["accounting"]["financing_spread_bp"])
        ds_dev = ev.pair(xd, yd, cd, rated, dtd)[0]
        ymd = ev.rescale(yd, cd, _vol(xd - cd), rated, dtd, spread_bp=25.0)
        s1, s2 = ev.sr(xd - cd) / math.sqrt(ANN), ev.sr(ymd - cd) / math.sqrt(ANN)
        rho = float(np.corrcoef(xd - cd, ymd - cd)[0, 1])
        fam.append({"child": child, "reference": ref, "kind": kind, "k": k, "financed_above_1x": bool(k > 1),
                    "matched_vol_abs_err": abs(_vol(ym - c) - vx), **row, "dsharpe_dev": ds_dev,
                    "sign_agrees_with_dev": bool(np.sign(row["dsharpe"]) == np.sign(ds_dev)),
                    "power_at_test_length": power(s1, s2, rho, int(ts.sum()), 0.05)})
    fam = pd.DataFrame(fam)
    fam["holm_p"] = adjust_pvalues(fam["p_one_sided"].to_numpy(), "holm")
    fam["beat_raw"] = (fam.dsharpe >= 0.05) & (fam.p_one_sided < 0.05)
    fam["beat_holm"] = (fam.dsharpe >= 0.05) & (fam.holm_p < 0.05)
    out["family"] = fam.assign(match=spec()["match"]["label"], **lab)
    out["headline"] = headline(fam)

    # every rung vs L1 (comparison row, descriptive)
    out["vs_l1"] = pd.DataFrame([{"rung": r, **ev.ablation_row(net[r], net["L1"], c, rate, dt)}
                                 for r in OFFICIAL + DESCRIPTIVE if r != "L1"]).assign(**lab)

    # costs: frozen rules re-scored (robustness_legs, counted no)
    par = paths.prereg()["r4_evaluation"]["parents"]
    cr = []
    for r in [x for x in OFFICIAL + ["L5-lev"] if x in par]:
        for k in ("1x", "2x", "3x", "f75"):
            x, y = books[r][k].net[ts], books[par[r]][k].net[ts]
            cr.append({"rung": r, "parent": par[r], "book": k, "sharpe": ev.sr(x - c),
                       "dsharpe_vs_parent": ev.pair(x, y, c, rate, dt, spread_bp=25.0 + (75.0 if k == "f75" else 0.0))[0]})
    out["costs"] = pd.DataFrame(cr).assign(label=spec()["scope"]["costs"]["label"], tier="disclosed-reuse",
                                           tlt_leg=lab["tlt_leg"])

    # crisis panels (COVID, 2022)
    pos = {k: v for k, v in ev.crisis_positions(D).items() if k in rules()["crisis"]}
    cz = []
    for r in OFFICIAL + DESCRIPTIVE:
        h = books[r]["1x"].held[ts]
        pm = {row["crisis"]: row for row in ev.crisis_matched(net[r], net[par[r]], c, rate, dt, pos)} if r in par else {}
        for k, p in pos.items():
            cz.append({"rung": r, "crisis": k, "start": str(D[p[0]].date()), "end": str(D[p[-1]].date()),
                       "return": float(np.prod(1 + net[r][p]) - 1), "line_return": float(np.prod(1 + line[r][p]) - 1),
                       "diff_vs_line": float(np.prod(1 + net[r][p]) - np.prod(1 + line[r][p])),
                       "parent": par.get(r), "parent_matched_return": pm[k]["parent_matched_return"] if pm else None,
                       "diff_vs_parent_matched": pm[k]["diff_matched"] if pm else None,
                       "spy_return": float(np.prod(1 + net["L0"][p]) - 1), "max_dd": float(ev.qdd.max_dd(net[r][p])),
                       "w_spy": float(h[p, 0].mean()), "w_tlt": float(h[p, 1].mean()),
                       "w_cash": float(np.maximum(1 - h[p].sum(axis=1), 0).mean())})
    out["crisis"] = pd.DataFrame(cz).assign(note=spec()["match"]["crisis_note"], **lab)

    # the owner's post-hoc 10-year row
    tr = []
    for r, b in B["books10"].items():
        x10 = b.net[ts]
        l10 = ev.line(b.net, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"][ts]
        a25 = ev.ablation_row(x10, net[r], c, rate, dt)
        aln = ev.ablation_row(x10, l10, c, rate, dt)
        row = {"variant": f"{r}@10y", "rung": r, "sharpe_10y": ev.sr(x10 - c), "sharpe_25y": ev.sr(net[r] - c),
               "cagr_10y": ev.metrics(x10, c)["cagr"], "cagr_25y": ev.metrics(net[r], c)["cagr"],
               "dsharpe_vs_25y": a25["dsharpe"], "lo_vs_25y": a25["lo"], "hi_vs_25y": a25["hi"],
               "p_vs_25y": a25["p_one_sided"], "dsharpe_vs_line": aln["dsharpe"], "lo_vs_line": aln["lo"],
               "hi_vs_line": aln["hi"], "p_vs_line": aln["p_one_sided"]}
        for k, p in pos.items():
            row[f"{k}_return_10y"] = float(np.prod(1 + x10[p]) - 1)
            row[f"{k}_return_25y"] = float(np.prod(1 + net[r][p]) - 1)
        tr.append(row)
    out["sens10y"] = pd.DataFrame(tr).assign(label=spec()["sensitivity_10y"]["label"], tier="disclosed-reuse")

    # v1 vs v2 side by side + the R1 corrections itemised
    if recon is not None:
        out["v1_vs_v2"], out["v1_corrections"] = v1_vs_v2(out["metrics"], recon)

    # DSR (D5.4)
    d = rules()["dsr"]
    dr = []
    for r in OFFICIAL:
        for row in dsr_rows(net[r] - c, d["n_headline"], d["n_raw"], d["v_dev"], r4_k_gap):
            if r4_dsr is not None:
                q = r4_dsr[(r4_dsr.rung == r) & r4_dsr.pool.str.startswith("headline")]
                row["dsr_development_headline"] = float(q.dsr.iloc[0]) if len(q) else None
            dr.append({"rung": r, **row})
    out["dsr"] = pd.DataFrame(dr).assign(label=spec()["dsr"]["label"], tier="disclosed-reuse", tlt_leg=lab["tlt_leg"])

    # placebos (D5.8, descriptive; counted no)
    out["placebo"] = placebos(B, ts, c, rate, dt, pos, net)

    # facts
    kp = B["core"].keep
    gated = rungs.carry(kp["corr126"])[ts, 1] == 0
    trd = rungs.carry(kp["trend"])[ts]
    g8 = B["core"].rt["g"][ts]
    facts.update({
        "L6_share_test_days_tlt_gated": float(gated.mean()),
        "trend_share_test_days_spy_out": float((trd[:, 0] == 0).mean()),
        "trend_share_test_days_tlt_out": float((trd[:, 1] == 0).mean()),
        "L8_g_min_test": float(g8.min()), "L8_share_test_days_g_below_1": float((g8 < 1).mean()),
        "vol_zoo_picks_test": {
            "label": "re-selected by the registered causal rule (losses <= prior year-end)",
            "L5 (L4 book, 25y)": {y + 1: B["picks"][y]["pick"] for y in sorted(B["picks"]) if y >= t0.year - 1},
            "L5@10y (L4 book, 10y)": {y + 1: B["picks10"][y]["pick"] for y in sorted(B["picks10"]) if y >= t0.year - 1},
            "L2-u (SPY)": {y + 1: B["picks_spy"][y]["pick"] for y in sorted(B["picks_spy"]) if y >= t0.year - 1},
            "footnote_frozen_2019_pick": B["picks"][t0.year - 1]["pick"]},
        "family_k": {f"{a} vs {b}": float(k) for a, b, k in zip(fam.child, fam.reference, fam.k, strict=True)},
        "max_matched_vol_abs_err_k_le_1": float(fam.loc[~fam.financed_above_1x, "matched_vol_abs_err"].max())
        if (~fam.financed_above_1x).any() else None,
        "max_matched_vol_abs_err_k_gt_1": float(fam.loc[fam.financed_above_1x, "matched_vol_abs_err"].max())
        if fam.financed_above_1x.any() else None,
        "share_family_sign_agrees": float(fam.sign_agrees_with_dev.mean()),
        "f75_equals_1x_sharpe_max_abs": {r: abs(ev.sr(books[r]["f75"].net[ts] - c) - ev.sr(net[r] - c))
                                         for r in OFFICIAL + ["L5-lev"]},
        "trial_var": dict(zip(("value", "source"), trial_var(d["v_dev"], int(ts.sum())), strict=True)),
    })

    # local daily books (gitignored): full history, for the figures
    loc = {"bill": inp.bill, "spy_proxy": inp.R[:, 0], "tlt_proxy": inp.R[:, 1],
           "corr126": regime.corr(inp, paths.rules()["r3"]["L6"]["windows"]["primary"]),
           "corr126_gate": rungs.carry(kp["corr126"])[:, 1], "trend_spy": rungs.carry(kp["trend"])[:, 0],
           "trend_tlt": rungs.carry(kp["trend"])[:, 1], "L8_g": B["core"].rt["g"]}
    for r, bk in books.items():
        loc[f"{r}_net"] = bk["1x"].net
        loc[f"{r}_w_spy"], loc[f"{r}_w_tlt"] = bk["1x"].held[:, 0], bk["1x"].held[:, 1]
        loc[f"{r}_line"] = line_full[r]
    for r, b in B["books10"].items():
        loc[f"{r}@10y_net"] = b.net
    out["local"] = pd.DataFrame(loc, index=idx)
    out["facts"] = facts
    return out
