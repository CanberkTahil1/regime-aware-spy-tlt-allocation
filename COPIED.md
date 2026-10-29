# Copied files (provenance)

Siblings are read-only: files are copied (never imported from a sibling's working tree), read with
`GIT_OPTIONAL_LOCKS=0`, and listed here with the source commit and the SHA-256 of the source file at copy time.

| File here | Source repo @ commit | Source path | Source SHA-256 | Changes |
|---|---|---|---|---|
| `.claude/agents/decision-advisor.md` | naive-vs-optimal @ b5f6278 (← enhanced-60-40 @ 427eeb3) | `.claude/agents/decision-advisor.md` | 7584af7349970d180a0850a673a5238243edc21876bca4896c4377b98fba5abc | windows, evidence tiers, standing rules and escalation list rewritten for this charter (no seal, public remote) |
| `.claude/agents/quant-reviewer.md` | naive-vs-optimal @ b5f6278 (← enhanced-60-40 @ 427eeb3) | `.claude/agents/quant-reviewer.md` | b85be1facf32a2f90054071de0b0da521023117d7ffcfd686f2c9cacbf3a11a9 | twelve-item checklist rewritten (windows, L0–L8, true turnover, legacy reproduction, Yahoo/Cboe, public remote) |
| `.claude/commands/task.md` | naive-vs-optimal @ b5f6278 (← enhanced-60-40 @ 427eeb3) | `.claude/commands/task.md` | d20e7fa88321032a4352aa0e081ba65dd46a69b0e6cdb33db1fb751c275d735c | `## Rn:` blocks, windows 1990–2019 / 2020+, escalation list, never push, `rn-done` tags |
| `.claude/commands/review.md` | naive-vs-optimal @ b5f6278 | `.claude/commands/review.md` | 7a99d3c72f4a96867aa4ca0a16fe17ef21a97e9c23cae941ff5679e3eb95630a | provenance comment only |
| `.claude/commands/status.md` | naive-vs-optimal @ b5f6278 (← quantkit @ c326b45) | `.claude/commands/status.md` | 2d066eec853484804b76caefcd3adb735f9af5c72af5754d1a891fb7371c529e | Rn phases, no seal; public-remote and data/prices.csv rows |
| `.claude/hooks/protect_siblings.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939 ← netiss-events @ 2e21799 ← slowcomp @ 5760057) | `.claude/hooks/protect_siblings.py` | e7d3db84f823dbc5668adedd55846d6482823aac240902c76bca4681764144a2 | `nvo` added to the sibling CLIs; provenance line |
| `.claude/settings.json` | naive-vs-optimal @ b5f6278 | `.claude/settings.json` | 763ca67207356a320828cfdfc8e1c2f420f5b8e7a2d8d169fb39e27b831c0c6f | unchanged |
| `src/rspy/__init__.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `src/nvo/__init__.py` | e74f3fae4b8877019a7c770fc7b1def61188982cdeefea0a8e40ae69a4340220 | docstring renamed |
| `src/rspy/__main__.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `src/nvo/__main__.py` | 27e1d5add8829eb7ee480df15ff4b907d75b99b9c749c241e558f6064903d97a | `nvo` → `rspy` |
| `src/rspy/pin.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939 ← netiss-events ← slowcomp ← resid-arb) | `src/nvo/pin.py` | 00037aa6311917c8d5c75f5fae980ae0b2e540b35618ecfc3118d91aea47fcfd | `nvo` → `rspy`, `NVO_` → `RSPY_` |
| `src/rspy/paths.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `src/nvo/paths.py` | b3272d5439ce2213679236d0c7f8d280a0e6912fccdac331e17133c6ebb20564 | seal/freeze/spec accessors dropped (R1 adds spec) |
| `tests/conftest.py` | naive-vs-optimal @ b5f6278 | `tests/conftest.py` | 9357d9b2a5a9b7eef7f712539c8780e2af1cca229157541000a33a077867efaa | renamed; SEC-lock lines dropped; `no_yahoo` fixture added (D0.2) |
| `tests/test_pin.py` | naive-vs-optimal @ b5f6278 | `tests/test_pin.py` | 2acf98847b2ca8ef7a85ec66443a0ae746a4a00b90a0c04a940f03be0ad59297 | renamed; real-pin test re-targeted to v0.19.1 / d68e374 |
| `tests/test_makefile.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `tests/test_makefile.py` | 36840bb406591c0337ff0dfdfb249764a6c4a70ebf8fe0b1680f074ce5819e66 | this DAG's targets; D0.3 test/test-nolegacy check added |
| `tests/test_precommit.py` | naive-vs-optimal @ b5f6278 | `tests/test_precommit.py` | 0f2f29a4e9f373ab7c2bfbd93dfeed6ed9725e146827813070bc4e746a8b1f87 | SEC User-Agent → token pattern and RSPY_SECRET_* tests; legacy/data case |
| `tests/test_protect_siblings.py` | naive-vs-optimal @ b5f6278 | `tests/test_protect_siblings.py` | d5735b0665cba2b0ab5759fc5d712931522f9e7467376e166af8e394d5ac486d | sibling names for this repo; `nvo` denied, `rspy` allowed |
| `Makefile` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `Makefile` | 582d29f0bf958d3b7e41a62d8323f27f0f9697a45a6078cdd88ec47fa34fd451 | header/variables kept; targets rewritten for `data test lint legacy ladder report-site all` |
| `.githooks/pre-commit` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `.githooks/pre-commit` | c33bf55d233347bede97a6e78ed8adc6e60a96456280aae6fe2be3f798c27cf9 | Keychain SEC check → generic token patterns + RSPY_SECRET_*; legacy/data; ACMR |
| `scripts/doctor.py` | naive-vs-optimal @ b5f6278 (← resid-book @ 9a1e939) | `scripts/doctor.py` | 70e26a39aa3f17f16dd94242922eea7ac5fbea18f3cd01d9ebf6a25fa466fc97 | seal/SEC/network rows dropped; OK/WARN/FAIL; public-remote, v1-data, yfinance rows |
| `LICENSES.md` (wording) | naive-vs-optimal @ b5f6278 | `LICENSES.md` | (wording only) | Fed, KF, Yahoo, Cboe clauses re-read raw on 2026-10-28 and confirmed verbatim |
