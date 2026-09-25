"""Issue #102: manually entered grids must reach EMGFile.grids."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox
from hdsemg_shared.fileio.matlab_file_io import MatFileIO

from hdsemg_select.controller import file_management
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.dialog.manual_grid_input import build_manual_grids

_app = QApplication.instance() or QApplication([])


def test_same_size_grids_stay_separate_and_do_not_overlap():
    grids = build_manual_grids([(8, 8, 1, 10), (8, 8, 1, 10)], total_channels=130)
    assert [g.grid_key for g in grids] == ["10mm_8x8", "10mm_8x8_2"]
    assert grids[0].emg_indices == list(range(0, 64))
    assert grids[0].ref_indices == [64]
    assert grids[1].emg_indices == list(range(65, 129))
    assert grids[1].ref_indices == [129]


def test_too_many_channels_is_rejected():
    with pytest.raises(ValueError, match="130"):
        build_manual_grids([(8, 8, 1, 10), (8, 8, 1, 10)], total_channels=129)


def test_file_without_grid_info_loads_with_manual_grids(tmp_path, monkeypatch):
    n_ch, n_samples = 130, 200
    path = str(tmp_path / "no_grid_info.mat")
    MatFileIO.save(
        path,
        np.random.default_rng(0).standard_normal((n_samples, n_ch)),
        np.arange(n_samples) / 2048.0,
        np.array([[f"channel {i}"] for i in range(n_ch)], dtype=object),
        2048.0,
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a)))
    monkeypatch.setattr(
        file_management, "manual_grid_input",
        lambda total, *_: build_manual_grids([(8, 8, 1, 10), (8, 8, 1, 10)], total),
    )

    assert file_management.FileManager().process_file(path, None) is True
    grids = global_state.get_emg_file().grids
    assert len(grids) == 2
    assert not set(grids[0].emg_indices) & set(grids[1].emg_indices)
    global_state.reset()
