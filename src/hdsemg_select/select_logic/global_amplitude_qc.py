"""Global amplitude quality control for HD-sEMG grids.

Answers two questions about a recording:

* **Did this grid record physiological signal during the contraction?**
  The global amplitude at the peak of the contraction, over the global
  amplitude at rest — the activation ratio.
* **Which channels contributed?** Seven measured numbers per channel, each
  turned into a pass/borderline/fail state by a configurable threshold.

Every measurement comes from ``hdsemg_shared``; nothing here computes EMG
maths of its own. What this module owns is the *plumbing* — turning a
hdsemg-select ``Grid`` plus the current channel selection into the
``emg_map`` the shared functions expect — and the *thresholds*, which are
deliberately not the shared library's business: where a threshold sits
depends on the muscle, the electrode, the task and the population.

References
----------
Merletti R, Cerone GL. Techniques for information extraction from the
    surface EMG signal, eq. 5.1-5.2. In: Merletti & Farina (2016/2018).
Del Vecchio A et al. J Appl Physiol (2025).
    doi:10.1152/japplphysiol.00810.2024
Detection and Reconstruction of Poor-Quality Channels in High-Density EMG
    Array Measurements. Sensors 23(10):4759 (2023).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from hdsemg_shared.filters.bandpass import bandpass_filter_exact_corners
from hdsemg_shared.filters.padding import pad_samples, reflect_pad, trim_pad
from hdsemg_shared.global_parameters import global_amplitude
from hdsemg_shared.preprocessing.grid_map import map_to_columns

try:  # hdsemg-shared declares the unit from 0.14.3 on (shared#53, #54)
    from hdsemg_shared.fileio.units import conversion_factor, normalize_unit
    _SHARED_UNITS = True
except ImportError:  # older release: fall back to the table below
    _SHARED_UNITS = False
from hdsemg_shared.quality import (
    propagation,
    channel_amplitude,
    channel_spectrum,
    clipping_fraction,
    flat_channels,
    line_noise_ratio,
    neighbor_correlation,
    robust_z,
)

from hdsemg_select._log.log_config import logger

#: Microvolts per unit. Only used when hdsemg-shared is too old to convert;
#: it is the same table shared's units module owns.
UNIT_TO_UV = {"V": 1e6, "mV": 1e3, "uV": 1.0, "µV": 1.0, "μV": 1.0}

#: Arbitrary units cannot be converted, by definition.
ARBITRARY_UNIT = "a.u."

#: The unit assumed when the file declares none. OTB loaders return
#: millivolts, which is what every recording this tool has seen carries.
ASSUMED_UNIT = "mV"

#: What a resting global amplitude plausibly is, in microvolts. Wide on
#: purpose: this catches a factor of 1000, not a factor of 2. A quiet
#: recording sits near 5 uV and a noisy one near 50; nothing physiological
#: rests below 0.5 uV or above 500.
PLAUSIBLE_REST_UV = (0.5, 500.0)

PASS = "pass"
BORDERLINE = "borderline"
FAIL = "fail"
NOT_AVAILABLE = "n/a"

#: Worst-first, so `max(states, key=_SEVERITY.get)` picks the grade.
_SEVERITY = {NOT_AVAILABLE: 0, PASS: 1, BORDERLINE: 2, FAIL: 3}

#: The seven checks, in the order they are reported.
CHECKS = (
    "activation_ratio",
    "amplitude_z",
    "spectrum_z",
    "line_noise",
    "clipping",
    "neighbor_correlation",
    "flat",
)

#: Human-readable names, used by the dialogs and the exported report.
CHECK_LABELS = {
    "activation_ratio": "Activation ratio",
    "amplitude_z": "Amplitude robust z",
    "spectrum_z": "Spectrum robust z (MNF)",
    "line_noise": "Line-noise ratio",
    "clipping": "Clipping fraction",
    "neighbor_correlation": "Neighbour correlation",
    "flat": "Flat (dead channel)",
}

#: How many times the grid is differenced for each derivation.
_DERIVATION_ORDER = {"MP": 0, "SD": 1, "DD": 2}

#: Which grid axis SD/DD difference along. 'cols' walks DOWN a column.
_DIFF_AXIS = {"cols": 1, "rows": 0}

#: Which direction is good. "up" means a larger value is better.
_DIRECTION = {
    "activation_ratio": "up",
    "amplitude_z": "down",
    "spectrum_z": "down",
    "line_noise": "down",
    "clipping": "down",
    "neighbor_correlation": "up",
}


@dataclass(frozen=True)
class QCThresholds:
    """Where each measured number becomes a verdict.

    ``*_pass`` is the value at which a check is fully satisfied and
    ``*_fail`` the value at which it is fully failed; between the two the
    check is borderline and its sub-score ramps linearly. Weights rank the
    channel list and never decide a grade.
    """

    activation_pass: float = 1.50
    activation_fail: float = 1.20
    amplitude_z_pass: float = 3.5
    amplitude_z_fail: float = 5.0
    spectrum_z_pass: float = 3.5
    spectrum_z_fail: float = 5.0
    line_noise_pass: float = 5.0
    line_noise_fail: float = 20.0
    clipping_pass: float = 0.001
    clipping_fail: float = 0.010
    neighbor_pass: float = 0.40
    neighbor_fail: float = 0.20

    grid_pass: float = 1.50
    grid_borderline: float = 1.30
    min_channel_fraction: float = 0.50

    weights: dict = field(default_factory=lambda: {
        "activation_ratio": 0.30,
        "amplitude_z": 0.15,
        "spectrum_z": 0.10,
        "line_noise": 0.15,
        "clipping": 0.10,
        "neighbor_correlation": 0.20,
    })
    enabled: dict = field(default_factory=lambda: {check: True for check in CHECKS})

    def bounds(self, check: str) -> tuple:
        """(pass_at, fail_at) for one check."""
        return {
            "activation_ratio": (self.activation_pass, self.activation_fail),
            "amplitude_z": (self.amplitude_z_pass, self.amplitude_z_fail),
            "spectrum_z": (self.spectrum_z_pass, self.spectrum_z_fail),
            "line_noise": (self.line_noise_pass, self.line_noise_fail),
            "clipping": (self.clipping_pass, self.clipping_fail),
            "neighbor_correlation": (self.neighbor_pass, self.neighbor_fail),
        }[check]


@dataclass(frozen=True)
class AmplitudeUnit:
    """How raw amplitudes turn into microvolts, and how sure we are.

    ``source`` is 'file' when EMGFile declared the unit, 'assumed' when it
    did not. ``warning`` is set when the resulting microvolt value is not
    physiologically plausible, which is what a silent factor of 1000 looks
    like from the outside.
    """

    label: str
    scale: float
    source: str
    warning: Optional[str] = None

    def to_uv(self, value):
        """A raw amplitude in microvolts, or None."""
        if value is None or not np.isfinite(value):
            return None
        return float(value) * self.scale


def resolve_amplitude_unit(declared, resting_floor) -> AmplitudeUnit:
    """Work out the amplitude unit, and check the answer is plausible.

    ``declared`` is ``EMGFile.unit`` — one of the canonical units, or None
    when the format declared nothing. The conversion itself belongs to
    hdsemg-shared, so it is used when available rather than duplicated.

    The resting floor is the test value: it is the most stable number the
    QC step produces and the one with the tightest physiological range.
    """
    label = _canonical(declared) if declared else None
    source = "file" if label else "assumed"
    if label is None:
        if declared:
            # The file said something the library does not recognise.
            return AmplitudeUnit(
                str(declared), 1.0, "file",
                f"The file declares its amplitude unit as {str(declared)!r}, which "
                f"hdsemg-shared does not recognise. Amplitudes are shown in that "
                f"unit unconverted; the activation ratio is unaffected because it "
                f"is a ratio."
            )
        label = ASSUMED_UNIT

    if label == ARBITRARY_UNIT:
        return AmplitudeUnit(
            label, 1.0, source,
            "The file declares arbitrary units, which cannot be converted to "
            "microvolts. Amplitudes are shown as recorded; the activation ratio "
            "is unaffected because it is a ratio."
        )

    scale = _scale_to_uv(label)
    if scale is None:
        return AmplitudeUnit(
            label, 1.0, source,
            f"No conversion from {label!r} to microvolts is available. Amplitudes "
            f"are shown as recorded; the activation ratio is unaffected."
        )

    warning = None
    if resting_floor is not None and np.isfinite(resting_floor) and resting_floor > 0:
        in_uv = resting_floor * scale
        low, high = PLAUSIBLE_REST_UV
        if not (low <= in_uv <= high):
            better = _plausible_alternative(resting_floor)
            suggestion = (f" A resting floor of "
                          f"{resting_floor * _scale_to_uv(better):.2f} uV "
                          f"would follow from {better}.") if better else ""
            warning = (
                f"Reading the data as {label} puts the resting floor at {in_uv:.4g} uV, "
                f"outside the plausible {low:g}-{high:g} uV.{suggestion} "
                f"The activation ratio is a ratio and is unaffected, but the absolute "
                f"amplitudes and the µV figures in the JSON would be wrong."
            )
            if source == "assumed":
                warning += (" The file declared no unit, so millivolts were "
                            "assumed.")
    return AmplitudeUnit(label, scale, source, warning)


def _canonical(declared):
    """The declared unit as one of the canonical spellings, or None."""
    if _SHARED_UNITS:
        return normalize_unit(declared)
    text = str(declared).strip()
    for known in UNIT_TO_UV:
        if text.lower() == known.lower():
            return "uV" if known in ("µV", "μV") else known
    return ARBITRARY_UNIT if text.lower() in ("a.u.", "au", "a.u") else None


def _scale_to_uv(label):
    """Microvolts per unit of `label`, from hdsemg-shared when it can."""
    if _SHARED_UNITS:
        try:
            return float(conversion_factor(label, "uV"))
        except ValueError:
            return None
    return UNIT_TO_UV.get(label)


def _plausible_alternative(resting_floor):
    """The unit that would make this resting floor physiological, if any."""
    low, high = PLAUSIBLE_REST_UV
    for candidate in ("uV", "mV", "V"):
        scale = _scale_to_uv(candidate)
        if scale and low <= resting_floor * scale <= high:
            return candidate
    return None


#: Below this propagation score the measured direction means nothing —
#: hdsemg-shared's own threshold for a trustworthy estimate.
TRUSTWORTHY_PROPAGATION = 0.5

#: A measured angle within this of the column axis still counts as "columns".
_AXIS_BOUNDARY_DEG = 45.0

#: Seconds of contraction used to measure the propagation direction. The
#: 250 ms peak window is far too short for it — on one real trial it read
#: 0 deg over 250 ms and -72 deg over 4.5 s, both at a score below 0.5.
#: Capped rather than using the whole contraction, which is slow.
DIRECTION_WINDOW_S = 4.0


@dataclass(frozen=True)
class FibreDirection:
    """Which way the action potentials actually travel across this grid.

    Advisory only. The researcher applied the electrodes and knows how the
    grid is aligned; a single trial's estimate does not overrule that, which
    is why nothing here changes the difference axis by itself.
    """

    angle_deg: float
    score: float
    cv_ms: float
    cv_status: str
    axis: str

    @property
    def trustworthy(self) -> bool:
        return bool(np.isfinite(self.score) and self.score >= TRUSTWORTHY_PROPAGATION)

    def disagrees_with(self, chosen_axis: str) -> bool:
        """True only when the estimate is worth listening to and differs."""
        return self.trustworthy and self.axis != chosen_axis

    def describe(self) -> str:
        confidence = ("reliable" if self.trustworthy
                      else "not reliable on this trial")
        return (f"measured fibre direction {self.angle_deg:.0f}\u00b0 "
                f"\u2192 {self.axis}, score {self.score:.2f} ({confidence})")


def measure_fibre_direction(data, grid, display_grid, fs, window=None,
                            ied_mm=None) -> Optional[FibreDirection]:
    """Measure the propagation direction, or None when it cannot be measured.

    0 degrees is the map's column axis, which is what ``diff_direction`` of
    'cols' differences along; +-90 is the row axis. Merletti, Vieira &
    Farina (2016), ch. 5, name the two cases longitudinal (along the fibres)
    and transversal, and the distinction is what makes an SD/DD channel
    represent a travelling action potential rather than cancel it.
    """
    spacing = ied_mm if ied_mm is not None else getattr(grid, "ied_mm", None)
    if not spacing:
        return None

    grid_channels = [ch for ch in grid.emg_indices if ch is not None]
    if not grid_channels:
        return None
    global_to_local = {ch: i for i, ch in enumerate(grid_channels)}
    sub = np.asarray(data[:, grid_channels], dtype=np.float64).T
    emg_map = _remap(build_emg_map(grid, display_grid, None), global_to_local)

    try:
        result = propagation(sub, emg_map, ied_mm=float(spacing), fs=fs,
                             window=window)
    except Exception as exc:  # noqa: BLE001 - advisory only, never fatal
        logger.info("Fibre direction not measurable: %s", exc)
        return None

    angle = float(result.fiber_angle_deg)
    from_column_axis = min(abs(angle), 180.0 - abs(angle))
    return FibreDirection(
        angle_deg=angle,
        score=float(result.propagation_score),
        cv_ms=float(result.cv_reported_ms),
        cv_status=str(result.cv_status),
        axis="cols" if from_column_axis <= _AXIS_BOUNDARY_DEG else "rows",
    )


@dataclass(frozen=True)
class QCWindows:
    """The rest and peak windows every measurement is taken inside.

    ``rest`` holds one or more (start, stop) sample-index pairs, stop
    exclusive. ``source`` is 'force' when the reference channel drove the
    segmentation, 'fallback' when there was no usable reference and the
    first and last seconds were used instead, or 'manual' after the user
    dragged them on the plot.
    """

    rest: list
    peak: tuple
    source: str

    def rest_mask(self, n_samples: int) -> np.ndarray:
        mask = np.zeros(n_samples, dtype=bool)
        for start, stop in self.rest:
            mask[start:stop] = True
        return mask

    def peak_mask(self, n_samples: int) -> np.ndarray:
        mask = np.zeros(n_samples, dtype=bool)
        mask[self.peak[0]:self.peak[1]] = True
        return mask


@dataclass(frozen=True)
class ChannelQC:
    """One channel's evidence and the verdict derived from it."""

    channel_index: int
    values: dict
    states: dict
    grade: str
    cqi: int
    worst_check: Optional[str]

    @property
    def selected_for_deselection(self) -> bool:
        return self.grade == FAIL


