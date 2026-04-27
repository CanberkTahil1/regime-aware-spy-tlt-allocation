# Regime-Aware SPY-TLT Allocation

This project develops and evaluates a **regime-aware tactical allocation strategy** between **SPY** and **TLT**.

Rather than holding a static mix of equities and long-duration Treasuries, the framework adjusts exposure based on market conditions. It combines regime detection, relative-value signals, and a crash-sensitive overlay within a backtesting pipeline that includes volatility targeting, transaction costs, grid search, and out-of-sample evaluation.

The purpose of the project is strictly **research-oriented**. It is designed to study whether simple, interpretable signals can improve risk-adjusted portfolio behavior across different market environments. It should be viewed as a quantitative research exercise rather than a live trading system or investment product.

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
The spread signal looks at the lagged return spread between SPY and TLT. When that spread becomes unusually wide relative to recent history, the strategy takes a mean-reversion view.

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

- lagged signals to avoid lookahead bias
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

Data is downloaded through `yfinance`, cached locally in `data/prices.csv`, and then split into three periods:

- **Train:** start date to `2015-01-01`
- **Validation:** `2015-01-01` to `2020-01-01`
- **Test:** `2020-01-01` onward

This structure keeps model development, parameter selection, and final performance evaluation separated in a more disciplined way.

## Grid search and model selection

The full workflow is orchestrated in `run.py`.

When executed, the pipeline:
1. loads or downloads the data
2. splits the sample into train, validation, and test periods
3. precomputes reusable features
4. runs a grid search on the validation set
5. selects the best parameter combination using validation Sharpe ratio
6. evaluates the selected strategy on the out-of-sample test period
7. saves tables and plots for review

The implementation also caches parameter-invariant features to improve efficiency during the search process.

## Outputs

Running the project generates the following outputs.

### Tables
- `results/tables/grid_search_results.csv`
- `results/tables/summary_metrics.csv`
- `results/tables/test_metrics.csv`

### Plot
- `results/plots/strategy_vs_spy.png`

These artifacts provide:
- validation results across parameter combinations
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

This will execute the full workflow from data loading to final output generation.

## Main files

### `config.py`
Centralized configuration for:
- filesystem paths
- dataset boundaries
- default model parameters
- backtest assumptions
- grid-search ranges
- display settings

### `data.py`
Handles:
- market data download
- local caching
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
  The workflow is configuration-driven and saves outputs systematically.

- **Practicality**
  The project includes implementation details that matter in realistic backtesting, such as lagging, turnover, transaction costs, and out-of-sample testing.

## Limitations

This project is strictly a **research backtest** and should not be interpreted as a live investment strategy.

Important limitations include:
- no live execution layer
- no broker integration
- simplified transaction cost modeling
- only two tradable assets
- no walk-forward re-optimization
- no broader macro feature set yet

As with any backtest, results are sensitive to assumptions, sample period choice, and modeling decisions.

## Possible extensions

A few natural next steps would be:
- walk-forward validation
- richer cost and slippage modeling
- additional macro or rates-based regime inputs
- a broader multi-asset universe
- benchmark comparison beyond SPY
