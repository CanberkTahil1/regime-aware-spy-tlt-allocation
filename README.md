# Regime-Aware SPY-TLT Allocation

This project develops and evaluates a **regime-aware tactical allocation strategy** between **SPY** and **TLT**.

Rather than holding a static mix of equities and long-duration Treasuries, the framework adjusts exposure based on market conditions. It combines regime detection, relative-value signals, and a crash-sensitive overlay within a backtesting pipeline that includes volatility targeting, transaction costs, grid search, and out-of-sample evaluation.

The purpose of the project is strictly **research-oriented**. It is designed to study whether simple, interpretable signals can improve risk-adjusted portfolio behavior across different market environments. It should be viewed as a quantitative research exercise rather than a live trading system or investment product.

**Headline result (out-of-sample, 2020-01-01 to 2025-12-31):** the strategy delivered a **1.00 Sharpe vs. 0.78 for SPY** and roughly **half the maximum drawdown (-17.7% vs. -33.7%)**, while slightly beating SPY's return at lower volatility. This is primarily a **risk-control** result, not a return-alpha claim — see [Results](#results) for full numbers and caveats.

## Research motivation

The central hypothesis is that the relationship between equities and duration is not constant across market regimes.

In supportive environments, equity exposure may remain attractive. In weaker or more unstable environments, long-duration Treasuries may become more valuable either as a defensive allocation or as part of a relative-value positioning framework. This project studies whether a small set of transparent rules can adapt to those changes more effectively than a static allocation.

The strategy is built around three core components:

- **Regime detection**
  Classifies the market using volatility and trend information.

- **Base signal generation**
  Uses spread-based and Bollinger-band signals to identify relative-value opportunities between SPY and TLT.

- **Crash overlay**
  Reduces SPY exposure during periods of rising market stress using drawdown- and volatility-sensitive logic.

The final result is a daily portfolio allocation between SPY and TLT.

## Project structure

```bash
REGIME-AWARE-SPY-TLT-ALLOCATION/
│
├── data/
│   └── prices.csv
│
├── results/
│   ├── plots/
│   │   └── strategy_vs_spy.png
│   └── tables/
│       ├── grid_search_results.csv
│       ├── summary_metrics.csv
│       └── test_metrics.csv
│
├── signals/
│   ├── bollinger.py
│   ├── regime.py
│   ├── regime_allocation.py
│   └── spread.py
│
├── backtest.py
├── config.py
├── data.py
├── run.py
├── utils.py
├── README.md
└── requirements.txt
```

## Strategy framework

### 1. Regime detection

The first step is to classify the market environment.

The model uses:
- **volatility**
- **trend**

Volatility can be measured either through:
- VIX relative to its rolling average, or
- realized SPY volatility relative to its own long-term average

Trend is measured using SPY momentum.

This stage is meant to answer a simple question: **what type of market environment are we currently observing?**

### 2. Relative-value signals

The project uses two base signal engines.

#### Spread signal
The spread signal looks at the close-to-close return spread between SPY and TLT. When that spread becomes unusually wide relative to recent history, the strategy takes a mean-reversion view. The backtest applies the execution lag centrally when converting signals into returns.

#### Bollinger-band signal
The Bollinger framework looks at the SPY/TLT price ratio. When the ratio moves too far from its rolling mean, the model adjusts positioning based on that deviation.

These two signals provide a simple and interpretable way to express relative-value views depending on the regime.

### 3. Regime-aware allocation logic

The regime state determines which signal logic is emphasized.

In broad terms:
- calmer uptrending environments allow stronger SPY exposure
- calmer but weaker environments can lean more on Bollinger-based positioning
- more volatile environments can rely more on spread-based positioning
- stressed environments activate a crash overlay that reduces equity exposure

The goal is not to maximize complexity, but to keep the allocation logic explicit and understandable.

### 4. Crash-sensitive overlay

An important part of the framework is the crash overlay.

Instead of treating all high-volatility periods the same, the model uses a combination of:
- VIX-relative stress
- drawdown conditions
- slow-crash behavior

to scale down SPY exposure when market conditions deteriorate. This allows the strategy to respond not only to sharp stress events but also to slower declines in market conditions.

### 5. Backtest construction

The backtest is designed for research purposes and includes:

- one-day execution lag to avoid lookahead bias
- volatility targeting
- transaction costs
- turnover measurement
- crisis-period analysis
- out-of-sample testing
- performance visualization

The framework evaluates both the strategy and the SPY benchmark over the holdout test period.

## Data

The project uses historical market data for:
- `SPY`
- `TLT`
- `^VIX`

Data is downloaded through `yfinance`, cached locally in `data/prices.csv`, and split into three non-overlapping periods:

- **Train:** start date (`2005-01-01`) to `2015-01-01`
- **Validation:** `2015-01-01` to `2020-01-01`
- **Test (out-of-sample):** `2020-01-01` to `2025-12-31`

**Reproducibility — the analysis window is frozen.** The test window has a fixed end date (`test_end_date = 2025-12-31` in `config.py`), and `data.py` truncates the loaded price history at that date (`prices.loc[:TEST_END_DATE]`). This means results do **not** drift as new market data arrives: re-running the pipeline reproduces the same numbers reported below, regardless of when it is run. This structure also keeps model development, parameter selection, and final performance evaluation cleanly separated.

## Grid search and model selection

The full workflow is orchestrated in `run.py`.