@dataclass(frozen=True)
class GlobalAmplitudeQCResult:
    """Everything the dialog draws and everything the JSON stores."""

    grid_key: str
    derivation: str
    method: str
    diff_direction: str

    time: np.ndarray
    amplitude: np.ndarray
    ref_signal: Optional[np.ndarray]
    ref_index: Optional[int]
    ref_label: str

    windows: QCWindows
    resting_floor: float
    peak_mean: float
    activation_ratio: float
    verdict: str

    n_channels: int
    n_selected: int
    n_grid_channels: int
    channel_scope: str
    channels: list
    thresholds: QCThresholds
    unit: AmplitudeUnit
    fibre: Optional[FibreDirection] = None

    @property
    def grades(self) -> dict:
        """How many channels landed in each grade."""
        counts = {PASS: 0, BORDERLINE: 0, FAIL: 0, NOT_AVAILABLE: 0}
        for channel in self.channels:
            counts[channel.grade] += 1
        return counts

    @property
    def failing(self) -> list:
        return [channel for channel in self.channels if channel.grade == FAIL]


# ----------------------------------------------------------------------
# Grid plumbing
# ----------------------------------------------------------------------

def build_emg_map(grid, display_grid: np.ndarray, channel_status=None) -> np.ndarray:
    """Turn a hdsemg-select grid into the (cols, rows) map shared expects.

    ``display_grid`` is (rows, cols) of LOCAL electrode indices with NaN at
    unwired positions — the same array the electrode layout and the fiber
    trajectory analysis use. ``emg_indices`` maps local to the channel
    number in the data matrix.

    When ``channel_status`` is given, every deselected position becomes NaN,
    so a deselected channel contributes nothing to the global amplitude.
    Applying the selection is the caller's job by design; this is where
    hdsemg-select does it.
    """
    rows, cols = display_grid.shape
    emg_indices = list(grid.emg_indices)
    emg_map = np.full((cols, rows), np.nan)
    for row in range(rows):
        for col in range(cols):
            cell = display_grid[row, col]
            if np.isnan(cell):
                continue
            local = int(cell)
            if local >= len(emg_indices):
                continue
            channel = emg_indices[local]
            if channel is None:
                continue
            if channel_status is not None and not channel_status[channel]:
                continue
            emg_map[col, row] = float(channel)
    return emg_map


