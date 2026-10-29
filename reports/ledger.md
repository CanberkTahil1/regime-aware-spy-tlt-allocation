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

### R2 amendment — the parent-chain walk (POST-HOC, owner O2.3, 2026-10-29; expectations before any chain result — first chain registration in ladder_prereg.jsonl 11:22:24Z, 34 s after the expectation commit; the chain code may already have existed)

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
| E2.13 | chain core: author's prediction (low confidence): L3 fails quantkit's in-crisis robustness vs L0 in 1994 (bonds fell), so the seat stays L0; if L3 passes, L4 is promoted over L3 and L5 is not (effect +0.01, CDaR −7% < −15%) | O2.3 | **held (main branch)** — L3 vs L0: effect +0.215, LW p 0.005, MCS pass, rspy legs pass on both routes (CDaR −23%), but quantkit robustness fails: L3's Sharpe is lower inside 1994 bonds (ΔSharpe −0.54; return −6.9% vs SPY −3.0%) and Q4 2018 (−0.10; at matched vol L3 −7.69% vs SPY −7.43%, reports/r2/crisis_matched.csv, so a real loss at equal risk). Seat **L0**; L4, L5 not tested. Note (review R2-amendment MINOR): the prediction was derivable from the already-seen crisis.csv, so "held" adds no evidence |
| E2.14 | code: the pre-registered walk's reports/r2/ladder.json and the register rows unchanged byte for byte; the chain walk uses the same `ev.walk`; a synthetic test checks the chain topology (L1 never an incumbent) and that the chain ladders register without a rung-set clash | O2.3 | **held** — ladder.json `cmp`-identical to the pre-change file; register rows 1–2 identical (chain rows appended); `test_chains_are_parent_only_and_cut_at_the_first_unbuilt_rung` (planted L1 in a chain raises), `test_chain_walk_registers_beside_the_prereg_walk_and_never_uses_l1` (same set under a new name raises PreregistrationError) |
| E2.15 | perf: `make ladder` ≤ 5 min, peak RSS ≤ 1.5 GB (rss_peak) with the chain walk added | performance contract | **held** — warm `make ladder` 911 MB summed peak, 19.9 s wall (rss_peak) |

**Chain-walk result (post-hoc, development, descriptive of the rule, not evidence):** both chains stop at their first
step; the seat holder is **L0 (SPY)** in each. Seat holder under the pre-registered walk: L1 (unchanged). No stock-bond
rung is promoted under either walk. The binding part is quantkit's in-crisis robustness ("no Sharpe loss inside any
development crisis window"); the CDaR route and the rspy legs would have passed L3. Corrected after review (R2-amendment
MATERIAL; the first wording compared raw returns at ~10% vs ~17% vol): at matched risk L3 loses both 1994 (−6.9% vs
−0.3%) and Q4 2018 (−7.69% vs −7.43%), so its robustness failure is not an artefact of the rule. The in-window Sharpe
limitation (O2.4) is real elsewhere — L2 vs L0 in the GFC — and changes no verdict (amendment 2 below).
Every rung vs L1 (comparison row, reports/r2/vs_l1.csv, LW 95%): L2 +0.02 [−0.03, +0.08], L3 +0.18 [−0.05, +0.41],
L4 +0.31 [−0.01, +0.63], L5 +0.32 [+0.01, +0.63] (p 0.022; unadjusted, one of 7 post-hoc descriptive comparisons — Holm ≈ 0.13), L5-lev +0.37 [+0.06, +0.68]; CDaR vs matched L1: L4 −44%,
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

## R3 — the regime layer L6–L8 (expectations committed before any R3 code or number)

Owner O2.4: the R2 walk verdict stands (nothing promoted past SPY); **no promotion walk for L6–L8**. Every R3 number is
descriptive: the ablation table (each layer vs its parent, vs 60/40 = L3, vs v1 = L1, vs the SPY + T-bills line, at
matched vol, 95% intervals). Decisions D3.1–D3.6 (advisor, reports/decisions.md). Pre-registration hashes (before any
R3 code or result): `spec/prereg.yaml` sha256 **fd05c7a468f0fb15cb94c71d669c7785e4d05f581a2bb91132f2a0ff792f8541**
(adds `r3_evaluation`); `spec/rules.yaml` sha256 **0014da1b5ab383e8b6dcc0ce07a69e82410af792e3a83cd551395ce386d11579**
(adds `accounting.band_zero_target`, `r3`). Scored: development 1990-01-02 → 2019-12-31; 2020+ is R5.
Disclosed priors: every R2 number (incl. L5 development vol 8.1%, max DD −12.99%, crisis.csv, crisis_matched.csv) and
the R3 signal-state table (reports/research/R3.md: corr126 > 0 at every 1994 month-end, < 0 throughout the GFC and Q4
2018; SPY in trend 23% of GFC days; TLT in trend 10% of 1994, 23% of Q4 2018). No R3 return has been computed.
Disclosed choices (D3.4 amendment 6): the 12-month placebo block is a reasoned choice, not a literature value.
Disclosures (D3.3): `sizing.judge` overlays are same-close (e_t earns r_{t+1}); the L8 book adds the charter's one
session and costs; the drawdown brake reads the excess-return NAV. D3.1: a zero target exits fully, but re-entry from
0 in a banded book stops at the band edge (target − 5 pp).
Not tested in R3 (D3.6, deferred to R4 with their D-items): v1 spread overlay, v1 Bollinger overlay (need a definition
of "overlay" for v1's unit-gross weights), GBM risk-side sizing (target, features, horizon, meaning of the 50%
haircut). Tranche offsets for L6/L7 (D3.2 amendment 1) are not built in R3 (record offset 0 only).

