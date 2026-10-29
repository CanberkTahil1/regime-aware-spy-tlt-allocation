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

## R1 (research: reports/research/R1.md, f7de1ab; all decider = advisor, before results)

### D1.1 — Cash / bill series · confidence high
- **Options:** (a) [rec] H.15 3-month secondary discount `RIFSGFSM03_N.B`, r_s = P^(−Δ/91) − 1, P = 1 − d·91/360, d = last
  rate dated ≤ previous session; (b) 4-week bill; (c) KF RF.
- **Choice:** (a), amended: (1) financing base = money-market yield y = (1/P − 1)·360/91 from the same lagged d, passed to
  `costs.financing.accrual(rate=y, spread 25 bp [+75], dt=Δ/360)` (d < y always; financing never cheaper than cash);
  (2) series, 91-day rule, lag and conversion in `spec/rules.yaml` `bills` with one_series_for [cash, sharpe_excess,
  sortino_excess, line, financing_base] before the prereg hash; (3) tests: y·91/360 = 91-day r_s; a missing print carries
  the last rate forward, never looks ahead.
- **Why the others lost:** (b) starts 2001-07; (c) charter fixes H.15, RF is Ibbotson/ICE.

### D1.2 — TLT proxy construction · confidence high
- **Options:** (a) [rec] `quantkit.bonds.total_return(gsw, 25, roll="daily", m=2, max_gap_days=7)`, SVENY25 mask, KF
  sessions; (b) max_gap 10; (c) monthly roll.
- **Choice:** (a), amended: (1) **`par_col=None`** (purchase coupon from the fitted curve, = naive-vs-optimal's validated
  construction; quantkit's "auto" uses published SVENPY25, ≤ 0.041 pp different, P1_checks.md:49); equivalence test vs
  the sibling's `par_total_return` 25y copied as `tests/reference/` (COPIED.md), ≤ 1e-10; (2) a return is valid only when
  SVENY25 is reported on both curve dates (notna → cummax); (3) curve-date returns compounded into the first KF session ≥
  date (never overwritten); a KF session with no curve return earns 0 and the next curve return spans it; both counted
  in the build log; 10/20/30y built identically (descriptive).
- **Why the others lost:** (b) departs from the validated construction; (c) unvalidated path.

### D1.3 — `rspy.accounting` · confidence high
- **Options:** (a) [rec] decide at close t, execute at close t+1, drift, true traded turnover, Proportional 3/2 bp per
  side, cash at bill, financing accrual, no shorts (raise), excess Sharpe, standard Sortino, reference + equivalence;
  (b) no drift; (c) same-close.
- **Choice:** (a), amended: (1) Sharpe = `stats.sharpe(net − bill)` with rf=None (quantkit divides by std(x), not
  std(x − rf)); Sortino on the same e; (2) one bill series per row with the t−1 rate (cash max(1 − Σw_{t−1}, 0) on the
  drifted held weights); (3) band rungs must walk on the drifted book (optional band in the same loop; equivalence with
  `trade.rules.band` at zero returns) — needed first at R2 (L3), built there; "trade to edge vs target" is a separate
  R2 D-item; (4) costs in the execution row, net = gross − Σ rate_i|dw_i|, drift ignores the cost's own NAV effect
  (documented); turnover = annualised one-way Σ|dw| incl. drift and vol scaling; (5) plain-loop reference in
  tests/reference, ≤ 1e-10; hypothesis timing test (returns at rows ≥ t+2 cannot change weights decided at t).
- **Note (author, reconciling D1.1 and D1.3-2):** cash and rf use D1.1's r_s; financing uses y·Δ/360 from the same lagged
  d (y·Δ/360 ≥ r_s): same rate, same lag, one source.
- **Why the others lost:** (b) understates turnover, makes bands meaningless; (c) barred, flatters (v1 audit 1.00 → 0.87).

### D1.4 — Reconciliation ladder · confidence medium
- **Options:** (a) [rec] S0 → S1 t+1 → S2 cash + financing → S3 charter costs on true turnover → S4 excess Sharpe/Sortino
  → S5 no shorts → S6 permitted prices → S7 VIX → realised vol; (b) S6+S7 merged; (c) data first.
- **Choice:** (a) with **S6 and S7 swapped**: S6 = VIX → realised-vol proxy (D1.5) on v1's local SPY; S7 = permitted
  prices (KF Hi 20, GSW 25y, H.15, KF calendar), realised vol from Hi 20; **S7 = L1**. Rows S0–S6 = v1 on its own local
  data (as BUILD_PROMPTS prescribes); S7 the only new-data row; no row mixes Cboe VIX with permitted data. Signs in the
  ledger before running; caption says attribution is order-dependent; test window = v1's 2020-01 → 2025-12-31 (label
  "seen by owner in v1, disclosed"); only derived statistics committed.
- **Author's disagreement on one expectation (logged before results):** the advisor suggested S3 ≤ 0. S3 both adds drift
  trades and lowers the rate (5 bp → 3/2 bp), so its sign is not predictable; registered as "sign not claimed" plus a
  turnover claim (traded turnover ≥ v1's reported 18.73×). Not a decision change; owner may override.
- **Flag for the owner (advisor):** rows S0–S6 and the R1 data QA publish statistics derived from local Yahoo/Cboe data,
  as BUILD_PROMPTS prescribes; not re-checked against Cboe's "derivative work" clause. Owner may ask to keep those rows
  local-only.
- **Why the others lost:** (a) as written mixes Cboe VIX into a permitted-data row; (b) price and VIX effects confounded;
  (c) contradicts BUILD_PROMPTS, worst licence position.

### D1.5 — VIX replacement · confidence high
- **Options:** (a) [rec] 21-session realised vol; (b) EWMA 0.94; (c) drop the VIX term.
- **Choice:** (a), amended: window = **20 sessions** = v1's own `REALIZED_VOL_WINDOW` (legacy/config.py:210) and its
  non-VIX path (legacy/signals/regime.py); pandas rolling std, ddof 1, min_periods 20, returns ≤ t; fed into v1's
  unchanged VIX / mean10 − 1 ratio; label "realised-vol proxy for VIX (v1's 20-day convention)"; disclose implied vs
  realised; descriptive corr(vix_score_VIX, vix_score_RV) on 2005–2019 (statistic only); any other window → variants.csv.
- **Why the others lost:** 21 is a new parameter; (b) new estimator, smooths the spike; (c) deletes 60% of base_crash.

### D1.6 — Data-QA method and bands · confidence medium-high
- **Options:** (a) [rec] monthly corr / TE with bands; (b) daily only; (c) no bands.
- **Choice:** (a), amended: bands in spec/prereg.yaml and ledger before computing; method = each series compounded within
  calendar months on its own sessions, 2005-01 → 2025-12, diff = proxy − ETF, TE = std(diff, ddof 1)·√12, plus annualised
  mean diff (level bias); descriptive: daily corr/TE and the 2005–19 vs 2020–25 split (2020+ "test, seen"); the charter
  label stays as written; R1 numbers shown beside it with their window; only statistics committed. A miss is logged; a
  proxy swap would be a charter change (owner). Disclosed prior: the 3.0% TLT band was set after seeing the sibling's
  2.06% (different window).
- **Bands:** Hi 20 vs SPY corr ≥ 0.98, TE ≤ 1.5%/yr; GSW 25y vs TLT corr ≥ 0.98, TE ≤ 3.0%/yr.
- **Why the others lost:** (b) curve-fit timing noise, not comparable to the validated monthly figures; (c) nothing can fail.
