# Ledger: expectations before code, results after

Status: `open` → `held` / `failed` / `not tested`, each closed with the command and the number that decided it.
`spec/prereg.yaml` does not exist yet (R1 writes it and hashes it here before any rung result).

## R0 — scaffold, licences, safety (expectations committed before any R0 code)

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E0.1 | v1 characterization reproduces `results/tables/test_metrics.csv` (8 metrics × strategy/SPY = 16 numbers) on the cached `data/prices.csv` (blob 900f1dbf0cab27f32da7926aa6bca5ef3a5dee03, from 5ccc12c): max abs diff ≤ 1e-12 | BUILD_PROMPTS R0 pre-registered | **held** — `make legacy`: max abs diff 1.22e-15 (16 numbers) ≤ 1e-12; also from v1's own main() |
| E0.2 | `summary_metrics.csv` reproduces: selected parameters and strategy string exactly; every float equal after v1's own rounding (4 dp, turnover 2 dp) | D0.3 | **held** — v1 main() → summary_metrics.csv equal (byte-identical file); selection rule on the committed grid picks the summary params |
| E0.3 | `grid_search_results.csv` reproduces: 648 rows; parameter columns exact; float columns ≤ 1e-12 abs; argmax of selection_score's train-shortlist rule picks the summary row | D0.3 | **held** — 648 rows, params exact, float max abs diff 1.05e-14 ≤ 1e-12 (pandas 3.1.0 / numpy 2.5.4 vs v1's unrecorded versions) |
| E0.4 | `make test lint` green; v2 code imports no Yahoo/Cboe client (a `force_download=True` call fails with the exclusion message) | BUILD_PROMPTS R0 exit; D0.2 | **held** — `make test` 52 passed, `make lint` pass; `test_download_path_fails_loudly`; doctor: yfinance absent |
| E0.5 | perf: `make test` ≤ 60 s wall, peak RSS ≤ 1.5 GB (reports/perf.md) | performance contract | **failed** (corrected 2026-10-28; first marked held on the wrong measure: max single process 185 MB vs a band perf.md defines as "≤ 1.5 GB total"). `-n auto` on 16 cores: 1952 MB peak summed tree RSS, 8.57 s wall. Cause: 16 xdist workers × ≈ 110–120 MB of numpy/pandas/numba imports. Reviewer R0 MINOR 1; D0.4 |
| E0.5-fix | same band: `make test` ≤ 60 s wall, peak RSS ≤ 1.5 GB, after D0.4 (`-n auto --maxprocesses 4`) | D0.4 (post-hoc fix, band unchanged) | **held** — `python scripts/rss_peak.py make test`: 52 passed, 625 MB summed over 12 processes (upper bound), 8.14 s wall |
| E1.0 (deferred to R1) | the loaded-module quantkit pin check covers > 0 files once `rspy` imports quantkit (R0 runs show "OK (0 files)") | reviewer R0 MINOR 2 | **held** at R1 (see the R1 table: 20 quantkit files checked) |

Note (D0.1): importing `legacy.config` creates `legacy/data/` and `legacy/results/{plots,tables}/` (v1's
`config.validate()`); `/legacy/data/` is gitignored.

A miss is recorded here with its cause; the 1e-12 band is never widened (D0.3 amendment 4).

Broken-input checks (2026-10-28): planting `COST_PER_UNIT * 1.0000001` in legacy/backtest.py fails
`test_legacy_module_is_v1_except_imports[backtest.py]`, `test_test_metrics_reproduce_from_committed_params` and
`test_v1_main_reproduces_all_three_tables`; restored from a copy (empty diff). Missing / edited data file → error naming
the blob (`test_data_guard_fails_on_missing_or_changed_file`).

## R1 — data swap and correct accounting (expectations committed before any R1 code or number)

