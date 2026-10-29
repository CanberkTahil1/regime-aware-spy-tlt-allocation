# R1 data QA (D1.6)

Monthly, 2005-01 → 2025-12, each series compounded on its own sessions; diff = proxy − ETF; TE = std(diff)·√12; the scored row is 2005–2025, the other rows are descriptive (2020+ = test, seen by owner in v1). Results: `qa.csv`; the eight largest |monthly diff| per pair with dates: `qa_worst_months.csv`.

**Limits.** The ETF comparison starts in 2005 (v1's cached file; TLT itself launched in 2002), so the 25-year proxy **cannot be checked against TLT in 1994 or 2000–02**, crisis windows the development sample relies on; there it rests on the construction check (quantkit = the validated reference, max diff 0.0 on the real curve, E1.10). The proxies carry no fund expenses, so a small positive mean diff is expected (SPY 0.09%/yr, TLT 0.15%/yr expense ratios). The local Yahoo file is a comparison only: never committed, never used by a rung.
