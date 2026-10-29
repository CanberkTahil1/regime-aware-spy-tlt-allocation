"""Content pin for the shared `quantkit` sibling.

Why: every statistic, allocator and model comes from quantkit, which evolves in its own sessions. A result here must
never move because quantkit changed underneath it. `pin()` records a SHA-256 of every quantkit source file plus its
git tag; `verify_pin()` lists every changed or missing pinned file (empty list = every pinned file byte-identical).
Files new in quantkit (not in the pin) cannot change code we already import, so they are warnings (`unpinned_files()`),
not failures. Re-pinning needs the owner's yes.

Copied from naive-vs-optimal (`src/nvo/pin.py` @ b5f6278, itself from resid-book @ 9a1e939 ← netiss-events @ 2e21799 ←
slowcomp @ 5760057 ← resid-arb @ c9c93b5; COPIED.md), renamed. quantkit is a NON-editable install of a git tag
(`quantkit @ git+file:///Users/a90537/github/quantkit@v0.19.2`), so the pinned tree is the installed package in
site-packages (`paths.quantkit_root()`), and the pin also records the tag and commit. `install_problems` fails an
editable or path install, a different commit, or a missing install record. Re-pin = change the tag, owner yes.

Two checks:
- full tree (`verify_pin`): `make pin`, `make verify-pin`, `make doctor` and `make freeze`.
- loaded modules (`verify_loaded`): every other make target and every pytest run hashes each quantkit file that is in
  `sys.modules` at the END of the run; a loaded file that changed, is not in the pin, or lies outside the pinned
  quantkit tree fails the run. A result can only move if code it actually ran moved.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
from types import ModuleType

from rspy import paths

PINNED_GLOBS = ("src/quantkit/**/*.py", "quantkit/**/*.py", "pyproject.toml")  # sibling layout | installed layout


def install_record() -> dict | None:
    """PEP 610 direct_url.json of the installed quantkit distribution (None if absent)."""
    from importlib import metadata

    try:
        txt = metadata.distribution("quantkit").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    return json.loads(txt) if txt else None


def install_problems(rec: dict | None, want_commit: str | None, want_tag: str | None) -> list[str]:
    """The installed quantkit must come from a git tag, non-editable, at the pinned commit."""
    if rec is None:
        return ["quantkit install record (direct_url.json) missing"]
    vcs = rec.get("vcs_info")
    if vcs is None:
        kind = "editable" if rec.get("dir_info", {}).get("editable") else "path/archive"
        return [f"quantkit installed from a {kind} source ({rec.get('url')}); must be a git tag (non-editable)"]
    out = []
    if want_tag and vcs.get("requested_revision") != want_tag:
        out.append(f"quantkit installed at revision {vcs.get('requested_revision')}, pin says tag {want_tag}")
    if want_commit and vcs.get("commit_id") != want_commit:
        out.append(f"quantkit installed at commit {vcs.get('commit_id')}, pin says {want_commit}")
    return out


def file_hashes(root: pathlib.Path | None = None) -> dict[str, str]:
    root = (root or paths.quantkit_root()).resolve()
    files = sorted({p for g in PINNED_GLOBS for p in root.glob(g) if p.is_file() and "__pycache__" not in p.parts})
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def _git(root: pathlib.Path, *args: str) -> str | None:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}  # never take a sibling's index.lock
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)
    return r.stdout.strip() or None


def pin(root: pathlib.Path | None = None, out: pathlib.Path | None = None) -> dict:
    """Record quantkit's code state. Writes spec/quantkit_pin.json in THIS repo only. Default root = the installed
    package: tag and commit come from its install record; an explicit root (tests) is read as a git tree."""
    if root is None:
        root = paths.quantkit_root().resolve()
        vcs = (install_record() or {}).get("vcs_info") or {}
        head, tag = vcs.get("commit_id"), vcs.get("requested_revision")
    else:
        root = root.resolve()
        head, tag = _git(root, "rev-parse", "HEAD"), _git(root, "describe", "--tags", "--exact-match")
    rec = {"quantkit_head_at_pin": head, "quantkit_tag_at_pin": tag, "files": file_hashes(root)}
    (out or paths.PIN).write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return rec


def _load(pin_file: pathlib.Path | None) -> tuple[pathlib.Path, dict[str, str] | None]:
    pin_file = pin_file or paths.PIN
    return pin_file, (json.loads(pin_file.read_text())["files"] if pin_file.exists() else None)


def verify_pin(root: pathlib.Path | None = None, pin_file: pathlib.Path | None = None) -> list[str]:
    """Failures (empty = every pinned quantkit file is byte-identical). New unpinned files are not failures."""
    pin_file, want = _load(pin_file)
    if want is None:
        return [f"no pin: {pin_file} (run `make pin` once quantkit has a tag)"]
    have = file_hashes(root)
    out = [f"changed: {f}" for f in sorted(want) if f in have and have[f] != want[f]]
    out += [f"missing: {f}" for f in sorted(set(want) - set(have))]
    if root is None:  # the real install: also its source (tag, commit, non-editable)
        meta = json.loads(pin_file.read_text())
        out += install_problems(install_record(), meta.get("quantkit_head_at_pin"), meta.get("quantkit_tag_at_pin"))
    return out


def unpinned_files(root: pathlib.Path | None = None, pin_file: pathlib.Path | None = None) -> list[str]:
    """Warnings: quantkit source files that exist but are not in the pin."""
    _, want = _load(pin_file)
    return [] if want is None else [f"new: {f}" for f in sorted(set(file_hashes(root)) - set(want))]


def loaded_files(modules: dict[str, ModuleType] | None = None, package: str = "quantkit") -> list[pathlib.Path]:
    """Source files of every module of `package` in `modules` (default sys.modules); modules without a file (namespace
    packages, builtins) are skipped."""
    modules = sys.modules if modules is None else modules
    out = set()
    for name, mod in list(modules.items()):
        f = getattr(mod, "__file__", None)
        if (name == package or name.startswith(package + ".")) and f:
            out.add(pathlib.Path(f).resolve())
    return sorted(out)


def verify_loaded(
    files: list[pathlib.Path] | None = None, root: pathlib.Path | None = None, pin_file: pathlib.Path | None = None
) -> list[str]:
    """Failures for the quantkit files this process loaded (default: `loaded_files()`); empty = all byte-identical."""
    pin_file, want = _load(pin_file)
    if want is None:
        return [f"no pin: {pin_file} (run `make pin` once quantkit has a tag)"]
    root = (root or paths.quantkit_root()).resolve()
    out = []
    for p in loaded_files() if files is None else files:
        try:
            rel = p.resolve().relative_to(root).as_posix()
        except ValueError:
            out.append(f"loaded outside the pinned tree: {p}")
            continue
        if rel not in want:
            out.append(f"loaded but not pinned: {rel}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != want[rel]:
            out.append(f"loaded and changed: {rel}")
    return out
