"""Pre-flight check: `make doctor`. Never prints secret values. Sibling git reads use GIT_OPTIONAL_LOCKS=0. No network.
FAIL rows exit 1; WARN rows are owner items that do not block (e.g. the pending O0.1 escalation).
Adapted from naive-vs-optimal `scripts/doctor.py` @ b5f6278 (COPIED.md): seal, SEC and network rows dropped; public
remote, v1 data and legacy rows added.
"""

import importlib
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / "src"), str(pathlib.Path(__file__).resolve().parents[1])]
from rspy import paths, pin  # noqa: E402
from tests.legacy_support import V1_BLOB, V1_DATA, git_blob_sha1  # noqa: E402

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
OK, WARN, FAIL = "OK  ", "WARN", "FAIL"


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=GIT_ENV)
    return r.stdout.strip()


rows = [("python 3.12", OK if sys.version_info[:2] == (3, 12) else FAIL, sys.version.split()[0])]
for pkg in ["numpy", "pandas", "pyarrow", "scipy", "numba", "yaml", "matplotlib", "pytest", "quantkit"]:
    try:
        importlib.import_module(pkg)
        rows.append((f"import {pkg}", OK, ""))
    except Exception:
        rows.append((f"import {pkg}", FAIL, f"not installed in {sys.executable} (uv sync --frozen)"))
try:
    importlib.import_module("yfinance")
    rows.append(("yfinance NOT installed (Yahoo excluded, D0.2)", FAIL, "installed"))
except ImportError:
    rows.append(("yfinance NOT installed (Yahoo excluded, D0.2)", OK, "absent"))
tag = json.loads(paths.PIN.read_text()).get("quantkit_tag_at_pin") if paths.PIN.is_file() else None
rows.append(("quantkit tag present (sibling, read-only)", OK if tag and tag in git(paths.sibling("quantkit"), "tag", "-l").split() else FAIL, str(tag)))
probs, warns = pin.verify_pin(), pin.unpinned_files()
note = "byte-identical, tag + commit match" + (f" ({len(warns)} new unpinned files)" if warns else "")
rows.append(("quantkit pin (spec/quantkit_pin.json)", OK if not probs else FAIL, note if not probs else "; ".join(probs[:3])))
bp = paths.ROOT / ".claude" / "BUILD_PROMPTS.md"
ignored = subprocess.run(["git", "check-ignore", "-q", str(bp)], cwd=paths.ROOT, env=GIT_ENV).returncode == 0
rows.append(("BUILD_PROMPTS present and gitignored", OK if bp.is_file() and ignored else FAIL, str(bp.relative_to(paths.ROOT))))
hooks = git(paths.ROOT, "config", "core.hooksPath")
rows.append(("git hooks path = .githooks", OK if hooks == ".githooks" else FAIL, hooks or "unset (git config core.hooksPath .githooks)"))
settings = paths.ROOT / ".claude" / "settings.json"
rows.append(("sibling guard hook installed", OK if settings.is_file() and "protect_siblings.py" in settings.read_text() else FAIL, ".claude/settings.json"))
remotes = git(paths.ROOT, "remote", "-v")
rows.append(("public remote present: session never pushes", WARN if remotes else OK, "origin (owner-only push)" if remotes else "none"))
if V1_DATA.is_file():
    blob = git_blob_sha1(V1_DATA.read_bytes())
    rows.append(("v1 data/prices.csv local copy = 5ccc12c blob", OK if blob == V1_BLOB else FAIL, blob[:12]))
else:
    rows.append(("v1 data/prices.csv local copy = 5ccc12c blob", FAIL, "missing (legacy tests will fail; make test-nolegacy)"))
tracked = bool(git(paths.ROOT, "ls-files", "data/prices.csv"))
rows.append(("data/prices.csv (Yahoo+Cboe) untracked (O0.1)", WARN if tracked else OK, "still tracked: owner decision pending" if tracked else "untracked"))
dirty = git(paths.ROOT, "status", "--porcelain")
rows.append(("git tree clean", OK if not dirty else WARN, "clean" if not dirty else "uncommitted changes"))
w = max(len(r[0]) for r in rows)
for name, status, note in rows:
    note = re.sub(r"\S+@\S+", "<redacted>", note)
    print(f"{status}  {name.ljust(w)}  {note}")
sys.exit(0 if all(s != FAIL for _, s, _ in rows) else 1)
