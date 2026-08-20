"""Tests for the QC report — the shape that lands in the selection JSON.

The report is the durable artefact of the QC step: it has to survive a
``json.dumps`` and it has to carry the evidence next to the verdict, so
either can be re-derived without the other.
"""

import json

import numpy as np
import pytest

from hdsemg_select.select_logic.global_amplitude_qc import (
    BORDERLINE,
    FAIL,
    PASS,
    QCThresholds,
    QCWindows,
    ChannelQC,
    GlobalAmplitudeQCResult,
    channel_report,
    grade_channel,
    qc_report,
)

FS = 1000.0


def _result(**overrides):
    time = np.arange(0, 10, 1 / FS)
    defaults = dict(
        grid_key="Grid_1", derivation="DD", method="RMS", diff_direction="cols",
        time=time, amplitude=np.ones(time.size) * 9.0,
        ref_signal=None, ref_index=None, ref_label="Performed Path",
        windows=QCWindows(rest=[(0, 2000), (8000, 10000)], peak=(5000, 5250),
                          source="force"),
        resting_floor=8.58, peak_mean=11.47, activation_ratio=1.34, verdict=FAIL,
        n_channels=48, n_selected=58, n_grid_channels=64,
        channel_scope="selected",
        channels=[grade_channel(0, {
            "activation_ratio": 1.21, "amplitude_z": -2.4, "spectrum_z": 0.8,
            "line_noise": 1.6, "clipping": 0.0, "neighbor_correlation": 0.27,
            "flat": False,
        }, QCThresholds())],
        thresholds=QCThresholds(),
    )
    defaults.update(overrides)
    return GlobalAmplitudeQCResult(**defaults)


def test_the_report_survives_json_serialisation():
    report = qc_report(_result(), FS)

    assert json.loads(json.dumps(report)) == report


def test_the_report_carries_the_definition_that_produced_it():
    report = qc_report(_result(), FS)

    assert report["derivation"] == "DD"
    assert report["method"] == "RMS"
    assert report["diff_direction"] == "cols"


def test_the_report_says_which_channels_produced_the_number():
    """A ratio over the whole grid and one over a selection are not the
    same measurement, so the scope has to be readable afterwards."""
    assert qc_report(_result(), FS)["channel_scope"] == "selected"
    assert qc_report(_result(channel_scope="all"), FS)["channel_scope"] == "all"


def test_windows_are_reported_in_seconds_not_samples():
    report = qc_report(_result(), FS)

    assert report["rest_windows_s"] == [[0.0, 2.0], [8.0, 10.0]]
    assert report["peak_window_s"] == [5.0, 5.25]
    assert report["window_source"] == "force"


def test_the_report_carries_the_evidence_and_the_verdict_together():
    report = qc_report(_result(), FS)

    assert report["activation_ratio"] == pytest.approx(1.34)
    assert report["resting_floor_uv"] == pytest.approx(8.58)
    assert report["verdict"] == FAIL
    assert report["thresholds"]["pass"] == 1.50


def test_a_fallback_window_says_so_in_the_report():
    """A pooled analysis has to be able to filter these trials out."""
    windows = QCWindows(rest=[(0, 3000)], peak=(5000, 5250), source="fallback")

    report = qc_report(_result(windows=windows), FS)

    assert report["window_source"] == "fallback"


def test_non_finite_numbers_become_null_rather_than_nan():
    """json.dumps writes a bare NaN, which is not valid JSON."""
    report = qc_report(_result(activation_ratio=float("nan"),
                               resting_floor=float("inf")), FS)

    assert report["activation_ratio"] is None
    assert report["resting_floor_uv"] is None
    json.loads(json.dumps(report))  # must not raise


def test_every_channel_is_keyed_by_its_channel_index():
    report = qc_report(_result(), FS)

    assert set(report["channels"]) == {"0"}
    assert report["channels"]["0"]["grade"] in (PASS, FAIL, "borderline")


def test_a_channel_report_keeps_the_raw_values():
    channel = grade_channel(4, {
        "activation_ratio": 1.21, "amplitude_z": -2.4, "spectrum_z": 0.8,
        "line_noise": 1.6, "clipping": 0.0, "neighbor_correlation": 0.27,
        "flat": False,
    }, QCThresholds())

    report = channel_report(channel)

    assert report["values"]["activation_ratio"] == pytest.approx(1.21)
    assert report["values"]["neighbor_correlation"] == pytest.approx(0.27)
    # Both sit between their bounds, so both ramp rather than snap to a verdict.
    assert report["states"]["neighbor_correlation"] == BORDERLINE
    assert report["states"]["activation_ratio"] == BORDERLINE
    # 1.21 is a hair above its fail bound of 1.20, so it scores worst of the two.
    assert report["worst_check"] == "activation_ratio"


def test_a_missing_value_stays_null_in_the_report():
    channel = ChannelQC(2, {"activation_ratio": None, "flat": False},
                        {"activation_ratio": "n/a"}, "n/a", 0, None)

    report = channel_report(channel)

    assert report["values"]["activation_ratio"] is None
    assert report["values"]["flat"] is False


def test_channel_counts_distinguish_derived_from_selected():
    """DD reduces 58 selected channels to 48 of global amplitude."""
    report = qc_report(_result(), FS)

    assert report["n_channels_contributing"] == 48
    assert report["n_channels_selected"] == 58
    assert report["n_channels_total"] == 64
