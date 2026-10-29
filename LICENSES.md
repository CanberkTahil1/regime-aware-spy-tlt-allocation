# Data licences and terms (re-read 2026-10-28, R0)

Every source is quoted (clause, URL, date read) **before first use**. Every quote below marked **[raw]** was re-read on
2026-10-28 from the page source (curl, then tags stripped), not through a summariser; the wording was first collected in
naive-vs-optimal's `LICENSES.md` @ b5f6278 (read 2026-10-27, COPIED.md) and every clause was confirmed verbatim on the
live page today. Paraphrase is in [brackets]. Standing rules: free data only; storage permitted (or public domain); no
outreach; licensed or unclear-terms data never enters git (`data/` is gitignored; the pre-commit hook refuses it).
**This repository has a public GitHub remote**, so "never redistributed" means: never committed.

## Permitted sources

### Federal Reserve Board: GSW nominal curve (TLT proxy) and H.15 (cash) — public domain
- **Terms [raw]** (https://www.federalreserve.gov/disclaimer.htm, read 2026-10-28, page "Last Update: August 02, 2024"):
  "Unless otherwise indicated, information on Board's website is in the public domain and may be copied and distributed
  without permission. Please cite to the Board as the source of the information." Third-party material: "permission to
  copy and distribute such photo, graphic, or material must be obtained from the non-Board source."
- **GSW nominal [raw]** (https://www.federalreserve.gov/data/nominal-yield-curve.htm, read 2026-10-28, page "Last Update:
  November 05, 2019"): "this model is a staff research product and not an official statistical release. Accordingly, it
  is subject to delay, revision, or methodological changes without advance notice." "We generally try to post the
  updated series once per week". → [pin vintages: hash every download (R1).]
- **H.15 [raw]** (https://www.federalreserve.gov/releases/h15/, read 2026-10-28, "Release date: October 28, 2026"):
  Treasury bill footnotes "Annualized using a 360-day year or bank interest." and "On a discount basis." → [convert
  bills from the discount basis before use (R1).]
- **Verdict:** permitted (public domain); cite the Board. Derived files may be stored; raw files stay in `data/` anyway.

### Ken French Data Library: daily "Hi 20" (SPY proxy) — THE ONE DISCLOSED RELAXATION (owner standing rule)
- **Notice [raw]** (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html, page source read
  2026-10-28, HTML comment in the page header): "All images and code are property of Ken French. Use in part or whole is
  illegal -- except by permission of Ken French or Dimensional Fund Advisors". Page footer: "Copyright Eugene F. Fama and
  Kenneth R. French". No data licence or storage clause is stated.
- **Stance (owner):** unclear terms; used as the SPY proxy for personal research only, **gitignored, never committed or
  redistributed**, labelled "SPY proxy" everywhere. Same stance as naive-vs-optimal, resid-book and enhanced-60-40.
- KF's own risk-free series is not used; cash comes from H.15.

## Excluded sources (v1 used both; v2 removes them)

| Source | URL read [raw] 2026-10-28 | Clause | Page date | Verdict |
|---|---|---|---|---|
| Yahoo (v1 prices via `yfinance`) | https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html | "access or collect data, or attempt to access or collect data, from our Services using any automated means, devices, programs, algorithms or methodologies, including but not limited to robots, spiders, scrapers, data mining tools, or data gathering or extraction tools, for any purpose without our express, prior permission" [listed among prohibited uses] | Last updated: 4 August 2026 | **excluded** |
| Cboe (v1 `^VIX`) | https://www.cboe.com/terms | "You may view, print and download one copy of the Materials for your personal non-commercial use … You may not otherwise copy, reproduce, alter, store either in hard copy or in an electronic retrieval system, license, transmit, display, broadcast, create a derivative work …, publish, rent, sublicense, distribute" | Last Updated: November 16, 2022 | **excluded** |

**Why v2 switched.** v1 downloaded SPY/TLT prices from Yahoo with an automated client and `^VIX` (Cboe data, served by
Yahoo), then committed both in `data/prices.csv` to a public GitHub repository. Yahoo's terms bar automated collection;
Cboe's bar storing and distributing its materials. v2 replaces them with storage-permitted or disclosed sources: Ken
French Hi 20 (SPY proxy, gitignored), a GSW-constructed 25-year Treasury (TLT proxy, public domain), H.15 bills (public
domain), and realised vol / vol-model forecasts instead of VIX.

**v1's committed `data/prices.csv`.** Untracked on 2026-10-28 by owner decision O0.1(a) (`reports/decisions.md`); it
remains in git history (commits 7d75046, 5ccc12c) and on the public remote until the owner rewrites history before the
next push. The session never pushes or rewrites history. The R0 legacy characterization tests read the local copy only, to reproduce v1 exactly; no
v2 result uses it.

Gaps: the Ken French page has no data licence (hence the disclosed relaxation). Re-read every permitted source's terms
before R5 (test run) and record the date here.

## Software (non-data), R4 D4.3

quantkit's `ml` extra, installed at the same pinned tag v0.19.2 for the GBM zoo row (`quantkit.ml.fit_cv` +
`lightgbm`). Versions and licences are read from the installed package METADATA (uv.lock), 2026-10-29: lightgbm 4.7.0
(MIT), scikit-learn 1.9.1 (BSD-3-Clause), xgboost 3.4.1 (Apache-2.0), catboost 1.2.10 (Apache-2.0), optuna 5.0.0
(MIT), shap 0.54.1 (MIT). These are code licences; nothing is vendored or redistributed beyond lockfile entries, and
none of them touches any data source's terms.

System prerequisite (R4 D4.8, not in uv.lock): Homebrew `libomp` (LLVM OpenMP runtime, Apache-2.0 WITH LLVM-exception),
23.1.4 on 2026-10-29. LightGBM's wheel links `@rpath/libomp.dylib`, which resolves to it. `make omp` (quantkit's
documented `python -m quantkit.omp --fix`) replaces scikit-learn's vendored libomp inside `.venv` with a symlink to the
same runtime; the original is kept as `libomp.dylib.bundled` and `quantkit.omp.restore()` undoes it. Nothing outside
`.venv` changes. `make doctor` fails if the runtime is missing.
