"""CLI: python -m rspy <cmd>.

- pin / verify-pin: record / check the full quantkit tree (make pin, make verify-pin, make doctor, make freeze).
- run SCRIPT [ARGS...]: run a make-target script in this process, then check every quantkit file it loaded against
  the pin (rspy.pin.verify_loaded). A loaded file that changed or is unpinned turns the exit code to 1.
Copied from naive-vs-optimal `src/nvo/__main__.py` @ b5f6278 (← resid-book @ 9a1e939; COPIED.md), renamed.
"""

from __future__ import annotations

import argparse
import runpy
import sys

from rspy import pin


def run(script: str, args: list[str]) -> int:
    sys.argv = [script, *args]
    code = 0
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as e:  # the script's own exit code is kept unless the pin check fails
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if isinstance(e.code, str):  # a refusal's reason is shown, not swallowed
            print(e.code, file=sys.stderr)
    probs = pin.verify_loaded()
    n = len(pin.loaded_files())
    print("quantkit pin (loaded modules): " + (f"OK ({n} files)" if not probs else "FAIL\n" + "\n".join(probs)))
    return 1 if probs else code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m rspy")
    ap.add_argument("cmd", choices=["pin", "verify-pin", "run"])
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        if not a.rest:
            ap.error("run needs a script path")
        return run(a.rest[0], a.rest[1:])
    if a.cmd == "pin":
        rec = pin.pin()
        print(
            f"pinned {len(rec['files'])} quantkit files at {rec['quantkit_tag_at_pin'] or rec['quantkit_head_at_pin']}"
        )
    else:
        probs, warns = pin.verify_pin(), pin.unpinned_files()
        for w in warns:
            print(f"warning (not pinned): {w}")
        print("quantkit pin: OK" if not probs else "\n".join(probs))
        return 1 if probs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
