"""R6 evaluation (spec/prereg_r6.yaml comparisons, verdict, dsr, checks; D6.4). Every number is descriptive.

Per window (development 1990-01-02 → 2019-12-31 "in-sample"; test 2020-01-02 → 2026-09-30 "disclosed reuse: ideas
inspired by this window"), on the window's rows only:
- metrics: `evaluate.metrics` (CAGR, vol, excess Sharpe, Sortino, max DD, CDaR-95, turnover, costs, financing, gross)
  for every candidate, reference rung, and the candidate's ex-ante line (`evaluate.line` on the full book, sliced);
- compare: `evaluate.ablation_row(x, ref)`: ref rescaled once ex post to x's excess vol in the window (bill + 25 bp
  above 1×), ΔSharpe with the LW 95% interval and one-sided p, CDaR-95 / max-DD ratios with dd_ratio_ci; references =
  own parent, L2, L3, the line (= L0 matched, D6.4 amendment 4), and L6 beside R6c_infl;
- verdict: `word` per window from the own-parent row (ΔSharpe ±0.05 or the CDaR 0.85 route), `verdict` for the pair;
- crisis (test): `evaluate.crisis_matched` for COVID and 2022 vs own parent, L2, L3, L0 (matched on the whole test);
- costs: Sharpe and the matched point ΔSharpe vs own parent at 1×, 2×, 3×, +75 bp (parent stressed alike);
- dsr: `testwin.dsr_rows` per window with N_headline / N_raw from prereg_r6; power at the test length (R5 formula).
Complexity: O(draws · T) per compared pair (≈ 140 pairs × LW 1,000 + 2 dd_ratio_ci 1,000), split over a process pool
(each task a pure function of its arrays; a thread pool: quantkit's bootstraps release the GIL partly (≈ 1.45× at 4
threads) and threads add no memory, where each spawned process cost ≈ 520 MB (perf.md); 1 vs N bit-identical, tested).
A (candidate, window, reference) pair that is both the own parent and a column (L2, L3, line) is computed once.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from quantkit.stats.power import power

from r6lib import spec
from rspy import evaluate as ev
from rspy import testwin

ANN = 252
REF_ROWS = ["L0", "L1", "L2", "L3", "L5", "L7"]
METRIC_COLS = ["cagr", "vol", "sharpe_excess", "sortino", "max_dd", "cdar95", "turnover_pa", "cost_pa",
               "financing_pa", "avg_gross"]


def candidates() -> list[dict]:
    """[{id, parent, family}] in registration order."""
    c = spec()["candidates"]
    out = [{"id": c["R6a"]["id"], "parent": c["R6a"]["parent"], "family": "R6a"}]
    out += [{"id": r["id"], "parent": r["parent"], "family": "R6b"} for r in c["R6b"]["rows"]]
    out += [{"id": r["id"], "parent": r["parent"], "family": "R6c"} for r in c["R6c"]["rows"]]
    out += [{"id": c["R6d"]["id"], "parent": c["R6d"]["parent"], "family": "R6d"}]
    out += [{"id": r["id"], "parent": r["parent"], "family": "R6e"} for r in c["R6e"]["rows"]]
    out += [{"id": c["R6f"]["id"], "parent": c["R6f"]["parent"], "family": "R6f"}]
    if len(out) != spec()["dsr"]["n_r6"]:
        raise RuntimeError(f"{len(out)} candidates, prereg_r6 says n_r6 = {spec()['dsr']['n_r6']}")
    return out


def windows(idx: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    w = spec()["windows"]
    out = {}
    for k in ("development", "test"):
        a, z = pd.Timestamp(str(w[k]["start"])), pd.Timestamp(str(w[k]["end"]))
        m = np.asarray((idx >= a) & (idx <= z))
        if idx[m][0] != a or idx[m][-1] != z:
            raise RuntimeError(f"{k} rows {idx[m][0].date()} .. {idx[m][-1].date()} != {a.date()} .. {z.date()}")
        out[k] = m
    return out


def label(window: str) -> str:
    return spec()["windows"][window]["label"]


def ref_book(parent: str) -> str:
    return "L0" if parent == "line" else parent


def _gross(b) -> np.ndarray:
    return b.gross_exposure if hasattr(b, "gross_exposure") else np.abs(b.held).sum(axis=1)


# ---- verdict (D6.4) ----------------------------------------------------------------------------------------------------
def word(ds: float, lo: float, hi: float, cr: float, cr_lo: float, cr_hi: float) -> tuple[str, str, bool]:
    """(better | same | worse, leg, clearly) for one window."""
    me = spec()["verdict"]["min_effect"]
    d, q = me["dsharpe"], me["cdar_ratio"]
    if ds >= d:
        return "better", "Sharpe", bool(lo > 0)
    if ds <= -d:
        return "worse", "Sharpe", bool(hi < 0)
    if np.isfinite(cr) and cr <= q:
        return "better", "drawdown", bool(cr_hi < 1)
    if np.isfinite(cr) and cr >= 1.0 / q:
        return "worse", "drawdown", bool(cr_lo > 1)
    return "same", "-", False


def verdict(dev: str, test: str) -> str:
    return spec()["verdict"]["words"][f"{dev},{test}"]


# ---- comparisons -------------------------------------------------------------------------------------------------------
def _task(a):
    x, y, c, rate, dt = a
    return ev.ablation_row(x, y, c, rate, dt)


def run_pairs(tasks: list[tuple], workers: int) -> list[dict]:
    if workers <= 1:
        return [_task(t) for t in tasks]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_task, tasks))


def evaluate(B: dict, *, workers: int = 1) -> dict:
    inp = B["inp"]
    idx = inp.index
    W = windows(idx)
    books = B["books"]
    cands = candidates()
    full = {k: v["1x"].net for k, v in books.items()}
    line = {c["id"]: ev.line(full[c["id"]], inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["returns"] for c in cands}
    tier = {"development": "in-sample", "test": "disclosed-reuse"}
    out: dict = {}

    # metrics
    m = []
    for w, mask in W.items():
        c = inp.bill[mask]
        for name in [x["id"] for x in cands] + REF_ROWS:
            b = books[name]["1x"]
            role = "R6 candidate" if name.startswith("R6") else "reference (R5 rung)"
            m.append({"row": name, "window": w, "role": role,
                      **ev.metrics(b.net[mask], c, b.turnover[mask], b.cost[mask], b.financing[mask], _gross(b)[mask])})
        for x in cands:
            m.append({"row": f"{x['id']}-line", "window": w, "role": "SPY + T-bills, ex ante at the candidate's vol",
                      **ev.metrics(line[x["id"]][mask], c)})
    out["metrics"] = pd.DataFrame(m).assign(label=lambda d: d.window.map(label), tier=lambda d: d.window.map(tier))

    # matched comparisons
    keys, tasks, slot = [], [], {}
    for w, mask in W.items():
        c, rate, dt = inp.bill[mask], inp.mmy[mask], inp.dt[mask]
        for x in cands:
            refs = [("own", x["parent"]), ("L2", "L2"), ("L3", "L3"), ("line", "line")]
            if x["id"] == "R6c_infl":
                refs.append(("beside", "L6"))
            for kind, r in refs:
                u = (x["id"], w, r)
                if u not in slot:
                    slot[u] = len(tasks)
                    tasks.append((full[x["id"]][mask], full[ref_book(r)][mask], c, rate, dt))
                keys.append(({"candidate": x["id"], "family": x["family"], "window": w, "reference": r, "kind": kind,
                              "own_parent": x["parent"]}, slot[u]))
    res = run_pairs(tasks, workers)
    cmp_ = pd.DataFrame([{**k, **res[j]} for k, j in keys])
    cmp_["reference_note"] = np.where(cmp_.reference == "line", "L0 rescaled ex post to the candidate's vol", "")
    out["compare"] = cmp_.assign(label=lambda d: d.window.map(label), tier=lambda d: d.window.map(tier))

    # power at the test length (development point Sharpes and correlation vs the own parent matched on development)
    dv, ts = W["development"], W["test"]
    cd, rated, dtd = inp.bill[dv], inp.mmy[dv], inp.dt[dv]
    pw = {}
    for x in cands:
        xd, yd = full[x["id"]][dv], full[ref_book(x["parent"])][dv]
        ymd = ev.rescale(yd, cd, float(np.std(xd - cd, ddof=1)) * math.sqrt(ANN), rated, dtd, spread_bp=25.0)
        s1, s2 = ev.sr(xd - cd) / math.sqrt(ANN), ev.sr(ymd - cd) / math.sqrt(ANN)
        rho = float(np.corrcoef(xd - cd, ymd - cd)[0, 1])
        pw[x["id"]] = power(s1, s2, rho, int(ts.sum()), 0.05)

    # verdicts
    own = cmp_[cmp_.kind == "own"].set_index(["candidate", "window"])
    mt = out["metrics"].set_index(["row", "window"])
    v = []
    for x in cands:
        row = {"candidate": x["id"], "family": x["family"], "own_parent": x["parent"]}
        ws = {}
        for w in W:
            o = own.loc[(x["id"], w)]
            wd, leg, clear = word(o.dsharpe, o.lo, o.hi, o.cdar_ratio, o.cdar_lo, o.cdar_hi)
            ws[w] = wd
            row |= {f"{w}_word": wd, f"{w}_leg": leg, f"{w}_clearly": clear, f"{w}_dsharpe": o.dsharpe,
                    f"{w}_lo": o.lo, f"{w}_hi": o.hi, f"{w}_cdar_ratio": o.cdar_ratio,
                    f"{w}_sharpe": mt.loc[(x["id"], w), "sharpe_excess"]}
        row["verdict"] = verdict(ws["development"], ws["test"])
        row["power_at_test_length"] = pw[x["id"]]
        if x["family"] == "R6e":
            for w in W:
                t_c, t_p = mt.loc[(x["id"], w), "turnover_pa"], mt.loc[("L2", w), "turnover_pa"]
                row[f"{w}_turnover_change_pct"] = 100.0 * (t_c / t_p - 1.0)
        v.append(row)
    out["verdict"] = pd.DataFrame(v).assign(label_development=label("development"), label_test=label("test"))

    # crisis panels (test window)
    D = pd.DatetimeIndex(idx[ts])
    pos = {k: p for k, p in ev.crisis_positions(D).items() if k in ("covid", "infl_2022")}
    c, rate, dt = inp.bill[ts], inp.mmy[ts], inp.dt[ts]
    cz = []
    for x in cands:
        xn = full[x["id"]][ts]
        h = books[x["id"]]["1x"].held[ts]
        for r in dict.fromkeys([x["parent"], "L2", "L3", "line"]):
            for q in ev.crisis_matched(xn, full[ref_book(r)][ts], c, rate, dt, pos):
                p = pos[q["crisis"]]
                cz.append({"candidate": x["id"], "reference": r, "own_parent": r == x["parent"], **q,
                           "w_spy": float(h[p, 0].mean()), "w_tlt": float(h[p, 1].mean()),
                           "w_cash": float(np.maximum(1 - h[p].sum(axis=1), 0).mean())})
    out["crisis"] = pd.DataFrame(cz).assign(label=label("test"), tier="disclosed-reuse",
                                            note="reference matched on the whole test window; in-crisis vols not matched")

    # costs
    cr = []
    for w, mask in W.items():
        c, rate, dt = inp.bill[mask], inp.mmy[mask], inp.dt[mask]
        for x in cands:
            for k in ("1x", "2x", "3x", "f75"):
                xs, ys = books[x["id"]][k].net[mask], books[ref_book(x["parent"])][k].net[mask]
                cr.append({"candidate": x["id"], "window": w, "book": k, "sharpe": ev.sr(xs - c),
                           "dsharpe_vs_own_parent": ev.pair(xs, ys, c, rate, dt,
                                                            spread_bp=25.0 + (75.0 if k == "f75" else 0.0))[0]})
    out["costs"] = pd.DataFrame(cr).assign(label=lambda d: d.window.map(label))

    # DSR
    d = spec()["dsr"]
    dr = []
    for w, mask in W.items():
        n_head = d["test"]["n_headline"] if w == "test" else d["development"]["n_used"]
        for x in cands:
            rows = testwin.dsr_rows(full[x["id"]][mask] - inp.bill[mask], n_head, d["test"]["n_raw"],
                                    d["test"]["v_dev"], d["test"]["k_gap"])
            rows[0]["pool"] = f"headline (N = {n_head}: R5/R4 N + {d['n_r6']} R6 rows)"
            rows[1]["pool"] = f"raw N = {d['test']['n_raw']} (variants.csv counted incl. R6)"
            dr += [{"candidate": x["id"], "window": w, **r} for r in rows]
    out["dsr"] = pd.DataFrame(dr).assign(label=lambda d_: d_.window.map(label))
    out["line_local"] = line
    return out


# ---- identity checks (prereg_r6 checks; ledger: E6.1 tolerance restated) ---------------------------------------------
def _rel(a: pd.DataFrame, b: pd.DataFrame, cols) -> float:
    """Max relative difference (the committed CSVs carry 10 significant digits: ≤ 5e-10 is exact to their rounding)."""
    cols = [c for c in cols if c in a.columns and c in b.columns]
    x, y = a[cols].to_numpy(float), b[cols].to_numpy(float)
    if (np.isfinite(x) != np.isfinite(y)).any():
        return math.inf
    ok = np.isfinite(x) & np.isfinite(y)
    d = np.abs(x[ok] - y[ok]) / np.maximum(np.abs(y[ok]), 1e-300)
    return float(np.where(np.abs(x[ok] - y[ok]) == 0, 0.0, d).max()) if ok.any() else 0.0


def identity(E: dict, B: dict, reports, data) -> dict:
    """{check: (value, tolerance)}: exact book equality against the local R2/R3/R5 books, and metrics against the
    committed R2-R5 tables within their rounding."""
    out = {}
    idx = B["inp"].index
    r5b = pd.read_parquet(data / "r5" / "books.parquet")
    if not r5b.index.equals(idx):
        raise RuntimeError("data/r5/books.parquet index != the R6 build index (run make r5-replay)")
    dev_rows = np.asarray(idx <= pd.Timestamp("2019-12-31"))
    old = {k: pd.read_parquet(data / k / "books.parquet") for k in ("r2", "r3")}
    for r in ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        b = B["books"][r]["1x"]
        cols = {"net": b.net, "w_spy": b.held[:, 0], "w_tlt": b.held[:, 1]}
        out[f"{r}_books_vs_r5_exact"] = (float(not all(np.array_equal(v, r5b[f"{r}_{k}"].to_numpy())
                                                       for k, v in cols.items())), 0.0)
        for k, o in old.items():
            if f"{r}_net" in o:
                out[f"{r}_books_dev_vs_{k}_exact"] = (float(not all(np.array_equal(v[dev_rows], o[f"{r}_{c}"].to_numpy())
                                                                    for c, v in cols.items())), 0.0)
    for r in ("L5", "L7"):
        out[f"R6b_{r}@10y_net_vs_r5_exact"] = (float(not np.array_equal(B["books"][f"R6b_{r}@10y"]["1x"].net,
                                                                        r5b[f"{r}@10y_net"].to_numpy())), 0.0)
    m = E["metrics"].set_index(["row", "window"])
    r5 = pd.read_csv(reports / "r5" / "metrics.csv")
    r5 = r5[r5.book == "1x"].set_index("rung")
    r2 = pd.read_csv(reports / "r2" / "metrics.csv")
    r3 = pd.read_csv(reports / "r3" / "metrics.csv")
    dev = pd.concat([r2[r2.book == "1x"], r3]).drop_duplicates("rung").set_index("rung")   # r3 has 1x rows only
    for r in REF_ROWS:
        out[f"{r}_test_metrics_vs_r5_rel"] = (_rel(m.loc[[(r, "test")]], r5.loc[[r]], METRIC_COLS), 5e-10)
        out[f"{r}_dev_metrics_vs_r2r3_rel"] = (_rel(m.loc[[(r, "development")]], dev.loc[[r]], METRIC_COLS), 5e-10)
    out["R6c_L6-63_dev_metrics_vs_r3_rel"] = (_rel(m.loc[[("R6c_L6-63", "development")]], dev.loc[["L6-63"]],
                                                   METRIC_COLS), 5e-10)
    s4 = pd.read_csv(reports / "r4" / "sensitivity.csv").set_index("variant")
    for r in ("L3", "L4", "L5", "L7"):
        a = m.loc[[(f"R6b_{r}@10y", "development")]].rename(columns={"sharpe_excess": "sharpe"})
        cols = ["sharpe", "cagr", "vol", "max_dd", "cdar95", "turnover_pa", "cost_pa"]
        b = s4.loc[[f"{r}@10y"]]
        out[f"R6b_{r}@10y_dev_vs_r4_abs"] = (float(np.abs(a[cols].to_numpy(float) - b[cols].to_numpy(float)).max()),
                                             1e-9)
    s5 = pd.read_csv(reports / "r5" / "sens10y.csv").set_index("variant")
    for r in ("L5", "L7"):
        x, y = float(m.loc[(f"R6b_{r}@10y", "test"), "sharpe_excess"]), float(s5.loc[f"{r}@10y", "sharpe_10y"])
        out[f"R6b_{r}@10y_test_sharpe_vs_r5_rel"] = (abs(x - y) / abs(y), 5e-10)
    return out
