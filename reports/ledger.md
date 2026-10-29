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
