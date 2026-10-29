"""Peak memory of a command's whole process tree (D0.4): `python scripts/rss_peak.py <cmd ...>`.

Samples `ps` every 0.1 s and sums RSS over the command and all its descendants (xdist workers included); prints the
peak, the process count at the peak and the wall time. Summed RSS double-counts shared pages, so this is an upper bound
on the true footprint: the conservative side for the charter's peak-RSS ≤ 1.5 GB budget. The command's own exit code is
returned. Every RSS row in reports/perf.md from R0 on uses this method.
"""

import subprocess
import sys
import time


def tree_rss_kb(root: int) -> tuple[int, int]:
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True).stdout
    rows = [tuple(map(int, line.split())) for line in out.splitlines() if line.strip()]
    kids: dict[int, list[int]] = {}
    for pid, ppid, _ in rows:
        kids.setdefault(ppid, []).append(pid)
    fam, stack = {root}, [root]
    while stack:
        for c in kids.get(stack.pop(), []):
            fam.add(c)
            stack.append(c)
    return sum(r for pid, _, r in rows if pid in fam), len(fam)


def main(cmd: list[str]) -> int:
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd)
    peak, n_at_peak = 0, 0
    while p.poll() is None:
        kb, n = tree_rss_kb(p.pid)
        if kb > peak:
            peak, n_at_peak = kb, n
        time.sleep(0.1)
    print(f"rss_peak: {peak / 1024:.0f} MB summed over {n_at_peak} processes; wall {time.perf_counter() - t0:.2f} s; "
          f"exit {p.returncode}", file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/rss_peak.py <cmd ...>")
    sys.exit(main(sys.argv[1:]))
