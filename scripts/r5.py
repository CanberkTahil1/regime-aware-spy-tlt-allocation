"""R5: the test window 2020-01-02 → 2026-09-30, frozen rules run once (spec/prereg.yaml r5_test; D5.1–D5.6).

Modes (D5.5):
- `--mode dry` (`make dry-run`): the whole pipeline on `testwin.synthetic_panel` into a new temporary directory. Refuses
  if RSPY_TEST_RUN is set; never writes under reports/ or the data directory. A code check, never evidence.
- `--mode run` (`make test-run`, run once): `freeze.guard` (lock hashes, clean locked files, RSPY_TEST_RUN=run-once,
  no reports/r5/test_run.json), then `freeze.start_record` BEFORE any statistic, then the build, the development
  identity checks (a mismatch stops the run: record status "stopped", the owner's call), the evaluation, the outputs,
  `freeze.complete_record`.
- `--mode replay` (`make r5-replay`, part of `make all`): needs a completed record and a matching lock; recomputes into
  a temporary directory, requires every committed reports/r5 table to be byte-identical, then writes the local books.
Committed (statistics only): reports/r5/{metrics, family, vs_l1, costs, crisis, sens10y, dsr, v1_vs_v2,
v1_corrections}.csv, headline.json,
facts.json, test_run.json. Local only (gitignored, KF-derived daily series): data/r5/books.parquet.
"""

import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time

import numpy as np
import pandas as pd

from rspy import freeze, paths, testwin
from rspy.data import build as dbuild

TABLES = ("metrics", "family", "vs_l1", "costs", "crisis", "sens10y", "dsr", "v1_vs_v2", "v1_corrections")
JSONS = ("headline", "facts")


