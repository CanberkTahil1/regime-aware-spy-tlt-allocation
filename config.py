"""
Typed project configuration for the regime-aware SPY-TLT strategy.

This module defines grouped configuration objects for data, paths,
model defaults, grid-search settings, backtest assumptions, and
display metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DATE_FORMAT = "%Y-%m-%d"

POSITION_COLUMNS = ("SPY_pos", "TLT_pos")

ASSET_COLUMNS = ("SPY", "TLT")

@dataclass(frozen=True)
class DataPaths:
    """Input and cached data paths."""

    data_dir: Path
    data_file: Path

    def ensure_directories(self) -> None:
        """Create required data directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class OutputPaths:
    """Output directories and result file paths."""

    results_dir: Path
    plots_dir: Path
    tables_dir: Path
    summary_metrics_file: Path
    grid_search_results_file: Path
    test_metrics_file: Path
    plot_file: Path

    def ensure_directories(self) -> None:
        """Create required output directories if they do not exist."""
        for path in (self.results_dir, self.plots_dir, self.tables_dir):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ProjectPaths:
    """Filesystem layout for the project."""

    base_dir: Path
    data: DataPaths
    output: OutputPaths

    @classmethod
    def from_base_dir(cls, base_dir: Path) -> "ProjectPaths":
        """Build project paths relative to the repository root."""
        data_dir = base_dir / "data"
        results_dir = base_dir / "results"
        plots_dir = results_dir / "plots"
        tables_dir = results_dir / "tables"

        return cls(
            base_dir=base_dir,
            data=DataPaths(
                data_dir=data_dir,
                data_file=data_dir / "prices.csv",
            ),
            output=OutputPaths(
                results_dir=results_dir,
                plots_dir=plots_dir,
                tables_dir=tables_dir,
                summary_metrics_file=tables_dir / "summary_metrics.csv",
                grid_search_results_file=tables_dir / "grid_search_results.csv",
                test_metrics_file=tables_dir / "test_metrics.csv",
                plot_file=plots_dir / "strategy_vs_spy.png",
            ),
        )

    def ensure_directories(self) -> None:
        """Create required project directories if they do not exist."""
        self.data.ensure_directories()
        self.output.ensure_directories()


@dataclass(frozen=True)
class SignalParams:
    """Parameter set for regime-aware base signal generation."""

    z_window: int
    threshold: float
    use_vix: bool


@dataclass(frozen=True)
class CrashParams:
    """Parameter set for crash detection and overlay construction."""

    slow_window: int
    slow_threshold: float
    dd_window: int
    dd_threshold: float
    crash_weight: float


@dataclass(frozen=True)
class DataConfig:
    """Dataset boundaries and market data settings."""

    start_date: str
    train_end_date: str
    validation_end_date: str
    tickers: tuple[str, ...]
    trading_days: int = 252

    def validate(self) -> None:
        """Validate date ordering and dataset settings."""
        start = datetime.strptime(self.start_date, DATE_FORMAT)
        train_end = datetime.strptime(self.train_end_date, DATE_FORMAT)
        validation_end = datetime.strptime(self.validation_end_date, DATE_FORMAT)

        if not start < train_end < validation_end:
            raise ValueError(
                "Invalid date ordering: "
                f"{self.start_date} < {self.train_end_date} < "
                f"{self.validation_end_date} must hold."
            )

        if self.trading_days <= 0:
            raise ValueError("trading_days must be positive.")

        if not self.tickers:
            raise ValueError("tickers must be non-empty.")


@dataclass(frozen=True)
class FeatureFlags:
    """Feature toggles for model behavior."""

    use_vix_filter: bool = False


