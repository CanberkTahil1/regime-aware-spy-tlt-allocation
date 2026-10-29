"""make report-site: committed phase results → quantkit.results bundle (data/site/, gitignored) → reports/site/index.html
(rspy.site docstring). Computes nothing. This charter has no sealed window: `Seal.none()` is declared explicitly."""

from quantkit import results as qr
from quantkit import viz
from quantkit.seal import Seal

from rspy import paths, site

b = site.bundle()
out = qr.export(b, paths.data_dir() / "site" / "R1", seals=[Seal.none()], source_root=paths.ROOT)
back = qr.read(out)  # round trip: table hashes and schema re-checked
idx = viz.report(back, paths.REPORTS / "site")
print(f"R1: tables {dict((k, len(v)) for k, v in back.tables.items())} → {idx} ({idx.stat().st_size / 1e6:.2f} MB)")
