"""The bridge between the stored settings and the QC step.

Keeps ``global_amplitude_qc`` free of any dependency on the application's
configuration: that module takes a ``QCThresholds`` and a handful of
numbers, and this one is where those come from.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from hdsemg_select.config.config_enums import Settings
from hdsemg_select.config.config_manager import config
from hdsemg_select.select_logic.global_amplitude_qc import CHECKS, QCThresholds

#: The bound names each check stores, in (pass, fail) order.
_BOUND_KEYS = {
    "activation_ratio": ("activation_pass", "activation_fail"),
    "amplitude_z": ("amplitude_z_pass", "amplitude_z_fail"),
    "spectrum_z": ("spectrum_z_pass", "spectrum_z_fail"),
    "line_noise": ("line_noise_pass", "line_noise_fail"),
    "clipping": ("clipping_pass", "clipping_fail"),
    "neighbor_correlation": ("neighbor_pass", "neighbor_fail"),
}


@dataclass(frozen=True)
class QCSettings:
    """Everything the QC dialog needs that the user can configure."""

    derivation: str = "DD"
    method: str = "RMS"
    diff_direction: str = "cols"
    bpf_low_hz: float = 15.0
    bpf_high_hz: float = 450.0
    smooth_hz: float = 15.0
    line_freq_hz: float = 50.0

    rest_below_pct: float = 2.0
    min_rest_s: float = 2.0
    peak_window_ms: float = 250.0
    fallback_s: float = 3.0

    thresholds: QCThresholds = None

    @property
    def line_freqs(self) -> tuple:
        """The mains frequency and its first two harmonics."""
        return (self.line_freq_hz, 2 * self.line_freq_hz, 3 * self.line_freq_hz)

    @property
    def bpf(self) -> dict:
        """Band-pass options for hdsemg-shared, shared by every measure."""
        return {"N": 2, "fcl": self.bpf_low_hz, "fch": self.bpf_high_hz,
                "corners": "exact"}

    @property
    def smooth(self) -> dict:
        """Time-smoothing options for the global amplitude."""
        return {"mode": "moving", "fc": self.smooth_hz, "window_s": None,
                "kernel": "bidirectional", "N": 2}


def load() -> QCSettings:
    """Read the stored settings, falling back to the documented defaults."""
    defaults = QCSettings()
    base = QCThresholds()

    bounds = config.get(Settings.GA_QC_CHANNEL_BOUNDS, {}) or {}
    weights = dict(base.weights)
    weights.update(config.get(Settings.GA_QC_CHANNEL_WEIGHTS, {}) or {})
    enabled = {check: True for check in CHECKS}
    enabled.update(config.get(Settings.GA_QC_CHANNEL_ENABLED, {}) or {})

    overrides = {}
    for check, (pass_key, fail_key) in _BOUND_KEYS.items():
        stored = bounds.get(check) or {}
        overrides[pass_key] = float(stored.get("pass", getattr(base, pass_key)))
        overrides[fail_key] = float(stored.get("fail", getattr(base, fail_key)))

    thresholds = replace(
        base,
        grid_pass=_number(Settings.GA_QC_GRID_PASS, base.grid_pass),
        grid_borderline=_number(Settings.GA_QC_GRID_BORDERLINE, base.grid_borderline),
        min_channel_fraction=_number(Settings.GA_QC_MIN_CHANNEL_FRACTION,
                                     base.min_channel_fraction),
        weights=weights, enabled=enabled, **overrides,
    )

    return QCSettings(
        derivation=str(config.get(Settings.GA_QC_DERIVATION, defaults.derivation)),
        method=str(config.get(Settings.GA_QC_METHOD, defaults.method)),
        diff_direction=str(config.get(Settings.GA_QC_DIFF_DIRECTION,
                                      defaults.diff_direction)),
        bpf_low_hz=_number(Settings.GA_QC_BPF_LOW_HZ, defaults.bpf_low_hz),
        bpf_high_hz=_number(Settings.GA_QC_BPF_HIGH_HZ, defaults.bpf_high_hz),
        smooth_hz=_number(Settings.GA_QC_SMOOTH_HZ, defaults.smooth_hz),
        line_freq_hz=_number(Settings.GA_QC_LINE_FREQ_HZ, defaults.line_freq_hz),
        rest_below_pct=_number(Settings.GA_QC_REST_BELOW_PCT, defaults.rest_below_pct),
        min_rest_s=_number(Settings.GA_QC_MIN_REST_S, defaults.min_rest_s),
        peak_window_ms=_number(Settings.GA_QC_PEAK_WINDOW_MS, defaults.peak_window_ms),
        fallback_s=_number(Settings.GA_QC_FALLBACK_S, defaults.fallback_s),
        thresholds=thresholds,
    )


def save(settings: QCSettings) -> None:
    """Write the settings back, one config key per group."""
    thresholds = settings.thresholds or QCThresholds()

    config.set(Settings.GA_QC_DERIVATION, settings.derivation)
    config.set(Settings.GA_QC_METHOD, settings.method)
    config.set(Settings.GA_QC_DIFF_DIRECTION, settings.diff_direction)
    config.set(Settings.GA_QC_BPF_LOW_HZ, settings.bpf_low_hz)
    config.set(Settings.GA_QC_BPF_HIGH_HZ, settings.bpf_high_hz)
    config.set(Settings.GA_QC_SMOOTH_HZ, settings.smooth_hz)
    config.set(Settings.GA_QC_LINE_FREQ_HZ, settings.line_freq_hz)

    config.set(Settings.GA_QC_REST_BELOW_PCT, settings.rest_below_pct)
    config.set(Settings.GA_QC_MIN_REST_S, settings.min_rest_s)
    config.set(Settings.GA_QC_PEAK_WINDOW_MS, settings.peak_window_ms)
    config.set(Settings.GA_QC_FALLBACK_S, settings.fallback_s)

    config.set(Settings.GA_QC_GRID_PASS, thresholds.grid_pass)
    config.set(Settings.GA_QC_GRID_BORDERLINE, thresholds.grid_borderline)
    config.set(Settings.GA_QC_MIN_CHANNEL_FRACTION, thresholds.min_channel_fraction)

    config.set(Settings.GA_QC_CHANNEL_BOUNDS, {
        check: {"pass": getattr(thresholds, pass_key),
                "fail": getattr(thresholds, fail_key)}
        for check, (pass_key, fail_key) in _BOUND_KEYS.items()
    })
    config.set(Settings.GA_QC_CHANNEL_WEIGHTS, dict(thresholds.weights))
    config.set(Settings.GA_QC_CHANNEL_ENABLED, dict(thresholds.enabled))


def _number(setting: Settings, default: float) -> float:
    """A stored value as a float, ignoring anything that is not one."""
    try:
        return float(config.get(setting, default))
    except (TypeError, ValueError):
        return float(default)
