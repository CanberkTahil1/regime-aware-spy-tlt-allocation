# Data licences and terms (read 2026-10-28, R0; re-read 2026-10-29 after R5)

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

### US Bureau of Labor Statistics: CPI-U NSA, series CUUR0000SA0 (R6c inflation gate only) — public domain (R6, owner O6.2)
- **Terms read 2026-10-29:** https://www.bls.gov/opub/copyright-information.htm (no page date). It says: "everything
  that we publish, both in hard copy and electronically, is in the public domain"; "You are free to use our public
  domain material without specific permission"; "we do ask that you cite the Bureau of Labor Statistics as the
  source". Source: U.S. Bureau of Labor Statistics, Consumer Price Index for All Urban Consumers (CPI-U), U.S. city
  average, all items, not seasonally adjusted (CUUR0000SA0).
- **Access:** the BLS public API v1 (`make r6-data`). The flat files at download.bls.gov return 403 to scripts. The
  raw JSON is kept in gitignored data/r6/raw with a sha256 manifest.
- **Why not FRED (owner O6.2):** FRED's terms bar storing or caching FRED content without consent. This repo takes
  each series from its source agency, like naive-vs-optimal.
- **Release timing** (read 2026-10-29 from https://www.bls.gov/bls/news-release/cpi.htm, 1994 → 2026): every CPI
  release fell inside the month after its reference month. Before 1994 this is assumed, not checked
  (spec/prereg_r6.yaml lag_check).
- **Gold (World Bank Pink Sheet, CC BY 4.0) is not used:** R6g was skipped (O6.2).

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

**v1's committed `data/prices.csv`.** Untracked on 2026-10-28 by owner decision O0.1(a) (`reports/decisions.md`).
On 2026-10-29 the owner removed it from all history with `git filter-repo` (with the tracked .DS_Store files and the R1
curve figures); commit shas changed then (old → new map in `reports/ledger.md`). The public remote keeps the old history
until the owner pushes the rewritten one. The session never pushes or rewrites history. The R0 legacy characterization tests read the local copy only, to reproduce v1 exactly; no
v2 result uses it.

Gaps: the Ken French page has no data licence (hence the disclosed relaxation). The R0 to-do "re-read every permitted
source's terms before R5 (test run)" is closed below — **late**: the re-read happened on 2026-10-29 after the R5 test run
(run 16:02–16:03 UTC; re-read 16:27 UTC), so the test run relied on the 2026-10-28 reading. No clause had changed.

## Re-read 2026-10-29 (after the R5 test run)

Each page was fetched on 2026-10-29 at 16:27 UTC as raw HTML (curl, HTTP 200). Tags were stripped, HTML comments were
kept, and each R0 clause above was searched verbatim (whitespace and typographic quotes normalised). Pages were also
scanned for licence, terms, permission, copyright and redistribution wording added since R0. The raw HTML is not
committed. Its SHA-256 is recorded for the record: the pages carry dynamic markup, so a byte-level diff against R0 was
not possible (R0 recorded no page hashes).

| Source | URL | Clauses above found verbatim | Page date (2026-10-28 → 2026-10-29) | Raw-page SHA-256 (2026-10-29) | Change affecting storage |
|---|---|---|---|---|---|
| Fed Board disclaimer (public domain) | https://www.federalreserve.gov/disclaimer.htm | 3 of 3 (public domain, "copied and distributed without permission", cite the Board; third-party material) | Last Update: August 02, 2024 → same | bf20ccfed6d017c8d27f828e2875ba84626f1f18c3b33f1896bf39ef15e63a38 | none |
| GSW nominal curve | https://www.federalreserve.gov/data/nominal-yield-curve.htm | 3 of 3 (staff research product; revision without notice; weekly updates) | Last Update: November 05, 2019 → same | 3e9ac5dae7eea017c11234aa5289ab3cb2c431eab662b1949af12399711c2111 | none |
| H.15 | https://www.federalreserve.gov/releases/h15/ | 2 of 2 (360-day year; discount basis) | Release date: October 28, 2026 → same | 562b19bd19e26f5d5347ea2313e31986e35f5c2adfdc2ab7b0e8e9c908c25f33 | none |
| Ken French Data Library | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html | 3 of 3 ("All images and code are property of Ken French. Use in part or whole is illegal -- except by permission of Ken French or Dimensional Fund Advisors"; "Copyright Eugene F. Fama and Kenneth R. French") | no page date → none | dd48316327898aea2e3ad3dd070b34c3325ce3b25ced7f719245efd5ad36146a | none: still no data licence or storage clause (disclosed relaxation unchanged: gitignored, never committed) |
| Yahoo (excluded) | https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html | 1 of 1 (no automated collection without express prior permission) | Last updated: 4 August 2026 → same | 4bcdd5402dcb56638165e1566de0c6a980b31a42eb3ab7ff092e1f9dacb2a257 | still excluded |
| Cboe (excluded) | https://www.cboe.com/terms | 3 of 3 (one copy for personal non-commercial use; no storing, distributing, …) | Last Updated: November 16, 2022 → same | ed7dff501562d66eee8d5b557975577e2b1e5b579f5d51f63a92bb5ad290742c | still excluded |

**Verdict (2026-10-29):** the terms are the same as at R0. The Fed sources are public domain (cite the Board), the Ken
French data stay a disclosed relaxation (local only), and Yahoo and Cboe stay excluded. Nothing in the repository or
its data handling needs to change.

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