Predictions are the author's, low-to-medium confidence; "at matched vol" = reference rescaled to the child's
development excess vol (D3.5). Δ = child − matched reference.

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E3.1 | L6 vs L5 (parent), development: ΔSharpe in [−0.25, +0.05] (bonds earned well in the 1990s positive-correlation spells L6 removes); LW one-sided p > 0.05 | BUILD_PROMPTS R3; author | **held** — `make ladder` → reports/r3/ablation.csv (L6 vs parent): ΔSharpe **−0.081** [−0.229, +0.066], one-sided p 0.863 (Holm 1.00); CDaR ratio 1.13 [0.80, 1.38] |
| E3.2 | L6 matters mainly in 1994: matched in-crisis return L6 − L5 ≥ +2 pp in bonds_1994; \|L6 − L5\| ≤ 2 pp in GFC and in Q4 2018 (gate off throughout: same holdings up to scale) | BUILD_PROMPTS R3 ("1994 and 2022-type"); research facts | **held** — `make ladder` → reports/r3/crisis.csv (L6 vs matched L5): 1994 **+5.87 pp** (L6 +0.07% vs −5.80%); GFC −1.16 pp, Q4 2018 −0.59 pp (in-window ΔSharpe 0.000: same holdings, the gap is the matching scale) |
| E3.3 | L7 vs L6 (parent): ΔSharpe in [−0.20, +0.15]; CDaR-95 ratio (L7 / matched L6) < 1 (point) | BUILD_PROMPTS R3 ("cuts drawdowns at some whipsaw cost") | **failed (CDaR part)** — ΔSharpe **−0.172** [−0.421, +0.076] (inside the band) but CDaR-95 ratio L7 / matched L6 = **1.137** [0.671, 1.701], not < 1. Diagnosis below |
| E3.4 | L7 cuts the 2000–02 and 2008 drawdowns: matched in-crisis return L7 − L6 > 0 in dotcom and in GFC; Q4 2018 L7 − L6 < 0 (TLT out ~3/4 of days, SPY mostly in: the hedge is removed when it worked); 1994 L7 − L6 ≥ −0.5 pp | BUILD_PROMPTS R3; research facts | **failed (1994 part)** — matched L7 − L6: dotcom **+10.0 pp**, GFC **+11.8 pp**, Q4 2018 **−2.5 pp** (all as predicted) but 1994 **−2.5 pp** < −0.5 pp. Diagnosis below |
| E3.5 | L8 fails `judge`: on = False (candidate one-sided LW p ≥ 0.05); L8 vs L7 matched ΔSharpe in [−0.05, +0.03]; g < 1 on < 10% of development days | BUILD_PROMPTS R3 ("most crash rules do"); D3.3 | **held** — reports/r3/crash.json: judge on = **False** (candidate one-sided p 0.999, placebo 0.188); L8 vs L7 ΔSharpe **−0.002** [−0.006, +0.003]; g < 1 on **2.7%** of development days (min g 0.857) |
| E3.6 | Gate rule (D3.4): neither L6 nor L7 "beats placebo" (each fails the gate-vs-parent p < 0.05 part); 100-seed percentile of L6's matched ΔSharpe < 95 | author | **held** — reports/r3/placebo.csv: L6 gate p 0.863, L7 p 0.901 (neither < 0.05 ⇒ neither beats placebo); L6 percentile **59** of 100 placebo seeds (L7 36) |
| E3.7 | vs 60/40 (L3) at matched vol: L6 and L7 ΔSharpe in [−0.10, +0.30] (L5 vs matched L3 ≈ +0.14 in R2's ablation chain) | owner O2.4; author | **failed (L7)** — vs matched 60/40: L6 **+0.057** [−0.126, +0.240] (inside), L7 **−0.115** [−0.436, +0.205] < −0.10 |
| E3.8 | vs v1 (L1) at matched vol: L6 and L7 ΔSharpe in [0.00, +0.50] (L5 +0.32 in R2) | owner O2.4; author | **held** — vs matched v1: L6 **+0.239** [−0.072, +0.551] (p 0.057), L7 **+0.067** [−0.294, +0.429] |
| E3.9 | vs the SPY + T-bills line (ex ante, L0-line): L6 and L7 ΔSharpe in [−0.10, +0.40] (L5 +0.26 in R2) | charter; author | **held** — vs the ex-ante SPY + T-bills line (then matched): L6 **+0.229** [−0.062, +0.521] (p 0.053), L7 **+0.023** [−0.349, +0.395] |
| E3.10 | L6 realised development vol below L5's by ≥ 0.5 pp (vol scale kept while TLT goes to cash, D3.1) | D3.1 amendment 4 | **held** — reports/r3/facts.json: L6 development vol **7.07%** vs L5 8.11% (−1.04 pp); on gated days 5.49% vs 8.49% |
| E3.11 | Zoo (descriptive): HMM and jump gates vs L5 matched ΔSharpe in [−0.20, +0.10], neither beats placebo; min-CDaR (+ vol layer) vs L5 in [−0.15, +0.10]; max-div = L4 weights ≤ 1e-10 at every decision row | D3.6; author | **held** — ΔSharpe vs L5: HMM gate −0.072 [−0.267, +0.123], jump gate −0.045 [−0.256, +0.166], neither beats placebo (p 0.749 / 0.637); min-CDaR +0.024 [−0.112, +0.160]; max-div − L4 max abs **8.8e-15** |
| E3.12 | code: the zero-target exemption leaves every R2 output unchanged — reports/r2/*.{csv,json} `cmp`-identical after `make ladder`, data/r2/books.parquet columns equal bit for bit; ladder_chains.json still cut at L5 (no R3 walk) | D3.1 amendment 1; O2.4 | **held** — after the band change and `make ladder`: every reports/r2/* file `git diff`-clean except facts.json `timing_s` (wall clock; restored); data/r2/books.parquet `DataFrame.equals` True (8,570 × 37); L1/L3/L5 rebuilt in r3.py equal R2's books bit for bit (facts.json); ladder_chains.json unchanged (chains cut at L5) |
| E3.13 | code: tests — gate decided ≤ t (perturbing rows > t leaves the decision unchanged); correlation = np.corrcoef reference ≤ 1e-10; faber read-back = SMA at decision rows (exact); no NaN gate/trend/zoo state at any development decision row; L8 g path = judge's candidate (Sharpe equal ≤ 1e-12); placebo = block permutation of the monthly vector, shared across sleeves; zero target exits fully under the band | D3.1–D3.6 | **held** — tests/test_r3.py (14) + tests/test_band.py zero-target tests (2); each guard broken → its test FAILS, restored → PASSES (accounting zero-target exit, gate causality, faber read-back e+2, block placebo, judge path, coverage guard, correlation look-ahead). Review R3 MATERIAL 1 (the script's L6–L8 wiring had no test; a one-row-early g or decision passed): fixed after review — targets built in `regime.targets` (the script's only path) and `test_script_wiring_uses_no_future_returns` FAILS for g read one row early, the L6 decision one row early and the L7 decision one row early; passes clean; every reports/r3 statistic unchanged |
| E3.14 | perf: `make ladder` (R2 + R3) ≤ 5 min and peak RSS ≤ 1.5 GB (rss_peak); R3 per-rung evaluation (books, 4 references, LW + 2 dd_ratio_ci, crisis) ≤ 10 s | performance contract; D3.5 amendment 6 | **held** — `python scripts/rss_peak.py make ladder`: warm **955 MB**, 62.9 s; cold (caches cleared) **937 MB**, 110.9 s; R3 ablation 20 rows in 17 s (≈ 0.85 s per row, ≤ 3.4 s per rung's four references) |

**E3.3 / E3.4 / E3.7 failures logged before diagnosis (2026-10-29, first `make ladder` with R3).** Diagnosis (sign,
timing, units, alignment checked; no bug found; nothing changed): the trend layer's holdings match the signal-state
table seen before code (SPY out 39% of 1994 days, 77% of GFC days; TLT out 77% of Q4 2018 days,
reports/r3/crisis_exposure.csv). 1994 was a flat, choppy year for SPY: the trend rule sold dips and missed recoveries
(L7 −2.2% vs L6 +0.07%; L6 had already removed TLT). L7's CDaR is higher than matched L6's because trend whipsaw creates
drawdowns of its own (matched L7 − L6: euro_2011 −8.9 pp, china_2015 −7.5 pp, Q4 2018 −2.5 pp; L7's max DD is in
2015-02 → 2016-01, L6's in 2001-11 → 2002-07). The same trend effect, without the correlation layer (L7-on-L5 vs L5),
gives −0.145 ΔSharpe: the cost is the trend layer's, not an interaction. No spec or code change.

**R3 result (development 1990–2019, descriptive; owner O2.4: no walk, the R2 verdict stands — nothing promoted past
SPY).** Ablation at matched vol (ΔSharpe, LW 95%; CDaR-95 ratio, paired bootstrap 95%; Holm over 20 p-values: every
Holm p = 1.00):

| Layer | vs parent | vs 60/40 (L3) | vs v1 (L1) | vs SPY + T-bills line |
|---|---|---|---|---|
| L6 corr regime (vs L5) | −0.08 [−0.23, +0.07]; CDaR ×1.13 | +0.06 [−0.13, +0.24] | +0.24 [−0.07, +0.55] | +0.23 [−0.06, +0.52] |
| L7 trend (vs L6) | −0.17 [−0.42, +0.08]; CDaR ×1.14 | −0.12 [−0.44, +0.21] | +0.07 [−0.29, +0.43] | +0.02 [−0.35, +0.40] |
| L8 crash (vs L7) | −0.00 [−0.01, +0.00]; CDaR ×1.00 | −0.12 [−0.44, +0.21] | +0.07 [−0.30, +0.43] | +0.02 [−0.35, +0.40] |

Owner windows at matched risk (child − parent rescaled to the child's vol; reports/r3/crisis.csv):
- **1994 bonds:** L6 **+5.9 pp** vs L5 (TLT out on 100% of days; +0.1% vs −5.8%) — the one window where the correlation
  layer acts. Caveat (review R3 MINOR): the TLT proxy cannot be checked against TLT before 2002 (reports/r1/qa.md), so
  the size of this 1994 number rests on the GSW 25-year construction alone; L7 −2.5 pp vs L6 (SPY whipsaw); vs matched SPY L6 −0.9 pp, L7 −3.4 pp.
- **GFC 2007-10 → 2009-03:** L6 −1.2 pp vs L5 (gate off throughout: identical holdings, the gap is the matching
  scale); **L7 +11.8 pp** vs L6 (+6.0% vs −5.7%: SPY out 77% of days); vs matched 60/40 L7 +17.4 pp, vs SPY +22.7 pp.
- **Q4 2018:** L6 −0.6 pp vs L5 (gate off); **L7 −2.5 pp** vs L6 (TLT out 77% of days, SPY mostly in: the hedge was
  removed when it worked).
Gates vs placebos: no gate beats its 12-month-block placebo; placebos themselves average about −0.10 ΔSharpe (sending
a sleeve to cash in a 30-year bull market for both assets costs Sharpe whatever the timing), and the gates sit inside
that distribution (L6 59th, L7 36th, HMM 64th, jump 86th percentile). Crash rule: `judge` on = False; the brake was
active on 2.7% of days and never below 0.86. Zoo: no row differs from L5 by more than its interval. min-CDaR: vol layer
on EWMA-slow until the first zoo pick (1991 year-end) — warm-up extended into 1990–91 for this zoo row only (disclosed).
**Answer to the owner's question:** L6 does what it was built for (1994) and nothing else in the development sample;
L7 helps in equity bear markets (dot-com, GFC) and hurts in choppy or hedge-working windows (1994, 2011, 2015, Q4 2018),
for a net Sharpe loss; L8 does nothing measurable (the brake is nearly inert at its pre-registered thresholds on a book
whose worst drawdown is ~13%, so its `judge` failure says little about crash rules in general — review R3 MINOR).
**Not tested in R3 (escalated O3.1):** v1 spread and Bollinger overlays on L5, GBM risk-side row. None beats its parent; L6 sits between 60/40 and v1 / the line.

**Owner O3.1 (2026-10-29, after the R3 review): (a) with a condition.** The v1 spread overlay on L5, the v1 Bollinger
overlay on L5 and the GBM risk-side sizing row (purged CV, 50% haircut) move to R4. **R4's first step, before any
computation:** write their definitions into spec/prereg.yaml and record its sha256 here. Zoo rows: they cannot change
any verdict and are counted in DSR N. R3 is closed on that basis (tag r3-done, owner "tag it").

## R4 — robustness, costs, and the three O3.1 zoo rows (expectations committed before any R4 code or number)

**O3.1 condition met first:** the definitions of the v1 spread overlay on L5, the v1 Bollinger overlay on L5 and the
GBM risk-side sizing row (purged walk-forward CV, 50% log-space haircut), plus the raw-GBM descriptive row, are written
in `spec/prereg.yaml` `r4_zoo` (with the R4 evaluation in `r4_evaluation`) **before any R4 computation**.
Pre-registration hashes: `spec/prereg.yaml` sha256 **c7779261dbd968cb7246fb3af02fda8942b07985e20b01d2168fa62dea70634f**;
`spec/rules.yaml` sha256 **23ba0469c87ee8ac098a7f82167bf27df8db15bb7a4a78a55c042aa8a7157d36** (adds `r4`).
Decisions D4.1–D4.7 (advisor, reports/decisions.md; none escalated: D4.3 is not a re-pin or a licence question).
variants.csv: +4 zoo rows, +41 sensitivity books, tranche offsets now counted in DSR (D4.6), robustness legs and v1's
permitted-data grid registered as not new trials.
Scope (D4.4): "built rungs; none promoted (R2 walk seats L1, post-hoc chains seat L0, R3 not walked per O2.4)". Every
R4 number is descriptive and cannot change any verdict. Scored: development 1990-01-02 → 2019-12-31; 2020+ is R5.
Disclosed priors: every R2/R3 number (reports/r2, reports/r3), including the development Sharpe ratios L0 0.48, L1
0.51, L3 0.69, L4 0.82, L5 0.83, L6 0.75, L7 0.58, L8 0.58, the turnovers (L1 27.6×/yr, L5 0.43, L7 1.65) and the
R3 2×/3× cost rows for L5–L8. No R4 return, signal state or forecast has been computed. Predictions are the author's,
low-to-medium confidence.

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E4.1 | Spread overlay vs matched L5: ΔSharpe in [−0.10, +0.05], LW p > 0.05; each state (SPY→cash, TLT→cash) on 0.5%–5% of development days; traded turnover in [1, 10]×/yr (L5 0.43) | D4.1; author | **failed (turnover part)** — `make ladder` → reports/r4/zoo.csv: turnover **11.2×/yr** > 10. Held: ΔSharpe −0.067 [−0.141, +0.007], p 0.978; SPY→cash 2.0% / TLT→cash 2.7% of days (facts.json). Diagnosis: one-day exits, ≈ 0.9 one-way per event |
| E4.2 | Bollinger overlay vs matched L5: ΔSharpe in [−0.15, +0.05], p > 0.05; each state on 2%–15% of development days; turnover in [1, 10]×/yr | D4.1; author | **failed (turnover part)** — turnover **26.2×/yr** > 10. Held: ΔSharpe −0.037 [−0.159, +0.086], p 0.731; 9.5% / 9.1% of days |
| E4.3 | GBM row vs matched L5: ΔSharpe in [−0.05, +0.05]; raw GBM in [−0.10, +0.10]; \|ΔSharpe(blend)\| ≤ \|ΔSharpe(raw)\| | D4.2 | **held** — GBM 50% vs L5 −0.003 [−0.029, +0.023]; raw +0.008 [−0.039, +0.056]; \|−0.003\| ≤ \|+0.008\| (zoo.csv); 30 walk-forward fits, first prediction 1990-01-02, 22 last 2019 rows on σ_zoo (facts.json gbm) |
| E4.4 | code: every GBM split passes `cv.check_split` (purge 22) and a split whose training label crosses the refit date raises `LeakageError`; predictions bit-identical with 1 vs 2 workers; overlay and GBM targets at row t unchanged when returns after t are perturbed | D4.2, D4.3 | **held** — tests/test_r4.py (18): check_split on every split, leaky split raises LeakageError, 1 vs 2 workers bit-identical (GBM and v1 grid), overlay / GBM features / GBM predictions unchanged ≤ t under a post-t shock; 8 guards broken → FAIL, restored → PASS; review MINOR (spread look-ahead probe passed): probe days now include s and s − 1, the reviewer's shift(−1) now FAILS |
| E4.5 | Costs: at 3×, every layer's ΔSharpe vs its matched parent moves by ≤ 0.02 from 1× (L3–L8 turnover ≤ 1.7×/yr); L1's own Sharpe falls by ≥ 0.08 from 1× to 3× (27.6×/yr traded) | D4.4; R3 cost rows | **failed (L2 part)** — costs.csv: L2 vs L0 ΔSharpe **+0.053 → +0.015** at 3× (−0.038 > 0.02; L2 trades 6.3×/yr); every other layer moves ≤ 0.006. Held: L1's own Sharpe 0.512 → 0.416 (−0.096 ≥ 0.08) |
| E4.6 | +75 bp financing: books with gross ≤ 1 on every row (L0, L3–L8) have net identical bit for bit to 1×; L5-lev vs L5 ΔSharpe moves by ≤ 0.05; L1 and L2 (gross up to 2) lose ≤ 0.10 Sharpe | D4.4 | **failed (bit-for-bit part)** — facts.json: only L0 bit-identical; L3–L8 carry float-dust financing ≤ 7e-18/yr (gross 1 ± ulp), Sharpe equal to 10 digits. Held: L5-lev vs L5 0.052 → 0.050; L1 −0.016, L2 −0.016 own Sharpe at +75 bp |
| E4.7 | Leave-one-crisis-out: dropping bonds_1994 lowers L6 vs L5 ΔSharpe by ≥ 0.02 (its one helpful window); dropping GFC lowers L7 vs L6 ΔSharpe by ≥ 0.03; no layer's ΔSharpe changes sign in more than 2 of 6 drops | D4.4; R3 crisis.csv | **held** — loco.csv: dropping bonds_1994 lowers L6 vs L5 by **0.041**; dropping GFC lowers L7 vs L6 by **0.083**; at most 1 sign flip of 6 (L2) |
| E4.8 | Decades: L5 excess Sharpe > 0.4 in each of 1990s/2000s/2010s; L3 vs matched L0 positive in ≥ 2 of 3 decades; L7 vs matched L6 negative in ≥ 2 of 3 | D4.4; author | **failed (L5 2000s)** — decades.csv: L5 Sharpe 0.842 / **0.345** / 1.425. Held: L3 vs L0 +0.166 (2000s), +0.419 (2010s); L7 vs L6 −0.135 (1990s), −0.633 (2010s) |
| E4.9 | Rolling 5-year: L5 vs matched L4 ΔSharpe positive in 30%–70% of windows (ΔSharpe +0.01 overall); L7 vs matched L6 positive in ≤ 45% of windows | D4.4 | **held** — rolling.csv: L5 vs L4 positive in **51.1%** of 5-year windows; L7 vs L6 in **30.7%** |
| E4.10 | Maturity: L5 development Sharpe at 10/20/30y within ±0.15 of 25y (0.83); L3 Sharpe within ±0.20 of 0.69; L6 − L5 matched return in bonds_1994 ≥ +2 pp at 20y and 30y; every SVENY10/20/30 leg reported from the 1986 start (assert) | D4.5 | **held** — sensitivity.csv: L5 Sharpe 0.906 / 0.842 / 0.829 at 10/20/30y (25y 0.833); L3 0.671 / 0.690 / 0.696 (0.695); L6 − L5 matched 1994 +5.6 / +5.9 / +5.9 pp (25y +5.9); SVENY10/20/30 assert passed |
| E4.11 | Band / calendar: every variant's development Sharpe within ±0.05 of its registered rung; band 0 on L5 at least doubles L5's turnover; quarterly lowers L3/L4 turnover | D4.5; Jaconetti et al. 2010 | **failed (L7 quarterly)** — L7 quarterly Sharpe 0.447 vs 0.580 (**−0.133**); every other variant within ±0.04. Held: L5 band 0 turnover 2.12 vs 0.43×/yr; quarterly L3 0.038 < 0.044, L4 0.173 < 0.222 |
| E4.12 | DSR: N_eff (ρ* 0.5) in [5, 80] from n_raw ≥ 800; DSR ≥ 0.95 for L4, L5, L6; DSR < 0.95 for L0 and L1 (DSR tests Sharpe > the expected best null, not edge over SPY) | D4.6; author | **failed** — dsr.csv / facts.json: n_eff **3** (N used 4) from **787** series; **L1 DSR 0.959** (not < 0.95). Held: L4 / L5 / L6 DSR 1.000 / 1.000 / 0.999; L0 0.942. At the register's raw N 748: L0 0.727, L1 0.781, L7 0.874 (review MATERIAL 2: now on the site) |
| E4.13 | PBO, primary zoo pool, S = 16: in [0.25, 0.75] (near-copies of L5: selection is close to a coin flip); S = 8 and 12 within ±0.15 of S = 16 | D4.7 | **held** — pbo.csv: zoo pool S = 16 **0.609**; S = 8 0.571, S = 12 0.695; near-duplicate-dropped companion 0.605 |
| E4.14 | Power: every layer with measured ΔSharpe ≤ 0 prints ∞; for the positive ones (L3 vs L0, L4 vs L3, L5 vs L4) the years needed exceed 20 for L4 vs L3 and 100 for L5 vs L4 | D4.4 | **held** — power.csv: ∞ for L6, L7, L8; L4 vs L3 **87** years, L5 vs L4 **945** years (L3 vs L0 30, L5-lev vs L5 52, L2 vs L0 570) |
| E4.15 | Waterfall: the per-day identity holds ≤ 1e-10 for every rung and cost row; cost drag ≤ 0.05%/yr for L3–L8 at 1×; L1 cost drag ≥ 0.5%/yr; financing non-zero only for L1, L2, L5-lev | D4.4 | **failed (financing part)** — waterfall.csv: L3–L8 financing 1e-19 – 7e-18/yr (float dust, as E4.6). Held: per-day identity max residual 1.4e-17; L3–L8 cost drag ≤ 0.039%/yr; L1 0.77%/yr |
| E4.16 | code: after R4 code, every reports/r2 and reports/r3 statistic file is unchanged (except timing); spec/quantkit_pin.json unchanged byte for byte after the `ml` install; `make verify-pin` passes | D4.3 | **held** — after `make ladder` (R2 + R3 + R4): every reports/r2, reports/r3 file and R2/R3 figure byte-identical except facts.json timing (restored); spec/quantkit_pin.json sha256 08d6c455… unchanged after the `ml` install and `make omp`; `make verify-pin` OK |
| E4.17 | perf: `make ladder` (R2 + R3 + R4) warm ≤ 5 min and peak RSS ≤ 1.5 GB; R4 part warm ≤ 150 s; GBM fits (30 walk-forward fits) ≤ 30 s; v1 grid (648 books) ≤ 90 s with a process pool | performance contract | **held after the perf fix** — first runs (v1 grid in 4 / 2 loky workers) 2,264 / 1,775 MB summed (logged above); grid in-process: `python scripts/rss_peak.py make ladder` **145 s, 1,122 MB**; R4 part cold 102 s / 995 MB, warm 72 s; GBM ≈ 7 s; v1 grid 31 s |

**R4 first full run (2026-10-29, `scripts/r4.py`; logged before diagnosis).** Contradicting the expectations:
- **E4.1:** spread overlay turnover is **11.2×/yr**, above the [1, 10] band. The other parts hold: ΔSharpe −0.067, p 0.978,
  SPY→cash on 2.0% of days and TLT→cash on 2.7%.
- **E4.2:** Bollinger overlay turnover is **26.2×/yr**, above [1, 10]. The other parts hold: ΔSharpe −0.037, p 0.731,
  9.5% and 9.1% of days.
- **E4.5:** L2 vs L0 ΔSharpe moves **−0.038** from 1× to 3×, against a band of ≤ 0.02. L2 trades 6.3×/yr; the other
  layers move ≤ 0.006.
- **E4.8:** L5's excess Sharpe in the 2000s is **0.345**, against a band of > 0.4.
- **E4.11:** **L7 quarterly** Sharpe is 0.447 against 0.580 registered (**−0.133**), outside ±0.05. Every other band
  and calendar variant is within ±0.04.
- **E4.12:** n_eff is **3** (k_cut 1 at ρ* 0.5, k_gap 3), so N used = **4**, below the [5, 80] band. The pool has 787
  series, below the predicted ≥ 800. **L1's DSR is 0.959**, not < 0.95. DSR ≥ 0.95 holds for L4–L6, and L0 is 0.942.
- **E4.17 (RSS):** v1's grid in 4 loky workers peaks at **2,264 MB summed over 8 processes**, above the 1.5 GB budget.
  Wall time is 85 s, within budget.

Two defects in my own reporting were found on the same run:
- `waterfall.vol_drag_pa` = mean·252 − CAGR goes negative for low-vol books (L4/L5: −0.1 pp). It mixes compounding of
  the mean with vol drag.
- The PBO secondary pool lists L5 twice, and the dedupe log prints "L5 == L5".

L4b and max_div differ by ~1e-15. The byte-exact dedupe registered in D4.7 therefore keeps both in the primary PBO
pool, although the advisor's premise was that they are identical.

**After review R4 (logged before any fix):**
- **E4.6** missed its bit-for-bit part. The +75 bp books for L3–L8 are **not** bit-identical to 1×
  (`facts.json *_f75_net_equals_1x` false; only L0 is identical).
  - Cause: their held weights sum to 1 ± 1 ulp, so `accrual` charges float-dust financing of 1e-19–1e-18 per year,
    and the +75 bp leg scales it.
  - Every Sharpe is equal to 10 digits.
- **E4.15** missed its "financing only L1, L2, L5-lev" part, for the same reason: L3–L8 show 1e-19–7e-18 per year.
- Not a bug in the economics. The accounting is unchanged (R2/R3 books depend on it bit for bit).
- The site text that claimed "bit for bit" was hard-coded and wrong (review MATERIAL 1). It is now built from the facts.

**R4 closed (2026-10-29):** 9 held, 8 failed (E4.1, E4.2, E4.5, E4.6, E4.8, E4.11, E4.12, E4.15), 0 not tested. Every
failure was diagnosed with no code bug in the economics (the failures are author bands that ignored a one-day round trip,
L2's daily turnover, the 2000s, quarterly trend lag, one-cluster DSR pools and float-dust financing). Reporting fixes,
each labelled: the vol-drag definition (D4.4 post-hoc amendment), PBO/DSR column labels, the site text drawn from facts,
the cache key now including rules.yaml (review R4). Every reported statistic is unchanged by them (diff: labels and
timing only). Answer for the README: in development 1990–2019, no R4 zoo row beats L5 (−0.067, −0.037, −0.003, +0.008);
costs and +75 bp change no layer's sign except L1 vs L0 (+0.03 → −0.06 at 3×); the correlation layer's only support is
1994 (dropping it lowers L6 vs L5 by 0.04), trend's is the GFC and dot-com; 10-year bonds would have helped every
bond-holding rung (+0.07 to +0.10 Sharpe; a GSW proxy not QA'd vs an ETF); a 30-year sample is too short to confirm
any layer's measured edge (L4 vs L3 needs 87 years).

## R5 — freeze, test, write-up (expectations committed before any R5 code or v2 test-window number)

**Owner instruction (1) met first:** the post-hoc 10-year sensitivity row (L5–L7 on a GSW 10-year leg instead of
25-year, test window, labelled, cannot change any verdict, counted in DSR N; the 25-year books stay official) is written
in `spec/prereg.yaml` `r5_test.sensitivity_10y` and registered in `reports/variants.csv` (`sensitivity_10y_test`,
n_configs 3, counted yes) **before the freeze**, together with the whole test-run definition (`r5_test`, D5.1–D5.7).
Pre-registration hashes: `spec/prereg.yaml` sha256 **9fc98fc81344a49a6a4230f4d2c88eb7726f211b5539525d214e11f4d6e3f10d**;
`spec/rules.yaml` sha256 **a3daa5837ae85b5e2c1f07f47b83bcefe5c2b9911a2178bf7953a5844f580c1b** (adds `r5`).
`make data` after the rules change rebuilt data/panel.parquet byte-identical (sha256 10aeb147…f771e).
Decisions D5.1–D5.7: advisor, none escalated (reports/decisions.md).

**Scope:** test window 2020-01-02 → 2026-09-30 (1,695 sessions; KF fetched 2026-10-29), labelled "seen by owner in v1,
disclosed". The run cannot change any development verdict (R2 walk seats L1, post-hoc chains seat L0, R3/R4
descriptive).

**Disclosed priors:**
- v1's own test 2020–2025: S0 CAGR 16.3%, Sharpe 1.00.
- L1 (= S7) excess Sharpe 0.78 on 2020–2025 (R1).
- Data QA 2005–2025.
- The author's general knowledge of public 2020–2025 market history (2020 COVID crash and the bond rally; 2022 joint
  stock–bond loss; higher bill rates from 2023).

No v2 rung has been computed on any 2020+ row. Predictions are the author's, low-to-medium confidence. "Matched" =
D5.2 (test-window ex post, one scalar).

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E5.1 | code (D5.1): every extended book (L0–L8, L5-lev, L2-u at 1×) equals data/r2, data/r3 bit for bit on rows ≤ 2019-12-31; vol-zoo picks 1989..2018 equal reports/r2/volzoo.json; a pick exists for every year 2019..2025 | D5.1 | open |
| E5.2 | code (D5.5): `python -m rspy freeze verify` OK after the lock commit; the runner refuses (non-zero exit, nothing written) without `RSPY_TEST_RUN=run-once`, with reports/r5/test_run.json present, with a changed or uncommitted locked file, with a changed panel; the synthetic dry run completes, writes nothing under reports/r5, and refuses `RSPY_TEST_RUN` or the repo's data/ | D5.5 | open |
| E5.3 | code (D5.2): the matched reference's test-window excess vol equals the child's ≤ 1e-10 for every family row; every scored series has exactly 1,695 rows | D5.2 | open |
| E5.4 | L0 (SPY proxy), test: CAGR in [11%, 17%]; excess Sharpe in [0.45, 0.95]; max DD in [−37%, −28%] | author | open |
| E5.5 | Bonds hurt on the test: L3 vs matched L0 ΔSharpe in [−0.45, +0.05] (development +0.215, sign likely disagrees); L3 Sharpe < L0 Sharpe | author | open |
| E5.6 | L5 vs its line ΔSharpe in [−0.70, +0.05]; L5 test excess Sharpe in [−0.10, 0.60] | author | open |
| E5.7 | Correlation layer: L6 − matched L5 cumulative return in infl_2022 ≥ +3 pp; L6 vs L5 test ΔSharpe in [−0.10, +0.50] | author; thesis | open |
| E5.8 | Trend layer: L7 − matched L6 in infl_2022 ≥ 0 pp; in covid ≤ +1 pp (10-month SMA exits late); L7 vs L6 test ΔSharpe in [−0.40, +0.40] | author | open |
| E5.9 | Crash rule: \|L8 vs L7 ΔSharpe\| ≤ 0.10 | author (development −0.002) | open |
| E5.10 | Headline (D5.3): all three questions — beat L2, beat 60/40, beat the line — answer "not shown in the test window" (no row with point ≥ +0.05 and Holm p < 0.05) | D5.3; R4 power | open |
| E5.11 | Crisis panels: in covid, L5 − its line ≥ +2 pp (the bond leg rallied); in infl_2022, L5 − its line ≤ −2 pp | author | open |
| E5.12 | L1 (v1 corrected) test excess Sharpe in [0.45, 1.05] (R1's 2020–2025 0.78, seen) | R1 | open |
| E5.13 | 10-year row (post-hoc): L5@10y − L5@25y test Sharpe in [0, +0.40]; L5@10y loses less than L5@25y in infl_2022 | owner lead; author | open |
| E5.14 | DSR (D5.4): the raw-N companion's V = 1/(T−1) = 5.90e-4 (> V_dev 5.38e-5); headline test DSR (N 5) < 0.95 for every official rung | D5.4; author | open |
| E5.15 | Costs on the test: at 3×, every parent-row ΔSharpe moves ≤ 0.03 from 1× except L2 vs L0 (≤ 0.08); at +75 bp, L3–L8 excess Sharpe equal to 1× within 1e-8 | R4 E4.5 / E4.6 | open |
| E5.16 | Sign agreement (descriptive): 30%–80% of the 24 family rows have the same ΔSharpe sign as in development | author | open |
| E5.17 | perf: dry run ≤ 120 s; the test run ≤ 120 s cold (three new vol-zoo series) and peak RSS ≤ 1.5 GB; `make test` ≤ 60 s | performance contract | open |

**Forward (optional, not built in R5; D5.7):** the prereg `windows.forward` entry stands as "after R5, optional
monthly log". It would start at 2026-10, available about 2026-12, behind the R5 freeze lock.

**Before the freeze (after the pre-run review R5; no test-window number exists):**
- `spec/prereg.yaml` amended with D5.8 (`r5_test.placebo_descriptive`; the exclusion list narrowed) and D5.9 /
  review MINOR (`r5_test.freeze.replay_exempt`, `locked_inputs`). New sha256 **1d9c7c4f7041dcb58fbeb735ce520b685feafa3e9ff349e340996fb8c03530a2**; rules.yaml unchanged
  (a3daa583…). variants.csv adds `test_placebo_regime` (counted no).
- **E5.3 restated before any result** (review R5 MINOR: the financing above 1× uses a varying rate, so ex-post matching
  is exact only without financing). The band is ≤ 1e-10 for rows with k ≤ 1 and ≤ 1e-6 (annualised vol) for rows with
  k > 1. The synthetic dry run, which now has bills and financing after review M1, gives 9.0e-8 on its one k > 1 row.
- New expectation, added before any result:

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E5.18 | Test placebo (D5.8, descriptive): L6's infl_2022 matched gain vs L5 sits at percentile ≥ 50 of its 100 shuffles (the gate is in cash for much of 2022); L7's ΔSharpe vs L6 percentile in [10, 90] | D5.8; author | open |
