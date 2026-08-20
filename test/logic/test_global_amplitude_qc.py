"""Tests for the global amplitude QC step.

The signals here are synthetic on purpose: a trapezoid burst on top of a
known noise floor, so the activation ratio has an answer that can be
checked rather than eyeballed.
"""

import numpy as np
import pytest

from hdsemg_select.select_logic.global_amplitude_qc import (
    BORDERLINE,
    FAIL,
    NOT_AVAILABLE,
    PASS,
    ChannelQC,
    QCThresholds,
    QCWindows,
    build_emg_map,
    detect_windows,
    grade_channel,
    analyze,
)

FS = 2000.0
ROWS, COLS = 8, 8
N_CHANNELS = ROWS * COLS


class _Grid:
    """The parts of a hdsemg-shared Grid this module touches."""

    def __init__(self, emg_indices, rows=ROWS, cols=COLS, key="Grid_1"):
        self.emg_indices = list(emg_indices)
        self.rows = rows
        self.cols = cols
        self.grid_key = key
        self.ied_mm = 8.0


def _display_grid(rows=ROWS, cols=COLS):
    return np.arange(rows * cols, dtype=float).reshape(rows, cols)


def _force(n_samples, fs, rest_s=6.0, ramp_s=3.0, hold_s=6.0):
    """A trapezoid: rest, ramp up, hold, ramp down, rest."""
    t = np.arange(n_samples) / fs
    force = np.zeros(n_samples)
    up = (t >= rest_s) & (t < rest_s + ramp_s)
    hold = (t >= rest_s + ramp_s) & (t < rest_s + ramp_s + hold_s)
    down = (t >= rest_s + ramp_s + hold_s) & (t < rest_s + 2 * ramp_s + hold_s)
    force[up] = 30.0 * (t[up] - rest_s) / ramp_s
    force[hold] = 30.0
    force[down] = 30.0 * (1 - (t[down] - rest_s - ramp_s - hold_s) / ramp_s)
    return force


def _trial(activation=3.0, n_channels=N_CHANNELS, duration_s=30.0, seed=0):
    """(data, time, force) with the burst `activation` times the noise floor.

    Broadband noise at every channel, amplitude-modulated by the force
    envelope inside the band the global amplitude measures.
    """
    rng = np.random.default_rng(seed)
    n_samples = int(duration_s * FS)
    t = np.arange(n_samples) / FS
    force = _force(n_samples, FS)
    envelope = 1.0 + (activation - 1.0) * (force / 30.0)

    data = np.empty((n_samples, n_channels + 1))
    for channel in range(n_channels):
        carrier = rng.standard_normal(n_samples)
        # Push the energy into 15-450 Hz so the band-pass keeps it.
        carrier += 0.5 * np.sin(2 * np.pi * 90.0 * t + rng.uniform(0, 2 * np.pi))
        data[:, channel] = 10.0 * carrier * envelope
    data[:, n_channels] = force  # the performed path, last column
    return data, t, force


# ----------------------------------------------------------------------
# Grid plumbing
# ----------------------------------------------------------------------

def test_build_emg_map_is_columns_by_rows_with_global_channels():
    grid = _Grid(range(N_CHANNELS))
    emg_map = build_emg_map(grid, _display_grid(), None)

    assert emg_map.shape == (COLS, ROWS)
    # display_grid[row, col] holds the local index; the map is transposed.
    assert emg_map[3, 2] == _display_grid()[2, 3]
    assert not np.any(np.isnan(emg_map))


def test_build_emg_map_puts_nan_at_deselected_positions():
    grid = _Grid(range(N_CHANNELS))
    status = [True] * N_CHANNELS
    status[5] = False

    emg_map = build_emg_map(grid, _display_grid(), status)

    assert np.count_nonzero(np.isnan(emg_map)) == 1
    assert 5.0 not in emg_map[~np.isnan(emg_map)]


def test_build_emg_map_keeps_unwired_positions_empty():
    """A 5x13 electrode with 64 channels has one position with no electrode."""
    display = np.arange(65, dtype=float).reshape(5, 13)
    display[4, 12] = np.nan
    grid = _Grid(range(64), rows=5, cols=13)

    emg_map = build_emg_map(grid, display, None)

    assert np.isnan(emg_map[12, 4])
    assert np.count_nonzero(~np.isnan(emg_map)) == 64


# ----------------------------------------------------------------------
# Windowing
# ----------------------------------------------------------------------

def test_detect_windows_finds_rest_on_both_sides_of_the_burst():
    data, _, force = _trial()
    amplitude = np.abs(data[:, 0])

    windows = detect_windows(force, amplitude, FS)

    assert windows.source == "force"
    assert len(windows.rest) == 2
    assert windows.rest[0][0] == 0
    assert windows.rest[-1][1] == amplitude.size


