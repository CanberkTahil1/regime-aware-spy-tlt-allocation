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

### O1.1 — Committed R1 outputs derived from Yahoo/Cboe (and near-daily KF curves) in a PUBLIC repo · ESCALATED TO OWNER · pending
- **Why escalated:** licence question (charter escalation list) and advisor vs reviewer disagreement: D1.4's advisor
  passed it on as an optional flag; the R1 quant-reviewer (MATERIAL 2) says it had to be escalated. Logged before any
  action; nothing is pushed.
- **What is committed now (b46f998 + review fixes):** statistics derived from v1's local Yahoo/Cboe file (rows S0–S6 of
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
any R2 code or result. Research: reports/research/R2.md (16791b4).

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
