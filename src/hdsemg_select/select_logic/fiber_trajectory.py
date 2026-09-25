from __future__ import annotations

import numpy as np
from hdsemg_shared.quality.propagation import PropagationResult, propagation

# Kept as an alias so callers can keep annotating with the local name.
FiberTrajectoryResult = PropagationResult


class FiberTrajectoryAnalyzer:
    """Thin adapter from hdsemg-select's grid layout to
    ``hdsemg_shared.quality.propagation.propagation()``.

    The direction is the one whose adjacent-bin delays (single differential)
    are most consistent; R² of the old anchor regression is only reported.
    """

    def analyze(
        self,
        signals: np.ndarray,
        grid,
        display_grid: np.ndarray,
        fs: float,
        angles: np.ndarray | None = None,
    ) -> PropagationResult:
        """Run the shared propagation measurement on one grid.

        Parameters
        ----------
        signals:      (n_samples, n_channels) monopolar EMG
        grid:         object with .ied_mm and .emg_indices
        display_grid: (rows, cols) array of local electrode indices; NaN = empty
        fs:           sampling rate in Hz
        angles:       directions to search, default -90..90 deg
        """
        rows, cols = display_grid.shape
        if rows < 2 and cols < 2:
            raise ValueError(
                f"Grid too small for propagation analysis ({rows}×{cols}); "
                "need at least 2 electrodes in one direction."
            )
        return propagation(
            np.asarray(signals).T,
            self._emg_map(grid, display_grid, np.shape(signals)[1]),
            ied_mm=float(grid.ied_mm),
            fs=float(fs),
            angles=angles,
        )

    @staticmethod
    def _emg_map(grid, display_grid: np.ndarray, n_channels: int) -> np.ndarray:
        """Global channel number per (row, col), NaN where nothing is placed.

        The map is passed with outer index = display row, inner = display
        column. shared projects outer*sin(θ) + inner*cos(θ), which is exactly
        the r*sin(θ) + c*cos(θ) convention the dialog draws, so the angle
        needs no conversion.
        """
        emg_indices = grid.emg_indices
        emg_map = np.full(display_grid.shape, np.nan)
        for (r, c), cell in np.ndenumerate(display_grid):
            if np.isnan(cell) or int(cell) >= len(emg_indices):
                continue
            ch = emg_indices[int(cell)]
            if ch < n_channels:
                emg_map[r, c] = ch
        return emg_map
