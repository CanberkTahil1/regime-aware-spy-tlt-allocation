# regime-aware-spy-tlt-allocation: charter (v2 rebuild)

## One-line thesis
A **regime-aware SPY/TLT/cash allocation** that holds stocks and long Treasuries together as a risk-based core, cuts
bonds to cash when the stock-bond hedge breaks (positive correlation, as in 2022), cuts either asset to cash in its own
downtrend, and targets a fixed volatility — aiming for **SPY-like returns with much lower volatility and drawdown**,
judged against SPY + T-bills mixed to the same volatility and against each simpler layer it adds.

## Why v2 (owner, 2026-10-28; audit findings on v1, re-run on a scratch copy)
- v1 was mostly vol-targeted SPY: TLT was held on ~3% of test days; average SPY position 1.09.
- Plain vol-targeted SPY beat v1 in train 2005–14 (CAGR 9.8% vs 7.8%; t −2.1) and validation 2015–19 (13.0% vs 11.5%);
  v1's test edge (+1.7%/yr, t ≈ 1.3) is not significant.
- Accounting gaps: leverage up to 2× with no financing and 0% on cash (≈ −0.6 pp/yr at approximate 2020–25 bill rates);
  same-close execution (trading one day later: test CAGR 16.3% → 13.9%, Sharpe 1.00 → 0.87); reported turnover 18.7×
  excludes vol-scaling trades (traded ≈ 26.6×); Sharpe without the risk-free rate; nonstandard Sortino; 648 configs
  searched without a multiple-testing count; no tests.
- Exploratory check on 2005–19 only (not evidence, free leverage still on): a vol-targeted inverse-vol SPY/TLT mix,
  monthly, had train Sharpe 1.14 vs v1 0.46, max DD −18% vs −39%, turnover 0.7× vs 20×.
- Data: v1 commits Yahoo prices and Cboe VIX (`data/prices.csv`) to a PUBLIC GitHub repo; both providers' terms bar
  storage/redistribution (see the owner's research notes). v2 switches to storage-permitted sources (R0/R1).
v1 stays in git history and is reproduced once (R1) as the "legacy" baseline row, labelled.

## Windows (owner: prior viewing of 2020–25 does not matter; still labelled)
| Window | Dates | Role |
|---|---|---|
| Warm-up | 1986-01 → 1989-12 | Estimation only (vol, correlation, trend lookbacks); never scored |
| Development | 1990-01 → 2019-12 | Expanding walk-forward; every ladder decision |
| Test | 2020-01 → last month Ken French has published at R5 | Frozen rules run once; labelled "seen by owner in v1, disclosed" |
| Forward | after R5 | Optional monthly log |
Long-history proxies make 1990–2019 possible (1994 bonds, 2000–02, 2008, 2011, 2015–16, 2018) instead of v1's
2005–2019. Pre-defined crisis windows: 1994-02→1994-11 (bonds), 2000-03→2002-10, 2007-10→2009-03, 2011-04→2011-10,
2015-05→2016-02, 2018-09→2018-12, 2020-02→2020-03, 2022-01→2022-10.

## Assets and data (D-items at R0/R1; free and storage-permitted only, LICENSES.md quotes each clause)
- **SPY sleeve:** Ken French daily "Hi 20" (large-cap, value-weighted) total return — the owner's standing disclosed
  relaxation, gitignored, never redistributed. Labelled "SPY proxy".
- **TLT sleeve:** constructed 25-year constant-maturity Treasury total return from the Fed's GSW curve (public domain),
  via `quantkit.bonds` (v0.19.2; bonds unchanged since v0.19.1). The owner's naive-vs-optimal P1 validated this construction vs TLT (corr 0.990,
  TE 2.06%/yr, construction exact to ≤ 0.04 pp): label "TLT proxy, QA vs TLT corr 0.99 / TE 2.06%/yr" everywhere.
