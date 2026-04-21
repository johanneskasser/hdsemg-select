import math
from typing import Optional

import numpy as np


def ms_to_samples(ms: float, fs: float) -> int:
    """Convert a duration in milliseconds to a sample count."""
    return max(1, round(ms * fs / 1000.0))


def compute_arv_window(
    data: np.ndarray,
    center_sample: int,
    window_samples: int,
) -> np.ndarray:
    """Return the ARV vector for a centered window around *center_sample*.

    data:            shape (n_samples, n_channels)
    center_sample:   0-based index into the sample axis
    window_samples:  total number of samples in the window (clamped at boundaries)

    Returns a 1-D array of length n_channels.
    """
    half = window_samples // 2
    start = max(0, center_sample - half)
    end = min(data.shape[0], center_sample + half + 1)
    if start >= end:
        return np.zeros(data.shape[1], dtype=float)
    return np.mean(np.abs(data[start:end, :]), axis=0)


def channels_to_grid(
    arv_values: np.ndarray,
    display_grid: np.ndarray,
    emg_indices: list,
) -> np.ndarray:
    """Map per-channel ARV values onto the physical electrode grid.

    display_grid:  (rows, cols) float array; each cell is a 0-based *local*
                   electrode index within the grid, or NaN for empty cells.
    emg_indices:   list mapping local electrode index → column in the data array.

    Returns a (rows, cols) float array with NaN for empty positions.
    """
    rows, cols = display_grid.shape
    result = np.full((rows, cols), np.nan, dtype=float)
    for r in range(rows):
        for c in range(cols):
            local = display_grid[r, c]
            if math.isnan(local):
                continue
            idx = int(local)
            if idx < len(emg_indices):
                data_col = emg_indices[idx]
                if data_col < len(arv_values):
                    result[r, c] = arv_values[data_col]
    return result
