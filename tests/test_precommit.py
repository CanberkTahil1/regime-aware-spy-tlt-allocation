"""The pre-commit hook refuses data/ and legacy/data/, parquet, a > 5 MB file, a token-shaped secret and the value of a
RSPY_SECRET_* env var; a clean file passes. Runs in a throwaway repository with this repo's hook; planted secrets are
fake. Adapted from naive-vs-optimal `tests/test_precommit.py` @ b5f6278 (COPIED.md): SEC User-Agent -> generic secrets."""

import pathlib
import shutil
import subprocess

import pytest

HOOK = pathlib.Path(__file__).resolve().parents[1] / ".githooks" / "pre-commit"


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    shutil.copy(HOOK, hooks / "pre-commit")
    r = tmp_path / "r"
    r.mkdir()
    for args in (["init", "-q"], ["config", "core.hooksPath", str(hooks)], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(r), *args], check=True)
    return r


def _commit(repo, rel, content, env=None):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    subprocess.run(["git", "-C", str(repo), "add", "-f", rel], check=True)
    r = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], capture_output=True, text=True,
                       env={**__import__("os").environ, **(env or {})})
    subprocess.run(["git", "-C", str(repo), "reset", "-q"], check=False)
    return r.returncode


FAKE_GH = "gh" + "p_" + "A" * 36  # assembled so this file does not itself trip the hook


def test_refuses_data_dir(repo):
    assert _commit(repo, "data/kf_hi20.csv", b"x") != 0  # a csv: only the data/ rule can refuse it
    assert _commit(repo, "legacy/data/prices.csv", b"x") != 0


def test_refuses_parquet_anywhere(repo):
    assert _commit(repo, "reports/x.parquet", b"x") != 0


def test_refuses_big_file(repo):
    assert _commit(repo, "big.bin", b"\0" * (5 * 1024 * 1024 + 1)) != 0


def test_refuses_token_pattern(repo):
    assert _commit(repo, "notes.txt", f"token = {FAKE_GH}\n".encode()) != 0


def test_refuses_planted_env_secret(repo):
    fake = "rspy-test-secret-value-123"
    assert _commit(repo, "notes.txt", f"k = {fake}\n".encode(), env={"RSPY_SECRET_TEST": fake}) != 0


def test_clean_file_passes(repo):
    assert _commit(repo, "ok.txt", b"fine\n", env={"RSPY_SECRET_TEST": "rspy-test-secret-value-123"}) == 0
