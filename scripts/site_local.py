"""make report-site-local (owner O1.1; as naive-vs-optimal O4.2): the full chart page and the curve figures from the
gitignored daily series → reports/site_local/index.html (2005–2019, in-sample), reports/site_local/test/index.html
(2020–2025, seen by owner in v1) and reports/figures_local/R1/ (SVG + PNG). All outputs are gitignored and must never be
committed (tests/test_site_local.py pins the ignore rules; the pre-commit hook refuses them)."""

import runpy

from quantkit import results as qr
from quantkit import viz
from quantkit.seal import Seal

from rspy import paths, site_local

out = qr.export(site_local.bundle(), paths.data_dir() / "site_local" / "R1", seals=[Seal.none()], source_root=paths.ROOT)
back = qr.read(out)
for tier, sub in (("in-sample", ""), ("disclosed-reuse", "test")):  # quantkit draws one evidence tier per chart
    opts = {k: {"tier": tier} for k in ("equity", "rolling_sharpe", "loss_waterfall", "ladder", "rung_compare")}
    idx = viz.report(back, paths.REPORTS / "site_local" / sub, options=opts)
    print(f"R1 local page ({tier}) {idx} ({idx.stat().st_size / 1e6:.2f} MB)")
runpy.run_path(str(paths.ROOT / "scripts" / "r1_figures_local.py"), run_name="__main__")
