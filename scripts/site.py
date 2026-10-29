"""make report-site: committed phase results → quantkit.results bundle (data/site/, gitignored) → reports/site/index.html
(rspy.site docstring). Computes nothing. This charter has no sealed window: `Seal.none()` is declared explicitly.
quantkit draws one evidence tier per chart: the main page is in-sample (R1 train/validation, R2 development); the
disclosed-reuse rows (R1 test 2020–25, seen by owner in v1) get their own page at reports/site/test/."""

from quantkit import results as qr
from quantkit import viz
from quantkit.seal import Seal

from rspy import paths, site

b = site.bundle()
out = qr.export(b, paths.data_dir() / "site" / "R2", seals=[Seal.none()], source_root=paths.ROOT)
back = qr.read(out)  # round trip: table hashes and schema re-checked
for tier, sub in (("in-sample", ""), ("disclosed-reuse", "test")):
    opts = {k: {"tier": tier} for k in ("loss_waterfall", "ladder", "rung_compare")}
    idx = viz.report(back, paths.REPORTS / "site" / sub, options=opts)
    print(f"R2 page ({tier}): tables {dict((k, len(v)) for k, v in back.tables.items())} → {idx} "
          f"({idx.stat().st_size / 1e6:.2f} MB)")
