# regime-aware-spy-tlt-allocation v2. Stages form a DAG over files; every target logs to logs/ (tee'd) and prints a tail.
# GNU make 3.81 (macOS) ignores .SHELLFLAGS, so pipefail rides in SHELL: a crashed script piped through tee/tail must
# fail the target (tests/test_makefile.py). Adapted from naive-vs-optimal Makefile @ b5f6278 (COPIED.md).
SHELL := /bin/bash -o pipefail
.SHELLFLAGS := -o pipefail -c
# Every command runs in the locked environment and never re-syncs it (uv.lock is canonical).
unexport VIRTUAL_ENV
UV := uv run --frozen --no-sync
PY := $(UV) python
# pin / verify-pin / doctor check the full quantkit tree; every other script runs through RUN (or pytest's conftest)
# and fails if a quantkit file it loaded changed or is unpinned.
RUN := $(PY) -m rspy run
export PYTHONPYCACHEPREFIX := $(CURDIR)/.cache/pycache
export NUMBA_CACHE_DIR := $(CURDIR)/.cache/numba
export MPLBACKEND := Agg

.PHONY: omp help doctor test test-nolegacy lint legacy fetch data reconcile ladder report-site report-site-local all pin verify-pin logs freeze freeze-verify dry-run test-run r5-replay r5-figures r6-data r6 r6-figures r6-figures-local
help:
	@echo "make doctor | test | test-nolegacy | lint | legacy | fetch | data | reconcile | ladder | report-site | report-site-local | all | pin | verify-pin | freeze | freeze-verify | dry-run | test-run | r5-replay | r6-data | r6 | r6-figures-local"
doctor:
	@$(PY) scripts/doctor.py
test: logs omp  # -n auto capped at 4 workers (D0.4: memory budget). Includes the v1 characterization (marker legacy, D0.3): a missing data/prices.csv FAILS
	$(PY) -m pytest -n auto --maxprocesses 4 --durations=10 2>&1 | tee logs/test.log | tail -25
test-nolegacy: logs omp  # explicit deselect for a machine without v1's cached data (D0.3)
	$(PY) -m pytest -n auto --maxprocesses 4 -m "not legacy" 2>&1 | tee logs/test_nolegacy.log | tail -25
lint:
	$(UV) ruff check src r6lib tests scripts .claude/hooks
legacy: logs  # R0: frozen v1 reproduces its committed tables on its own cached data (outputs to tmp, never results/)
	$(PY) -m pytest -p no:xdist -m legacy -v --durations=5 2>&1 | tee logs/legacy.log | tail -20
fetch: logs  # R1: download KF, GSW, H.15 into data/raw (manifest + sha256); then build
	$(RUN) scripts/make_data.py --fetch 2>&1 | tee logs/fetch.log | tail -30
data: logs  # R1: KF Hi 20, GSW 25y TR (TLT proxy) + 10/20/30y, H.15 bills -> data/panel.parquet (content-hashed)
	$(RUN) scripts/make_data.py 2>&1 | tee logs/data.log | tail -30
reconcile: logs  # R1: legacy reconciliation S0-S7 + data QA -> reports/r1/ (stats) + data/r1/ (local daily books)
	$(RUN) scripts/reconcile.py 2>&1 | tee logs/reconcile.log | tail -60
	$(RUN) scripts/r1_diagnose.py 2>&1 | tee -a logs/reconcile.log | tail -3
	$(RUN) scripts/r1_figures.py 2>&1 | tee -a logs/reconcile.log | tail -3
ladder: logs data omp  # R2-R4: L0-L8 + zoo + robustness -> reports/r2/, r3/, r4/ (statistics) + reports/figures/R2/, R3/, R4/ (statistics figures) + data/r2/, r3/, r4/ (local books)
	$(RUN) scripts/ladder.py 2>&1 | tee logs/ladder.log | tail -40
	$(RUN) scripts/r2_figures.py 2>&1 | tee -a logs/ladder.log | tail -2
	$(RUN) scripts/r3.py 2>&1 | tee -a logs/ladder.log | tail -60
	$(RUN) scripts/r3_figures.py 2>&1 | tee -a logs/ladder.log | tail -2
	$(RUN) scripts/r4.py 2>&1 | tee -a logs/ladder.log | tail -80
	$(RUN) scripts/r4_figures.py 2>&1 | tee -a logs/ladder.log | tail -2