def _remap(emg_map: np.ndarray, global_to_local: dict) -> np.ndarray:
    """The same map, with channel numbers pointing into the submatrix."""
    out = np.full(emg_map.shape, np.nan)
    for col in range(emg_map.shape[0]):
        for row in range(emg_map.shape[1]):
            cell = emg_map[col, row]
            if np.isnan(cell):
                continue
            local = global_to_local.get(int(cell))
            if local is not None:
                out[col, row] = float(local)
    return out


# ----------------------------------------------------------------------
# Windowing
# ----------------------------------------------------------------------

def detect_windows(reference, amplitude, fs, rest_below_pct=2.0, min_rest_s=2.0,
                   peak_ms=250.0, fallback_s=3.0) -> QCWindows:
    """Find the rest stretches and the peak window of a contraction.

    Rest is where the reference path sits within ``rest_below_pct`` of its
    own span above its own baseline — a fraction of the trial's peak force
    rather than of an MVC, so it needs no calibration file and no units.
    The peak window is the ``peak_ms`` of highest mean global amplitude
    outside rest.

    With no usable reference channel the first and last ``fallback_s``
    seconds become the rest windows, and the result says so through
    ``source``, so a pooled analysis can filter those trials out.
    """
    n_samples = int(amplitude.size)
    peak_n = max(1, int(round(peak_ms * 1e-3 * fs)))

    rest_runs, source = [], "force"
    if reference is not None and np.any(np.isfinite(reference)):
        finite = reference[np.isfinite(reference)]
        baseline = float(np.percentile(finite, 5))
        span = float(np.percentile(finite, 99)) - baseline
        if span > 0:
            at_rest = reference <= baseline + (rest_below_pct / 100.0) * span
            rest_runs = [run for run in _runs(at_rest)
                         if (run[1] - run[0]) >= int(round(min_rest_s * fs))]

    if not rest_runs:
        source = "fallback"
        edge = min(int(round(fallback_s * fs)), max(1, n_samples // 4))
        rest_runs = [(0, edge), (max(edge, n_samples - edge), n_samples)]
        logger.info("Global amplitude QC: no usable reference path, using edge rest windows.")

    return QCWindows(rest=rest_runs, peak=_peak_window(amplitude, rest_runs, peak_n),
                     source=source)


def _runs(mask: np.ndarray) -> list:
    """Contiguous True runs of a boolean mask as (start, stop) pairs."""
    padded = np.concatenate(([False], np.asarray(mask, dtype=bool), [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2].tolist(), edges[1::2].tolist()))


def _peak_window(amplitude: np.ndarray, rest_runs: list, peak_n: int) -> tuple:
    """The peak_n samples of highest mean amplitude that are not at rest."""
    n_samples = int(amplitude.size)
    peak_n = min(peak_n, n_samples)
    kernel = np.ones(peak_n) / peak_n
    rolling = np.convolve(np.nan_to_num(amplitude, nan=0.0), kernel, mode="valid")

    allowed = np.ones(rolling.size, dtype=bool)
    for start, stop in rest_runs:
        allowed[max(0, start - peak_n + 1):stop] = False
    if not np.any(allowed):
        allowed[:] = True  # nothing but rest; measure the best of it anyway

    start = int(np.argmax(np.where(allowed, rolling, -np.inf)))
    return start, start + peak_n


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------

def _sub_score(check: str, value: float, thresholds: QCThresholds) -> Optional[float]:
    """0 at the fail bound, 1 at the pass bound, linear between them."""
    if value is None or not np.isfinite(value):
        return None
    pass_at, fail_at = thresholds.bounds(check)
    if _DIRECTION[check] == "down":
        value = abs(value)
        if fail_at == pass_at:
            return 1.0 if value <= pass_at else 0.0
        return float(np.clip((fail_at - value) / (fail_at - pass_at), 0.0, 1.0))
    if pass_at == fail_at:
        return 1.0 if value >= pass_at else 0.0
    return float(np.clip((value - fail_at) / (pass_at - fail_at), 0.0, 1.0))


def _state(score: Optional[float]) -> str:
    if score is None:
        return NOT_AVAILABLE
    if score >= 1.0:
        return PASS
    if score <= 0.0:
        return FAIL
    return BORDERLINE


def grade_channel(channel_index: int, values: dict, thresholds: QCThresholds) -> ChannelQC:
    """Turn one channel's measured values into states, a grade and a CQI.

    The grade is the **worst** state among the enabled checks, never an
    average — one fatal defect must not be averaged away by six healthy
    ones. The CQI is a weighted mean of the sub-scores and exists only to
    rank the list.
    """
    states, scores = {}, {}
    for check in CHECKS:
        if not thresholds.enabled.get(check, True):
            continue
        if check == "flat":
            states[check] = FAIL if values.get("flat") else PASS
            continue
        score = _sub_score(check, values.get(check), thresholds)
        states[check] = _state(score)
        if score is not None:
            scores[check] = score

    if states.get("flat") == FAIL:
        return ChannelQC(channel_index, values, states, FAIL, 0, "flat")

    grade = max(states.values(), key=_SEVERITY.get) if states else NOT_AVAILABLE
    total = sum(thresholds.weights.get(check, 0.0) for check in scores)
    cqi = int(round(100 * sum(
        thresholds.weights.get(check, 0.0) * score for check, score in scores.items()
    ) / total)) if total > 0 else 0

    ranked = [check for check in states
              if states[check] not in (PASS, NOT_AVAILABLE)]
    worst = min(ranked, key=lambda check: scores.get(check, 0.0)) if ranked else None
    return ChannelQC(channel_index, values, states, grade, cqi, worst)


# ----------------------------------------------------------------------
# The analysis
# ----------------------------------------------------------------------

def analyze(data, time, fs, grid, display_grid, channel_status, thresholds,
            channel_scope="selected", unit=None, measure_direction=True,
            derivation="DD", method="RMS", diff_direction="cols",
            reference_index=None, reference_label="", windows=None,
            rest_below_pct=2.0, min_rest_s=2.0, peak_ms=250.0, fallback_s=3.0,
            bpf=None, smooth=None,
            line_freqs=(50.0, 100.0, 150.0)) -> GlobalAmplitudeQCResult:
    """Run the whole QC step for one grid.

    Parameters
    ----------
    data:           (n_samples, n_channels) raw, unfiltered signal
    time:           (n_samples,) time vector in seconds
    fs:             sampling frequency in Hz
    grid:           hdsemg-shared Grid object
    display_grid:   (rows, cols) local electrode indices, NaN where unwired
    channel_status: per-channel selection flags, indexed globally
    channel_scope:  'selected' measures only the selected channels of the
                    grid; 'all' ignores the selection and measures every
                    channel. 'all' is what a freshly loaded file needs —
                    QC is the step that informs a selection, so requiring
                    one first would be backwards. The scope is reported
                    and stored, never inferred silently downstream.
    thresholds:     QCThresholds
    unit:           the unit EMGFile declares for the data, or None. When
                    None the documented assumption is used and the result
                    says so, and warns if that makes the numbers implausible
    windows:        reuse an existing QCWindows instead of detecting them
    bpf, smooth:    band-pass and smoothing options, see hdsemg-shared's
                    global_amplitude; None means its documented defaults

    Raises
    ------
    ValueError: when the grid has no channels, when scope is 'selected' and
        none of them are, or when the grid is too small for the requested
        derivation (raised by hdsemg-shared).
    """
    grid_channels = [ch for ch in grid.emg_indices if ch is not None]
    if not grid_channels:
        raise ValueError(f"Grid '{grid.grid_key}' has no EMG channels.")

    global_to_local = {ch: i for i, ch in enumerate(grid_channels)}
    sub = np.asarray(data[:, grid_channels], dtype=np.float64).T  # channels-by-samples

    channel_scope = _check_scope(channel_scope)
    map_all = _remap(build_emg_map(grid, display_grid, None), global_to_local)
    map_selected = (
        map_all if channel_scope == "all"
        else _remap(build_emg_map(grid, display_grid, channel_status), global_to_local)
    )

    n_selected = int(np.count_nonzero(~np.isnan(map_selected)))
    if n_selected == 0:
        raise ValueError(
            f"No channel of grid '{grid.grid_key}' is selected. Switch "
            f"'Measure' to 'all channels' to grade the grid before selecting."
        )

    result = global_amplitude(sub, map_selected, fs, method=method,
                              derivation=derivation, diff_direction=diff_direction,
                              bpf=bpf, smooth=smooth)
    amplitude = np.asarray(result.amplitude, dtype=np.float64)

    reference = None
    if reference_index is not None and 0 <= reference_index < data.shape[1]:
        reference = np.asarray(data[:, reference_index], dtype=np.float64)

    if windows is None:
        windows = detect_windows(reference, amplitude, fs,
                                 rest_below_pct=rest_below_pct,
                                 min_rest_s=min_rest_s, peak_ms=peak_ms,
                                 fallback_s=fallback_s)

    n_samples = amplitude.size
    rest_mask = windows.rest_mask(n_samples)
    peak_mask = windows.peak_mask(n_samples)

    resting_floor = float(np.nanmedian(amplitude[rest_mask])) if np.any(rest_mask) else float("nan")
    peak_mean = float(np.nanmean(amplitude[peak_mask])) if np.any(peak_mask) else float("nan")
    ratio = peak_mean / resting_floor if resting_floor and np.isfinite(resting_floor) else float("nan")

    channels = _grade_channels(sub, map_all, fs, grid_channels, rest_mask, peak_mask,
                               thresholds, line_freqs, bpf)

    return GlobalAmplitudeQCResult(
        grid_key=grid.grid_key,
        derivation=derivation, method=method, diff_direction=diff_direction,
        time=np.asarray(time, dtype=np.float64),
        amplitude=amplitude,
        ref_signal=reference, ref_index=reference_index, ref_label=reference_label,
        windows=windows,
        resting_floor=resting_floor, peak_mean=peak_mean, activation_ratio=ratio,
        verdict=_grid_verdict(ratio, n_selected, len(grid_channels), thresholds),
        n_channels=int(result.n_channels), n_selected=n_selected,
        n_grid_channels=len(grid_channels), channel_scope=channel_scope,
        channels=channels, thresholds=thresholds,
        unit=resolve_amplitude_unit(unit, resting_floor),
        fibre=(measure_fibre_direction(
            data, grid, display_grid, fs,
            window=_direction_window(windows, n_samples, fs))
            if measure_direction else None),
    )


def _check_scope(channel_scope: str) -> str:
    if channel_scope not in ("selected", "all"):
        raise ValueError(
            f"channel_scope must be 'selected' or 'all', got {channel_scope!r}.")
    return channel_scope


def _direction_window(windows, n_samples, fs) -> slice:
    """A stretch of contraction long enough to measure propagation in.

    Centred on the peak window and grown to DIRECTION_WINDOW_S, then clipped
    to the record. Rest is not excluded: at this width the contraction
    dominates, and a shorter window is the worse error.
    """
    half = int(round(0.5 * DIRECTION_WINDOW_S * fs))
    middle = (windows.peak[0] + windows.peak[1]) // 2
    start = max(0, middle - half)
    stop = min(n_samples, max(start + 1, middle + half))
    return slice(start, stop)


def _grid_verdict(ratio, n_selected, n_total, thresholds) -> str:
    """Pass, borderline or fail — or n/a when too little of the grid is left.

    A verdict on a grid whose channels have mostly been deselected is not a
    verdict on the grid.
    """
    if n_total and (n_selected / n_total) < thresholds.min_channel_fraction:
        return NOT_AVAILABLE
    if not np.isfinite(ratio):
        return NOT_AVAILABLE
    if ratio >= thresholds.grid_pass:
        return PASS
    if ratio >= thresholds.grid_borderline:
        return BORDERLINE
    return FAIL


def _grade_channels(sub, emg_map, fs, grid_channels, rest_mask, peak_mask,
                    thresholds, line_freqs, bpf=None) -> list:
    """Measure the seven checks over the grid, then grade each channel."""
    peak_amp = channel_amplitude(sub, fs, bpf=bpf, window=peak_mask).rms
    rest_amp = channel_amplitude(sub, fs, bpf=bpf, window=rest_mask).rms
    with np.errstate(divide="ignore", invalid="ignore"):
        activation = np.where(rest_amp > 0, peak_amp / rest_amp, np.nan)

    spectrum = channel_spectrum(sub, fs, window=peak_mask).mnf
    noise = line_noise_ratio(sub, fs, freqs=tuple(line_freqs)).ratio
    clipping = clipping_fraction(sub)
    neighbour = neighbor_correlation(sub, emg_map, fs, bpf=bpf, window=peak_mask)
    dead = set(flat_channels(sub))

    amplitude_z = robust_z(peak_amp)
    spectrum_z = robust_z(spectrum)

    channels = []
    for local, channel in enumerate(grid_channels):
        channels.append(grade_channel(channel, {
            "activation_ratio": _value(activation, local),
            "amplitude_z": _value(amplitude_z, local),
            "spectrum_z": _value(spectrum_z, local),
            "line_noise": _value(noise, local),
            "clipping": _value(clipping, local),
            "neighbor_correlation": _value(neighbour, local),
            "flat": local in dead,
            "peak_amplitude_uv": _value(peak_amp, local),
            "rest_amplitude_uv": _value(rest_amp, local),
            "mnf_hz": _value(spectrum, local),
        }, thresholds))
    return channels


def _value(array, index):
    """One entry of a shared-library result as a plain float, or None."""
    if array is None or index >= len(array):
        return None
    value = float(array[index])
    return value if np.isfinite(value) else None


# ----------------------------------------------------------------------
# Report shape — shared by the dialog's export and the selection JSON
# ----------------------------------------------------------------------

def qc_report(result: GlobalAmplitudeQCResult, fs: float) -> dict:
    """The grid's QC block: the settings, the evidence and the verdict.

    Evidence and verdict sit side by side deliberately, so either can be
    re-derived without the other.
    """
    thresholds = result.thresholds
    return {
        "derivation": result.derivation,
        "method": result.method,
        "diff_direction": result.diff_direction,
        "fibre_direction": (None if result.fibre is None else {
            "angle_deg": _clean(result.fibre.angle_deg),
            "propagation_score": _clean(result.fibre.score),
            "conduction_velocity_ms": _clean(result.fibre.cv_ms),
            "cv_status": result.fibre.cv_status,
            "suggested_diff_direction": result.fibre.axis,
            "trustworthy": result.fibre.trustworthy,
            "agrees_with_chosen": not result.fibre.disagrees_with(
                result.diff_direction),
        }),
        "channel_scope": result.channel_scope,
        "rest_windows_s": [[start / fs, stop / fs] for start, stop in result.windows.rest],
        "peak_window_s": [result.windows.peak[0] / fs, result.windows.peak[1] / fs],
        "window_source": result.windows.source,
        "reference_signal": result.ref_label or None,
        "amplitude_unit": result.unit.label,
        "amplitude_unit_source": result.unit.source,
        "amplitude_unit_warning": result.unit.warning,
        "resting_floor_raw": _clean(result.resting_floor),
        "peak_mean_raw": _clean(result.peak_mean),
        "resting_floor_uv": _clean(result.unit.to_uv(result.resting_floor)),
        "peak_mean_uv": _clean(result.unit.to_uv(result.peak_mean)),
        "activation_ratio": _clean(result.activation_ratio),
        "verdict": result.verdict,
        "thresholds": {"pass": thresholds.grid_pass,
                       "borderline": thresholds.grid_borderline,
                       "min_channel_fraction": thresholds.min_channel_fraction},
        "n_channels_contributing": result.n_channels,
        "n_channels_selected": result.n_selected,
        "n_channels_total": result.n_grid_channels,
        "channels": {str(channel.channel_index): channel_report(channel)
                     for channel in result.channels},
    }


def channel_report(channel) -> dict:
    """One channel's raw values next to the states they produced."""
    return {
        "values": {key: _clean(value) for key, value in channel.values.items()},
        "states": dict(channel.states),
        "grade": channel.grade,
        "cqi": channel.cqi,
        "worst_check": channel.worst_check,
    }


def _clean(value):
    """A float that JSON can hold — NaN and inf become null."""
    if isinstance(value, bool) or value is None:
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return number if np.isfinite(number) else None


# ----------------------------------------------------------------------
# One channel's own trace, for looking at a borderline grade by eye
# ----------------------------------------------------------------------

def channel_trace(data, grid, display_grid, channel_index, fs,
                  derivation="DD", diff_direction="cols", bpf=None):
    """The band-passed signal of ONE channel, in the chosen derivation.

    A grade is a number; deciding whether to keep a borderline channel
    means looking at the signal behind it. This returns exactly the trace
    that channel contributes to the global amplitude.

    Returns
    -------
    (trace, label, is_derived)
        ``trace`` is 1-D over the same samples as ``data``. ``is_derived``
        is False when the requested derivation has no value at this grid
        position — the last rows of a column carry no SD/DD, because the
        difference needs the electrodes below them — in which case the
        monopolar trace is returned and ``label`` says so.

    Raises
    ------
    ValueError: when the channel is not part of the grid.
    """
    grid_channels = [ch for ch in grid.emg_indices if ch is not None]
    if channel_index not in grid_channels:
        raise ValueError(
            f"Channel {channel_index} is not part of grid '{grid.grid_key}'.")

    global_to_local = {ch: i for i, ch in enumerate(grid_channels)}
    sub = np.asarray(data[:, grid_channels], dtype=np.float64).T
    emg_map = _remap(build_emg_map(grid, display_grid, None), global_to_local)

    position = _position_of(emg_map, global_to_local[channel_index])
    if position is None:
        raise ValueError(
            f"Channel {channel_index} has no position in grid '{grid.grid_key}'.")

    stacked = np.stack(map_to_columns(sub, emg_map))  # (nCols, nRows, nSamples)
    order = _DERIVATION_ORDER[_check_choice(derivation)]
    column, row = position

    trace, is_derived = stacked[column, row], not order
    if order:
        axis = _DIFF_AXIS[diff_direction]
        index = row if axis == 1 else column
        if stacked.shape[axis] - order > index:
            # np.diff drops `order` entries from that axis; the survivor at
            # (column, row) is the difference anchored at this electrode.
            trace = np.diff(stacked, n=order, axis=axis)[column, row]
            is_derived = True

    axis_name = "columns" if diff_direction == "cols" else "rows"
    if not order:
        label = "monopolar"
    elif is_derived:
        label = f"{derivation} along {axis_name}"
    else:
        label = (f"monopolar — this electrode sits at the edge of the {axis_name}, "
                 f"so no {derivation} is defined for it")
    return _bandpass_one(trace, bpf, fs), label, is_derived


def _position_of(emg_map, local_index):
    """(column, row) of a channel in the map, or None."""
    hits = np.argwhere(emg_map == float(local_index))
    return tuple(int(value) for value in hits[0]) if hits.size else None


def _bandpass_one(trace, bpf, fs):
    """One channel band-passed in the same band every other measure uses."""
    options = {'N': 2, 'fcl': 15.0, 'fch': 450.0, 'corners': 'exact', **(bpf or {})}
    data = np.asarray(trace, dtype=np.float64)[np.newaxis, :]
    if not np.all(np.isfinite(data)):
        return np.asarray(trace, dtype=np.float64)
    pad = pad_samples(data.shape[-1], fs, 0.25)
    filtered = bandpass_filter_exact_corners(
        reflect_pad(data, pad), options['N'], options['fcl'], options['fch'], fs)
    return trim_pad(filtered, pad)[0]


def _check_choice(derivation):
    if derivation not in _DERIVATION_ORDER:
        raise ValueError(
            f"derivation must be one of {list(_DERIVATION_ORDER)}, got {derivation!r}.")
    return derivation
