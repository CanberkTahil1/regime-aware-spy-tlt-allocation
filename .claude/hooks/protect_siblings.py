#!/usr/bin/env python3
"""PreToolUse guard: sibling repos under ~/github are READ-ONLY for every agent in this repo (CLAUDE.md rule 2).

Why: this project installs the shared quantkit library from a tag (hash-pinned) and reads sibling files read-only
(pinned book return streams via git show); other siblings hold seals and live records. Reading them is fine; changing
them is not. Every repo under ~/github except this one is a sibling.

Copied from naive-vs-optimal (`.claude/hooks/protect_siblings.py` @ b5f6278, itself from resid-book @ 9a1e939 ←
netiss-events @ 2e21799 ← slowcomp @ 5760057; COPIED.md); nvo (naive-vs-optimal) added to the sibling CLIs.

- Write / Edit / MultiEdit / NotebookEdit: denied when the target resolves outside this repo but inside ~/github
  (symlinks are resolved, so data/disprev/raw|processed count as the sibling). Also denied: this guard and
  .claude/settings.json (the owner edits them by hand), and any write that sets disableAllHooks.
- Bash, per step (split on && || ; | and newlines), when the step names a sibling path: denied if it runs a mutating
  command (rm, mv, rsync, ln, touch, mkdir, chmod, chown, truncate, unlink, sed -i, make, uv), a mutating git
  subcommand, cp/tee/redirect INTO a sibling, or inline Python that writes.
- Always denied: `python -m disprev|regms|residarb|bondflows|loblab|mafrm|slowcomp|netiss|six40|varbt|nvo ...` (siblings' CLIs), `disprev live ...`, and
  launchctl start/stop/load/unload/bootout/kickstart/kill/remove/disable of any com.disprev.*, com.spyedge.*, com.bondflows.*, com.loblab.*, com.slowcomp.* or com.netiss.* label.
- Fail closed: an internal error on an input that names a sibling denies the call.

This is a text check, not a filesystem lock (a script written in one step and run in another is not seen); the
charter rule and the quant-reviewer cover those routes. Output: PreToolUse JSON on stdout (deny); nothing = allow.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2]).resolve()
GITHUB = ROOT.parent
ME = re.escape(ROOT.name)
SIB = re.compile(rf"(?:\.\./|github/)(?!{ME}(?:/|\b))[A-Za-z0-9_.-]+|data/disprev/(?:raw|processed)")
GUARD_FILES = {ROOT / ".claude/hooks/protect_siblings.py", ROOT / ".claude/settings.json"}
MUTATING = {"rm", "rmdir", "mv", "rsync", "ln", "touch", "mkdir", "chmod", "chown", "truncate", "unlink", "make", "uv"}
MUTATING |= {"install", "patch", "dd", "shred"}
GIT_WRITE = {"commit", "checkout", "reset", "tag", "push", "stash", "clean", "rebase", "merge", "restore", "rm", "mv"}
GIT_WRITE |= {"add", "switch", "cherry-pick", "revert", "am", "apply", "pull", "fetch", "gc", "prune", "worktree"}
PY_WRITE = re.compile(
    r"open\([^)]*['\"][wax+]|\.write\(|write_text|write_bytes|to_parquet|to_csv|unlink|rmtree|os\.remove|"
    r"os\.rename|\.rename\(|\.replace\(|shutil\.|subprocess|os\.system|\.touch\(|truncate|mkdir|symlink"
)
LAUNCH = re.compile(
    r"launchctl\s+(kickstart|start|stop|kill|bootout|bootstrap|load|unload|remove|disable|enable)\b[^;&|\n]*"
    r"com\.(disprev|spyedge|six40|regms|bondflows|loblab|slowcomp|netiss)"
)


def deny(reason: str) -> int:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"sibling guard: {reason}. Siblings are read-only (CLAUDE.md rule 2); stop and ask.",
        }
    }
    print(json.dumps(out))
    return 0


def outside(p: str) -> bool:
    t = Path(p).expanduser()
    t = (ROOT / t if not t.is_absolute() else t).resolve()
    if t in GUARD_FILES:
        return True
    try:
        t.relative_to(ROOT)
        return False
    except ValueError:
        pass
    try:
        t.relative_to(GITHUB)
        return True
    except ValueError:
        return False


def steps(cmd: str) -> list[str]:
    return [s.strip() for s in re.split(r"&&|\|\||;|\||\n", cmd) if s.strip()]


def bash_reason(cmd: str) -> str | None:
    if re.search(
        r"(^|\s)(python3?|uv run python3?)\s+-m\s+(disprev|regms|residarb|bondflows|loblab|mafrm|slowcomp|netiss|six40|varbt|nvo)\b", cmd
    ) or re.search(r"\bdisprev\s+live\b", cmd):
        return "a sibling's CLI"
    if LAUNCH.search(cmd):
        return "launchctl on a sibling's scheduled job"
    if "disableAllHooks" in cmd:
        return "disableAllHooks"
    GUARD = re.compile(r"protect_siblings\.py|\.claude/settings\.json")
    for s in steps(cmd):
        tgt = re.search(r">{1,2}\s*(\S+)", s)
        if tgt and GUARD.search(tgt.group(1)):
            return "changing the guard"
        head = s.split()[0] if s.split() else ""
        if head in ("rm", "mv", "cp", "tee", "ln", "chmod", "truncate") and GUARD.search(s):
            return "changing the guard"
        if head == "sed" and re.search(r"\s-i", s) and GUARD.search(s):
            return "changing the guard"
    in_sib = False  # after `cd <sibling>`, every later step runs inside it
    for s in steps(cmd):
        if re.match(r"(pushd|cd)\s", s):
            in_sib = bool(SIB.search(s)) or (in_sib and not re.match(r"(pushd|cd)\s+/", s))
            continue
        if not (in_sib or SIB.search(s)):
            continue
        redirect = re.search(r">{1,2}\s*(\S+)", s)
        if redirect and (SIB.search(redirect.group(1)) or (in_sib and not redirect.group(1).startswith("/"))):
            return f"redirect into a sibling: {s[:80]}"
        try:
            toks = shlex.split(s)
        except ValueError:
            toks = s.split()
        if not toks:
            continue
        head = os.path.basename(toks[0])
        if head in MUTATING:
            return f"mutating command on a sibling: {s[:80]}"
        if head == "sed" and any(t.startswith("-i") for t in toks[1:]):
            return f"sed -i on a sibling: {s[:80]}"
        if head in ("cp", "tee") and (SIB.search(toks[-1]) or in_sib):
            return f"{head} into a sibling: {s[:80]}"
        if head == "git":
            i = 0
            while i < len(toks) - 1 and toks[i + 1] in ("-C", "-c"):
                i += 2
            sub = toks[i + 1 : i + 2]
            if sub and sub[0] in GIT_WRITE:
                return f"git {sub[0]} touching a sibling: {s[:80]}"
        if head.startswith("python") and (PY_WRITE.search(s) or in_sib):
            return f"inline Python that writes, naming a sibling: {s[:80]}"
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        ev = json.loads(raw)
        tool, ti = ev.get("tool_name", ""), ev.get("tool_input", {}) or {}
        if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            p = ti.get("file_path") or ti.get("notebook_path") or ""
            if p and outside(p):
                return deny(f"write to {p}")
            body = json.dumps(ti)
            if "disableAllHooks" in body:
                return deny("disableAllHooks")
            return 0
        if tool == "Bash":
            r = bash_reason(ti.get("command", ""))
            return deny(r) if r else 0
        return 0
    except Exception as e:  # fail closed only when a sibling is involved
        if SIB.search(raw) or "disprev" in raw:
            return deny(f"guard error ({type(e).__name__})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