@dataclass(frozen=True)
class GridSearchSpace:
    """Hyperparameter search space for the strategy."""

    z_windows: tuple[int, ...]
    thresholds: tuple[float, ...]
    slow_windows: tuple[int, ...]
    slow_thresholds: tuple[float, ...]
    dd_windows: tuple[int, ...]
    dd_thresholds: tuple[float, ...]
    crash_weights: tuple[float, ...]

    @property
    def num_candidates(self) -> int:
        """Return the total number of grid-search parameter combinations."""
        return (
            len(self.z_windows)
            * len(self.thresholds)
            * len(self.slow_windows)
            * len(self.slow_thresholds)
            * len(self.dd_windows)
            * len(self.dd_thresholds)
            * len(self.crash_weights)
        )

    def validate(self) -> None:
        """Validate the hyperparameter search space."""
        if not self.z_windows:
            raise ValueError("z_windows must be non-empty.")
        if not self.thresholds:
            raise ValueError("thresholds must be non-empty.")
        if not self.slow_windows:
            raise ValueError("slow_windows must be non-empty.")
        if not self.slow_thresholds:
            raise ValueError("slow_thresholds must be non-empty.")
        if not self.dd_windows:
            raise ValueError("dd_windows must be non-empty.")
        if not self.dd_thresholds:
            raise ValueError("dd_thresholds must be non-empty.")
        if not self.crash_weights:
            raise ValueError("crash_weights must be non-empty.")

        if any(x <= 0 for x in self.z_windows):
            raise ValueError("z_windows must contain only positive integers.")
        if any(x <= 0 for x in self.thresholds):
            raise ValueError("thresholds must contain only positive values.")
        if any(x <= 0 for x in self.slow_windows):
            raise ValueError("slow_windows must contain only positive integers.")
        if any(x <= 0 for x in self.dd_windows):
            raise ValueError("dd_windows must contain only positive integers.")
        if any(x < 0 for x in self.crash_weights):
            raise ValueError("crash_weights must be non-negative.")


@dataclass(frozen=True)
class RegimeDefaults:
    """Default parameters for regime classification."""

    vix_window: int = 10
    momentum_window: int = 30
    realized_vol_window: int = 20
    realized_vol_avg_window: int = 100

    def validate(self) -> None:
        """Validate regime-classification defaults."""
        if self.vix_window < 2:
            raise ValueError("vix_window must be at least 2.")
        if self.momentum_window < 2:
            raise ValueError("momentum_window must be at least 2.")
        if self.realized_vol_window < 2:
            raise ValueError("realized_vol_window must be at least 2.")
        if self.realized_vol_avg_window < 2:
            raise ValueError("realized_vol_avg_window must be at least 2.")


@dataclass(frozen=True)
class SpreadDefaults:
    """Default parameters for the spread signal."""

    window: int = 20
    threshold: float = 1.5

    def validate(self) -> None:
        """Validate spread-signal defaults."""
        if self.window < 2:
            raise ValueError("spread window must be at least 2.")
        if self.threshold <= 0:
            raise ValueError("spread threshold must be positive.")


@dataclass(frozen=True)
class BollingerDefaults:
    """Default parameters for the Bollinger signal."""

    window: int = 20
    num_std: float = 2.0

    def validate(self) -> None:
        """Validate Bollinger-signal defaults."""
        if self.window < 2:
            raise ValueError("bollinger window must be at least 2.")
        if self.num_std <= 0:
            raise ValueError("bollinger num_std must be positive.")


