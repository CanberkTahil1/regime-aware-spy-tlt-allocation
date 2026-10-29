"""make r6-data (R6, owner O6.2): download CPI-U NSA (BLS CUUR0000SA0) from the BLS public API into data/r6/raw/bls/
(gitignored) with a manifest line per file (sha256). Never part of `make all` (like `make fetch`, D6.5)."""

import time

from r6lib import cpi

t0 = time.perf_counter()
for line in cpi.fetch():
    print(f"fetched {line['path']}: {line['bytes']:,} bytes sha256 {line['sha256'][:12]}")
probs = cpi.verify()
if probs:
    raise SystemExit("\n".join(probs))
s = cpi.read()
print(f"CPI {s.index[0]} .. {s.index[-1]}: {s.notna().sum()} published months, missing {[str(m) for m in s.index[s.isna()]]}")
print(f"make r6-data: {time.perf_counter() - t0:.1f} s")