When executed, the pipeline:
1. loads or downloads the data (and freezes it at `test_end_date`)
2. splits the sample into train, validation, and test periods
3. precomputes reusable features
4. runs a grid search on train and validation scoring windows using prior history as warm-up context
5. uses the train period to shortlist parameters
6. selects a robust parameter combination using train/validation stability
7. evaluates the selected strategy on the out-of-sample test period
8. saves tables and plots for review

The implementation also caches parameter-invariant features to improve efficiency during the search process. Crucially, the **test period is never used for parameter selection** — it is touched only once, for final evaluation.

## Results

All figures below are **out-of-sample** (test period `2020-01-01` to `2025-12-31`). Parameters were selected on the train/validation windows only.

**Selected parameters:** `z_window=10`, `threshold=2.5`, `slow_window=60`, `slow_threshold=-0.03`, `dd_window=50`, `dd_threshold=-0.03`, `crash_weight=0.2`.

| Metric            | Strategy | SPY (benchmark) |
|-------------------|---------:|----------------:|
| Annualized return |   16.3%  |      15.0%      |
| Volatility        |   16.4%  |      20.7%      |
| Sharpe            |   1.00   |      0.78       |
| Sortino           |   1.29   |      0.89       |
| Max drawdown      |  -17.7%  |     -33.7%      |
| Calmar            |   0.92   |      0.45       |
| Win rate          |   55.6%  |      55.2%      |

Sharpe across the three windows: **train 0.54 → validation 0.77 → test 1.00**.

### How to read these results (honestly)

- **This is a risk-control story, not an alpha story.** The strategy roughly matched SPY's return while cutting volatility by about 20% and nearly halving the maximum drawdown. The edge is in the *risk-adjusted* profile (Sharpe, Sortino, Calmar), not in outsized returns.
- **The out-of-sample result is regime-dependent.** Test Sharpe (1.00) exceeds in-sample/train Sharpe (0.54). This is unusual and should be interpreted with care: the test window (2020–2025) contains the 2020 COVID crash and the 2022 equity/duration selloff — exactly the environments a defensive, crash-overlay design is built to handle. The strong test result therefore reflects a favorable sample period, **not** evidence of a stable, persistent edge.
- **Costs are included, and turnover is high.** Returns are net of transaction costs and use a one-day execution lag with volatility targeting. Annualized turnover is roughly **18.7x**, so the strategy is turnover-heavy and sensitive to the cost assumption.

## Outputs

Running the project generates the following outputs.

### Tables
- `results/tables/grid_search_results.csv`
- `results/tables/summary_metrics.csv`
- `results/tables/test_metrics.csv`

### Plot
- `results/plots/strategy_vs_spy.png`

These artifacts provide:
- train and validation results across parameter combinations
- final selected parameters
- out-of-sample performance statistics
- benchmark comparison against SPY
- cumulative performance visualization

## Installation

Install the required packages with:

```bash
pip install -r requirements.txt
```

A minimal `requirements.txt` for this project is:

```txt
numpy
pandas
matplotlib
yfinance
```

## How to run

Run the full pipeline with:

```bash
python run.py
```

This will execute the full workflow from data loading to final output generation, and reproduce the results reported above.

## Main files

### `config.py`
Centralized configuration for:
- filesystem paths
- dataset boundaries (start, train end, validation end, and the frozen `test_end_date`)
- default model parameters
- backtest assumptions
- grid-search ranges
- display settings

### `data.py`
Handles:
- market data download
- local caching
- freezing the analysis window at `test_end_date`
- return construction
- train / validation / test splitting

### `signals/regime.py`
Contains the regime classification logic.

### `signals/spread.py`
Implements the spread-based mean-reversion signal.

### `signals/bollinger.py`
Implements the Bollinger-band signal based on the SPY/TLT ratio.

### `signals/regime_allocation.py`
Combines regime detection, base signal logic, and crash overlay logic into final portfolio weights.

### `utils.py`
Contains helper logic for conditional normalization.

### `backtest.py`
Provides:
- strategy return construction
- performance metrics
- turnover analysis
- crisis-period analysis
- plotting utilities

### `run.py`
Acts as the entry point for the end-to-end research pipeline.

## Research characteristics

A few aspects of the project were intentional:

- **Interpretability**
  Each layer of the decision process is meant to remain understandable.

- **Modularity**
  Data handling, signals, configuration, and evaluation are separated cleanly.

- **Reproducibility**
  The workflow is configuration-driven, the analysis window is frozen at a fixed `test_end_date`, and outputs are saved systematically — so reported numbers reproduce exactly.

- **Practicality**
  The project includes implementation details that matter in realistic backtesting, such as lagging, turnover, transaction costs, and out-of-sample testing.

## Limitations

This project is strictly a **research backtest** and should not be interpreted as a live investment strategy.

Important limitations include:
- no live execution layer
- no broker integration
- simplified transaction cost modeling
- only two tradable assets
- high turnover (~18.7x annualized), so results are sensitive to cost assumptions
- no walk-forward re-optimization
- a single out-of-sample window, whose result is regime-dependent (see Results)
- no broader macro feature set yet

As with any backtest, results are sensitive to assumptions, sample period choice, and modeling decisions.

## Possible extensions

A few natural next steps would be:
- walk-forward validation
- richer cost and slippage modeling
- additional macro or rates-based regime inputs
- a broader multi-asset universe
- benchmark comparison beyond SPY