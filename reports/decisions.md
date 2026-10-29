# Decisions log (logged before acting)

Decider = advisor (the `decision-advisor` subagent, which did not write the code) or owner (escalation list).
Research for R0: `reports/research/R0.md`.

## R0

### D0.1 — Layout of `legacy/` · decider = advisor · confidence high · before results
- **Question:** how does v1 move to `legacy/` "unchanged except imports"?
- **Options:** (a) [rec] package, `legacy.`-qualified imports, `git mv results legacy/results`; (b) `legacy/` on sys.path,
  zero edits; (c) leave at root.
- **Choice:** (a), amended: (1) `data/prices.csv` is NOT moved (owner escalation); (2) tests check the root
  `data/prices.csv` blob = 900f1dbf…, monkeypatch `legacy.data.DATA_PATH` to it, redirect every v1 output constant to
  `tmp_path`, and compare against the committed `legacy/results/tables/*.csv` (never overwrite them; no copy/symlink into
  `legacy/data/`); (3) the yfinance stub (D0.2) is the safety net, not the mechanism; (4) `legacy/__init__.py` added;
  the `git mv` and the import-prefix edits go in **separate commits** so `git diff -M` shows 100% renames then
  import-only hunks; (5) tracked `results/.DS_Store` is not moved (untracking = delete → owner, flagged with the
  prices.csv escalation); (6) importing `legacy.config` creates `legacy/data`, `legacy/results/{plots,tables}` as a
  side effect (noted; `/legacy/data/` gitignored).
- **Why the others lost:** (b) generic top-level names (`config`, `data`, `utils`, `signals`) would shadow next to
  `rspy`; (c) breaks the R0 Do list and keeps the shadowing at the root.

### D0.2 — v1's `import yfinance` · decider = advisor · confidence high · before results
- **Options:** (a) [rec] no yfinance dependency; a raising stub in `sys.modules`; (b) yfinance as dev dependency;
  (c) move the import into `_download_price_data`.
- **Choice:** (a), amended: (1) stub is a real `ModuleType("yfinance")` whose module `__getattr__` raises
  `AttributeError` with "yfinance is excluded by the charter (Yahoo)…"; (2) one stub, used by the conftest and by the
  `make legacy` entry point; never in `src/rspy`, never an installable package; (3) a test that
  `load_data(force_download=True)` fails with the exclusion message; (4) v1's `requirements.txt` (lists yfinance) is a
  historical record only and never feeds the uv lock.
- **Why the others lost:** (b) installs a Yahoo client into a repo that excludes Yahoo and re-enables a live download;
  (c) edits a function body, not an import line.

### D0.3 — Characterization scope; missing data · decider = advisor · confidence high · before results
- **Options:** (a) [rec] pin all three committed tables, check the data blob, FAIL if missing; (b) test_metrics only;
  (c) skip when missing.
- **Choice:** (a), amended: (1) `legacy` pytest marker; `make test` runs them; a missing file FAILS naming the path and
  blob; deselecting needs an explicit `-m "not legacy"` (`make test-nolegacy`), no env-var escape; (2) blob checked by
  hashing the file's bytes (git blob SHA-1), not `HEAD:data/prices.csv`, so it survives an untrack; constant
  900f1dbf0cab27f32da7926aa6bca5ef3a5dee03 from 5ccc12c; (3) summary: v1's own rounding then exact equality, plus
  exact parameters and strategy string; the grid test asserts v1's selection rule picks the summary row; parameter
  columns exact, floats ≤ 1e-12; (4) bands in the ledger before running; a miss is a failed expectation, never a wider
  tolerance; (5) `slow` mark only after the runtime is recorded in `reports/perf.md`, and it stays in `make test`.
- **Why the others lost:** (b) does not show v1's selection reproduces (R1 and the multiple-testing count need the
  grid); (c) a skipped test is a green test that checks nothing.

### D0.4 — `make test` memory over budget at -n auto · decider = advisor · confidence high · AFTER results (post-hoc: yes)
- **Trigger:** reviewer R0 MINOR 1. E0.5 was marked held on the largest single process (185 MB); the budget is
  "≤ 1.5 GB total" (perf.md). Sampled summed RSS of the pytest tree (upper bound): -n auto (16 workers) 1952 MB / 8.57 s;
  -n 8 1093 MB / 8.45 s; -n 4 665 MB / 8.31 s.
- **Options:** (a) [rec] E0.5 → failed; fix with `-n auto --maxprocesses 4`; re-measure as E0.5-fix, band unchanged;
  (b) plain `-n 4`; (c) restate the budget per-process; (d) defer to R1.
- **Choice:** (a), amended: keep E0.5's text, status → failed with cause; perf.md method = committed sampler
  (`scripts/rss_peak.py`, summed RSS of the process tree every 0.1 s, upper bound); correction rows added, old rows not
  edited; both `test` and `test-nolegacy` capped; -n 16/8/4 table recorded. Engineering fix only: no return series
  touched, so no variants.csv / DSR count. Not a charter change (`--maxprocesses` caps `-n auto`).
- **Why the others lost:** (b) starts 4 workers even on 2 cores; (c) loosens a pre-registered band after a miss;
  (d) leaves a known-false "held".

### O0.1 — v1's `data/prices.csv` (Yahoo + Cboe VIX) on the PUBLIC remote · ESCALATED TO OWNER · pending
- Options: (a) [rec] `git rm --cached data/prices.csv` in a commit (already gitignored), keep the local untracked copy
  for the legacy tests (they hash the bytes, D0.3), leave history rewriting to the owner; (b) also rewrite history
  (owner runs it; irreversible for anyone who cloned); (c) leave it.
- Also flagged: tracked `.DS_Store`, `results/.DS_Store`, `signals/.DS_Store` (untracking = delete; the last two are
  all that remains in the root `results/` and `signals/` after the D0.1 move; reviewer R0 MINOR 3).
- Status: **not touched by the session.** The session never pushes or rewrites history.
- **Owner decision (2026-10-28): (a).** Untrack `data/prices.csv` and the three `.DS_Store` files (local copies kept;
  all gitignored). History rewriting: later, by the owner, before the next push. The session does not push. Owner also
  said "tag it": `r0-done`.
