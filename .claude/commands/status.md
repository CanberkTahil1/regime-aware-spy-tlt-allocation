---
description: One-screen regime-aware-spy-tlt status — phases done, tags, open expectations, perf budgets, last commits, what's next. Read-only.
---
<!-- Adapted from ../naive-vs-optimal/.claude/commands/status.md @ b5f6278 (itself from quantkit @ c326b45; COPIED.md):
Rn phases, r*-done tags, no seal; adds the public-remote and data/prices.csv rows. -->
Report in one screen, changing nothing: (1) for each `## Rn:` in `.claude/BUILD_PROMPTS.md`, done if tag `rn-done`
exists, in progress if `reports/research/Rn.md` or a `## Rn` ledger section exists, else not started; (2) `git tag -l`;
(3) `git status -sb` ahead/behind the public remote (never fetch or push) and whether `data/prices.csv` is still tracked;
(4) open ledger rows; (5) the latest row per budget in `reports/perf.md`; (6) `git log --oneline -5` and tree clean or
not; (7) next phase.