@dataclass(frozen=True)
class ModelDefaults:
    """Default model settings outside the grid-search space."""

    regime: RegimeDefaults
    spread: SpreadDefaults
    bollinger: BollingerDefaults

    def validate(self) -> None:
        """Validate model defaults."""
        self.regime.validate()
        self.spread.validate()
        self.bollinger.validate()


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest and portfolio construction assumptions."""

    target_vol: float = 0.15
    vol_window: int = 20
    cost_per_unit: float = 0.0005
    crisis_drawdown_threshold: float = -0.10

    def validate(self) -> None:
        """Validate backtest assumptions."""
        if self.target_vol <= 0:
            raise ValueError("target_vol must be positive.")
        if self.vol_window < 2:
            raise ValueError("vol_window must be at least 2.")
        if self.cost_per_unit < 0:
            raise ValueError("cost_per_unit must be non-negative.")


@dataclass(frozen=True)
class DisplayConfig:
    """Human-readable labels and plot titles."""

    strategy_name: str
    plot_title: str

    def validate(self) -> None:
        """Validate display labels."""
        if not self.strategy_name.strip():
            raise ValueError("strategy_name must be non-empty.")
        if not self.plot_title.strip():
            raise ValueError("plot_title must be non-empty.")


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    paths: ProjectPaths
    data: DataConfig
    features: FeatureFlags
    grid: GridSearchSpace
    model: ModelDefaults
    backtest: BacktestConfig
    display: DisplayConfig

    def validate(self) -> None:
        """Validate the full application configuration."""
        self.paths.ensure_directories()
        self.data.validate()
        self.grid.validate()
        self.model.validate()
        self.backtest.validate()
        self.display.validate()


def build_config() -> AppConfig:
    """Construct the project configuration."""
    base_dir = Path(__file__).resolve().parent

    config = AppConfig(
        paths=ProjectPaths.from_base_dir(base_dir),
        data=DataConfig(
            start_date="2005-01-01",
            train_end_date="2015-01-01",
            validation_end_date="2020-01-01",
            tickers=("SPY", "TLT", "^VIX"),
            trading_days=252,
        ),
        features=FeatureFlags(
            use_vix_filter=False,
        ),
        grid=GridSearchSpace(
            z_windows=(10, 20, 30),
            thresholds=(1.5, 2.0, 2.5),
            slow_windows=(20, 40, 60),
            slow_thresholds=(-0.03, -0.05),
            dd_windows=(50, 100),
            dd_thresholds=(-0.03, -0.05),
            crash_weights=(0.2, 0.3, 0.4),
        ),
        model=ModelDefaults(
            regime=RegimeDefaults(
                vix_window=10,
                momentum_window=30,
                realized_vol_window=20,
                realized_vol_avg_window=100,
            ),
            spread=SpreadDefaults(
                window=20,
                threshold=1.5,
            ),
            bollinger=BollingerDefaults(
                window=20,
                num_std=2.0,
            ),
        ),
        backtest=BacktestConfig(
            target_vol=0.15,
            vol_window=20,
            cost_per_unit=0.0005,
            crisis_drawdown_threshold=-0.10,
        ),
        display=DisplayConfig(
            strategy_name="Regime-Aware SPY-TLT Allocation",
            plot_title="Regime-Aware SPY-TLT Allocation Strategy vs SPY",
        ),
    )
    config.validate()
    return config


CONFIG = build_config()


BASE_DIR = CONFIG.paths.base_dir

DATA_DIR = CONFIG.paths.data.data_dir
RESULTS_DIR = CONFIG.paths.output.results_dir
PLOTS_DIR = CONFIG.paths.output.plots_dir
TABLES_DIR = CONFIG.paths.output.tables_dir

DATA_PATH = CONFIG.paths.data.data_file
SUMMARY_METRICS_FILE = CONFIG.paths.output.summary_metrics_file
GRID_SEARCH_RESULTS_FILE = CONFIG.paths.output.grid_search_results_file
TEST_METRICS_FILE = CONFIG.paths.output.test_metrics_file
PLOT_FILENAME = CONFIG.paths.output.plot_file

START_DATE = CONFIG.data.start_date
TRAIN_END_DATE = CONFIG.data.train_end_date
VALIDATION_END_DATE = CONFIG.data.validation_end_date
TRADING_DAYS = CONFIG.data.trading_days
TICKERS = CONFIG.data.tickers

USE_VIX_FILTER = CONFIG.features.use_vix_filter

Z_WINDOWS = CONFIG.grid.z_windows
THRESHOLDS = CONFIG.grid.thresholds
SLOW_WINDOWS = CONFIG.grid.slow_windows
SLOW_THRESHOLDS = CONFIG.grid.slow_thresholds
DD_WINDOWS = CONFIG.grid.dd_windows
DD_THRESHOLDS = CONFIG.grid.dd_thresholds
CRASH_WEIGHTS = CONFIG.grid.crash_weights

VIX_WINDOW = CONFIG.model.regime.vix_window
MOMENTUM_WINDOW = CONFIG.model.regime.momentum_window
REALIZED_VOL_WINDOW = CONFIG.model.regime.realized_vol_window
REALIZED_VOL_AVG_WINDOW = CONFIG.model.regime.realized_vol_avg_window

SPREAD_WINDOW = CONFIG.model.spread.window
SPREAD_THRESHOLD = CONFIG.model.spread.threshold

BOLLINGER_WINDOW = CONFIG.model.bollinger.window
BOLLINGER_NUM_STD = CONFIG.model.bollinger.num_std

TARGET_VOL = CONFIG.backtest.target_vol
VOL_WINDOW = CONFIG.backtest.vol_window
COST_PER_UNIT = CONFIG.backtest.cost_per_unit
CRISIS_DRAWDOWN_THRESHOLD = CONFIG.backtest.crisis_drawdown_threshold

STRATEGY_NAME = CONFIG.display.strategy_name
PLOT_TITLE = CONFIG.display.plot_title