- **Cash:** Fed H.15 bills (public domain). Earned on uninvested capital; financing = bill rate + spread on borrowed
  notional.
- **Removed:** Yahoo (prices) and Cboe VIX. Realised vol and vol-model forecasts replace VIX.
- Optional later (owner D): gold/commodities from the World Bank Pink Sheet (monthly, CC BY 4.0, labelled) as a 4th
  sleeve — off by default; the repo's identity is SPY/TLT/cash.

## The ladder (pre-registered order; each rung adds ONE layer; parameters fixed from the literature, not searched)
- **L0** SPY · **L0-line** SPY + T-bills at the rung's volatility (the benchmark every rung is judged against)
- **L1** legacy v1 (frozen v1 code + selected params, run on the new data and new accounting) — the baseline to beat
- **L2** vol-targeted SPY (v1's real driver, isolated)
- **L3** static 60/40 SPY/TLT (monthly, 5 pp band)
- **L4** inverse-vol SPY/TLT (63-day vol, monthly, band) · **L4b** ERC on the 2×2 covariance (zoo)
- **L5** L4 + portfolio vol target (10% annual, ex ante, cap 1.0× gross unlevered; L5-lev cap 1.5× with financing)
- **L6** L5 + **stock-bond correlation regime**: when the trailing 63/126-day SPY–TLT correlation > 0 (pre-registered
  threshold 0; sensitivity ±0.2 descriptive), TLT's weight moves to cash
- **L7** L6 + **per-asset trend**: each sleeve held only above its 10-month SMA (Faber, `quantkit.signals.trend.faber`),
  else that sleeve to cash
- **L8** L7 + **crash rule**: de-risk to cash on a drawdown/vol-spike trigger (no shorts ever), judged by
  `quantkit.sizing.judge` against vol targeting alone and its block-shuffled placebo
- **Zoo (exploratory, every row registered, never promoted unless re-registered):** HMM / jump-model regime gate,
  vol-model zoo (EWMA fast/slow, GJR-GARCH-t, EGARCH-t, HAR on daily returns) for the vol target, min-CDaR / max-div
  objectives, one GBM risk-side sizing row, v1's spread and Bollinger signals as overlays on L5.
Promotion between rungs: `quantkit.ladder` four-part rule (min effect ΔSharpe ≥ +0.05 or CDaR ≥ 15% lower at matched
vol; paired one-sided `sharpe_diff_lw`; no loss at 2× costs / +75 bp financing / leave-one-crisis-out; inside the 90%
MCS on vol-matched returns). Ties go to the simpler rung. Every rung also gets "beyond 60/40" (ΔSharpe vs vol-matched
L3 ≥ +0.05), descriptive.

## Accounting (binding, R1)
Signals at month-end close t (monthly rungs) or close t (daily vol target), trades at close t+1; costs 2 bp/side
Treasuries, 3 bp/side SPY (current-ETF row; 2× and 3× stress), charged on TRUE traded turnover including vol-scaling
trades; cash earns the H.15 bill rate; borrowed notional pays bill + 25 bp (+75 bp stress); no shorts; Sharpe and
Sortino on excess returns (standard downside deviation vs 0); turnover reported as traded turnover.

## Package and layout
- Python 3.12, uv lockfile, ruff, pytest (-n auto), hypothesis. Package `rspy` under `src/rspy/` (data, accounting,
  rungs, evaluate, report); legacy v1 modules move to `legacy/` untouched (only imports adjusted) for L1.
- `spec/rules.yaml` single parameter source; `spec/prereg.yaml` (ladder order, windows, crisis list, promotion rule,
  costs) hashed into `reports/ledger.md` before any rung result. `reports/` (ledger, decisions, variants.csv, perf.md,
  research/Rn.md, reviews/Rn.md), `learn/` (Rn.md, decisions.md, INTERVIEW.md), `LICENSES.md`, `COPIED.md`.
- **quantkit** pinned non-editable at **v0.19.2** (`quantkit @ git+file:///Users/a90537/github/quantkit@v0.19.2`) with
  the loaded-module hash check: bench (vol-matched line, financing), bonds (GSW), signals.trend (faber), trade (bands,
  tranche/timing luck), sizing (vol target, judge), state (HMM, jump model), vol (model zoo), stats (sharpe_diff_lw, MCS,
  DSR, PBO, drawdown, power), ladder, stress, results + viz. Never re-implement what quantkit provides.

## Performance contract (owner rule: fast and lean in time AND space, never at the cost of correctness)
1. Budgets before code: every step gets a time and peak-memory budget in `reports/perf.md` and a one-line complexity
   note. Targets: data build ≤ 30 s; one rung full evaluation (all tranche offsets × 3 cost rows × 1,000 bootstrap
   paths) ≤ 10 s; the whole ladder + zoo ≤ 5 min; peak RSS ≤ 1.5 GB.
2. Right algorithm first: vectorised NumPy over pandas row loops; `scipy.signal.lfilter` for EWMAs; O(T) rolling
   statistics (cumulative-sum or online updates, never O(T·w) recomputation); numba for path-dependent loops
   (drawdowns, bands, bootstrap); monthly decisions computed on the monthly grid and broadcast, not recomputed daily;
   process pools for the rung × offset × cost × bootstrap grid; shared inputs (returns, vol, correlation, trend) built
   once and cached on disk as Parquet keyed by input + code + spec hashes.
3. Space: float64 for P&L and statistics, float32 only for large intermediates with an equivalence test; columnar
   Parquet; no full-history copies per candidate (views/slices).
4. Correctness gate: every fast path has a plain reference in `tests/reference/` and an equivalence test (exact for
   ints/bools, ≤ 1e-10 float64); 1 vs N workers bit-identical; fixed seeds; v1 reproduced to ≤ 1e-12 on its own data
   before any change (R1).

## Charts every phase (owner rule)
Each phase with results ends with `make report-site`: `reports/site/index.html` via `quantkit.results` + `quantkit.viz`
AND every chart as its own PNG/SVG in `reports/figures/Rn/` (descriptive names). Required set: growth of $1 with
drawdown underneath (rungs vs SPY vs the line), **exposure over time** (SPY / TLT / cash weights stacked), correlation
regime shading, crisis small multiples, rolling 5-year excess Sharpe, the ladder chart with intervals, return-vs-CDaR
scatter with the line, cost waterfall, ablation bar chart (what each layer added). Charts only draw numbers already in
the ledger/reports.

## How to work
Priority: correctness → owner decisions → speed and memory → brevity. Decisions go to the `decision-advisor` agent
(escalate only: deletes, pushes, history rewrites, tags, licence questions, charter changes, changing a pre-registered
number after results, low confidence, advisor vs reviewer disagreement); each logged in `reports/decisions.md` before
acting and in plain language in `learn/decisions.md`. One `quant-reviewer` round per phase. Expectations in the ledger
before code. Never weaken a test to pass. Stop before tagging; tag `rn-done` only on the owner's "tag it". zsh commands
for the owner carry no `#` comments. Secrets only from Keychain/env. Siblings (quantkit, naive-vs-optimal,
enhanced-60-40, …) are read-only: copy with provenance in COPIED.md, never import from their working trees. No
outreach to any vendor or person. **The repo has a public GitHub remote: never push, force-push or rewrite history —
those are owner-only actions.** Do not mention claude.ai connectors in the repo.

## Definition of done
README leads with the answer: did any layer beat (a) plain vol-targeted SPY, (b) 60/40, (c) SPY + T-bills at matched
risk — in development and in 2020–latest, with the 2022 crisis shown; the ablation table and chart; v1 vs v2 side by
side with the accounting corrections itemised; costs/financing sensitivities; DSR with the effective number of trials;
`make all` reproduces every figure from raw permitted data; the data-licence section explains the switch from Yahoo/VIX.
