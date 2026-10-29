---
description: Run the quant-reviewer subagent standalone on a diff range, a path, or the whole repository.
argument-hint: <sha..sha | path | all>
---

<!-- Copied from ../naive-vs-optimal/.claude/commands/review.md @ b5f6278 (COPIED.md), unchanged. -->

Invoke the **`quant-reviewer`** subagent with scope **$ARGUMENTS**:

- For a commit range `a..b`, give it `git diff a..b`.
- For a path, give it that path and everything that imports from it.
- For `all`, the scope is the whole repository at `HEAD`. Also have it check that every ledger row marked resolved really is resolved.

Give it nothing else: no summary and no framing. Print its findings verbatim and don't act on them unless the owner asks.