Pre-registration hashes (before any rung result): `spec/prereg.yaml` sha256 **cb9b7fa9c11578b86e181331c4f0fe10bae515c383b3b8257dd28210fbb8027a**; `spec/rules.yaml` sha256 21cf66f97f77b7383fde543f2a86763a2415bdc95ce7aebff5a7769aca26faf6.

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E1.1 | S0 = v1 reproduced: test metrics max abs diff ≤ 1e-12 (as E0.1) | BUILD_PROMPTS pre-registered | **held** — `tests/test_legacy_bridge.py::test_mirror_is_v1_and_s0_reproduces_committed_test_metrics`: mirror vs v1's compute_strategy_returns ≤ 1e-15; S0 test metrics vs test_metrics.csv ≤ 1e-12 (CAGR 0.1631, Sharpe 1.0033) |
| E1.2 | S1 (t+1) ≤ 0: ΔCAGR ≤ 0 and ΔSharpe ≤ 0 vs S0 in each of train / validation / test | BUILD_PROMPTS pre-registered | **failed** (logged before diagnosis, 2026-10-28): `make reconcile` S1 − S0: train ΔCAGR **+1.64 pp** (7.75% → 9.39%), ΔSharpe(v1 def) **+0.093** (0.543 → 0.637); validation −3.29 pp / −0.204; test −2.27 pp / −0.133. Holds in validation and test, fails in train. Diagnosis below. |
| E1.3 | S2: financing charge ≥ 0 on every row (= return effect ≤ 0), > 0 on rows held at gross > 1; cash interest ≥ 0 | BUILD_PROMPTS pre-registered | **failed (cash clause only)** — the pre-registered clause held: `make reconcile` S2 on v1's path: financing > 0 on all 3,243 rows held long above gross 1, = 0 on the other 2,039, never < 0. The added clause "cash interest ≥ 0" failed on 8 sessions: H.15 printed negative 3-month yields (2015, 2020; min −0.05%), so cash correctly earned a negative bill. Wrong premise, not a bug; code unchanged |
| E1.4 | S3: sign NOT claimed (more turnover from drift, lower rate 5 → 3/2 bp); traded turnover (annualised, test) ≥ 18.73× (v1's reported turnover, which excludes vol scaling) | D1.4 (author's disagreement logged) | **held** — S3 traded turnover (test) 26.73× ≥ 18.73× (v1's reported, signal definition); sign (descriptive): ΔCAGR S3 − S2 train +0.70%, validation +0.90%, test +0.69% (lower rate outweighs the drift trades) |
| E1.5 | S4: net returns identical to S3 (exact); only the metric changes | D1.4 | **held** — `reports/r1/facts.json` S3_equals_S4_returns_exact = true (pandas `.equals`) |
| E1.6 | S5, S6, S7: descriptive (no sign claimed); S7 = L1 runs through `rspy.accounting` without a short | D1.4 | **held** — S7 runs through rspy.accounting with no short (min weight 0.0). Descriptive: S5 ΔSharpe(excess) train +0.027 / val +0.054 / test -0.004; S6 +0.006 / -0.007 / -0.006; S7 +0.049 / -0.044 / +0.084. L1 = S7: excess Sharpe train 0.63, validation 0.52, test 0.78 |
| E1.7 | Data QA monthly 2005-01 → 2025-12: Hi 20 vs SPY corr ≥ 0.98 and TE ≤ 1.5%/yr; GSW 25y vs TLT corr ≥ 0.98 and TE ≤ 3.0%/yr | D1.6 / prereg | **held** — `reports/r1/qa.csv` 2005-01 → 2025-12 (252 months): Hi 20 vs SPY corr 0.9973, TE 1.08%/yr (mean diff +0.43%/yr); GSW 25y vs TLT corr 0.9941, TE 1.49%/yr (mean diff +0.25%/yr). Descriptive 2020–25 (seen): 25y TE 2.07%/yr ≈ the 2.06% label |
| E1.8 | `rspy.accounting` fast path = plain reference loop ≤ 1e-10; timing property (returns at rows ≥ t+2 cannot change weights decided at t) | D1.3 | **held** — `tests/test_accounting.py` fast = reference ≤ 1e-10 (3 seeds, daily and sparse decisions, 2× costs, stress spread); hypothesis timing test (40 draws). Planted same-close execution fails 5 tests (mutation, restored) |
| E1.9 | Bills: y·91/360 = 91-day r_s (≤ 1e-15); a missing H.15 print carries the last rate, never a later one | D1.1 | **held** — `tests/test_accounting.py` y·91/360 = 91-day r_s ≤ 1e-15; carry-forward never uses the same session's print (planted look-ahead fails the test) |
| E1.10 | TLT proxy (quantkit, par_col=None) = sibling `par_total_return` 25y (copied reference) ≤ 1e-10 | D1.2 | **held** — synthetic curve ≤ 1e-10 (`tests/test_bonds.py`); real GSW curve: quantkit(par_col=None) vs the copied reference max abs diff **0.0** over 10,214 returns (published-coupon "auto" would differ by up to 0.71%/day). Removing the both-dates mask fails 2 tests |
| E1.11 | perf: `make data` ≤ 30 s; reconciliation (8 steps × 3 windows) ≤ 10 s; peak RSS ≤ 1.5 GB (rss_peak) | performance contract | **held** — `make fetch`+build 2.4 s (build alone 1.9 s); `make reconcile` 1.4 s, 617 MB summed RSS; `make test` 9.4 s, 1,140 MB summed (rss_peak upper bound) |
| E1.0 | (from R0) loaded-module pin check covers > 0 quantkit files | reviewer R0 MINOR 2 | **held** — the conftest's loaded-module check now covers 20 quantkit files in R1 test runs (was 0 at R0) |

**E1.2 diagnosis (after the failure was logged in c0b9b2b):** no bug — S1 rebuilt by hand equals the bridge (max diff 0.0)
and `test_t_plus_one_and_accounting_timing_agree` ties the two timing frameworks. Not a 2008 artefact (train ex
2008–09H1: Sharpe 0.81 → 0.90). Execution lag 0/1/2/3 Sharpe (v1 def): train 0.54 / 0.64 / 0.58 / 0.57 (same-close
worst), validation 0.77 / 0.56 / 0.74 / 0.76 (t+1 worst): one-day timing of this contrarian daily signal has no stable
sign (SPY lag-1 autocorrelation −0.09 in 2005–14). The premise "a fast signal loses at t+1" was wrong for v1 in train;
the row stays failed; code and spec unchanged.

**R1 also fixed (found by the R1 test run, not a reviewer):** `tests/test_legacy_v1.py::test_v1_selection_rule_picks_the_summary_row`
imported legacy without the yfinance stub and passed in R0 only when another test had imported legacy first in the same
xdist worker; it now takes the `no_yahoo` fixture (assertion unchanged).

**Deferred by the R1 review (open):**

| ID | Item | Phase | Status |
|---|---|---|---|
| E1.12 | Growth / drawdown charts show the vol-matched SPY + T-bills line (`quantkit.bench.vol_matched`) once L0-line exists | R2 | open |
| E1.13 | `make all` reproduces every figure from raw PERMITTED data on a machine without v1's file (legacy tests and `reconcile` are local targets, D0.3) | R5 (Definition of done) | open |

**Owner O1.1 applied (2026-10-28):** statistics stay committed (reports/r1/*, the three statistics figures, the
statistics-only page); the four curve figures (growth + drawdown, exposure, rolling 5-year Sharpe, crisis panels; PNG +
SVG) are untracked and rebuilt locally by `make report-site-local` into the gitignored reports/figures_local/R1/ and
reports/site_local/ (one page per evidence tier). `tests/test_site_local.py` fails if those paths stop being ignored
(checked: removing the rule fails it) or if any curve figure is tracked; the pre-commit hook refuses both paths. The
untracked files remain in history (b46f998, ae4028b) until the owner's rewrite with data/prices.csv before the next push.
E1.12 (vol-matched line) now belongs on the local curve charts.

## R2 — the core mix L2–L5 (expectations committed before any R2 code or number)

Pre-registration hashes (after the D2.x additions, before any rung result): `spec/prereg.yaml` sha256
**85aa8714587428dbad0be1d275283a19a2ecfd4f9d0f4270e5ccc222b82c2340**; `spec/rules.yaml` sha256
32fb3806b0a0876f3077f0144afab8bbbf6ace46063a1cd55e6281cbe8323409. quantkit v0.19.2 (owner O2.1).
Scored window: development 1990-01-02 → 2019-12-31, daily; test 2020+ is not run in R2.

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E2.1 | L4 excess Sharpe > L1's and > L2's (ΔSharpe > 0, point estimates, development) | BUILD_PROMPTS R2 | **held** — `make ladder` → reports/r2/metrics.csv (1× books, 1990-01-02 → 2019-12-31): excess Sharpe L4 **0.822** vs L1 0.512, L2 0.533 |
| E2.2 | L5 excess Sharpe > L1's and > L2's (ΔSharpe > 0, development) | BUILD_PROMPTS R2 | **held** — L5 excess Sharpe **0.833** vs L1 0.512, L2 0.533 (same file) |
| E2.3 | L4 and L5 max drawdown shallower than both L1's and L2's (|max DD| smaller, development) | BUILD_PROMPTS R2 | **held** — max DD L4 **−18.2%**, L5 **−13.0%** vs L1 −43.3%, L2 −47.7% (same file) |
| E2.4 | L5 traded turnover (one-way Σ\|Δw\| incl. drift and vol-scaling trades) < 2.0×/yr, development | BUILD_PROMPTS R2 | **held** — L5 traded turnover **0.43×/yr** (same file; vol-scaling and drift trades included) |
| E2.5 | `rspy.accounting` with the drift-aware band = plain reference loop ≤ 1e-10; band 0 = the unbanded book bit-identically; planted "band vs last target" (quantkit convention, no drift) fails the test | D2.1 | **held** — `tests/test_band.py`: fast = reference ≤ 1e-10 (4 cases incl. per-sleeve widths); band 0 bit-identical; edge test. Broken-input check: replacing the edge clip with "trade to target" in accounting.py fails tests/test_band.py (restored, suite green) |
| E2.6 | L2 decision = v1's mirror on an all-SPY signal: v1 `compute_strategy_returns` (own data, own accounting) ≤ 1e-12 | D2.3 | **held** — `tests/test_r2_legacy.py`: mirror on an all-SPY signal = v1 `compute_strategy_returns` ≤ 1e-12 on v1's cached data |
| E2.7 | L4 fast σ = `quantkit.alloc.cov.sample_cov` reference ≤ 1e-10; L4b (quantkit erc) weights = L4 weights ≤ 1e-10 at every 1990–2019 month-end; property test on random SPD 2×2 | D2.6, D2.7 | **held** — `tests/test_r2.py`: σ = `sample_cov` ≤ 1e-10 (all 63 required; planted min_periods=2 fails); ERC = inverse vol (hypothesis, 60 draws, ρ ∈ [−0.99, 0.99]); real data: max \|L4b − L4\| = **8.8e-15** (reports/r2/facts.json) |
| E2.8 | Record book = `quantkit.trade.tranche(...)["books"][0]` bit-identically; all 21 offset books built; short-month collisions counted | D2.5 | **held** — facts.json L3/L4/L5_record_equals_offset0_book = true (`np.array_equal` against `tranche(...)["books"][0]`); `test_record_book_is_tranche_offset_zero`; collisions counted in timing_luck.csv (offsets 19/20) |
| E2.9 | L0-line: every weight input dated < t (planted future value cannot change w_t); line finite from 1990-01-02 | D2.8 | **held** — `test_ex_ante_line_never_uses_row_t_or_later` (planted ×5 from row t changes no weight ≤ t); facts.json line_first_finite_scored = 1990-01-02 |
| E2.10 | Vol zoo: quantkit `vol_forecast` audit passes for all five models; the year-end pick uses rows ≤ that year-end only (planted post-year-end loss cannot change it) | D2.2 | **held** — every zoo model ran `vol_forecast(..., audit=8)` (raises LeakageError on a mismatch; none); `test_zoo_pick_ignores_losses_after_the_year_end`; planting `Ly = L` (all rows) fails it |
| E2.11 | perf: one rung full evaluation ≤ 10 s; whole R2 ladder + zoo ≤ 5 min; peak RSS ≤ 1.5 GB (rss_peak); worker count 1 vs N bit-identical where a pool is used | performance contract | **failed** (first run, logged before diagnosis): 2,227 MB summed peak > 1.5 GB. Time parts held: cold `make ladder` 28.2 s ≤ 5 min; one rung's evaluation < 2 s ≤ 10 s (facts.json timing_s: 14 rungs' books 1.5 s, metrics + lines + walk 4.7 s, 21-offset timing luck 2.3 s for 3 rungs). 1 vs N workers: not tested (no pool used) |

Notes before code: (1) the dev feasibility check (research R2 header) has L4's ex-ante vol below 10% at 85% of
month-ends, so the author expects L5 to equal L4 most days and the L5 − L4 effect to be small; E2.2 is kept as
pre-registered. (2) D2.4: rescaling a rung's excess returns by one constant implies financing at the bill rate; the
financed rescale (bill + 25 bp) is used only inside the CDaR and LOCO legs. (3) D2.2 limitation: the L4 book's
returns mix past weights; the gap vs EWMA on current weights × past sleeve returns is reported, never used.
(4) D2.3 disclosed prior: the owner's v1 audit (legacy, 2005–19, free leverage) found vol-targeted SPY beat v1.

**E2.11 miss logged before diagnosis (2026-10-28, first `make ladder` run):** `python scripts/rss_peak.py make ladder`:
**2,227 MB** summed peak RSS over 6 processes (budget ≤ 1.5 GB); wall 29.6 s (≤ 5 min: within). Diagnosis follows.

**E2.11 diagnosis:** the peak came from `volzoo.select`: each yearly MCS draws (1,000, T) bootstrap arrays
(quantkit `stationary_bootstrap_index`: ≈ 190 MB of temporaries at T 7,500); macOS keeps freed pages charged to the
process (current RSS did not fall after `del`), and T grows every year, so no freed block was reused (30 years → 2.2 GB).
Fix (no quantkit change): compute the years latest first; each year is independent and seeded, so the picks are
byte-identical (reports/r2/volzoo.json compared before/after).

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E2.11-fix | same band after the fix: whole `make ladder` ≤ 5 min, peak RSS ≤ 1.5 GB (rss_peak) | E2.11 (post-hoc fix, band unchanged) | **held** — cold (forecast cache cleared): 957 MB, 28.2 s; warm: 914 MB, 15.6 s |

**R2 walk (development, D2.4):** stopped at its first step. L2 vs L1: quantkit effect +0.021 < 0.05, LW one-sided p 0.23,
and L2 loses Sharpe inside five of six development crises (1994, dot-com, GFC, 2011, 2015); the rspy Sharpe-route legs
pass, the CDaR route does not apply (L2's CDaR-95 is higher than L1's matched). **Seat holder: L1**; L3, L4, L5 are
"not tested (sequence stopped)" (reports/r2/ladder.json). Attribution (corrected after review MATERIAL 1): stopping at
the first failure is quantkit's fixed-sequence rule (owner, quantkit Q10 ladder docstring); the walk ORDER
L1 → L2 → L3 → L4 → L5, with L2 as L3's incumbent, is the advisor's reading of the charter (D2.4), not an owner rule.
The reviewer disputes it (L3 adds bonds to L0, not a layer to L2): escalated to the owner as O2.3; nothing changed. Descriptive only (not
promotion evidence): vs the SPY + T-bills line at matched vol (ex ante), ΔSharpe L3 +0.17 [0.01, 0.32] (p 0.017), L4
+0.24 [−0.06, 0.54] (p 0.055), L5 +0.26 [−0.04, 0.55] (p 0.038), L1 −0.08, L2 −0.06 (reports/r2/lines.csv); ablation at
matched vol: bonds (L3 vs L0) +0.21 Sharpe / −23% CDaR, risk weighting (L4 vs L3) +0.13 / −31%, portfolio vol target
(L5 vs L4) +0.01 / −7% (reports/r2/ablation.csv). L5's cap 1.0 binds on 84% of days (facts.json), as noted before code.
L5 held gross never exceeds 1.0 (no financing); L5-lev's target cap is 1.5 but its held gross reaches 1.515 (band and
drift; above 1.5 on 1.5% of development days, data/r2/books.parquet) — "cap 1.5" is a target cap (review MINOR 2).
Vol zoo (pick made at year-end y, used in y+1): EWMA-slow at 1989–2002 and 2004–2006 year-ends, GJR-GARCH-t at 2003 and 2007–2018 (reports/r2/volzoo.json). D2.2 limitation
diagnostic: EWMA-60 vol of the L4 book / of current weights × past sleeve returns: median 1.00 (5–95%: 0.95–1.08).
Not in R2: DSR / PBO with the effective number of trials (R4–R5), the 2020+ test window (R5).

### R2 amendment — the parent-chain walk (POST-HOC, owner O2.3, 2026-10-29; expectations before any chain code)

Charter amended first (32bf308): L1 is a comparison row, not a parent; parent chains L0 → L2 and
L0 → L3 → L4 → L5 (→ L6 → L7 → L8 in R3). Attribution corrected again: the pre-registered order L1 → L2 → … came from the
owner's plan listing L1 first; D2.4 transcribed it (the review-MATERIAL-1 note above called it the advisor's reading).
The pre-registered walk above stays the record of R2's pre-registered result. Post-hoc prereg hash:
`spec/prereg.yaml` sha256 **5f44f7daab556f3f27fe1da8499a0820b457b8d3c1fbda7219882b56eaa565b3** (adds
`promotion_rule.walk_chains`, `comparison_rows`, L1 `walk_role`; nothing else changed); `spec/rules.yaml` unchanged
(32fb3806…). Same promotion rule, same books, same development rows. Counted in variants.csv (`walk_chains_O2.3`).
Disclosed priors: every R2 number above was seen before these expectations, incl. ablation.csv (matched ΔSharpe L2 vs
L0 +0.053, L3 vs L0 +0.215, L4 vs L3 +0.127, L5 vs L4 +0.011 / CDaR −7%) and crisis.csv.

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E2.12 | chain vt_spy: L2 not promoted over L0 (seat L0) — effect ≈ +0.05 at best, LW p > 0.05 expected | O2.3 | **held** — reports/r2/ladder_chains.json: L2 vs L0 effect +0.053, LW p 0.254, and loses Sharpe inside all six development crisis windows (1994, dot-com, GFC, 2011, 2015, Q4 2018); seat **L0** |
| E2.13 | chain core: author's prediction (low confidence): L3 fails quantkit's in-crisis robustness vs L0 in 1994 (bonds fell), so the seat stays L0; if L3 passes, L4 is promoted over L3 and L5 is not (effect +0.01, CDaR −7% < −15%) | O2.3 | **held (main branch)** — L3 vs L0: effect +0.215, LW p 0.005, MCS pass, rspy legs pass on both routes (CDaR −23%), but quantkit robustness fails: L3's Sharpe is lower inside 1994 bonds (ΔSharpe −0.54; return −6.9% vs SPY −3.0%) and Q4 2018 (−0.10, although L3 lost less: −7.7% vs −12.9%; in-window Sharpe of a losing window rewards higher vol). Seat **L0**; L4, L5 not tested |
| E2.14 | code: the pre-registered walk's reports/r2/ladder.json and the register rows unchanged byte for byte; the chain walk uses the same `ev.walk`; a synthetic test checks the chain topology (L1 never an incumbent) and that the chain ladders register without a rung-set clash | O2.3 | **held** — ladder.json `cmp`-identical to the pre-change file; register rows 1–2 identical (chain rows appended); `test_chains_are_parent_only_and_cut_at_the_first_unbuilt_rung` (planted L1 in a chain raises), `test_chain_walk_registers_beside_the_prereg_walk_and_never_uses_l1` (same set under a new name raises PreregistrationError) |
| E2.15 | perf: `make ladder` ≤ 5 min, peak RSS ≤ 1.5 GB (rss_peak) with the chain walk added | performance contract | **held** — warm `make ladder` 911 MB summed peak, 19.9 s wall (rss_peak) |

**Chain-walk result (post-hoc, development, descriptive of the rule, not evidence):** both chains stop at their first
step; the seat holder is **L0 (SPY)** in each. Seat holder under the pre-registered walk: L1 (unchanged). No stock-bond
rung is promoted under either walk. The binding part is quantkit's in-crisis robustness ("no Sharpe loss inside any
development crisis window"); the CDaR route and the rspy legs would have passed L3. Observation for the owner (no
action, changing the rule now would be post-hoc again): the in-window Sharpe compares a negative mean over a smaller vol,
so a lower-vol rung that loses less can still "lose" a window (Q4 2018 above); 1994 is a real loss on returns too.
Every rung vs L1 (comparison row, reports/r2/vs_l1.csv, LW 95%): L2 +0.02 [−0.03, +0.08], L3 +0.18 [−0.05, +0.41],
L4 +0.31 [−0.01, +0.63], L5 +0.32 [+0.01, +0.63] (p 0.022), L5-lev +0.37 [+0.06, +0.68]; CDaR vs matched L1: L4 −44%,
L5 −47%. Chart: reports/figures/R2/promotion_walks.png. DSR N: one extra trial (variants.csv `walk_chains_O2.3`).

### R2 amendment 2 — in-crisis matched-vol return (POST-HOC descriptive, owner O2.4, 2026-10-29; expectations before code)

Known limitation (owner O2.4): quantkit's robustness leg compares in-window Sharpe; when both books lose money in a
window, the more volatile book can "win" (Q4 2018: L3 −7.7% vs L0 −12.9%, yet L3 fails). Descriptive row added beside it
(reports/r2/crisis_matched.csv): for every walk step, in-window cumulative return of the child vs the parent scaled
ex post to the child's development excess vol with T-bills (`evaluate.rescale`, financed above 1× at bill + 25 bp — the
same matching as the rspy legs). Cannot change any verdict; not in the promotion rule; no variants.csv row (no
selection).

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E2.16 | L3 vs L0 at matched vol (k ≈ 0.60 from development vols 10.3% / 17.3%): 1994 still a loss for L3 (L3 −6.9% vs matched SPY ≈ −0.5%); Q4 2018 close to a tie (matched SPY ≈ −7.5% vs L3 −7.7%, sign uncertain) | O2.4 | **held** — reports/r2/crisis_matched.csv: 1994 L3 −6.94% vs matched SPY −0.26% (loss); Q4 2018 L3 −7.69% vs matched SPY −7.43% (a loss by 0.26 pp) |
| E2.17 | code: the verdict files (ladder.json, ladder_chains.json) unchanged byte for byte; the row's matched parent = `evaluate.rescale` exactly (test) | O2.4 | **held** — both files `cmp`-identical after the change; `test_crisis_matched_parent_is_the_legs_rescale`; the row's in-window ΔSharpe reproduces quantkit's robustness numbers (1994 −0.5388, Q4 2018 −0.1038) |

**Result (descriptive, cannot change any verdict):** at matched vol, 60/40 **still fails 1994** (−6.9% vs −0.3%) and
also **Q4 2018** (−7.69% vs −7.43%): so Q4 2018 is not an instance of the pathology once risk is matched (the owner's
example was the raw comparison −7.7% vs −12.9%). A real instance does exist in the walks: L2 vs L0 in the GFC — L2
−27.4% vs matched SPY −41.4%, yet its in-window Sharpe is lower (ΔSharpe −0.39); L2 still loses five other windows at
matched vol, so its verdict would not change either. The limitation stands as recorded (decisions O2.4); the
registered leg is unchanged. For R3 (owner O2.4): the walk verdict stands (nothing promoted past SPY); L6–L8 are tested
through the charter's ablation table (each layer vs its own parent, vs 60/40 and vs v1, 95% intervals, descriptive),
not through the walk.
