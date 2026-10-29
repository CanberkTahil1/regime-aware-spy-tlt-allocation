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
  900f1dbf0cab27f32da7926aa6bca5ef3a5dee03 from 7b02cee; (3) summary: v1's own rounding then exact equality, plus
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

## R1 (research: reports/research/R1.md, 67b4e98; all decider = advisor, before results)

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

### O1.1 — Committed R1 outputs derived from Yahoo/Cboe (and near-daily KF curves) in a PUBLIC repo · ESCALATED TO OWNER · pending
- **Why escalated:** licence question (charter escalation list) and advisor vs reviewer disagreement: D1.4's advisor
  passed it on as an optional flag; the R1 quant-reviewer (MATERIAL 2) says it had to be escalated. Logged before any
  action; nothing is pushed.
- **What is committed now (c086a39 + review fixes):** statistics derived from v1's local Yahoo/Cboe file (rows S0–S6 of
  `reports/r1/reconciliation.*`, `qa.csv`, `qa_worst_months.csv`, `e12_diagnosis.json`); figures in
  `reports/figures/R1/` whose SVGs carry the S0 and SPY-proxy / L1 wealth curves at near-daily resolution (3.5–3.6k
  vertices per path); the site holds statistics only (no series).
- **Options:** (a) [author's recommendation] keep the statistics tables; re-render every curve figure as PNG only from
  monthly-resampled series (no vector paths recoverable to daily resolution); keep the site as is; (b) also make rows
  S0–S6 and the QA local-only (remove them from git: a delete, owner-only); (c) keep everything as committed (the
  advisor's reading: BUILD_PROMPTS prescribed these rows and only derived statistics are published).
- **Status:** not acted on. Whatever is chosen happens before the owner's next push (with the O0.1 history rewrite).
- **Owner decision (2026-10-28): "Other".** (1) Keep committed: all statistics tables (S0–S7 rows, QA corr/TE).
  (2) Stop tracking every committed curve figure (SVG and PNG) that traces a wealth/return path derived from Yahoo, Cboe
  or Ken French data. (3) Add `make report-site-local`: curves (equity + drawdown, exposure, rolling Sharpe, crisis
  panels) rendered from the gitignored series into gitignored `reports/site_local/` and `reports/figures_local/Rn/`,
  with a test that fails if those directories stop being ignored (as naive-vs-optimal O4.2). (4) The committed page
  shows statistics only. (5) Nothing after r0-done has been pushed; the owner removes these files and data/prices.csv
  from history in one rewrite before the next push. (6) Tag r1-done after this; do not push.
- **Applied as:** untracked (`git rm --cached`, files moved into the ignored `reports/figures_local/R1/`):
  growth_and_drawdown, rolling_5y_excess_sharpe, crisis_small_multiples, exposure_l1 (.png/.svg). Kept committed
  (statistics only): reconciliation_by_step, cagr_waterfall_test, data_qa (.png/.svg), reports/r1/*, reports/site/
  (summary/loss/windows tables, no series).

## R2

### O2.1 — Re-pin quantkit v0.19.1 → v0.19.2 and use `viz.headline` for headline figures · OWNER · 2026-10-28
- **Why owner:** re-pins are owner-only (charter "How to work"; instruction recorded at R1 start).
- **Owner decision:** "yes". Re-pin to v0.19.2 (commit 2120ae9; adds `quantkit.viz.headline` and `quantkit.stats.annual`,
  no change to any module this repo loaded at v0.19.1 other than the `viz` and `stats` package `__init__`s); verify the
  pin check; use `viz.headline` for headline figures with readable names (SPY, v1 legacy, Vol-targeted SPY, 60/40,
  Inverse-vol SPY/TLT, Inverse-vol + vol target, SPY+T-bills at matched vol); regenerate R1's headline figure with it.
  Curve figures go to the gitignored `reports/figures_local/R2/` (and R1/); committed figures stay statistics-only (O1.1).
- **Applied as:** pyproject tag, `uv lock`, `make pin`, `tests/test_pin.py` real-pin test re-targeted, the version string
  in CLAUDE.md / agents / commands / `rspy.paths` / `rspy.pin` / `rspy.site` docstrings updated (the owner's yes covers
  the charter's version number; no other charter text changes).

All R2 D-items below: **decider = advisor** (decision-advisor subagent, one call per item, 2026-10-28), logged before
any R2 code or result. Research: reports/research/R2.md (306b934).

### D2.1 — Vol-target mechanics and the no-trade band · confidence medium-high
- **Options:** (a) [rec] daily vol decisions, monthly weight decisions, one drift-aware 5 pp per-sleeve band in
  rspy.accounting, traded to the edge; (b) as (a) but to target; (c) monthly scaling only; (d) daily, no band.
- **Choice:** (a), amended: banded rungs named in spec/rules.yaml (L3, L4, L4b, L5, L5-lev); **L2 has no band** (v1 had
  none; full turnover charged); L3/L4/L4b check the band at month-end decisions only, L5/L5-lev daily (the extra daily
  checks are part of L5's layer, stated in the ablation); 5 pp absolute per sleeve on NAV weights, cash residual never
  banded; the edge rule cited "[quantkit docstring]" (not checked against the paper).
- **Why the others lost:** (b) a second band convention beside quantkit's edge rule, more trading; (c) contradicts the
  charter's "close t (daily vol target)"; (d) brings back v1's turnover and breaks L5-inherits-L4.

### D2.2 — Vol-model zoo: series and selection · confidence high
- **Options:** (a) [rec] univariate h = 1 forecasts of the unscaled parent book's daily return, yearly QLIKE + 90% MCS,
  simplest model inside; (b) lowest QLIKE; (c) per-sleeve + correlation; (d) fixed EWMA hl 10.
- **Choice:** (a), amended: every model config pinned in spec/rules.yaml with its quantkit `spec_hash` in the ledger
  (EWMA hl 10 / 60; GJR-GARCH-t and Beta-t-EGARCH window 1000, every 21, anchor 500; HAR same, daily variance = r²
  only, no overnight term (no OHLC)); MCS size 0.10, reps 1000, block 21, seed 0, method R; rows with a zero proxy
  (rounded KF returns) dropped for all models together, counted per year; fixed order EWMA-slow, EWMA-fast, HAR,
  GJR-GARCH-t, Beta-t-EGARCH; every year-end MCS set and pick logged in reports/r2/; "rolling QLIKE" is met by the
  charter's expanding walk-forward (the 1989-12 pick uses warm-up losses only: estimation, not scoring); limitation
  logged: the L4 book mixes past weights — descriptive gap vs EWMA on current weights × past sleeve returns.
- **Why the others lost:** (b) chases noise among indistinguishable models; (c) ad hoc covariance step; (d) breaks
  BUILD_PROMPTS "chosen by rolling QLIKE / MCS".

### D2.3 — What L2 is · confidence high
- **Options:** (a) [rec] SPY with v1's own scaling (15%, 20-day, cap 2, daily, financed, costed) + descriptive L2-u
  (10% ex ante, cap 1, D2.2 machinery); (b) L2-u only; (c) v1 scaling, cap 1.
- **Choice:** (a), amended: parameters pre-registered in spec/prereg.yaml (target 0.15, 20-day sample std of the book's
  own returns ≤ t ×√252, cap 2.0, source legacy/backtest.py:57-70); L2-u registered (descriptive); both in
  variants.csv; L2 built from the `legacy_bridge.v1_scaled` mirror with SPY_pos = 1, TLT_pos = 0 (test: equals v1's
  compute_strategy_returns ≤ 1e-12 on that signal); financing paid and average gross shown in every L2 row.
  Disclosed prior: the owner's "Why v2" audit (legacy, 2005–19, free leverage) found vol-targeted SPY beat v1; the
  choice rests on the charter wording, not that number. (Amendment 3 "report L2 with and without the band" is moot:
  D2.1 gives L2 no band.)
- **Why the others lost:** (b) drops the charter's isolation of v1's driver; (c) a hybrid matching neither.

### D2.4 — Promotion rule implementation · confidence high
- **Options:** (a) [rec] quantkit `Ladder.promote` on daily vol-rescaled bill-excess returns AND rspy legs (CDaR route,
  +75 bp, LOCO), sibling pattern; (b) quantkit only; (c) monthly grid.
- **Choice:** (a), amended: (1) pre-register alpha 0.05, mean_block 21, reps 1000, seed 0, knowledge date 2019-12-31,
  the CDaR route and per-route legs in spec/prereg.yaml; (2) the sibling's `no_worse` and `crisis_return` gates dropped
  (crisis returns descriptive); (3) **no −0.03 floor**: every leg is "no loss" (ΔSharpe ≥ 0 at 2× costs, +75 bp, each
  of the six LOCO samples, both routes; CDaR route also needs CDaR below the matched parent's in each leg);
  (4) a step passing by the CDaR route only (quantkit's effect part fails, its walk stops) counts as promoted if
  quantkit's test, robust and MCS parts pass and the CDaR route + legs pass; the walk then continues with a fresh
  registered `Ladder.promote` on [that rung, the remaining rungs], logged; (5) 2× and +75 bp books rescaled by the same
  per-rung constant as the 1× book (constant rescaling of excess returns = financing at the bill; the financed rescale
  at bill + 25 bp only inside the CDaR and LOCO legs); (6) quantkit stress windows set explicitly to the six
  development crises (its default 2020/2022 would leak the test window); (7) COPIED.md entry listing 2–4 as departures.
  Walk L1 → L2 → L3 → L4 → L5; L0/L0-line benchmarks; L4b, L5-lev, L2-u and zoo rows descriptive.
- **Why the others lost:** (b) breaches the charter's CDaR route, +75 bp and LOCO; (c) 360 rows instead of ~7,500 for a
  daily vol target.

### D2.5 — Tranche offsets and the rung of record · confidence high
- **Options:** (a) [rec] record = month-end decision; all 21 offsets reported; (b) 4 weekly offsets; (c) tranched book
  as record.
- **Choice:** (a), amended: the record book = quantkit **offset 0** (decided at the last close of month m, traded on the
  first session of m+1), test: standalone rung = `tranche(...)["books"][0]` bit-identically; every offset decides one
  session before its trade row and checks the band only on its own decision rows; short-month collisions counted per
  offset, all 21 books kept; L2 excluded (no monthly decision); promotion uses offset 0 on 1990–2019 only; RTL,
  tranched book and per-offset range descriptive; test-window timing luck first computed at R5; nothing selects an
  offset (if anything ever does, all 21 go to variants.csv).
- **Why the others lost:** (b) coarser, no saving that matters (budget covers K = 21); (c) not the charter's execution
  rule, and netting flatters costs.

### D2.6 — L4b (ERC) · confidence high
- **Choice:** (a) `quantkit.alloc.risk.erc` on the 63-day sample covariance (same window and ddof 1 as L4's σ), the
  two-asset identity tested (property test on random SPD 2×2 incl. ρ near ±1; series equality ≤ 1e-10 at every
  1990–2019 month-end); no separate evaluation, reported "L4b ≡ L4 (two-asset identity)"; variants.csv row now
  (zoo, n 1, counted in DSR, duplicates L4).
- **Why the others lost:** (b) erc_lw adds an unregistered estimator just to differ; (c) dropping a prereg row.

### D2.7 — L4 inverse-vol estimator · confidence high
- **Choice:** (a) sample std (ddof 1) of the 63 daily returns ending at the decision close, w ∝ 1/σ; reference in
  tests/reference/ from `quantkit.alloc.cov.sample_cov(R[t−62:t+1], ddof=1)`, fast path ≤ 1e-10; all 63 returns
  required (warm-up covers it, no min_periods fallback); σ unannualised (ratio only); no EWMA variant.
- **Why the others lost:** (b) EWMA hl 12 silently changes the pre-registered 63-day window.

### D2.8 — The L0-line · confidence high
- **Choice:** (a) `quantkit.bench.vol_matched(rung, hi20, bill, mode="ex_ante", window=63, lag=1)` financed above w = 1
  at the same lagged H.15 money-market yield + 25 bp with dt = calendar days / 360 (one bill series, spec/rules.yaml);
  in cost/financing stress rows the stress hits the rung only, the line keeps base financing; line scored from
  1990-01 (weights from warm-up rows); realised vol of line and rung reported side by side; ex-post line descriptive;
  window/lag/mode written into spec/rules.yaml before any rung number. Closes E1.12.
- **Why the others lost:** (b) full-sample σ = look-ahead in the judge; (c) no source for 60 over 63.

### O2.2 — Headline chart labels vs the owner's names · ESCALATED TO OWNER · pending
- **Why escalated:** the owner fixed the readable names; three do not fit the pinned quantkit v0.19.2 `viz.headline`,
  which raises when "<name>  $<end value>" leaves the figure (measured: any label over ~17 characters, in any position).
  Changing quantkit needs a new tag + re-pin (owner-only).
- **Options:** (a) [author's recommendation] keep the interim chart labels (Inv-vol + vol tgt, Inv-vol SPY/TLT,
  Vol-target SPY, SPY+T-bills line) with each full name printed in the footer, as now; (b) quantkit fix (margin sized to
  the labels or wrapped end labels) in a new quantkit tag, then re-pin and redraw; (c) other short labels the owner names.
- **Status:** (a) applied as an interim (src/rspy/figures.py `SHORT`); reversible by editing one dict.
- **Owner (2026-10-29): keep short labels with the footer key**, readable abbreviations: SPY, v1, VT SPY, 60/40, InvVol,
  InvVol+VT, SPY+bills (figures.SHORT). Longer labels become an optional quantkit Q15 carry-over request
  (reports/quantkit_carryovers.md); quantkit is not edited from this repo. **Resolved.**

### O2.3 — The promotion walk's order (D2.4) · ESCALATED TO OWNER (advisor vs quant-reviewer) · pending
- **Why escalated:** advisor vs reviewer disagreement on an outcome-determining charter reading (R2 review MATERIAL 1).
  D2.4 (advisor, before results) fixed the walk L1 → L2 → L3 → L4 → L5; quantkit stops at the first failure. The walk
  stopped at L2 vs L1 (ΔSharpe +0.021, LW p 0.23), so L3–L5 were never tested. The reviewer: the charter says each rung
  adds ONE layer and is judged against its parent; L3 (60/40) adds bonds to L0, not a layer to L2, so L3-vs-L2 is not a
  parent comparison and a vol-targeted-SPY result can never let the stock-bond rungs be tested.
- **Options:** (a) [advisor's pre-registered choice] keep it: R2's seat holder is L1; L3–L5 stay descriptive; the
  question is revisited only through R3's rungs (which build on L5 and would also never be tested); (b) post-hoc, a
  second registered walk on parent chains (L1 → L3 → L4 → L5, each step a one-layer parent comparison; L2 judged vs L0
  separately), labelled post-hoc, its rows counted in variants.csv and DSR, results shown beside the pre-registered
  walk, never replacing it; (c) amend the charter's ladder text to define the walk topology explicitly before R3, and
  run (b) under it.
- **Author's note (not a recommendation):** (b) is the cheapest honest way to answer the charter's question without
  hiding the pre-registered result; it is post-hoc by construction.
- **Status:** not acted on; the committed result is the pre-registered walk.
- **Owner (2026-10-29): (c).** Charter ladder text amended first, in its own commit, labelled post-hoc. Reason: the
  pre-registered walk order contradicted the charter's "each rung adds ONE layer"; the order came from the owner's plan
  listing L1 first (so the R2 review's attribution of the ORDER to the advisor alone is corrected: D2.4 transcribed it).
  New structure: L1 is a comparison row, not a parent; parent chains L0 → L2 and L0 → L3 → L4 → L5 (→ L6 → L7 → L8 in
  R3). Prereg re-hashed, the chains walked with the same promotion rule, the new walk counted in the DSR trial count
  (variants.csv), shown beside the pre-registered walk, which stays as recorded (L2 did not beat L1). Every rung is
  still compared descriptively with L1. **Resolved.**

### O2.4 — In-crisis Sharpe pathology: known limitation + descriptive matched-vol row · OWNER 2026-10-29
- **Owner:** record as a known limitation that comparing in-window Sharpe when both books lose money can favour the more
  volatile book (Q4 2018: 60/40 −7.7% vs SPY −12.9%, yet "fails"). Add a labelled POST-HOC descriptive row beside the
  registered crisis leg: in-window cumulative return at matched vol (parent scaled to the child's development vol with
  T-bills, `evaluate.rescale`, financed above 1× at bill + 25 bp). It cannot change any verdict; report whether 60/40
  still fails 1994 under it.
- **Owner, for R3:** the walk verdict stands (nothing promoted past SPY). R3 tests L6–L8 through the charter's ablation
  table (each layer vs its own parent, plus vs 60/40 and vs v1, with 95% intervals, descriptive), not through the walk.
- **Finding (author + R2-amendment review MATERIAL, 2026-10-29):** the owner's example does not survive matching: at
  matched vol 60/40 loses Q4 2018 too (−7.69% vs −7.43%) and 1994 (−6.9% vs −0.3%). The limitation itself is real
  (L2 vs L0, GFC: −27.4% vs matched SPY −41.4%, yet a lower in-window Sharpe); no verdict changes.

## R3 (research: reports/research/R3.md, e87bcd9; all decider = advisor, before any R3 result; owner O2.4 scope: no walk, ablation table)

### D3.1 — L6 mechanics (correlation regime → TLT to cash) · confidence high
- **Options:** (a) [rec] Pearson 126 (63) daily-return correlation at the month-end decision close, L6 = L5's daily
  target with TLT set to 0 while gated (vol scale stays L5's), a zero target exits fully; (b) re-run the vol target on
  the gated book; (c) daily gate decisions; (d) keep the band on a zero target (5 pp stub).
- **Choice:** (a), amended: (1) zero-target exemption written into spec/rules.yaml as a mechanical accounting rule for
  every rung ("a sleeve whose target is exactly 0 trades to 0; the band applies otherwise") before any L6 number, with
  a bit-identity check on every R2 book; (2) disclose the asymmetry: re-entry from 0 in a banded book still stops at
  the edge (target − 5 pp); (3) the gate reads the decision rows of the offset being built and reaches the daily target
  via `carry` (decided ≤ t), tested like R2's vol_target wiring; (4) report L6's realised development vol overall and
  in gated months beside the matched row; (5) L6-126 at 0 is the rung; L6-63 and ±0.2 descriptive; each a variants row.
- **Why the others lost:** (b) one layer making two changes (adds SPY), contradicts prereg "TLT weight to cash";
  (c) unregistered cadence, flips on noise (SE ≈ 0.09); (d) a 5 pp stub is not cash and keeps TLT through 1994.

### D3.2 — L7 mechanics (per-asset trend) · confidence medium-high
- **Options:** (a) [rec] `signals.trend.faber(months=10)` on each sleeve's total-return level, decision read back to
  the month-end row, below-SMA sleeve target 0 (exits fully), no re-scaling, plus a descriptive "trend on L5" row;
  (b) price-only levels; (c) daily `trend.sma(210)`.
- **Choice:** (a), amended: (1) tranche offsets o > 0 need the same SMA rule at that offset's decision rows (one code
  path, tested equal to faber at o = 0) — R3 builds only the record offset 0 (no R3 timing-luck item), so this binds
  when L6/L7 offsets are built (R4); (2) coverage guard: faber is fed the full 1986-onward panel; no NaN trend state at
  any scored decision row (asserted); the final month-end (e + 2 past the sample) is read from the tested SMA path,
  never filled; (3) "trend on L5 (no corr layer)" and "L7 on L6-63" registered as descriptive variants before the
  build; (4) zero-target exit per D3.1.
- **Why the others lost:** (b) no price-only 25y Treasury proxy; mixed definitions across sleeves; (c) unregistered
  variant, more whipsaw, breaks the monthly grid.

### D3.3 — L8 crash rule · confidence high (choice), medium (wiring)
- **Options:** (a) [rec] quantkit `sizing` rule "dd" with its defaults (d1 1, d2 2.5 × target 0.10, e_min 0.25),
  tested by `sizing.judge(L7 net − bill, 0.10, "dd", sigma = 0.10 constant, cap 1.0)` (base exposure ≡ 1, so "vol
  targeting alone" = L7), book = L7 target × g_t traded t+1; (b) cppi α 0.8; (c) vol-spike trigger.
- **Choice:** (a), amended: (1) `judge` on development rows only; the book's g path from one `sizing.overlay(rule="dd",
  sigma const, cap 1, target 0.10)` run from 1990-01, tested equal to judge's candidate (same arguments; judge does not
  return the path); (2) target, d1, d2, e_min, block 21, seed 0, cap, σ written into spec before L7/L8 runs; thresholds
  not rescaled to L7's realised vol; (3) ledger disclosures: judge is same-close (book adds the lag and costs), DD read
  on the excess-return NAV, expectation "rarely fires, judge on = False, L8 − L7 ≈ 0" (L5 dev max DD −12.99% ⇒ g ≈ 0.85
  at worst); (4) turnover includes g changes; report the share of development days with g < 1.
- **Why the others lost:** (b) cash lock after −20%, never re-risks; (c) duplicates the daily vol target already in the
  book, and `judge` does not test it (would re-implement quantkit).

### D3.4 — Gate placebo · confidence medium
- **Options:** (a) [rec] shuffle the gate's monthly decision vector with `vol.shuffle_blocks`, 12-month blocks, seed 0;
  "beats placebo" = gate vs parent one-sided LW p < 0.05 AND placebo vs parent p ≥ 0.05; 100-seed percentile
  descriptive; (b) quantkit's daily block 21 read at month-ends; (c) 6-month blocks.
- **Choice:** (a), amended: (1) shuffle only the layer tested (L7: trend states shuffled, L6's real gate kept; zoo
  gates on real L5); (2) one permutation per gate shared by both sleeves; (3) shuffle the 360 development month-ends
  only (test window separately, if ever); (4) placebo compared at matched vol with the same costs and exit rule;
  (5) block 12, seed 0, seeds 0–99 and the definition in spec before any R3 return; seed-0 placebos registered (phase
  ":placebo"), the 100-seed set one null-distribution procedure; (6) the ledger says block 12 is a reasoned choice,
  not a literature value; block 6 a descriptive sensitivity row.
- **Why the others lost:** (b) a near month-level permutation: persistence lost, placebo a straw man; (c) cuts spells at
  the median length; kept as sensitivity.

### D3.5 — Ablation statistics · confidence high
- **Options:** (a) [rec] reference rescaled to the child's development excess vol; ΔSharpe LW 95% + one-sided p;
  paired-bootstrap intervals on drawdown; in-crisis matched rows; Holm printed; (b) LW on ΔSharpe only, CDaR point;
  (c) raw unmatched differences.
- **Choice:** (a), amended: (1) drawdown intervals via `quantkit.stats.drawdown.dd_ratio_ci(child, matched_ref,
  stat="cdar", alpha=0.95)` and `stat="max_dd"` (1,000 draws, mean block 21, seed 0, 95%), as ratios and ratio − 1,
  n_nan printed — no hand-rolled bootstrap; (2) match once on the realised series, then bootstrap the pair; (3) footnote
  the interval as a sampling interval with 21-session blocks (likely too narrow for long drawdowns), bootstrap median
  shown; block pinned; (4) Holm family fixed now: every ΔSharpe p in the R3 ablation table (rows × 4 references);
  (5) crisis-matched rows for all six development windows, 1994 / GFC / Q4 2018 highlighted, O2.4 in-window ΔSharpe
  kept beside them; (6) calls sequential at fixed T; RSS checked with rss_peak.py against 1.5 GB as an expectation.
- **Why the others lost:** (b) no interval on the thesis metric (drawdown); (c) confounds the layer with its risk.

### D3.6 — Zoo scope in R3 · confidence high
- **Options:** (a) [rec] build HMM gate, jump-model gate, min-CDaR (756 sessions) and max-div (identity) now; defer v1
  spread/Bollinger overlays and the GBM risk row to R4; (b) build every row now; (c) defer the whole zoo.
- **Choice:** (a), amended: (1) zoo gates mirror D3.1: L5's SPY target set to 0 on turbulent months (hmm_p > 0.5 /
  jm_regime = 1 at the month-end close), L5's vol scale kept, D3.4 placebo; (2) quantkit state defaults (window 2000,
  every 126, anchor 500) on SPY-proxy returns from 1986; test: no NaN state at any development month-end; (3) max-div
  given the 63-row sample covariance explicitly (quantkit's Ledoit-Wolf default would break the identity), tested equal
  to L4 at every decision row, counted; (4) min-CDaR α 0.95, 756 sessions only, floor None; both additive and
  compounded CDaR reported; (5) all four rows registered in variants.csv in the expectation commit; ledger "not tested
  in R3" for spread/Bollinger overlays and GBM, naming the R4 D-items (overlay definition for unit-gross v1 weights;
  GBM target, features, horizon, haircut meaning).
- **Why the others lost:** (b) four-plus author-chosen definitions in one phase invite an uncounted definition search;
  (c) the gates and min-CDaR are already fully defined by quantkit and the literature.

### O3.1 — D3.6's deferral of three zoo rows to R4 · ESCALATED TO OWNER (advisor vs quant-reviewer) · pending
- **Why escalated:** R3 review MATERIAL 2: the advisor (D3.6, before results) moved the v1 spread overlay on L5, the v1
  Bollinger overlay on L5 and the GBM risk-side row (purged CV, 50% haircut) from R3's Do list to R4 without an owner
  decision; the reviewer holds that cutting the owner's phase scope is the owner's call. Advisor vs reviewer
  disagreement ⇒ owner (charter "How to work").
- **Options:** (a) [advisor's choice] accept the deferral: R4 decides the four missing definitions (what "overlay" means
  for v1's unit-gross, possibly-short weights; GBM target, features, horizon, meaning of the 50% haircut) before any of
  those rows has a result, in time for R4's PBO/CSCV; R3 is reported as incomplete on these three rows; (b) build them
  in an R3 amendment before the tag (advisor decides the definitions first, expectations before code); (c) drop them
  from the zoo (charter change: the zoo list is in CLAUDE.md).
- **Status:** not acted on; nothing about these rows is built. The ledger lists them as "not tested in R3".
- **Owner (2026-10-29): (a), with a condition.** The three rows move to R4. At R4 start, before anything is computed,
  their definitions (v1 spread overlay on L5; v1 Bollinger overlay on L5; GBM risk-side sizing row with purged CV and
  the 50% haircut) are written and registered in spec/prereg.yaml, and its hash goes into the ledger. They are zoo rows:
  they cannot change any verdict and are counted in DSR N. **Resolved.**

## R4 (research: reports/research/R4.md, d8fc4f4; all decider = advisor, before any R4 computation; owner O3.1: the three deferred zoo rows are defined in spec/prereg.yaml `r4` and hashed before any R4 number)

### D4.1 — v1 spread / Bollinger overlays on L5 · confidence high
- **Options:**
  - (a) [rec] Cash-only event overlay: v1's frozen signal code with its selected parameters. The flagged sleeve goes to
    cash on signal days only.
  - (b) Replace L5 with v1's floored weights on signal days.
  - (c) v1's floored weights replace L4's mix.
- **Choice:** (a), amended:
  1. It fires only on signal days. If spread z > 2.5, or the Bollinger ratio is above its upper band, the SPY column
     goes to 0. If z < −2.5, or the ratio is below its lower band, the TLT column goes to 0. This is v1's short TLT leg,
     floored. Any other day, including NaN z or a zero sd, keeps L5 unchanged.
  2. The signal is applied unconditionally. v1 used spread only in its VIX high-vol state and Bollinger only in its
     low-vol downtrend state. This is a registered departure from v1.
  3. `legacy/signals/{spread,bollinger}.py` are called unchanged (window 10, th 2.5, num_std 2). Spread runs on proxy
     daily returns and Bollinger on proxy total-return levels. Only each function's state is used, never its weights.
     The decision is at close t and traded at t+1, through the tested `regime.gate` path with a look-ahead test.
  4. L5's vol scale is kept. L5's 5 pp band applies with the zero-target exit; re-entry stops at the band edge.
  5. For each row, report the share of development days in each state and the traded turnover. Two variants rows;
     zoo; counted in DSR N.
- **Why the others lost:** (b) puts 100% of the book in one sleeve and changes the mix and the concentration together,
  so it no longer isolates the signal. (c) is a different rung (v1's mostly-SPY allocator) that repeats L1/L2.

### D4.2 — GBM risk-side sizing row · confidence medium ("50% haircut" is an interpretation; the raw row covers the other reading)
- **Options:**
  - (a) [rec] A LightGBM vol forecast shrunk 50% in log space toward L5's own forecast, refit walk-forward with a purge.
  - (b) (a) plus CPCV early stopping.
  - (c) A Harvey–Liu 50% Sharpe haircut in reporting only.
- **Choice:** (a), amended:
  1. Label = log √(252·mean r²) of the unscaled L4 book's daily log net returns over sessions t+2 … t+22. This is zero
     mean, the zoo's QLIKE proxy. σ̂_zoo and σ̂_GBM are both annualised before the blend.
  2. The zoo feature is exactly the stitched σ̂ that sizes L5 in R2 (no new zoo run). Undefined rows are dropped and
     counted. Training may use the 1986–89 warm-up; the first scored prediction is in 1990.
  3. The bill feature is the lagged H.15 yield the financing uses (mmy), not a same-day print.
  4. Splits are hand-built `cv.Split`s, one per year y+1, with label_end = t+22, purge 22, embargo 0, and
     `check_split` on each (tested). `search=None`, `early_stopping=None`, seed 0, threads 1. Predictions come only
     from `fit_cv`'s split results.
  5. The haircut is frozen at 0.5 with no sweep. The blended and raw rows are 2 trials, both zoo.
  6. Expectation: ΔSharpe vs matched L5 in [−0.05, +0.05], with the blended row no further from L5 than the raw row.
- **Why the others lost:** (b) adds a search, and CPCV trains on later years, so it cannot size a tradable book.
  (c) is cosmetic on a sizing row and duplicates the DSR; quantkit deprecates `haircut_sharpe` for decisions.

### D4.3 — GBM backend · confidence high · not escalated (advisor: not a re-pin, not a licence question)
- **Options:**
  - (a) [rec] Add the `ml` extra of the same pinned tag v0.19.2.
  - (b) Use scikit-learn HistGradientBoosting directly.
  - (c) Drop the GBM row.
- **Choice:** (a), amended:
  1. LICENSES.md gets a "Software (non-data)" line, with versions and licences read from the installed METADATA.
  2. `make verify-pin` must pass with spec/quantkit_pin.json unchanged byte for byte. If pin.py would rewrite it, stop:
     that is a re-pin.
  3. A test checks the GBM row is bit-identical with 1 worker and with N workers; `threads` is pinned in the spec.
  4. A perf budget is set before code. Only the LightGBM path is imported.
  5. The real `uv lock` / `uv sync` runs in the repo, and uv.lock is committed (no push).
- **Why the others lost:** (b) re-implements what quantkit provides and drops `fit_cv`'s leakage guards. (c)
  contradicts O3.1 (a charter change).

### D4.4 — Robustness scope (no rung promoted) · confidence high
- **Options:**
  - (a) [rec] Every built main rung.
  - (b) The seat holders only.
  - (c) L2–L8 without L1 and L5-lev.
- **Choice:** (a), amended:
  1. The header reads "built rungs; none promoted (R2 walk seats L1, post-hoc chains seat L0, R3 not walked per
     O2.4)". Every row is descriptive.
  2. Parents: L2→L0, L3→L0, L4→L3, L5→L4, L6→L5, L7→L6, L8→L7, L5-lev→L5. L1 has no parent (a comparison row) and is
     compared with the line and L0. L0 is compared with the line only. Every rung is also compared with matched L1 and
     L3. Matching uses `evaluate.rescale`, at spread 100 bp in the +75 bp leg.
  3. Waterfall on arithmetic annualised means: gross + cash − SPY cost − TLT cost − financing = net, then − bill =
     excess. The identity holds per day ≤ 1e-10. The CAGR gap (vol drag) is shown separately. Bars for 1×, 2×, 3×
     and +75 bp; zero bars are kept.
  4. Power: `periods_needed` on per-period Sharpe ratios, with ρ = corr(child excess, matched parent excess). Where
     the edge is ≤ 0 it prints "∞ (measured edge ≤ 0)". quantkit's HEADER caveat is printed, labelled optimistic.
  5. Rolling 5-year ΔSharpe matches the parent once over the full development period.
  6. Development rows only. LOCO uses the six development windows. Descriptive and zoo rows stay out of these tables.
     Cost, financing and LOCO legs are not new trials (noted in variants.csv).
- **Why the others lost:** (b) says nothing about the layers. (c) drops the charter's v1 side-by-side and the only
  levered row.

### D4.5 — Sensitivity grids · confidence high
- **Options:**
  - (a) [rec] One factor at a time.
  - (b) The full width × calendar grid.
  - (c) Maturity on L3/L5 only.
- **Choice:** (a), amended:
  1. The 10y/20y/30y legs are labelled "GSW <n>y constant-maturity proxy, not QA'd vs an ETF". An assert checks that
     SVENY<n> is reported from the 1986 warm-up start.
  2. Each variant is compared with its registered rung at matched vol (LW ΔSharpe, CDaR-95 ratio) and with the line,
     with turnover and cost drag. Development only.
  3. The band acts on each rung's existing decision rows: month-end for L3/L4, daily for L5–L7, so band 0 there means
     daily rescaling. Quarterly = the Mar/Jun/Sep/Dec month-end rows at offset 0 for the mix, the L6 gate and the L7
     read-back. The vol scale and the L8 brake stay daily.
  4. Two effects are disclosed as untested: quarterly timing luck and band × calendar interactions.
  5. All 41 books (maturity 3 × 7 [L1, L3–L8]; band 3 × 5 [L3–L7]; quarterly 1 × 5) are registered before any is built.
  6. L8 is in the maturity grid only.
- **Why the others lost:** (b) adds near-duplicate trials for interactions the literature does not expect to matter.
  (c) hides L6, where duration matters (1994), and drops L1.

### D4.6 — DSR trial pool · confidence high (medium on the placebo amendment)
- **Options:**
  - (a) [rec] Every registered row with a return series plus v1's 648-config grid on permitted data.
  - (b) Raw N.
  - (c) (a) without v1's grid.
- **Choice:** (a), amended:
  1. The placebos the register already counts (L8_placebo, the 8 seed-0 gate placebos) stay in. The 100-seed sets
     stay out.
  2. Tranche offsets go in. Their flag goes from no to yes before any DSR result.
  3. N used = n_eff + selection-only rows (walk_chains_O2.3: +1).
  4. v1's grid is run on the L1/S7 path (KF Hi 20, GSW 25y, realised-vol proxy for ^VIX, charter accounting), varied
     only through v1_params, and scored 1990–2019.
  5. Two companion rows: DSR at raw N, and DSR without v1's grid; k_cut_sens is reported. The headline uses ρ* 0.5.
  6. The S0–S6 rows and diagnostics stay out. R4 rows are registered first.
- **Why the others lost:** (b) treats near-duplicates as independent. (c) understates the search behind L1 (the
  flattering direction).

### D4.7 — PBO pool and blocks · confidence high
- **Options:**
  - (a) [rec] L5 + the zoo, S = 16.
  - (b) Everything in one pool.
  - (c) S = 10.
- **Choice:** (a), amended:
  1. Exact-duplicate columns are dropped before the CSCV (L4b ≡ max_div), with the dropped ids logged. They stay in
     DSR N.
  2. Secondary pool (descriptive): every selectable rung and sensitivity variant plus the deduped zoo. No placebos, no
     tranche offsets, no line.
  3. Inputs are development daily excess returns at the record offset and 1× costs. A zero-variance column is logged
     and dropped.
  4. S = 8 and S = 12 are printed beside S = 16 whatever they show.
- **Why the others lost:** (b) pads the pool with non-trials. (c) has coarser halves and no reason to be primary.

### D4.4 amendment (POST-HOC, after the first R4 run; reporting definition only, not a trial) — vol drag
- `waterfall.vol_drag_pa` was first defined as mean·252 − CAGR, which also contains the compounding of the mean and went
  negative for low-vol books (L4/L5: −0.1 pp, first run). Redefined as (1 + mean daily net)^252 − 1 − CAGR (≥ 0 by
  AM–GM), with the compounded mean reported beside it. No number in the identity, no ΔSharpe and no verdict uses it.
  Labelled post-hoc here after review R4 MINOR. Test: a hand-computed value (`test_waterfall_vol_drag_equals_a_hand_computed_value`).

### D4.8 — OpenMP runtime for the GBM row (arose in the build; reviewer R4 MINOR: acted on before it was logged) · confidence high · decider = advisor
- **Facts:**
  - After D4.3, `quantkit.ml.fit_cv` raised `OpenMPConflictError`: scikit-learn's vendored libomp and Homebrew's libomp
    (which LightGBM links via @rpath) were both loaded.
  - quantkit's documented consumer step is `python -m quantkit.omp --fix`, once per environment after `uv sync`. It
    symlinks the vendored copy to Homebrew's runtime, keeps the original as `.bundled`, and `restore()` undoes it.
- **Options:**
  - (a) [rec] Keep an idempotent `make omp` step (a prerequisite of test, test-nolegacy and ladder) and log it.
  - (b) Avoid loading scikit-learn's runtime. This needs a quantkit change; siblings are read-only, and a re-pin is the
    owner's.
  - (c) Drop the `ml` extra and the GBM row. This contradicts O3.1.
- **Choice:** (a), amended:
  1. It is stated plainly: `make omp` edits the installed scikit-learn inside `.venv` only. It is reversible and is
     re-applied after any `uv sync`.
  2. Homebrew libomp (23.1.4 on 2026-10-29) is an unpinned system prerequisite that D4.3 already brought in, since
     LightGBM needs it regardless. It is noted in LICENSES.md. The README setup note waits for the owner-approved R5
     README rewrite.
  3. `make doctor` fails if Homebrew libomp is missing, and `make omp` fails loudly instead of quantkit's silent
     "nothing to do".
  4. The doctor reports the libomp version and the symlink state.
  5. E4.16 (pin JSON unchanged, R2/R3 statistics unchanged) and the E4.4 1 vs 2 worker identity were checked with the
     fix applied.
  6. No quantkit edit.
- **Why the others lost:** (b) needs a quantkit change or re-pin and is fragile on import order. (c) is a charter-level
  change for an environment problem with a documented, reversible fix.

## R5 (research: reports/research/R5.md, 7e59241; all decider = advisor, before any v2 test-window number; none escalated)

Owner instructions (2026-10-29, not D-items): register the post-hoc 10-year sensitivity row (L5–L7 on GSW 10y, test
window, labelled, cannot change a verdict, counted in DSR N; the 25-year books stay official) in spec/prereg.yaml with
its hash in the ledger **before** the freeze; freeze; synthetic dry run; one test run labelled "seen by owner in v1,
disclosed"; headline figures into the gitignored reports/figures_local/R5/; README drafted, committed only with the
owner's approval; never push.

### D5.1 — How the frozen rules continue into 2020+ · confidence high · decider = advisor
- **Options:** (a) [rec] the registered procedures run on unchanged: vol-zoo MCS re-selected at each year-end 2019–2025,
  L8 brake path from 1990-01-02, continuous books (positions carried from 2019-12-31), rolling estimators roll on;
  (b) freeze the fitted state at 2019-12-31 (2019 pick for every test year); (c) restart every book at 2020-01-02 from cash.
- **Choice:** (a), amended:
  1. Every year-end list is extended in the one prereg commit before the freeze (vol-zoo selection 1989..2025). The GBM
     refit years are not extended because the GBM row is out of the test scope (D5.6). Every `range(1989, end_year)` call
     takes the test end explicitly, not the development `scored` end.
  2. Hard guard: a vol-zoo pick must exist for every year 2020–2026; `volzoo.stitched`'s silent default fallback is
     refused on scored test rows.
  3. Rows ≤ 2019-12-31 of every extended book (and the picks 1989..2018, the L8 multiplier, the trend keep) must equal
     the R2/R3 books bit for bit on the same data vintage; a mismatch stops the run and is the owner's call (never a
     wider tolerance).
  4. The trend fallback now sits at 2026-09; the bit-for-bit check is what proves development rows were not moved.
  5. The 2020–2025 picks are labelled "re-selected by the registered causal rule (losses ≤ prior year-end)"; the frozen
     2019 pick is shown only as a descriptive footnote.
- **Why the others lost:** (b) changes the registered rule at R5 (the rule, not the fitted state, is what is frozen).
  (c) discards the warm-up the estimators need (1,000-day GARCH windows, 126-day correlation, 10-month SMA, the L8 path),
  adds an artificial entry trade, and breaks the continuity check.

### D5.2 — "At matched risk" on the test window · confidence high · decider = advisor
- **Options:** (a) [rec] R3/R4's procedure on the scored window: each reference rescaled once ex post to the child's
  test-window excess vol (bill + 25 bp above 1×), LW 95% + one-sided p, paired-bootstrap CDaR / max-DD ratios; the
  ex-ante L0-line beside it; (b) scale constants fixed from development; (c) both.
- **Choice:** (a), amended:
  1. The test-window match text is written into spec/prereg.yaml `r5_test` before the freeze.
  2. Inputs are sliced to test rows before `rescale` / `ablation_row` / `crisis_matched`; a unit test checks that the
     matched reference's test-window excess vol equals the child's to ≤ 1e-10. Docstrings say "scored-window" vol.
  3. k and the share of rows financed above 1× are printed per pair. Every matched number is labelled "matched ex post on
     the test window (one scalar), descriptive", with the ex-ante line in the same table.
  4. Crisis panels carry a footnote: k uses the whole test window's vol, crises included (as in development).
- **Why the others lost:** (b) is not matched on 2020+ (development vol moves by decade: L0 14/22/15%) and mixes leverage
  with skill; the line already gives the ex-ante comparison. (c) adds a reported variant that invites column-picking.

### D5.3 — What the test run can conclude · confidence high · decider = advisor
- **Options:** (a) [rec] no development verdict changes; matched ΔSharpe + LW 95% + one-sided p for each layer vs its
  parent, vs L2, vs L3 and vs the line; "beat" = point ≥ +0.05 and p < 0.05; Holm and power printed; (b) re-run the
  four-part walk on the test; (c) point estimates only.
- **Choice:** (a), amended:
  1. The comparison family is listed by name in prereg `r5_test` before the freeze.
  2. Two levels: the per-comparison "beat" flag (raw one-sided p < 0.05, the R3 gate-rule precedent) and the README's
     headline "did any layer beat L2 / 60/40 / the line": yes only if the point estimate is ≥ +0.05 **and** the Holm-adjusted p < 0.05 within the
     family; otherwise "not shown in the test window", with the raw flags beside.
  3. One-directional: a test "beat" seats or promotes nothing; a test "no" demotes nothing. Written next to the numbers
     with the R4 power (optimistic iid planning) at 6.75 years.
  4. CDaR / max-DD ratios and the COVID / 2022 panels are descriptive, outside the beat rule.
  5. A descriptive column says whether each test ΔSharpe agrees in sign with development.
- **Why the others lost:** (b) is a second decision process on owner-seen data, and the MCS / leave-one-crisis-out parts
  have no calibration on 6.75 years. (c) leaves the README's yes/no to a threshold chosen after the numbers.

### D5.4 — DSR on the test window · confidence medium-high · decider = advisor
- **Options:** (a) [rec] test-window DSR per official rung with N from the development register (headline n_eff 3 +
  selection-only 1 + the owner's 10-year row 1 = 5; companion raw N 748 + 3 = 751); (b) re-estimate n_eff on test copies
  of the 787-series pool; (c) no test DSR.
- **Choice:** (a), amended:
  1. The raw-N companion's trial-Sharpe variance is V = max(V_dev, 1/(T_test − 1)), both printed. V_dev is the
     ddof-1 variance of the development pool's per-period Sharpe ratios, recomputed from development data only
     (fceef9b: reports/r4/facts.json dsr_pool.sr_pp_var_ddof1 = 5.379623993123816e-05) and written into prereg
     before the freeze. 1/(T_test − 1) is quantkit's null variance and needs only the session count. Not the variance
     across the test rungs: they are not trials of one selection, and it would use test numbers.
  2. The headline row (dsr_effective, one development cluster) already falls back to 1/(T − 1); stated beside the table.
  3. Double counting disclosed: maturity_sensitivity (R4, 21 configs, counted) already holds L5–L7 at 10y in
     development (L5@10y was the development best_in_pool); the +1 / +3 counts them again, erring conservative as the
     owner instructed. Written in the variants.csv note.
  4. Labelled "descriptive; seen by owner in v1, disclosed; cannot change any verdict", with the development DSR
     (reports/r4/dsr.csv) beside it.
  5. The variants.csv row and the prereg hash precede any test number.
- **Why the others lost:** (b) adds test exposure for no decision value (trials are counted where the selection
  happened). (c) drops the deflation of the window being reported.

### D5.5 — Freeze contents and the run-once guard · confidence high · decider = advisor
- **Options:** (a) [rec] lean lock (spec, pin, uv.lock, engine files, data hashes, rules commit), `rspy freeze verify`,
  runner refuses unless hashes match, locked files clean, `RSPY_TEST_RUN=run-once`, no reports/r5/test_run.json; no tag;
  (b) dispersion-reversal's full guard with tags; (c) specs only.
- **Choice:** (a), amended:
  1. Content hashes decide; the commit sha is a label only ("sha before the owner's history rewrite; re-point after").
  2. data/panel.parquet's own SHA-256 is locked beside the build key.
  3. The test window is locked explicitly: 2020-01 → 2026-09 (last KF session 2026-09-30); a later refetch fails the
     lock instead of silently extending the test.
  4. The engine set also covers the Makefile and every repo module the runner actually loads (checked at run time, the
     pin.py pattern), not only a glob.
  5. The runner writes reports/r5/test_run.json atomically with status "started" and the lock hashes **before** any test
     statistic, and completes it at the end; a rerun needs a visible deletion logged here as a post-hoc event.
  6. The dry run refuses if RSPY_TEST_RUN is set or RSPY_DATA resolves to the repo's data/; a pytest asserts it never
     writes reports/r5/test_run.json; its output is "code check, not evidence", with no ledger result row.
- **Why the others lost:** (b) depends on tags (owner-only) and is more machinery than one run needs. (c) leaves the
  engine and data unguarded.

### D5.6 — Scope of the test run · confidence high · decider = advisor
- **Options:** (a) [rec] L0–L8 (L1 comparison row), L5-lev and L2-u descriptive, the line per rung, the owner's 10-year
  L5–L7, 1× official plus 2× / 3× / +75 bp, crisis panels, ablation, v1 vs v2, test DSR; no zoo, no R3 descriptive rows,
  no tranche offsets, no placebos; (b) (a) + zoo + R3 descriptive rows; (c) official rungs at 1× only.
- **Choice:** (a), amended:
  1. L4b (ERC, `role: zoo`) is excluded by name.
  2. The official book is tranche offset 0; offsets 1–20 are not run, and no tranche average stands in for it.
  3. Robustness on the test is 2×, 3×, +75 bp on L0–L8 and L5-lev, labelled "frozen rule re-scored (robustness_legs,
     counted no)"; leave-one-crisis-out, decades and rolling 5y are not run on 6.75 years.
  4. The 10-year row is registered in prereg and variants.csv (n_configs 3, counted yes, descriptive) before the freeze,
     labelled "post-hoc (owner), not QA'd vs an ETF"; never in a verdict or the ablation chain.
  5. The excluded list is written into prereg before the freeze hash.
- **Why the others lost:** (b) adds 20+ never-promotable rows to cherry-pick from and undercuts D5.4. (c) fails the
  definition of done (costs, v1 vs v2) and drops the owner's row and the benchmarks.

### D5.7 — The optional monthly forward log · confidence high · decider = advisor
- **Options:** (a) [rec] not built in R5, offered in the handoff; (b) build `make forward` now.
- **Choice:** (a), amended:
  1. The handoff states the forward window: from 2026-10 (available around 2026-12 given KF's lag).
  2. Conditions for a later `make forward`: runs behind the R5 lock's hash check, append-only, each row with the KF
     manifest sha256 and fetch date, labelled "forward, unseen", no ladder decisions, windows unchanged.
  3. A "Forward (optional, not built in R5)" line in the ledger next to the prereg `forward` entry.
- **Why the other lost:** no forward month exists at R5; an untested harness in the run-once phase goes beyond scope.

### D5.4 order note (review R5 MINOR, acknowledged)
- V_dev was computed and committed (fceef9b) before D5.4 was logged here (99827a9). It used development data only and
  the research note (7e59241) recommended it first, but "log before acting" was not followed. No number moved.

### D5.8 — Placebo for the regime layers on the test window (raised by review R5 M4, before the freeze) · confidence medium · decider = advisor
- **Options:**
  - (a) [rec] Both: bind the README to the development placebo verdicts, and add a descriptive test-window placebo for
    L6, L7 and L8 (seeds 0–99).
  - (b) README binding only.
  - (c) Keep D5.6 (no placebo).
- **Choice:** (a), amended:
  1. The primary fix is the README binding. Every test L6–L8 number sits beside the development placebo verdict
     (reports/r3/placebo.csv: L6 and L7 beats_placebo False; L8 via R3's sizing.judge), built from facts.
  2. The shuffle uses test rows only. L6 shuffles the correlation keep and L7 the trend keep, in 12-month blocks; L8
     shuffles the multiplier in 21-row blocks. Development states are never mixed in.
  3. Report the gate's percentile among seeds 0–99 and the placebo median / p05 / p95 of the matched ΔSharpe vs the
     parent and of the matched COVID and 2022 returns. No p-value, no "beats" verdict on the test (≈ 7 blocks). The
     caveat is printed beside every placebo figure.
  4. One-directional: the placebo can only qualify or weaken a claim, never upgrade a gate or enter the family, Holm or
     the ablation chain. If a gate's 2022 gain is inside the placebo's p05–p95, the README says "2022 gain not
     distinguishable from holding fewer bonds at random times".
  5. The prereg exclusion list narrows to "placebo seeds beyond 0–99, block-6 sensitivity, zoo-gate placebos". The
     placebo sets are registered in variants.csv (counted no) before the freeze hash, with a perf budget.
- **Reviewer vs advisor:** no disagreement. The advisor amends its own D5.6, because a control row is not a strategy
  row, so D5.6's cherry-pick reason does not apply.
- **Why the others lost:**
  - (b) leaves the 2022 "fewer bonds vs timing" question about the test window unexamined.
  - (c) lets a 2022 gate gain stand unqualified.

### D5.9 — The Makefile in the replay check (raised by review R5 MINOR, before the freeze) · confidence high · decider = advisor
- **Options:**
  - (a) [rec] The run guard checks every locked file; replay exempts only the Makefile.
  - (b) Replay checks engine and data only.
  - (c) Keep the Makefile in the replay check.
- **Choice:** (a), amended:
  1. The Makefile hash stays in the lock, and the test-run guard requires it to match and be clean.
  2. Replay prints "Makefile changed since freeze (orchestration; outputs still required byte-identical)" when the
     Makefile differs.
  3. The exemption is written into prereg r5_test.freeze.replay_exempt before the freeze hash.
- **Why the others lost:**
  - (b) would let a dependency move (uv.lock, pyproject) pass the lock check.
  - (c) would make any later harmless target, such as the forward log, break `make all` permanently.

## R6 (research: reports/research/R6.md, f6e8b38; before any R6 number; owner instruction 2026-10-29: test the R5-inspired ideas on both windows, common-sense verdicts, no new holdout, no parameter search)

Every R6 idea was suggested after seeing 2020–2026. The test window is labelled "disclosed reuse: ideas inspired by
this window" and development 1990–2019 "in-sample". No R6 verdict promotes or demotes anything.

### O6.1 — Where R6 is registered · ESCALATED TO OWNER · OWNER 2026-10-29
- **Conflict:** BUILD_PROMPTS R6 says "`r6:` in `spec/prereg.yaml`". R5's lock (spec/freeze.lock.json) content-hashes
  spec/prereg.yaml, spec/rules.yaml (rules also feed data/build.json's key) and every src/rspy/**/*.py. An appended
  section fails `make freeze-verify`, `make r5-replay` and `make all` permanently.
- **Options:** (a) [rec] a separate spec/prereg_r6.yaml, sha256 in the ledger before any R6 number; (b) append and
  replay the r5-done tree in a temporary worktree from the Makefile; (c) append and accept a broken replay.
- **Owner's choice:** (a). "The BUILD_PROMPTS wording 'r6 section in prereg.yaml' was the owner's error; record the
  deviation." Consequence: R6 parameters live in spec/prereg_r6.yaml (rules.yaml stays the parameter source for every
  locked rung); R6 code lives outside the lock (`r6lib/`, `scripts/r6*.py`, `tests/test_r6.py`).

### O6.2 — New data for R6c (CPI) and R6g (gold) · ESCALATED TO OWNER (licence) · OWNER 2026-10-29
- **Options:** (a) [rec] CPI only (via FRED CPIAUCNS), skip gold; (b) CPI and gold (Pink Sheet); (c) neither.
- **Owner's choice (other):** CPI only, fetched **directly from the BLS** (CPI-U NSA, series CUUR0000SA0), with BLS's
  public-domain notice quoted in LICENSES.md (URL, date). **Not via FRED:** its terms bar storing or caching FRED content
  without consent, so this repo, like naive-vs-optimal, takes series from the source agency. Skip R6g and say why: this
  repo has no monthly-frequency engine. Use the CPI release lag (published about mid-month for the prior month).

### D6.1 — R6e, asymmetric vol targeting: weekly step-ups or a 5-day EWMA · confidence high · decider = advisor
- **Options:** (a) [rec] weekly step-ups as the row of record, plus the EWMA as the one sensitivity row; (b) weekly
  only; (c) EWMA only.
- **Choice:** (a), amended:
  1. raw_t is L2's unchanged scale min(0.15/σ20, 2), vol through t−1 (legacy_bridge.v1_scaled), on L2's target rows.
     Weekly: held_t = raw_t if raw_t < held_{t−1}; else raw_t if t is the last session of its ISO calendar week (a
     short week uses its last actual session); else held_{t−1}. held starts at raw on the first defined row.
  2. EWMA row: held_t = raw_t if raw_t < held_{t−1}, else held_{t−1} + (1/3)(raw_t − held_{t−1}) (span 5).
  3. The same pipeline as L2: signal timing, `v1_target` next-close mapping, the 2× cap, financing, true-turnover costs.
  4. Judged at matched vol (lower average gross must not pass as "better"); turnover, cost_pa and avg_gross beside.
  5. The Friday anchor is disclosed, never swept.
  6. A plain-loop reference in tests/reference/, plus property tests: a cut applies the same day; the weekly row equals
     raw at every week-end session.
  7. Both rows in variants.csv (DSR N +2).
- **Why the others lost:** (b) gives no reading on whether the form matters; the prompt names the EWMA. (c) trades a
  little every up-day, cuts turnover less, and drops the prompt's first form without a basis.

### D6.2 — R6c, the faster correlation regime and the inflation-volatility gate · confidence medium-high · decider = advisor
- **Options:** (a) [rec] two one-layer rows on L5 (R6c-63 = R3's L6-63 unchanged; R6c-infl = L5 with the inflation
  gate in place of the correlation gate), no combination; (b) one row, the 126-day gate OR the inflation gate; (c) (a)
  plus "63-day OR inflation" as a sensitivity row.
- **Choice:** (a), amended:
  1. The carry fallback should never fire on a scored decision. Expected count = 0 is written in prereg_r6 and tested;
     `regime.check_coverage` runs on the R6c-infl keep unchanged. A non-zero count is a registration error to log, not
     a reason to loosen the guard.
  2. The release lag is a checked fact. The rule: a decision at the month-end close of M uses CPI months ≤ M−1. Checked
     2026-10-29 against the BLS CPI release archive (bls.gov/bls/news-release/cpi.htm, 1994 → 2026): every release fell
     inside the month after its reference month. The latest relative releases: Sep 2013 on 2013-10-30, Sep 2025 on
     2025-10-24, Nov 2025 on 2025-12-18. Before 1994 the archive is absent, so the lag is assumed (disclosed); those
     decisions are warm-up or development only.
  3. Free choices written before running:
     - keep = [1, 0 if high else 1] on L6's month-end rows, traded at the next close, applied to L5's daily target
       (L5's vol scale unchanged, rules.yaml r3.L6.action);
     - the plain sample median (an even count averages the two middle values), v_m inside its own 120-month window;
     - CPI as published, no rebasing;
     - CPI from 1975 for estimation only.
  4. The prompt's wording ("L6 with the 63-day window … and an inflation-volatility gate") can be read as one combined
     row. (a) splits it into two one-layer rows on purpose. The combined row is not run.
  5. R6c-63's development row is R3's number, marked "previously computed (R3)". Only its test row is new.
- **Why the others lost:** (b) puts two changes in one row, so a gain cannot be attributed, and it keeps the slow
  126-day gate. (c) is a third candidate, not one value of an open choice. OR-ing two gates fires at least as often as
  either, so it would look best exactly in 2022.

### D6.3 — R6f, how the equal-weight blend is booked · confidence high · decider = advisor
- **Options:** (a) [rec] a fund of three books (L2, L3, L7), shares reset to 1/3 monthly, no cross-book netting, the
  reset trade charged per asset; (b) one book with daily target (1/3)Σheld_i; (c) a return blend with no reset cost.
- **Choice:** (a), amended:
  1. The reset is decided at the month-end close t and traded at close t+1. Shares are 1/3 at t+1 and earn from t+2.
     Within the month v_i drifts with each book's net return (after its own costs and financing).
  2. The reset turnover per asset is |Σ_i (1/3 − v_i) · w_i,asset|, using the drifted v_i and the held w_i at the
     execution close t+1. Cash is the residual, moved free.
  3. Rates: 3 bp SPY, 2 bp TLT per side (rules.yaml accounting). Netting applies only inside the reset trade itself,
     never against the books' own trades that day.
  4. The 2×/3× cost and +75 bp rows stress every sub-book and the reset charge together.
  5. Turnover reported: Σ_i v_i,t · turnover_i,t + the reset turnover. The fund's average and maximum gross go beside
     it (L2 runs up to 2×).
  6. v_i = 1/3 at the fund's first session. Each sub-book's warm-up follows its own rung.
- **Why the others lost:** (b) rebalances the split daily, which is not the registered "monthly"; L3's band would act
  on the mix; daily cross-book netting is a cost credit the prompt never gave. (c) drops a real trade's cost.

### D6.4 — Comparators, matching, the common-sense verdict and DSR N · confidence high · decider = advisor
- **Options:** (a) [rec] one own parent per candidate, ±0.05 ΔSharpe bands, fixed words, DSR N + n_R6; (b) verdict
  from the LW interval only; (c) a Holm family over R6 rows.
- **Choice:** (a), amended:
  1. The charter's full minimum effect (prereg promotion_rule.min_effect), per window, vs the own parent matched:
     - "better" = ΔSharpe ≥ +0.05, or (CDaR-95 ratio ≤ 0.85 and ΔSharpe > −0.05);
     - "worse" = ΔSharpe ≤ −0.05, or (CDaR ratio ≥ 1/0.85 and ΔSharpe < +0.05);
     - else "about the same". The leg that fired ("Sharpe" / "drawdown") is printed.
  2. "Clearly" only when the 95% interval excludes 0 in the word's direction (LW for Sharpe; dd_ratio_ci excludes 1
     for a drawdown verdict).
  3. Fixed words over all 9 (development, test) pairs:
     - B/B "better in both periods"
     - S/B, W/B "better only in the period that inspired it"
     - B/S "better in development only"
     - B/W "better in development, worse in the test"
     - S/S "no real difference"
     - S/W, W/S "worse"
     - W/W "worse in both periods"
  4. "The line" in the ΔSharpe columns = L0 rescaled once ex post to the candidate's excess vol in that window, the
     same convention as every other reference. The ex-ante line is reported only as a metrics row.
  5. Own parents: R6a → L2; R6b rows → the same rung at 25y; R6c-63 → L6 (126-day, the registered primary); R6c-infl
     → L5 (L6 beside); R6d → L5; R6e rows → L2; R6f → the line.
  6. Every table carries the window labels. A verdict promotes and demotes nothing. Power at the test length goes
     beside the test column (development point Sharpes, quantkit stats.power, optimistic iid).
  7. DSR, test window: N_headline = 5 + n_R6, N_raw = 751 + n_R6, V = max(V_dev, 1/(T−1)). Development:
     n_used = 4 + n_R6. n_R6 = 15 is fixed from variants.csv and hashed before any R6 number.
  - Disclosed: some R6 rows already had numbers before this rule existed. L6-63 has development numbers (R3); the 10y
    L5–L7 rows have development (R4) and test (R5) numbers. The rule is generic and not tuned to them.
- **Why the others lost:** (b) ≈ 7 test years gives almost no power, so every row would read "no difference". (c) a
  confirmatory family on a window that inspired the ideas would overstate the evidence; the owner asked for plain words.

### D6.5 — Orchestration · confidence high · decider = advisor
- **Options:** (a) [rec] Makefile targets r6-data / r6 / r6-figures-local, `r6` in `all`; (b) no Makefile change.
- **Choice:** (a), amended:
  1. `r6-data` stays out of `all`, like `fetch`. `r6` depends on `logs data omp` and fails clearly if data/r6/raw, its
     manifest or a sha256 is missing or wrong. It never fetches on its own.
  2. The R6 local figures hook into `report-site-local`; the standalone `r6-figures-local` target is kept.
  3. In `all`, `r6` goes after `r5-figures` and before `report-site`.
  4. The Makefile edit is committed on its own, before any R6 number. The ledger records the old/new Makefile sha256 and
     the expected `make freeze-verify` output ("locked file changed: Makefile"), the outcome D5.9 foresaw.
  5. freeze.py, the lock and prereg.yaml are not edited. `make r5-replay` runs once after the edit and must print the
     D5.9 line and stay byte-identical; logged.
- **Why the other lost:** (b) breaks the charter's "make all reproduces every figure".

### R6 review (reports/reviews/R6.md) — decisions after the R6 results (post-hoc, logged before acting)

### O6.3 — Verdict wording (review MATERIAL 2: reviewer vs advisor D6.4) · ESCALATED TO OWNER · OWNER 2026-10-29
- **Finding:** 3 of the 4 rows worded "better only in the period that inspired it" were worse in development, while
  the mirror case had its own phrase. 0 of 15 test words have an interval excluding 0 (test power 0.01–0.29).
- **Options:** (a) [rec] add a 10th phrase and the flags; (b) flags only; (c) keep D6.4.
- **Owner's choice:** (a).
  - (worse, better) now reads "worse in development, better in the test". (same, better) keeps "better only in the
    period that inspired it".
  - "clearly / not clearly" (per window) and the test power go beside every verdict and every count, in the tables,
    figures and README draft.
  - Logged post-hoc with the new spec hash (spec/prereg_r6.yaml `post_hoc.words`).

### O6.4 — The R6 Makefile targets vs R5's lock (review MINOR 5; reverses advisor D6.5) · ESCALATED TO OWNER · OWNER 2026-10-29
- **Finding:** the R6 targets changed a locked file, so `make freeze-verify` exits 1 for good. freeze.py is locked
  too, so it cannot learn the exemption.
- **Options:** (a) [rec] keep the change (D6.5); (b) revert the Makefile and run R6 by documented commands.
- **Owner's choice (other):**
  - Restore the R5-locked Makefile byte for byte (sha256 2020ab31…), so `make freeze-verify` passes again.
  - Move the R6 targets into a separate `Makefile.r6`, run as `make -f Makefile.r6 all`, and document it in the
    README draft's Reproduce section and in the ledger.
  - Add a test that `make freeze-verify` exits 0.

### D6.6 — Placebos for the R6 gates (review MATERIAL 1) · confidence high · decider = advisor · POST-HOC
- **Finding (reviewer's 40-seed probe, seen before this decision):** on the test window, the inflation gate's +0.384
  equals the median of shuffled timings (50% ≥ real), with a flat cut at +0.325. Bond-only trend's +0.248 is below the
  shuffle median of +0.293 and the flat cut's +0.290.
- **Options:** (a) [rec] the D5.8 placebo (seeds 0–99, 12-month blocks) plus a flat-cut row for every R6 gate;
  (b) shuffle only; (c) disclosure only.
- **Choice:** (a), amended:
  1. **Same pipeline, only the timing differs.** The flat cut multiplies the gated sleeve by the gate's mean kept share
     in that window, at the exact point where the gate acts (same vol layer, band, costs, financing, t+1 execution).
     The shuffled keep goes through the same code path.
  2. **R6c_L6-63's placebo and flat cut are judged against L5,** the layer its gate adds to (as D5.8 for L6). The
     own-parent ΔSharpe vs L6 is kept beside it.
  3. **Development binds; the test only qualifies.** In development (≈ 30 blocks), "timing beats random and flat cut?"
     = real ΔSharpe above the placebo p95 AND above the flat cut, yes/no. On the test (≈ 7 blocks): the percentile and
     inside-p05–p95 only, with no "beats" word and no p-value. Inside → the README says "not distinguishable from
     holding fewer bonds (stocks) at random times / a flat cut".
  4. **The verdict words are not edited by the placebo;** it adds qualifier columns only (one-directional).
  5. **Seeds 0–99 are fixed in the prereg_r6 addendum before the run.** The addendum states that the reviewer's 40-seed
     probe overlaps them and was seen first. Registered in variants.csv as controls (counted no), with a perf budget.
     Block-6 sensitivity is excluded (as D5.8).
  6. **Windows are shuffled separately** (each window's own decision rows, never mixed). The warm-up is never scored.
- **Why the others lost:** (b) cannot show that R6d's test gain is a flat-cut effect; (c) lets a verdict stand that
  random timings matched.