def write(E: dict, out: pathlib.Path, local: pathlib.Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    for k in TABLES:
        E[k].to_csv(out / f"{k}.csv", index=False, float_format="%.10g")
    for k in JSONS:
        (out / f"{k}.json").write_text(json.dumps(E[k], indent=1, sort_keys=True, default=float) + "\n")
    E["local"].to_parquet(local / "books.parquet")
    return {f"reports/r5/{p.name}": paths.sha256(p) for p in sorted(out.iterdir()) if p.name != "test_run.json"}


def stored_identity(B: dict) -> dict:
    """Extended books vs the stored R2/R3 local books (data/r2, data/r3), rows ≤ 2019-12-31, bit for bit."""
    out = {}
    for d, names in (("r2", ["L0", "L1", "L2", "L3", "L4", "L5", "L5-lev", "L2-u"]), ("r3", ["L6", "L7", "L8"])):
        f = paths.data_dir() / d / "books.parquet"
        if not f.exists():
            out[f"{d}_books_present"] = False
            continue
        o = pd.read_parquet(f)
        n = len(o)
        if not B["core"].inp.index[:n].equals(o.index):
            out[f"{d}_index"] = False
            continue
        for r in names:
            out[f"{r}_equals_{d}_book"] = bool(np.array_equal(B["books"][r]["1x"].net[:n], o[f"{r}_net"].to_numpy()))
    return out


def r4_inputs() -> tuple[pd.DataFrame | None, int]:
    p = paths.REPORTS / "r4"
    k_gap = json.loads((p / "facts.json").read_text())["dsr_pool"]["k_gap"]
    return pd.read_csv(p / "dsr.csv"), int(k_gap)


def compute(panel: pd.DataFrame, *, stored: bool) -> tuple[dict, dict, dict]:
    t0 = time.perf_counter()
    end = str(paths.rules()["r5"]["scored"][1])
    B = testwin.build(panel, end)
    t_build = time.perf_counter()
    ident = testwin.dev_identity(B, testwin.dev_only_books(panel))
    if stored:
        ident |= stored_identity(B)
    t_ident = time.perf_counter()
    bad = [k for k, v in ident.items() if v is False]
    if bad:
        return {}, ident, {"stopped": f"development rows moved: {bad}"}
    r4d, kg = r4_inputs()
    E = testwin.evaluate(B, r4_dsr=r4d, r4_k_gap=kg, recon=pd.read_csv(paths.REPORTS / "r1" / "reconciliation.csv"))
    E["facts"]["dev_identity"] = ident
    timing = {"build": round(t_build - t0, 2), "identity": round(t_ident - t_build, 2),
              "evaluate": round(time.perf_counter() - t_ident, 2), "total": round(time.perf_counter() - t0, 2)}
    return E, ident, timing


def show(E: dict) -> None:
    pd.set_option("display.width", 220)
    m = E["metrics"]
    print(m[m.book == "1x"].set_index("rung")[["cagr", "vol", "sharpe_excess", "max_dd", "cdar95", "turnover_pa"]]
          .round(4).to_string())
    print(E["family"][["child", "reference", "k", "dsharpe", "lo", "hi", "p_one_sided", "holm_p", "beat_raw",
                       "beat_holm", "dsharpe_dev", "sign_agrees_with_dev", "power_at_test_length"]].round(3)
          .to_string(index=False))
    print(json.dumps(E["headline"], indent=1, default=float))
    print(E["crisis"][["rung", "crisis", "return", "line_return", "diff_vs_line", "parent",
                       "diff_vs_parent_matched"]].round(4).to_string(index=False))
    print(E["sens10y"].drop(columns=["label", "tier"]).round(3).to_string(index=False))
    print(E["dsr"][["rung", "pool", "dsr", "sr_ann", "sr0_ann", "trial_var_source"]].round(3).to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dry", "run", "replay"], required=True)
    ap.add_argument("--seed", type=int, default=paths.rules()["r5"]["dry_run"]["seed"])
    a = ap.parse_args()
    if a.mode == "dry":
        if os.environ.get(freeze.ENV):
            sys.exit(f"dry run refused: {freeze.ENV} is set (the dry run never runs beside the real one)")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="rspy_r5_dry_"))
        for forbidden in (paths.REPORTS, paths.data_dir()):
            if forbidden.resolve() in tmp.resolve().parents:
                sys.exit(f"dry run refused: output {tmp} is under {forbidden}")
        rec_before = (paths.ROOT / freeze.RECORD).exists()
        E, ident, timing = compute(testwin.synthetic_panel(a.seed), stored=False)
        if not E:
            sys.exit(f"dry run: {timing['stopped']}")
        write(E, tmp / "r5", tmp / "local")
        assert (paths.ROOT / freeze.RECORD).exists() == rec_before, "the dry run touched reports/r5/test_run.json"
        show(E)
        print(f"DRY RUN (synthetic, seed {a.seed}; code check, not evidence) -> {tmp}; identity {all(ident.values())} "
              f"({len(ident)} checks); timing {timing}")
        return 0
    if a.mode == "run":
        try:
            freeze.guard()
        except freeze.GuardError as e:
            sys.exit(str(e))
        rec = freeze.start_record()
        print("test_run.json started:", rec["started_utc"], "lock", rec["lock_sha256"][:12])
        E, ident, timing = compute(dbuild.load(), stored=True)
        unl = freeze.loaded_unlocked(freeze.read())
        if not E or unl:
            p = paths.ROOT / freeze.RECORD
            r = json.loads(p.read_text())
            r.update({"status": "stopped", "reason": timing.get("stopped") or f"unlocked modules loaded: {unl}",
                      "dev_identity": ident})
            p.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
            sys.exit(f"test run STOPPED (owner's call): {r['reason']}")
        outs = write(E, paths.REPORTS / "r5", paths.data_dir() / "r5")
        freeze.complete_record(outs, timing)
        show(E)
        print(f"TEST RUN complete ({testwin.spec()['label']}); timing {timing}")
        return 0
    rec_p = paths.ROOT / freeze.RECORD
    if not rec_p.exists() or json.loads(rec_p.read_text())["status"] != "completed":
        sys.exit("replay refused: no completed reports/r5/test_run.json")
    probs = freeze.verify(git=False)
    if probs:
        sys.exit("replay refused: the lock does not match:\n  " + "\n  ".join(probs))
    E, ident, timing = compute(dbuild.load(), stored=True)
    if not E:
        sys.exit(f"replay: {timing['stopped']}")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="rspy_r5_replay_"))
    write(E, tmp / "r5", tmp / "local")
    diff = [f for f in (*(f"{k}.csv" for k in TABLES), *(f"{k}.json" for k in JSONS))
            if (tmp / "r5" / f).read_bytes() != (paths.REPORTS / "r5" / f).read_bytes()]
    if diff:
        sys.exit(f"replay: committed reports/r5 differ from the recomputation: {diff} (kept in {tmp})")
    (paths.data_dir() / "r5").mkdir(parents=True, exist_ok=True)
    shutil.copy(tmp / "local" / "books.parquet", paths.data_dir() / "r5" / "books.parquet")
    print(f"replay: every reports/r5 table byte-identical; local books -> data/r5 ({timing})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
