"""The R5 freeze lock and the run-once guard (D5.5; spec/prereg.yaml r5_test.freeze).

`spec/freeze.lock.json` records content hashes; they alone decide (the commit sha is a label: the owner's history
rewrite will change it). Locked:
- `SPEC`: the pre-registration, the rules, the quantkit pin, uv.lock, pyproject.toml and the Makefile;
- the engine (`engine_files`): every module that turns data into test-window P&L: src/rspy/**/*.py except the
  figure/page modules (`NOT_ENGINE`), legacy/**/*.py (L1), tests/legacy_support.py (the yfinance stub L1 imports),
  scripts/r5.py;
- the data: the build key of data/build.json (raw-file, rspy.data code and rules hashes), the SHA-256 of
  data/panel.parquet's bytes and the test window (first / last session; a later KF refetch fails the lock).
`verify` lists every mismatch, an engine file the lock does not know, a repo module loaded by the run that is not locked
(`loaded_unlocked`, the pin.py pattern) and uncommitted changes to a locked file. `guard` adds the run-once conditions:
env RSPY_TEST_RUN=run-once and no reports/r5/test_run.json yet. `start_record` writes that record (status "started",
the lock's hashes) atomically BEFORE any test statistic; `complete_record` fills it at the end.
Pattern from dispersion-reversal `src/disprev/holdout/{freeze,guard}.py` @ c09713a (COPIED.md): no tag (owner-only
here), no freeze-changes register (one run).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

import pandas as pd

from rspy import paths

LOCK = "spec/freeze.lock.json"
RECORD = "reports/r5/test_run.json"
ENV, ENV_VALUE = "RSPY_TEST_RUN", "run-once"
SPEC = ("spec/prereg.yaml", "spec/rules.yaml", "spec/quantkit_pin.json", "uv.lock", "pyproject.toml", "Makefile")
NOT_ENGINE = ("src/rspy/figures.py", "src/rspy/site.py", "src/rspy/site_local.py")
EXTRA_ENGINE = ("tests/legacy_support.py", "scripts/r5.py")
VERSION = 1


class GuardError(RuntimeError):
    pass


def engine_files(root: pathlib.Path) -> list[str]:
    out = [p for g in ("src/rspy/**/*.py", "legacy/**/*.py") for p in root.glob(g) if "__pycache__" not in p.parts]
    rel = sorted({str(p.relative_to(root)) for p in out} - set(NOT_ENGINE))
    return sorted({*rel, *(f for f in EXTRA_ENGINE if (root / f).exists())})


def _git(root: pathlib.Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, text=True).stdout.strip()


def data_payload(data_dir: pathlib.Path) -> dict:
    build = json.loads((data_dir / "build.json").read_text())
    idx = pd.read_parquet(data_dir / "panel.parquet", columns=["hi20"]).index
    t = paths.rules()["r5"]["scored"]
    test = idx[(idx >= pd.Timestamp(str(t[0]))) & (idx <= pd.Timestamp(str(t[1])))]
    return {"build_key": build["key"], "panel_sha256": paths.sha256(data_dir / "panel.parquet"),
            "last_session": str(idx[-1].date()),
            "test_window": {"first": str(test[0].date()), "last": str(test[-1].date()), "sessions": int(len(test))}}


def payload(root: pathlib.Path | None = None, data_dir: pathlib.Path | None = None) -> dict:
    root = root or paths.ROOT
    files = {f: paths.sha256(root / f) for f in (*SPEC, *engine_files(root))}
    return {"version": VERSION, "files": files, "data": data_payload(data_dir or paths.data_dir()),
            "note": "content hashes decide; rules_commit is a label (sha before the owner's history rewrite; re-point after)"}


def write(root: pathlib.Path | None = None, data_dir: pathlib.Path | None = None) -> dict:
    root = root or paths.ROOT
    if (root / LOCK).exists():
        raise GuardError(f"{LOCK} exists: a re-freeze is not allowed")
    lock = {**payload(root, data_dir), "frozen_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%MZ"),
            "rules_commit": _git(root, "rev-parse", "HEAD")}
    (root / LOCK).write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    return lock


def read(root: pathlib.Path | None = None) -> dict:
    return json.loads(((root or paths.ROOT) / LOCK).read_text())


def loaded_unlocked(lock: dict, root: pathlib.Path | None = None) -> list[str]:
    """Repo modules in sys.modules whose file is neither locked nor a test/figure module."""
    root = (root or paths.ROOT).resolve()
    out = []
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if not f:
            continue
        p = pathlib.Path(f).resolve()
        if root not in p.parents or ".venv" in p.parts:
            continue
        rel = str(p.relative_to(root))
        if rel.startswith("tests/") and rel not in EXTRA_ENGINE:
            continue
        if rel not in lock["files"] and rel not in NOT_ENGINE:
            out.append(rel)
    return sorted(out)


def verify(root: pathlib.Path | None = None, data_dir: pathlib.Path | None = None, *, git: bool = True) -> list[str]:
    root = root or paths.ROOT
    if not (root / LOCK).exists():
        return [f"{LOCK} missing (run `make freeze`)"]
    lock = read(root)
    now = payload(root, data_dir)
    probs = []
    for f, h in lock["files"].items():
        cur = now["files"].get(f)
        if cur is None:
            probs.append(f"locked file missing: {f}")
        elif cur != h:
            probs.append(f"locked file changed: {f}")
    probs += [f"engine file not in the lock: {f}" for f in sorted(set(now["files"]) - set(lock["files"]))]
    for k in ("build_key", "panel_sha256", "last_session", "test_window"):
        if now["data"][k] != lock["data"][k]:
            probs.append(f"data changed since the freeze: {k}")
    if git:
        dirty = _git(root, "status", "--porcelain", "--", LOCK, *lock["files"])
        probs += [f"uncommitted change: {ln}" for ln in dirty.splitlines()]
    return probs


def guard(root: pathlib.Path | None = None, data_dir: pathlib.Path | None = None) -> None:
    """Refuse the test run unless every run-once condition holds (D5.5). Raises GuardError listing every problem."""
    root = root or paths.ROOT
    probs = verify(root, data_dir)
    if os.environ.get(ENV) != ENV_VALUE:
        probs.append(f"env {ENV}={ENV_VALUE} not set")
    if (root / RECORD).exists():
        probs.append(f"{RECORD} exists: the test window has been run (a rerun needs a logged, visible deletion)")
    if probs:
        raise GuardError("test run refused:\n  " + "\n  ".join(probs))


def start_record(root: pathlib.Path | None = None) -> dict:
    root = root or paths.ROOT
    lock = read(root)
    rec = {"status": "started", "started_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "label": paths.prereg()["r5_test"]["label"], "lock_sha256": paths.sha256(root / LOCK),
           "lock_rules_commit": lock["rules_commit"], "head": _git(root, "rev-parse", "HEAD"),
           "panel_sha256": lock["data"]["panel_sha256"], "test_window": lock["data"]["test_window"],
           "note": "commit shas are labels (owner's history rewrite pending; re-point after)"}
    p = root / RECORD
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "x") as f:  # atomic create: refuses if it appeared meanwhile
        f.write(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return rec


def complete_record(outputs: dict[str, str], timing: dict, root: pathlib.Path | None = None) -> dict:
    root = root or paths.ROOT
    p = root / RECORD
    rec = json.loads(p.read_text())
    if rec["status"] != "started":
        raise GuardError(f"{RECORD} status is {rec['status']!r}, not 'started'")
    rec.update({"status": "completed", "completed_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "outputs_sha256": outputs, "timing_s": timing})
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    tmp.replace(p)
    return rec


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "verify"
    try:
        if cmd == "write":
            lock = write()
            print(f"frozen: {len(lock['files'])} files, panel {lock['data']['panel_sha256'][:12]}, test "
                  f"{lock['data']['test_window']}")
        elif cmd == "verify":
            p = verify()
            print("freeze OK" if not p else "\n".join(p))
            return 1 if p else 0
        else:
            print(f"unknown freeze command {cmd!r} (write | verify)", file=sys.stderr)
            return 2
    except GuardError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0