def test_detect_windows_puts_the_peak_outside_rest():
    data, _, force = _trial()
    amplitude = np.abs(data[:, 0])

    windows = detect_windows(force, amplitude, FS, peak_ms=250.0)

    start, stop = windows.peak
    assert stop - start == int(round(0.250 * FS))
    assert not windows.rest_mask(amplitude.size)[start:stop].any()


def test_detect_windows_falls_back_to_the_edges_without_a_reference():
    _, _, _ = _trial()
    amplitude = np.ones(int(10 * FS))

    windows = detect_windows(None, amplitude, FS, fallback_s=3.0)

    assert windows.source == "fallback"
    assert len(windows.rest) == 2


def test_detect_windows_ignores_rest_stretches_that_are_too_short():
    """A brief dip inside a contraction must not become the noise floor."""
    n_samples = int(20 * FS)
    force = np.full(n_samples, 30.0)
    force[:int(5 * FS)] = 0.0
    force[int(10 * FS):int(10.2 * FS)] = 0.0  # a 200 ms dip

    windows = detect_windows(force, np.ones(n_samples), FS, min_rest_s=2.0)

    assert len(windows.rest) == 1
    assert windows.rest[0] == (0, int(5 * FS))


# ----------------------------------------------------------------------
# Grading
# ----------------------------------------------------------------------

def _values(**overrides):
    healthy = {
        "activation_ratio": 3.0,
        "amplitude_z": 0.2,
        "spectrum_z": 0.1,
        "line_noise": 1.4,
        "clipping": 0.0,
        "neighbor_correlation": 0.8,
        "flat": False,
    }
    healthy.update(overrides)
    return healthy


def test_a_healthy_channel_passes_every_check():
    channel = grade_channel(7, _values(), QCThresholds())

    assert channel.grade == PASS
    assert channel.cqi == 100
    assert channel.worst_check is None


def test_the_grade_is_the_worst_check_not_the_average():
    """Six healthy checks must not average away one fatal one."""
    channel = grade_channel(7, _values(line_noise=50.0), QCThresholds())

    assert channel.grade == FAIL
    assert channel.worst_check == "line_noise"
    assert channel.cqi > 0  # the other six still score


def test_a_value_between_the_bounds_is_borderline():
    channel = grade_channel(7, _values(activation_ratio=1.35), QCThresholds())

    assert channel.states["activation_ratio"] == BORDERLINE
    assert channel.grade == BORDERLINE


def test_a_flat_channel_fails_outright():
    channel = grade_channel(7, _values(flat=True, activation_ratio=9.0), QCThresholds())

    assert channel.grade == FAIL
    assert channel.cqi == 0
    assert channel.worst_check == "flat"


def test_a_missing_measurement_is_not_a_failure():
    channel = grade_channel(7, _values(neighbor_correlation=None), QCThresholds())

    assert channel.states["neighbor_correlation"] == NOT_AVAILABLE
    assert channel.grade == PASS


def test_a_disabled_check_is_not_graded():
    thresholds = QCThresholds(enabled={"line_noise": False})
    channel = grade_channel(7, _values(line_noise=50.0), thresholds)

    assert "line_noise" not in channel.states
    assert channel.grade == PASS


def test_cqi_ranks_a_worse_channel_below_a_better_one():
    thresholds = QCThresholds()
    better = grade_channel(1, _values(activation_ratio=1.45), thresholds)
    worse = grade_channel(2, _values(activation_ratio=1.25), thresholds)

    assert better.cqi > worse.cqi


# ----------------------------------------------------------------------
# End to end
# ----------------------------------------------------------------------

def test_a_strong_contraction_passes_the_activation_check():
    data, time, _ = _trial(activation=3.0)
    grid = _Grid(range(N_CHANNELS))

    result = analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                     QCThresholds(), derivation="MP", reference_index=N_CHANNELS)

    assert result.windows.source == "force"
    assert result.activation_ratio > 2.0
    assert result.verdict == PASS


def test_a_contraction_that_never_leaves_the_noise_floor_fails():
    data, time, _ = _trial(activation=1.05)
    grid = _Grid(range(N_CHANNELS))

    result = analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                     QCThresholds(), derivation="MP", reference_index=N_CHANNELS)

    assert result.activation_ratio < 1.20
    assert result.verdict == FAIL


def test_the_derivation_reaches_hdsemg_shared():
    """DD differences twice down a column, so it must not equal MP."""
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    status = [True] * (N_CHANNELS + 1)

    monopolar = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                        derivation="MP", reference_index=N_CHANNELS)
    double = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                     derivation="DD", reference_index=N_CHANNELS)

    assert double.n_channels < monopolar.n_channels
    assert not np.allclose(monopolar.amplitude, double.amplitude)