report-site: logs  # every phase with results: reports/site/index.html + reports/figures/Rn/ (stub until R1)
	$(RUN) scripts/site.py 2>&1 | tee logs/report_site.log | tail -5
report-site-local: logs  # owner O1.1: curve figures + full page from the gitignored series -> reports/site_local, reports/figures_local (never committed)
	$(RUN) scripts/site_local.py 2>&1 | tee logs/report_site_local.log | tail -5
	$(RUN) scripts/r2_figures_local.py 2>&1 | tee -a logs/report_site_local.log | tail -2
	$(RUN) scripts/r3_figures_local.py 2>&1 | tee -a logs/report_site_local.log | tail -2
	$(RUN) scripts/r4_figures_local.py 2>&1 | tee -a logs/report_site_local.log | tail -2
	$(RUN) scripts/r5_figures_local.py 2>&1 | tee -a logs/report_site_local.log | tail -2
	$(RUN) scripts/r6_figures_local.py 2>&1 | tee -a logs/report_site_local.log | tail -2
pin:  # owner-approved only: records the installed quantkit tag
	@$(PY) -m rspy pin
verify-pin:  # full tree (also run by doctor)
	@$(PY) -m rspy verify-pin
logs:
	mkdir -p logs
omp:  # R4 D4.3: one OpenMP runtime per process (quantkit.omp: sklearn's vendored libomp -> the one LightGBM uses; idempotent, .venv only, quantkit.omp.restore() undoes it)
	@$(PY) -c "import pathlib, sys; sys.exit(0 if any(pathlib.Path(p).exists() for p in ('/opt/homebrew/opt/libomp/lib/libomp.dylib', '/usr/local/opt/libomp/lib/libomp.dylib')) else 'FAIL: Homebrew libomp missing (brew install libomp; D4.8)')"
	@$(PY) -m quantkit.omp --fix | tail -1
freeze:  # R5 D5.5: write spec/freeze.lock.json (content hashes; refuses if it exists). Commit it before `make test-run`.
	@$(PY) -m rspy freeze write
freeze-verify:
	@$(PY) -m rspy freeze verify
dry-run: logs data omp  # R5 D5.5: the whole test pipeline on a seeded synthetic panel into a temporary directory (code check, not evidence)
	$(RUN) scripts/r5.py --mode dry 2>&1 | tee logs/dry_run.log | tail -40
test-run: logs data omp  # R5, RUN ONCE: refuses unless the lock matches, locked files are clean, RSPY_TEST_RUN=run-once and reports/r5/test_run.json is absent
	$(RUN) scripts/r5.py --mode run 2>&1 | tee logs/test_run.log | tail -80
r5-replay: logs data omp  # R5: recompute the test window into a temporary directory, require byte-identical reports/r5, write the local books
	$(RUN) scripts/r5.py --mode replay 2>&1 | tee logs/r5_replay.log | tail -5
r5-figures: logs  # R5 statistics figures (reports/figures/R5, committed) from reports/r5
	$(RUN) scripts/r5_figures.py 2>&1 | tee logs/r5_figures.log | tail -3
r6-data: logs  # R6 (owner O6.2): CPI-U NSA (BLS CUUR0000SA0) from the BLS public API into data/r6/raw (manifest + sha256); never in `all` (D6.5)
	$(RUN) scripts/r6_data.py 2>&1 | tee logs/r6_data.log | tail -5
r6: logs data omp  # R6 (spec/prereg_r6.yaml): candidates + R5 references on development and test -> reports/r6 (statistics) + data/r6 (local books); refuses missing/altered CPI files
	$(RUN) scripts/r6.py 2>&1 | tee logs/r6.log | tail -30
	$(RUN) scripts/r6_figures.py 2>&1 | tee -a logs/r6.log | tail -2
r6-figures: logs  # R6 statistics figures (reports/figures/R6, committed) from reports/r6
	$(RUN) scripts/r6_figures.py 2>&1 | tee logs/r6_figures.log | tail -3
r6-figures-local: logs  # R6 headline (viz.headline) from data/r6 -> reports/figures_local/R6 (gitignored)
	$(RUN) scripts/r6_figures_local.py 2>&1 | tee logs/r6_figures_local.log | tail -3
# Raw permitted data to every figure.
all: data test lint ladder r5-replay r5-figures r6 report-site  # reconcile (R1) is a local legacy target: it needs v1's cached file
