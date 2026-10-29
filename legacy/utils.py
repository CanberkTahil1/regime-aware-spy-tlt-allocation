"""
Conditional normalization for the regime-aware SPY-TLT allocation framework.

This module normalizes portfolio weights outside crash periods while
preserving crash overlays when crash conditions are active.
"""

import pandas as pd

from config import POSITION_COLUMNS


def apply_conditional_normalization(
    signals: pd.DataFrame,
    crash_mask: pd.Series,
) -> pd.DataFrame:
    """
    Normalize portfolio weights outside crash periods.

    Non-crash rows are scaled to unit gross exposure. Crash rows are left
    unchanged so that defensive overlays remain intact.

    Args:
        signals: DataFrame containing 'SPY_pos' and 'TLT_pos' columns.
        crash_mask: Boolean Series aligned with `signals.index`. True denotes
            a crash period and skips normalization.

    Returns:
        DataFrame indexed like `signals` with normalized non-crash rows and
        unchanged crash rows.

    Raises:
        KeyError: If required position columns are missing.
        ValueError: If `crash_mask` is not aligned with `signals`.
        TypeError: If `crash_mask` is not a pandas Series.

    Notes:
        Gross exposure is defined as |SPY_pos| + |TLT_pos|. Rows with zero
        gross exposure remain numerically stable by replacing the divisor
        with 1.0.
    """
    _validate_inputs(signals, crash_mask)

    normalized = signals.copy()
    non_crash_mask = ~crash_mask.astype(bool)

    gross_exposure = normalized[list(POSITION_COLUMNS)].abs().sum(axis=1)
    gross_exposure = gross_exposure.replace(0, 1.0)

    normalized.loc[non_crash_mask, list(POSITION_COLUMNS)] = (
        normalized.loc[non_crash_mask, list(POSITION_COLUMNS)]
        .div(gross_exposure.loc[non_crash_mask], axis=0)
        .to_numpy()
    )

    return normalized


def _validate_inputs(
    signals: pd.DataFrame,
    crash_mask: pd.Series,
) -> None:
    """
    Validate inputs for conditional normalization.

    Args:
        signals: Position DataFrame.
        crash_mask: Crash-regime indicator aligned with `signals.index`.

    Raises:
        TypeError: If `crash_mask` is not a pandas Series.
        KeyError: If required columns are missing.
        ValueError: If the index of `crash_mask` does not match `signals`.
    """
    if not isinstance(crash_mask, pd.Series):
        raise TypeError("crash_mask must be a pandas Series.")

    missing_cols = set(POSITION_COLUMNS) - set(signals.columns)
    if missing_cols:
        raise KeyError(f"Missing required columns: {sorted(missing_cols)}")

    if not signals.index.equals(crash_mask.index):
        raise ValueError("crash_mask index must exactly match signals index.")
