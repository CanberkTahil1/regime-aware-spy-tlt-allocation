"""make data: build data/panel.parquet from data/raw (content-hashed; a no-op when current). `--fetch` downloads the raw
files first (KF, GSW, H.15; manifest with sha256)."""

import json
import sys
import time

from rspy import paths
from rspy.data import build, fetch

t0 = time.perf_counter()
if "--fetch" in sys.argv:
    for line in fetch.fetch_public():
        print(f"fetched {line['path']}: {line['bytes']:,} bytes sha256 {line['sha256'][:12]}")
missing = [str(p) for p in build.raw_files().values() if not p.exists()]
if missing:
    sys.exit(f"raw files missing (run `make fetch`): {missing}")
if build.is_current():
    print("data/panel.parquet is current (build key unchanged)")
else:
    panel, log = build.build()
    build.write(panel, log, build.build_key())
    print(json.dumps(log, indent=1))
    print(f"panel: {panel.shape[0]:,} sessions × {panel.shape[1]} columns -> {paths.data_dir() / 'panel.parquet'}")
print(f"make data: {time.perf_counter() - t0:.1f} s")
