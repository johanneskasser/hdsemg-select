import numpy as np
import pytest

from hdsemg_select.select_logic.fiber_trajectory import (
    FiberTrajectoryAnalyzer,
    FiberTrajectoryResult,
)


def _make_propagating_wave(
    rows: int,
    cols: int,
    fiber_angle_deg: float,
    cv_ms: float,
    fs: float,
    ied_mm: float,
    n_samples: int = 4096,
    iz_proj: float | None = None,
) -> np.ndarray:
    """Synthesise a clean monopolar signal array with a propagating MUAP.

    iz_proj: innervation zone position in projected IED units along the fiber.
             When set, the IZ fires first and the wave propagates outward in
             both directions (biphasic model).
    """
    ied_m = ied_mm * 1e-3
    angle_rad = np.radians(fiber_angle_deg)
    t = np.arange(n_samples) / fs

    # MUAP template: zero-mean Gaussian derivative
    t0 = 0.05  # s, pulse centre within signal
    sigma = 0.003  # s
    template = -(t - t0) / sigma**2 * np.exp(-((t - t0) ** 2) / (2 * sigma**2))

    signals = np.zeros((n_samples, rows * cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            proj = r * np.sin(angle_rad) + c * np.cos(angle_rad)
            if iz_proj is not None:
                # Biphasic: IZ fires first, wave propagates outward to both ends
                delay_s = abs(proj - iz_proj) * ied_m / cv_ms
            else:
                delay_s = proj * ied_m / cv_ms
            delay_samples = int(round(delay_s * fs))
            shifted = np.roll(template, delay_samples)
            ch_idx = r * cols + c
            signals[:, ch_idx] = shifted.astype(np.float32)

    return signals


def _simple_display_grid(rows: int, cols: int) -> np.ndarray:
    grid = np.arange(rows * cols, dtype=float).reshape(rows, cols)
    return grid


class FakeGrid:
    def __init__(self, rows: int, cols: int, ied_mm: float = 10.0):
        self.rows = rows
        self.cols = cols
        self.ied_mm = ied_mm
        self.emg_indices = list(range(rows * cols))


class TestFiberTrajectoryResult:
    def test_is_dataclass(self):
        r = FiberTrajectoryResult(
            fiber_angle_deg=15.0,
            conduction_velocity_ms=4.0,
            iz_position_m=None,
            r_squared=0.95,
            search_angles=np.linspace(-90, 90, 181),
            search_r2=np.zeros(181),
            pairwise_delays_ms=np.array([0.5, 1.0]),
            pairwise_distances_m=np.array([0.01, 0.02]),
        )
        assert r.fiber_angle_deg == 15.0
        assert r.conduction_velocity_ms == 4.0
        assert r.iz_position_m is None


class TestFiberTrajectoryAnalyzerCleanSignal:
    """Tests with clean synthetic propagating waves — tight tolerances."""

    def test_angle_recovery_0_degrees(self):
        rows, cols, angle, cv = 8, 8, 0.0, 4.0
        signals = _make_propagating_wave(rows, cols, angle, cv, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert abs(result.fiber_angle_deg - angle) <= 3.0

    def test_angle_recovery_20_degrees(self):
        rows, cols, angle, cv = 8, 8, 20.0, 4.0
        signals = _make_propagating_wave(rows, cols, angle, cv, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert abs(result.fiber_angle_deg - angle) <= 3.0

    def test_cv_recovery(self):
        rows, cols, angle, cv = 8, 8, 0.0, 4.0
        signals = _make_propagating_wave(rows, cols, angle, cv, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert abs(result.conduction_velocity_ms - cv) <= 0.5

    def test_r_squared_high_for_clean_signal(self):
        rows, cols = 8, 8
        signals = _make_propagating_wave(rows, cols, 0.0, 4.0, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert result.r_squared >= 0.80

    def test_iz_detection(self):
        rows, cols, angle, cv = 8, 8, 0.0, 4.0
        # IZ at projected position 3 (column 3 for 0° fiber), ied_mm=10mm → 0.03 m
        signals = _make_propagating_wave(
            rows, cols, angle, cv, fs=2048.0, ied_mm=10.0, iz_proj=3.0
        )
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        # Test IZ detection at the known fiber angle (bypasses angle search)
        analyzer = FiberTrajectoryAnalyzer()
        iz_pos = analyzer.detect_iz_at_angle(
            signals, grid, display_grid, fs=2048.0, angle_deg=0.0
        )
        assert iz_pos is not None
        expected_m = 3.0 * 0.01  # 3 IEDs × 10 mm
        assert abs(iz_pos - expected_m) <= 2 * 0.01

    def test_result_arrays_shape(self):
        rows, cols = 8, 8
        signals = _make_propagating_wave(rows, cols, 0.0, 4.0, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols, ied_mm=10.0)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert result.search_angles.shape == (181,)
        assert result.search_r2.shape == (181,)
        assert len(result.pairwise_delays_ms) == len(result.pairwise_distances_m)


class TestFiberTrajectoryAnalyzerEdgeCases:
    def test_raises_on_grid_too_small(self):
        signals = np.zeros((1024, 1))
        grid = FakeGrid(1, 1)
        display_grid = _simple_display_grid(1, 1)
        with pytest.raises(ValueError, match="too small"):
            FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)

    def test_no_iz_returns_none_when_no_reversal(self):
        rows, cols = 8, 8
        # Monotonic wave — no sign reversal expected at the correct angle
        signals = _make_propagating_wave(rows, cols, 0.0, 4.0, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols)
        display_grid = _simple_display_grid(rows, cols)
        analyzer = FiberTrajectoryAnalyzer()
        iz_pos = analyzer.detect_iz_at_angle(
            signals, grid, display_grid, fs=2048.0, angle_deg=0.0
        )
        assert iz_pos is None

    def test_nan_electrodes_skipped(self):
        rows, cols = 4, 4
        signals = _make_propagating_wave(rows, cols, 0.0, 4.0, fs=2048.0, ied_mm=10.0)
        grid = FakeGrid(rows, cols)
        display_grid = _simple_display_grid(rows, cols)
        # Blank out some positions
        display_grid[0, 0] = np.nan
        display_grid[3, 3] = np.nan
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        assert isinstance(result, FiberTrajectoryResult)

    def test_zero_line_channels_excluded(self):
        """Zero-line (dead) channels must not contaminate the analysis."""
        rows, cols, angle, cv = 8, 8, 0.0, 4.0
        signals = _make_propagating_wave(rows, cols, angle, cv, fs=2048.0, ied_mm=10.0)
        # Zero out the leftmost column — at 0° this is the anchor, worst-case position
        signals[:, 0:rows] = 0.0
        grid = FakeGrid(rows, cols)
        display_grid = _simple_display_grid(rows, cols)
        result = FiberTrajectoryAnalyzer().analyze(signals, grid, display_grid, fs=2048.0)
        # Analysis must still complete with a plausible angle and non-trivial R²
        assert abs(result.fiber_angle_deg - angle) <= 5.0
        assert result.r_squared >= 0.70
