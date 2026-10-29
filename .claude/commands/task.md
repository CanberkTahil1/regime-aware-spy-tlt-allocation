---
description: Run one build phase end to end — research the decisions, advisor decides, expectations, build, check, review, learn note, wrap-up — then stop before tagging.
argument-hint: <phase id, e.g. R1>
---

<!-- Adapted from ../naive-vs-optimal/.claude/commands/task.md @ b5f6278 (itself from enhanced-60-40 @ 427eeb3; COPIED.md):
`## Rn:` blocks, this charter's windows (development 1990–2019 only for any choice; test 2020+ run once), no seal, the
public remote (never push), the quantkit pin check and the stop-before-tagging rule. -->

You are running build phase **$ARGUMENTS**. Run one phase end to end, then stop. Do not start another. Never tag.

## Setup

1. Read `CLAUDE.md` in full. It governs, and nothing in the phase text amends it.
2. Read `spec/rules.yaml`, `spec/prereg.yaml` and the tail of `reports/ledger.md`.
3. In `.claude/BUILD_PROMPTS.md`, find `## $ARGUMENTS:` and read it through the next `## R`: *Do*, *Decisions* /
   *Escalate*, *Pre-registered*, *Exit*. If it's missing, stop and say so.
4. **quantkit gate:** check the pin (`make verify-pin`; tag v0.19.1 in `spec/quantkit_pin.json`). If the phase needs a
   different tag, stop and ask the owner: re-pins are the owner's alone.
5. Run `git status` and `git log --oneline -5`. **If the tree is dirty, stop.** Record HEAD as `SESSION_START`.

## Phase 1 — Research the decisions, the advisor decides, expectations first

1. **Research each D-item under *Decisions* before routing it.** The listed options are starting points.
   - **Literature and practice:** primary sources (papers, agency documentation, library docs).
   - **A cheap data check, where one exists, on development data only** (1990–2019; warm-up 1986–1989 for estimation).
     Never use a 2020+ number for a choice, and never choose after seeing a result (that is tuning).
   - Write `reports/research/$ARGUMENTS.md`: per decision, each option in one line, what the sources say (a citation
     per claim), the data check, your recommendation and its strongest reason, and the interviewer's likely pushback.
     One page per decision at most. Commit it as `$ARGUMENTS: research`.
2. **The `decision-advisor` decides each D-item** (charter "How to work"). It did not write the code.
   - Invoke it once per decision with the question, every option (recommended first, each with its trade-off and key
     source) and the facts with file:line references. Don't argue for your pick beyond putting it first.
   - **Log it before acting** in `reports/decisions.md` (question, options, choice, amendments, why each other option
     lost, confidence, **decider = advisor**), plus one plain-language entry in `learn/decisions.md`.
   - **Escalate to the owner instead** (multiple choice, the advisor's pick first and labelled) for the charter's
     escalation list: deletes, pushes, history rewrites, tags, licence questions, charter changes, changing a
     pre-registered number after results, re-pins, low advisor confidence, or advisor vs `quant-reviewer` disagreement.
   - The same rule applies to D-items that come up later in the phase.
3. Write a short plan: tests first, then the implementation. No code yet.
4. Append the *Pre-registered* rows to `reports/ledger.md` as `open`, each with a numeric band, and commit them as
   `$ARGUMENTS: expectation` (ledger and decisions only; no code, no results). If an expectation looks wrong, say so now.

## Phase 2 — Build

**If the phase contains a run-once or irreversible step** (the R5 test run, the forward log), split
Phase 2 around it: build; dry-run on development or synthetic data; run Phase 4's review **before** the step; fix; then
the owner confirms and only then the step runs. The dry run is a code-correctness check, never evidence.

1. Implement the *Do* list. One line per transform with dates ("value at t uses data ≤ t (lag k)"), then its test, then
   the code. Reuse quantkit; never re-implement it. Fast versions only after a `tests/reference/` equivalence test.
2. Walk each *Exit* and *Pre-registered* item and show evidence: a command and its output, or a test going from failing
   to passing. A sentence alone isn't evidence.
3. Each guard gets one broken-input check: copy the file aside, break it, run the named test, copy it back, clear
   `.cache/pycache`, rerun. Never `git checkout --` a file.
4. **If a result contradicts the expectation:** log it in the ledger first, then diagnose (sign, timing, units,
   alignment, sample size). Change code only for a demonstrated bug, with a test. Never change the spec to agree.
5. Perf pass against the budgets in `reports/perf.md` (time and peak memory); a miss is profiled and fixed.

## Phase 3 — Self-check

Run `make test lint` (and `make report` if the phase touches reports). Report `n passed · lint pass|fail`.

## Phase 4 — Review (one round)

Invoke the **`quant-reviewer`** subagent with only the phase id, the `## $ARGUMENTS:` block verbatim and `git diff $SESSION_START`
verbatim (or the range, if the diff is large). Don't summarise your work. Answer each finding with **fixed** (show the
change), **disputed** (a reason that holds against the reviewer's own check) or **deferred** (logged in the ledger).
BLOCKING findings must be fixed and re-checked with the reviewer's probe; if one survives, stop and surface it.

## Phase 5 — Learn note

Write `learn/$ARGUMENTS.md` for the owner, plain language, under one page:

```
# $ARGUMENTS — <title>

## In two sentences
## What happened, step by step      (3–6 bullets; files and functions to open)
## Why these choices                (one line per decision: who decided, what, why)
## The one number to remember       (unit and sample)
## Concept check                    (1–2 ideas, with the formula if there is one)
## Try it yourself (5 minutes)      (one command and what he should see)
## Interview questions              (three, each with a 2–3 sentence model answer)
## What could be wrong              (the weakest point, plainly)
```

Add the three questions to `learn/INTERVIEW.md`.

## Phase 6 — Wrap-up

1. Write `reports/reviews/$ARGUMENTS.md` with every finding verbatim and its disposition.
2. Close each ledger row as `held` / `failed` / `not tested`, with the number that decided it. A runnable command and a
   number go in the ledger (standing rule 12).
3. Commit naming the phase. **Never push, force-push or rewrite history** (public remote; owner-only actions). **Do not
   tag**: `r<n>-done` only after the owner says "tag it".

## Handoff

End with this block and nothing after it:

```
=== $ARGUMENTS COMPLETE ===
Commits: <expectation sha> → <session sha>
Tests: <n passed> · lint: <pass|fail>
Owner decisions: <one line each (escalated items only)>
Advisor decisions: <one line each: D-number, choice, confidence — the owner can override any of these before the tag>
Reviewer: findings <blocking>/<material>/<minor>; resolved <fixed>/<disputed>/<deferred>
Expectations: <held>/<failed>/<not tested> — failures named
Next: read learn/$ARGUMENTS.md; say "tag it" to tag r<n>-done
```