def test_deselected_channels_do_not_reach_the_global_amplitude():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    status = [True] * (N_CHANNELS + 1)
    for channel in range(10):
        status[channel] = False

    result = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                     derivation="MP", reference_index=N_CHANNELS)

    assert result.n_selected == N_CHANNELS - 10
    assert result.n_grid_channels == N_CHANNELS


def test_a_grid_with_nothing_selected_raises_and_points_at_the_way_out():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    status = [False] * (N_CHANNELS + 1)

    with pytest.raises(ValueError, match="all channels"):
        analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                channel_scope="selected", derivation="MP",
                reference_index=N_CHANNELS)


def test_scope_all_measures_a_grid_that_has_no_selection_yet():
    """A file straight off disk has every EMG channel deselected — QC is the
    step that informs a selection, so it must run before one exists."""
    data, time, _ = _trial(activation=3.0)
    grid = _Grid(range(N_CHANNELS))
    status = [False] * (N_CHANNELS + 1)

    result = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                     channel_scope="all", derivation="MP",
                     reference_index=N_CHANNELS)

    assert result.channel_scope == "all"
    assert result.n_selected == N_CHANNELS
    assert result.verdict == PASS


def test_scope_all_ignores_the_selection_entirely():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    status = [True] * (N_CHANNELS + 1)
    for channel in range(20):
        status[channel] = False

    selected = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                       channel_scope="selected", derivation="MP",
                       reference_index=N_CHANNELS)
    every = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                    channel_scope="all", derivation="MP",
                    reference_index=N_CHANNELS)

    assert selected.n_selected == N_CHANNELS - 20
    assert every.n_selected == N_CHANNELS
    assert not np.allclose(selected.amplitude, every.amplitude)


def test_an_unknown_scope_is_rejected():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))

    with pytest.raises(ValueError, match="channel_scope"):
        analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                QCThresholds(), channel_scope="everything", derivation="MP")


def test_a_mostly_deselected_grid_gets_no_verdict():
    """A verdict on a selection is not a verdict on a grid."""
    data, time, _ = _trial(activation=3.0)
    grid = _Grid(range(N_CHANNELS))
    status = [True] * (N_CHANNELS + 1)
    for channel in range(N_CHANNELS - 8):
        status[channel] = False

    result = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                     channel_scope="selected", derivation="MP",
                     reference_index=N_CHANNELS)

    assert result.verdict == NOT_AVAILABLE
    assert np.isfinite(result.activation_ratio)  # the number is still measured


def test_every_grid_channel_is_graded_including_deselected_ones():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    status = [True] * (N_CHANNELS + 1)
    status[3] = False

    result = analyze(data, time, FS, grid, _display_grid(), status, QCThresholds(),
                     derivation="MP", reference_index=N_CHANNELS)

    assert len(result.channels) == N_CHANNELS
    assert {channel.channel_index for channel in result.channels} == set(range(N_CHANNELS))


def test_a_dead_channel_is_found_and_fails():
    data, time, _ = _trial()
    data[:, 17] = 0.0
    grid = _Grid(range(N_CHANNELS))

    result = analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                     QCThresholds(), derivation="MP", reference_index=N_CHANNELS)

    dead = next(c for c in result.channels if c.channel_index == 17)
    assert dead.grade == FAIL
    assert dead.worst_check == "flat"


def test_mains_pickup_is_found_on_the_channel_carrying_it():
    data, time, _ = _trial()
    t = time
    data[:, 21] += 400.0 * np.sin(2 * np.pi * 50.0 * t)
    grid = _Grid(range(N_CHANNELS))

    result = analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                     QCThresholds(), derivation="MP", reference_index=N_CHANNELS)

    noisy = next(c for c in result.channels if c.channel_index == 21)
    assert noisy.values["line_noise"] > 20.0
    assert noisy.states["line_noise"] == FAIL


def test_supplied_windows_are_used_instead_of_detection():
    data, time, _ = _trial()
    grid = _Grid(range(N_CHANNELS))
    windows = QCWindows(rest=[(0, int(2 * FS))], peak=(int(12 * FS), int(12.25 * FS)),
                        source="manual")

    result = analyze(data, time, FS, grid, _display_grid(), [True] * (N_CHANNELS + 1),
                     QCThresholds(), derivation="MP", reference_index=N_CHANNELS,
                     windows=windows)

    assert result.windows.source == "manual"
    assert result.windows.peak == (int(12 * FS), int(12.25 * FS))
