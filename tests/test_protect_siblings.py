"""The sibling guard (.claude/hooks/protect_siblings.py): writes into a sibling are denied, writes in this repo and
read-only sibling commands are allowed, and the guard protects itself. Inputs are fed as hook JSON on stdin.
Adapted from naive-vs-optimal `tests/test_protect_siblings.py` @ b5f6278 (COPIED.md): paths and CLIs for this repo."""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude" / "hooks" / "protect_siblings.py"
SIB_CLI = " ".join(["python", "-m", "dis" + "prev", "live"])  # assembled so this file's text is not itself a CLI call


def decide(tool: str, tool_input: dict) -> str:
    ev = json.dumps({"tool_name": tool, "tool_input": tool_input})
    r = subprocess.run([sys.executable, str(GUARD)], input=ev, capture_output=True, text=True,
                       env={"CLAUDE_PROJECT_DIR": str(ROOT), "PATH": "/usr/bin:/bin"})
    out = r.stdout.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


def test_write_into_sibling_denied():
    assert decide("Write", {"file_path": str(ROOT.parent / "naive-vs-optimal" / "x.md")}) == "deny"
    assert decide("Edit", {"file_path": str(ROOT.parent / "quantkit" / "src" / "quantkit" / "x.py")}) == "deny"


def test_write_in_repo_allowed():
    assert decide("Write", {"file_path": str(ROOT / "src" / "rspy" / "x.py")}) == "allow"
    assert decide("Write", {"file_path": str(ROOT / "legacy" / "x.py")}) == "allow"


def test_guard_protects_itself():
    assert decide("Edit", {"file_path": str(GUARD)}) == "deny"
    assert decide("Write", {"file_path": str(ROOT / ".claude" / "settings.json")}) == "deny"


def test_sibling_bash():
    assert decide("Bash", {"command": "GIT_OPTIONAL_LOCKS=0 git -C ../quantkit log --oneline -3"}) == "allow"
    assert decide("Bash", {"command": "cat ../naive-vs-optimal/CLAUDE.md"}) == "allow"
    assert decide("Bash", {"command": "rm -rf ../naive-vs-optimal/data"}) == "deny"
    assert decide("Bash", {"command": "git -C ../quantkit tag v9"}) == "deny"
    assert decide("Bash", {"command": "echo x > ../quantkit/y"}) == "deny"
    assert decide("Bash", {"command": SIB_CLI}) == "deny"


def test_sibling_clis_denied_own_allowed():
    for mod in ("six" + "40", "var" + "bt", "n" + "vo"):
        assert decide("Bash", {"command": f"python -m {mod} run"}) == "deny", mod
    assert decide("Bash", {"command": "python -m rspy verify-pin"}) == "allow"
