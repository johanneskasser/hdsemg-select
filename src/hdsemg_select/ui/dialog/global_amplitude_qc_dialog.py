"""Global Amplitude QC dialog.

Two views on one analysis: the grid's activation check with the global
amplitude drawn over the performed path, and the per-channel quality that
says which electrodes contributed to it.

The analysis runs in a background thread — a 64-channel grid over a 30 s
trial takes a couple of seconds — so the dialog stays responsive.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.widgets import SpanSelector
from PyQt5.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QSizePolicy, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from hdsemg_select._log.log_config import logger
from hdsemg_select.select_logic import ga_qc_config
from hdsemg_select.select_logic.global_amplitude_qc import (
    BORDERLINE, CHECK_LABELS, CHECKS, FAIL, NOT_AVAILABLE, PASS,
    GlobalAmplitudeQCResult, QCWindows, analyze, qc_report,
)
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.dialog.ga_qc_method_dialog import GaQcMethodDialog
from hdsemg_select.ui.dialog.ga_qc_suggestion_dialog import GaQcSuggestionDialog
from hdsemg_select.ui.electrode_layout import get_display_grid
from hdsemg_select.ui.theme import BorderRadius, Colors, Spacing

#: Grade colours, shared by the heatmap, the table and the chips.
GRADE_COLOR = {
    PASS: Colors.GREEN_500,
    BORDERLINE: Colors.YELLOW_500,
    FAIL: Colors.RED_500,
    NOT_AVAILABLE: Colors.GRAY_400,
}
GRADE_TEXT = {
    PASS: (Colors.GREEN_100, Colors.GREEN_800),
    BORDERLINE: (Colors.YELLOW_100, Colors.YELLOW_600),
    FAIL: (Colors.RED_100, Colors.RED_700),
    NOT_AVAILABLE: (Colors.GRAY_100, Colors.GRAY_500),
}

_SECTION_STYLE = (
    "font-size: 11px; font-weight: 600; text-transform: uppercase; "
    f"letter-spacing: 0.05em; color: {Colors.TEXT_MUTED};"
)

_VERDICT_TEXT = {
    PASS: "Grid passes the activation check",
    BORDERLINE: "Grid is borderline on the activation check",
    FAIL: "Grid fails the activation check",
    NOT_AVAILABLE: "No verdict for this grid",
}

#: Columns of the channel table.
_TABLE_COLUMNS = [
    ("Ch", "channel"), ("CQI", "cqi"), ("Act. ratio", "activation_ratio"),
    ("Amp z", "amplitude_z"), ("MNF z", "spectrum_z"), ("Line", "line_noise"),
    ("Clip", "clipping"), ("r nb", "neighbor_correlation"),
    ("Grade", "grade"), ("Worst driver", "worst"),
]


class _QCWorker(QObject):
    """Runs the QC analysis off the UI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, kwargs: dict):
        super().__init__()
        self._kwargs = kwargs

    def run(self):
        try:
            self.finished.emit(analyze(**self._kwargs))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
            logger.error("Global amplitude QC failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))


class GlobalAmplitudeQCDialog(QDialog):
    """Grid activation check and per-channel quality for one grid at a time."""

    def __init__(self, grid_handler, parent=None):
        super().__init__(parent)
        self._grid_handler = grid_handler
        self._main_window = parent
        self._settings = ga_qc_config.load()
        self._result: Optional[GlobalAmplitudeQCResult] = None
        self._results_by_grid: dict = {}
        self._windows_override: Optional[QCWindows] = None
        self._grid_key: Optional[str] = None
        self._display_grid: Optional[np.ndarray] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_QCWorker] = None
        self._span: Optional[SpanSelector] = None
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(80)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        flags = self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle("Global Amplitude QC")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self.resize(1120, 780)

        self._build_ui()
        self._populate_grid_combo()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)
        root.addLayout(self._build_top_bar())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_grid_tab(), "Grid")
        self._tabs.addTab(self._build_channels_tab(), "Channels")
        root.addWidget(self._tabs, stretch=1)

    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._grid_combo = self._combo(160)
        self._grid_combo.currentIndexChanged.connect(self._on_grid_changed)

        self._derivation_combo = self._combo(70, ["MP", "SD", "DD"])
        self._derivation_combo.setCurrentText(self._settings.derivation)
        self._derivation_combo.setToolTip(
            "MP monopolar, SD single differential, DD double differential.\n"
            "Chosen here, stored per grid in the selection JSON."
        )
        self._method_combo = self._combo(70, ["RMS", "ARV"])
        self._method_combo.setCurrentText(self._settings.method)
        self._axis_combo = self._combo(96, ["columns", "rows"])
        self._axis_combo.setCurrentText(
            "columns" if self._settings.diff_direction == "cols" else "rows")
        self._axis_combo.setToolTip(
            "Which grid axis SD and DD difference along.\n"
            "Point it along the muscle fibres — Signal ▸ Fiber Trajectory\n"
            "Analysis measures which way they actually run."
        )
        self._scope_combo = self._combo(120, ["all channels", "selected channels"])
        self._scope_combo.setToolTip(
            "Which channels of the grid enter the global amplitude.\n"
            "A freshly loaded file has no selection yet — QC is the step that\n"
            "informs one — so 'all channels' is the default until you make one."
        )
        for combo in (self._derivation_combo, self._method_combo, self._axis_combo,
                      self._scope_combo):
            combo.currentIndexChanged.connect(self._on_definition_changed)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")

        self._run_btn = QPushButton("▶  Run QC")
        self._run_btn.setMinimumWidth(120)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BLUE_600}; color: white; "
            f"border-radius: 4px; padding: 5px 14px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.BLUE_700}; }}"
            f"QPushButton:disabled {{ background-color: {Colors.BORDER_DEFAULT}; "
            f"color: {Colors.TEXT_MUTED}; }}"
        )
        self._run_btn.clicked.connect(self._start_analysis)
        self._run_btn.setEnabled(False)

        self._redetect_btn = self._outline_button(
            "Re-detect windows", "Discard dragged windows and segment from the "
                                 "performed path again")
        self._redetect_btn.clicked.connect(self._redetect_windows)
        self._redetect_btn.setEnabled(False)

        self._method_btn = self._outline_button(
            "ⓘ  About the method", "How the global amplitude and the channel "
                                    "grades are defined")
        self._method_btn.clicked.connect(self._open_method_dialog)

        self._export_btn = QPushButton("Export JSON")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_json)

        bar.addWidget(self._label("Grid:"))
        bar.addWidget(self._grid_combo)
        bar.addSpacing(6)
        bar.addWidget(self._label("Derivation:"))
        bar.addWidget(self._derivation_combo)
        bar.addWidget(self._label("Method:"))
        bar.addWidget(self._method_combo)
        bar.addWidget(self._label("Difference along:"))
        bar.addWidget(self._axis_combo)
        bar.addWidget(self._label("Measure:"))
        bar.addWidget(self._scope_combo)
        bar.addSpacing(6)
        bar.addWidget(self._status_lbl)
        bar.addStretch()
        bar.addWidget(self._method_btn)
        bar.addWidget(self._redetect_btn)
        bar.addWidget(self._run_btn)
        bar.addWidget(self._export_btn)
        return bar

    # -- grid tab ------------------------------------------------------

    def _build_grid_tab(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setSpacing(8)
        body.setContentsMargins(8, 8, 8, 8)

        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(self._section("Global amplitude + performed path"))
        figure = Figure(figsize=(6.5, 4.2), facecolor=Colors.BG_PRIMARY)
        self._plot_ax = figure.add_subplot(111)
        self._plot_canvas = FigureCanvas(figure)
        self._plot_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._plot_toolbar = self._make_toolbar(self._plot_canvas)
        left.addWidget(self._plot_toolbar)
        left.addWidget(self._plot_canvas, stretch=1)

        drag_row = QHBoxLayout()
        drag_row.setSpacing(6)
        drag_row.addWidget(self._label("Drag on the plot to set:"))
        self._drag_combo = self._combo(130, ["peak window", "rest window"])
        drag_row.addWidget(self._drag_combo)
        self._windows_lbl = QLabel("")
        self._windows_lbl.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
        drag_row.addWidget(self._windows_lbl, stretch=1)
        left.addLayout(drag_row)
        body.addLayout(left, stretch=62)

        right = QVBoxLayout()
        right.setSpacing(8)

        self._verdict_lbl = QLabel("Run QC to measure this grid.")
        self._verdict_lbl.setWordWrap(True)
        self._set_verdict_style(NOT_AVAILABLE)
        right.addWidget(self._verdict_lbl)

        right.addWidget(self._section("Grid evidence"))
        cards = QVBoxLayout()
        cards.setSpacing(6)
        row_one, self._floor_card, self._peak_card = self._card_row(
            "resting floor [µV]", "peak-window mean [µV]")
        row_two, self._ratio_card, self._channels_card = self._card_row(
            "activation ratio", "channels contributing")
        cards.addLayout(row_one)
        cards.addLayout(row_two)
        right.addLayout(cards)

        right.addWidget(self._section("Channel grades"))
        grades_box = QGroupBox()
        grades_box.setStyleSheet(
            f"QGroupBox {{ background-color: {Colors.BG_PRIMARY}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 10px; }}"
        )
        grades_layout = QVBoxLayout(grades_box)
        grades_layout.setSpacing(8)
        self._grades_lbl = QLabel("—")
        self._grades_lbl.setWordWrap(True)
        self._grades_lbl.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY};")
        grades_layout.addWidget(self._grades_lbl)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._review_btn = QPushButton("Review channels")
        self._review_btn.setEnabled(False)
        self._review_btn.clicked.connect(lambda: self._tabs.setCurrentIndex(1))
        self._suggest_btn = self._outline_button(
            "Suggest deselection", "Review the failing channels and deselect the "
                                   "ones you agree with")
        self._suggest_btn.setEnabled(False)
        self._suggest_btn.clicked.connect(self._open_suggestion_dialog)
        buttons.addWidget(self._review_btn)
        buttons.addWidget(self._suggest_btn)
        grades_layout.addLayout(buttons)
        right.addWidget(grades_box)

        right.addStretch()
        note = QLabel(
            "Derivation, method and difference axis chosen here are written to this "
            "grid's <b>global_amplitude</b> block in the selection JSON on save."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"font-size: 10px; color: {Colors.TEXT_MUTED}; "
            f"background-color: {Colors.BG_TERTIARY}; "
            f"border: 1px solid {Colors.BORDER_MUTED}; border-radius: 4px; padding: 6px;"
        )
        right.addWidget(note)
        body.addLayout(right, stretch=38)

        self._draw_empty_plot()
        return page

    # -- channels tab --------------------------------------------------

    def _build_channels_tab(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setSpacing(8)
        body.setContentsMargins(8, 8, 8, 8)

        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(self._section("Channel quality index over the electrode grid"))
        figure = Figure(figsize=(4.2, 4.2), facecolor=Colors.BG_PRIMARY)
        self._heatmap_ax = figure.add_subplot(111)
        self._heatmap_canvas = FigureCanvas(figure)
        self._heatmap_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._heatmap_canvas.mpl_connect("button_press_event", self._on_heatmap_click)
        self._heatmap_toolbar = self._make_toolbar(self._heatmap_canvas)
        left.addWidget(self._heatmap_toolbar)
        left.addWidget(self._heatmap_canvas, stretch=1)

        left.addWidget(self._section("Evidence"))
        self._evidence_table = QTableWidget(0, 5)
        self._evidence_table.setHorizontalHeaderLabels(
            ["Metric", "Value", "Threshold", "State", "Reading"])
        self._evidence_table.verticalHeader().setVisible(False)
        self._evidence_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._evidence_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._evidence_table.setMaximumHeight(230)
        self._evidence_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.Stretch)
        left.addWidget(self._evidence_table)
        body.addLayout(left, stretch=42)

        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(self._section(
            "All channels — measured values, never a bare verdict"))
        self._channel_table = QTableWidget(0, len(_TABLE_COLUMNS))
        self._channel_table.setHorizontalHeaderLabels([c[0] for c in _TABLE_COLUMNS])
        self._channel_table.verticalHeader().setVisible(False)
        self._channel_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._channel_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._channel_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._channel_table.setSortingEnabled(True)
        self._channel_table.horizontalHeader().setSectionResizeMode(
            len(_TABLE_COLUMNS) - 1, QHeaderView.Stretch)
        self._channel_table.itemSelectionChanged.connect(self._on_channel_selected)
        right.addWidget(self._channel_table, stretch=1)

        self._channel_summary_lbl = QLabel("Run QC to grade the channels.")
        self._channel_summary_lbl.setStyleSheet(
            f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        right.addWidget(self._channel_summary_lbl)
        body.addLayout(right, stretch=58)

        self._draw_empty_heatmap()
        return page

    # -- small builders ------------------------------------------------

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        return label

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(_SECTION_STYLE)
        return label

    @staticmethod
    def _combo(width: int, items=None) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(width)
        if items:
            combo.addItems(items)
        return combo

    def _make_toolbar(self, canvas: FigureCanvas) -> NavigationToolbar:
        """The standard matplotlib toolbar — Save, zoom, pan, reset.

        Same treatment as Crop Signal and the Density Map, so the Save
        button sits where it does in every other plot in the app.
        """
        toolbar = NavigationToolbar(canvas, self)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px;
            }}
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px;
            }}
            QToolButton:hover {{
                background-color: {Colors.GRAY_100};
                border-color: {Colors.BORDER_DEFAULT};
            }}
        """)
        return toolbar

    @staticmethod
    def _outline_button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BG_PRIMARY}; "
            f"color: {Colors.BLUE_600}; border: 1px solid {Colors.BLUE_500}; "
            f"border-radius: 4px; padding: 5px 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.BLUE_50}; }}"
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; "
            f"border-color: {Colors.BORDER_DEFAULT}; }}"
        )
        button.setToolTip(tooltip)
        return button

    def _card_row(self, left_label: str, right_label: str):
        row = QHBoxLayout()
        row.setSpacing(6)
        left = self._make_metric_card(left_label)
        right = self._make_metric_card(right_label)
        row.addWidget(left)
        row.addWidget(right)
        return row, left, right

    @staticmethod
    def _make_metric_card(label: str) -> QGroupBox:
        box = QGroupBox()
        box.setStyleSheet(
            f"QGroupBox {{ background-color: {Colors.BG_PRIMARY}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 8px; }}"
        )
        layout = QVBoxLayout(box)
        layout.setSpacing(2)
        value = QLabel("—")
        value.setAlignment(Qt.AlignCenter)
        value.setObjectName("value")
        value.setStyleSheet("font-size: 20px; font-weight: 700;")
        caption = QLabel(label)
        caption.setAlignment(Qt.AlignCenter)
        caption.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")
        layout.addWidget(value)
        layout.addWidget(caption)
        return box

    @staticmethod
    def _set_card(box: QGroupBox, text: str, color: str = None):
        value = box.findChild(QLabel, "value")
        if value is not None:
            value.setText(text)
            value.setStyleSheet(
                f"font-size: 20px; font-weight: 700; color: {color or Colors.TEXT_PRIMARY};")

    def _set_verdict_style(self, verdict: str):
        palette = {
            PASS: (Colors.GREEN_50, Colors.GREEN_600, Colors.GREEN_800),
            BORDERLINE: (Colors.YELLOW_50, Colors.YELLOW_600, Colors.YELLOW_600),
            FAIL: (Colors.RED_50, Colors.RED_600, Colors.RED_700),
            NOT_AVAILABLE: (Colors.BG_TERTIARY, Colors.BORDER_DEFAULT, Colors.TEXT_SECONDARY),
        }[verdict]
        background, border, text = palette
        self._verdict_lbl.setStyleSheet(
            f"background-color: {background}; border: 1px solid {border}; "
            f"border-radius: 6px; padding: 10px 12px; color: {text}; font-size: 13px;"
        )

    # ------------------------------------------------------------------
    # Grid selection
    # ------------------------------------------------------------------

    def _populate_grid_combo(self):
        self._grid_combo.blockSignals(True)
        self._grid_combo.clear()
        emg_file = global_state.get_emg_file()
        if emg_file and emg_file.grids:
            for grid in emg_file.grids:
                label = grid.grid_key + (f"  [{grid.muscle}]" if grid.muscle else "")
                self._grid_combo.addItem(label, userData=grid.grid_key)
        self._grid_combo.blockSignals(False)
        self._on_grid_changed()

    def _on_grid_changed(self):
        self._grid_key = None
        self._display_grid = None
        self._windows_override = None
        emg_file = global_state.get_emg_file()
        index = self._grid_combo.currentIndex()
        if not emg_file or index < 0 or not emg_file.grids:
            self._run_btn.setEnabled(False)
            return

        grid_key = self._grid_combo.itemData(index)
        grid = emg_file.get_grid(grid_key=grid_key)
        if grid is None:
            self._run_btn.setEnabled(False)
            return

        self._grid_key = grid_key
        self._display_grid = self._resolve_display_grid(grid)
        self._default_scope_for(grid)
        self._run_btn.setEnabled(True)
        self._show_result(self._results_by_grid.get(grid_key))

    def _default_scope_for(self, grid):
        """Measure the selection when there is one, the whole grid otherwise.

        A file straight off disk has every EMG channel deselected, so insisting
        on a selection would make QC unusable exactly when it is most needed.
        """
        status = global_state.get_channel_status()
        selected = any(
            channel is not None and channel < len(status) and status[channel]
            for channel in grid.emg_indices
        )
        self._scope_combo.blockSignals(True)
        self._scope_combo.setCurrentText(
            "selected channels" if selected else "all channels")
        self._scope_combo.blockSignals(False)

    def _resolve_display_grid(self, grid) -> np.ndarray:
        """The physical electrode layout, or a plain column-major fallback."""
        electrode = self._grid_handler._extract_electrode_name(grid.emg_indices)
        display_grid = get_display_grid(electrode, grid.rows, grid.cols)
        if display_grid is None:
            display_grid = np.arange(grid.rows * grid.cols,
                                     dtype=float).reshape(grid.rows, grid.cols)
        return display_grid

    def _on_definition_changed(self):
        """A different definition invalidates the result it produced."""
        self._settings = ga_qc_config.load()
        if self._grid_key and self._grid_key in self._results_by_grid:
            self._status_lbl.setText("Definition changed — run QC again.")

    def _reference_for(self, grid):
        """The performed path if the grid names one, else its first reference."""
        refs = list(grid.ref_indices or [])
        index = getattr(grid, "performed_path_idx", None)
        if index is None or index not in refs:
            index = refs[0] if refs else None
        if index is None:
            return None, ""
        return int(index), self._describe(int(index))

    @staticmethod
    def _describe(channel: int) -> str:
        emg_file = global_state.get_emg_file()
        description = emg_file.description if emg_file is not None else None
        try:
            name = description[channel]
            while isinstance(name, np.ndarray):
                name = name.item() if name.size == 1 else name.flat[0]
            return str(name)
        except (IndexError, TypeError, KeyError, ValueError):
            return f"Channel {channel + 1}"

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def _start_analysis(self):
        if self._thread is not None:
            return  # a run is already in flight; let it finish
        emg_file = global_state.get_emg_file()
        data = global_state.get_effective_emg_data()
        time = global_state.get_effective_time()
        if emg_file is None or data is None or time is None or self._display_grid is None:
            return
        grid = emg_file.get_grid(grid_key=self._grid_key)
        if grid is None:
            return

        self._settings = ga_qc_config.load()
        reference_index, reference_label = self._reference_for(grid)
        kwargs = dict(
            data=data, time=time, fs=float(emg_file.sampling_frequency), grid=grid,
            display_grid=self._display_grid,
            channel_status=list(global_state.get_channel_status()),
            channel_scope=("all" if self._scope_combo.currentText() == "all channels"
                           else "selected"),
            thresholds=self._settings.thresholds,
            derivation=self._derivation_combo.currentText(),
            method=self._method_combo.currentText(),
            diff_direction="cols" if self._axis_combo.currentText() == "columns" else "rows",
            reference_index=reference_index, reference_label=reference_label,
            windows=self._windows_override,
            rest_below_pct=self._settings.rest_below_pct,
            min_rest_s=self._settings.min_rest_s,
            peak_ms=self._settings.peak_window_ms,
            fallback_s=self._settings.fallback_s,
            bpf=self._settings.bpf, smooth=self._settings.smooth,
            line_freqs=self._settings.line_freqs,
        )

        self._set_busy(True)
        self._thread = QThread(self)
        self._worker = _QCWorker(kwargs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.failed.connect(self._on_analysis_failed)
        self._thread.start()

    def _set_busy(self, busy: bool):
        for widget in (self._run_btn, self._grid_combo, self._derivation_combo,
                       self._method_combo, self._axis_combo, self._scope_combo):
            widget.setEnabled(not busy)
        self._redetect_btn.setEnabled(not busy and self._result is not None)
        if busy:
            self._spinner_idx = 0
            self._spinner_timer.start()
        else:
            self._spinner_timer.stop()
            self._status_lbl.setText("")

    def _tick_spinner(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_idx = (self._spinner_idx + 1) % len(frames)
        self._status_lbl.setText(f"{frames[self._spinner_idx]}  measuring…")

    def _clear_thread(self):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    def _on_analysis_done(self, result: GlobalAmplitudeQCResult):
        self._clear_thread()
        self._results_by_grid[result.grid_key] = result
        # Hand the report to the state so a save carries it into the JSON.
        global_state.set_ga_qc_report(
            result.grid_key, qc_report(result, self._sampling_frequency()))
        self._set_busy(False)
        self._show_result(result)

    def _on_analysis_failed(self, message: str):
        self._clear_thread()
        self._set_busy(False)
        QMessageBox.warning(self, "Global Amplitude QC", message)

    def _redetect_windows(self):
        self._windows_override = None
        self._start_analysis()

    # ------------------------------------------------------------------
    # Presenting
    # ------------------------------------------------------------------

    def _show_result(self, result: Optional[GlobalAmplitudeQCResult]):
        self._result = result
        enabled = result is not None
        for widget in (self._export_btn, self._review_btn, self._redetect_btn):
            widget.setEnabled(enabled)
        self._suggest_btn.setEnabled(enabled and bool(result.failing))

        if result is None:
            self._verdict_lbl.setText("Run QC to measure this grid.")
            self._set_verdict_style(NOT_AVAILABLE)
            for card in (self._floor_card, self._peak_card, self._ratio_card,
                         self._channels_card):
                self._set_card(card, "—")
            self._grades_lbl.setText("—")
            self._windows_lbl.setText("")
            self._channel_table.setRowCount(0)
            self._evidence_table.setRowCount(0)
            self._channel_summary_lbl.setText("Run QC to grade the channels.")
            self._draw_empty_plot()
            self._draw_empty_heatmap()
            return

        self._update_verdict(result)
        self._update_cards(result)
        self._update_grades(result)
        self._update_windows_label(result)
        self._draw_plot(result)
        self._draw_heatmap(result)
        self._fill_channel_table(result)

    def _update_verdict(self, result):
        self._set_verdict_style(result.verdict)
        if result.verdict == NOT_AVAILABLE:
            fraction = int(round(100 * result.thresholds.min_channel_fraction))
            detail = (f"Fewer than {fraction} % of this grid's channels are selected, "
                      f"so the activation ratio of {_fmt(result.activation_ratio, 2)}× "
                      f"describes a selection rather than a grid.")
        else:
            detail = (f"Amplitude at the peak is <b>{_fmt(result.activation_ratio, 2)} ×</b> "
                      f"the resting floor; this grid needs "
                      f"<b>{result.thresholds.grid_pass:.2f} ×</b>.")
        if result.channel_scope == "all":
            detail += ("<br><i>Measured over every channel of the grid — no selection "
                       "was applied.</i>")
        self._verdict_lbl.setText(
            f"<b>{_VERDICT_TEXT[result.verdict]}</b><br>{detail}")

    def _update_cards(self, result):
        self._set_card(self._floor_card, _fmt(result.resting_floor, 2))
        self._set_card(self._peak_card, _fmt(result.peak_mean, 2))
        self._set_card(self._ratio_card, f"{_fmt(result.activation_ratio, 2)}×",
                       GRADE_COLOR[result.verdict])
        self._set_card(self._channels_card,
                       f"{result.n_selected} / {result.n_grid_channels}")
        scope = ("every channel of the grid was measured (no selection applied)"
                 if result.channel_scope == "all"
                 else f"{result.n_selected} of {result.n_grid_channels} channels are "
                      f"selected")
        self._channels_card.findChild(QLabel, "value").setToolTip(
            f"{scope}; the {result.derivation} derivation reduced them to "
            f"{result.n_channels} channels of global amplitude."
        )

    def _update_grades(self, result):
        counts = result.grades
        drivers = {}
        for channel in result.channels:
            if channel.grade == FAIL and channel.worst_check:
                drivers[channel.worst_check] = drivers.get(channel.worst_check, 0) + 1
        ranked = sorted(drivers.items(), key=lambda item: -item[1])[:3]
        driver_text = ", ".join(
            f"<b>{CHECK_LABELS[check].lower()}</b> on {count}" for check, count in ranked)
        summary = (f"{counts[PASS]} pass · {counts[BORDERLINE]} borderline · "
                   f"{counts[FAIL]} fail")
        if driver_text:
            summary += f"<br>Worst driver: {driver_text}."
        self._grades_lbl.setText(summary)
        self._suggest_btn.setText(f"Suggest deselection ({len(result.failing)})")

    def _update_windows_label(self, result):
        fs = self._sampling_frequency()
        rest = " + ".join(f"{start / fs:.1f}–{stop / fs:.1f} s"
                          for start, stop in result.windows.rest)
        peak_start, peak_stop = result.windows.peak
        self._windows_lbl.setText(
            f"Rest {rest}  ·  Peak {peak_start / fs:.2f}–{peak_stop / fs:.2f} s  "
            f"({result.windows.source})"
        )

    @staticmethod
    def _sampling_frequency() -> float:
        emg_file = global_state.get_emg_file()
        return float(emg_file.sampling_frequency) if emg_file else 1.0

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def _draw_empty_plot(self):
        self._plot_ax.clear()
        self._plot_ax.text(0.5, 0.5, "Run QC to see the global amplitude",
                           ha="center", va="center", fontsize=10,
                           color=Colors.TEXT_MUTED,
                           transform=self._plot_ax.transAxes)
        self._plot_ax.set_xticks([])
        self._plot_ax.set_yticks([])
        self._plot_canvas.draw_idle()

    def _draw_plot(self, result: GlobalAmplitudeQCResult):
        axes = self._plot_ax
        figure = axes.figure
        figure.clear()
        axes = figure.add_subplot(111)
        self._plot_ax = axes

        time = result.time
        floor = result.resting_floor
        pass_mark = floor * result.thresholds.grid_pass if np.isfinite(floor) else np.nan

        for start, stop in result.windows.rest:
            axes.axvspan(time[start], time[min(stop, time.size - 1)],
                         color=Colors.BLUE_100, alpha=0.5, zorder=0)

        if result.ref_signal is not None:
            self._draw_reference(axes, result)

        axes.plot(time, result.amplitude, linewidth=0.8, color=Colors.BLUE_600,
                  label=f"{result.derivation} global amplitude", zorder=3)
        if np.isfinite(floor):
            axes.axhline(floor, color=Colors.RED_700, linewidth=1.2,
                         label=f"resting floor {floor:.2f} µV", zorder=4)
            axes.axhline(pass_mark, color=Colors.RED_700, linewidth=1.2, linestyle="--",
                         label=f"pass mark {result.thresholds.grid_pass:.2f} × the floor",
                         zorder=4)

        peak_start, peak_stop = result.windows.peak
        axes.axvspan(time[peak_start], time[min(peak_stop, time.size - 1)],
                     color=Colors.GRAY_400, alpha=0.55, zorder=2,
                     label="peak window")
        if np.isfinite(result.peak_mean):
            axes.plot([time[peak_start], time[min(peak_stop, time.size - 1)]],
                      [result.peak_mean] * 2, color=Colors.GREEN_700, linewidth=3,
                      label=f"window mean {result.peak_mean:.2f} µV", zorder=5)

        axes.set_xlabel("time [s]", fontsize=9)
        axes.set_ylabel("global amplitude [µV]", fontsize=9)
        axes.tick_params(labelsize=8)
        axes.legend(fontsize=7, loc="upper right", framealpha=0.9)
        figure.tight_layout()
        self._attach_span(axes)
        self._plot_toolbar.update()  # the axes are new; drop the old view stack
        self._plot_canvas.draw_idle()

    def _draw_reference(self, axes, result):
        """The performed path behind the amplitude, scaled so the axes align.

        A twin axis rather than a second subplot: the question is whether the
        amplitude rises *where the force does*, and that is easiest to see
        when the two share an x axis and a visual baseline.
        """
        twin = axes.twinx()
        reference = result.ref_signal
        twin.fill_between(result.time, reference, np.nanmin(reference),
                          color=Colors.YELLOW_500, alpha=0.25, zorder=1)
        twin.plot(result.time, reference, color="#b45309", linewidth=1.1,
                  alpha=0.85, zorder=1)
        twin.set_ylabel(result.ref_label or "performed path", fontsize=8,
                        color="#b45309")
        twin.tick_params(axis="y", labelsize=8, colors="#b45309")
        axes.set_zorder(twin.get_zorder() + 1)
        axes.patch.set_visible(False)

    def _attach_span(self, axes):
        """One span selector, pointed at whichever window the user picked."""
        try:
            self._span = SpanSelector(
                axes, self._on_span_selected, "horizontal", useblit=True,
                props=dict(alpha=0.25, facecolor=Colors.BLUE_500),
                interactive=False, drag_from_anywhere=True,
            )
        except TypeError:  # matplotlib < 3.5 spells the arguments differently
            self._span = SpanSelector(
                axes, self._on_span_selected, "horizontal", useblit=True,
                rectprops=dict(alpha=0.25, facecolor=Colors.BLUE_500),
            )

    def _on_span_selected(self, t_min: float, t_max: float):
        if self._result is None or t_max <= t_min:
            return
        if self._plot_toolbar.mode != "":
            return  # the toolbar owns this drag: zooming, not windowing
        time = self._result.time
        start = int(np.searchsorted(time, t_min))
        stop = int(np.searchsorted(time, t_max))
        if stop - start < 2:
            return

        current = self._result.windows
        if self._drag_combo.currentText() == "peak window":
            windows = QCWindows(rest=list(current.rest), peak=(start, stop),
                                source="manual")
        else:
            windows = QCWindows(rest=[(start, stop)], peak=current.peak,
                                source="manual")
        self._windows_override = windows
        self._start_analysis()

    # ------------------------------------------------------------------
    # Channels view
    # ------------------------------------------------------------------

    def _draw_empty_heatmap(self):
        self._heatmap_ax.clear()
        self._heatmap_ax.text(0.5, 0.5, "Run QC to grade the channels",
                              ha="center", va="center", fontsize=10,
                              color=Colors.TEXT_MUTED,
                              transform=self._heatmap_ax.transAxes)
        self._heatmap_ax.set_xticks([])
        self._heatmap_ax.set_yticks([])
        self._heatmap_canvas.draw_idle()

    def _draw_heatmap(self, result, focus: Optional[int] = None):
        """CQI where the electrode physically sits, so a bad patch reads as one."""
        axes = self._heatmap_ax
        axes.clear()
        display_grid = self._display_grid
        if display_grid is None:
            return

        emg_file = global_state.get_emg_file()
        grid = emg_file.get_grid(grid_key=result.grid_key) if emg_file else None
        if grid is None:
            return
        emg_indices = list(grid.emg_indices)
        by_channel = {channel.channel_index: channel for channel in result.channels}

        rows, cols = display_grid.shape
        self._heatmap_cells = {}
        for row in range(rows):
            for col in range(cols):
                cell = display_grid[row, col]
                if np.isnan(cell) or int(cell) >= len(emg_indices):
                    continue
                channel_index = emg_indices[int(cell)]
                channel = by_channel.get(channel_index)
                if channel is None:
                    continue
                self._heatmap_cells[(row, col)] = channel_index
                focused = channel_index == focus
                axes.add_patch(_cell_patch(col, row, GRADE_COLOR[channel.grade], focused))
                axes.text(col, row, f"{channel.cqi}", ha="center", va="center",
                          fontsize=8, fontweight="bold", color="white", zorder=3)
                axes.text(col, row - 0.30, f"{channel_index + 1}", ha="center",
                          va="center", fontsize=6, color="white", alpha=0.85, zorder=3)

        axes.set_xlim(-0.6, cols - 0.4)
        axes.set_ylim(rows - 0.4, -0.6)
        axes.set_aspect("equal")
        axes.set_xticks([])
        axes.set_yticks([])
        for spine in axes.spines.values():
            spine.set_visible(False)
        axes.figure.tight_layout()
        self._heatmap_toolbar.update()
        self._heatmap_canvas.draw_idle()

    def _on_heatmap_click(self, event):
        if event.inaxes is not self._heatmap_ax or self._result is None:
            return
        if self._heatmap_toolbar.mode != "":
            return
        cell = (int(round(event.ydata)), int(round(event.xdata)))
        channel_index = getattr(self, "_heatmap_cells", {}).get(cell)
        if channel_index is None:
            return
        self._select_channel_row(channel_index)

    def _fill_channel_table(self, result):
        table = self._channel_table
        table.setSortingEnabled(False)
        table.setRowCount(len(result.channels))
        ordered = sorted(result.channels, key=lambda channel: channel.cqi)

        for row, channel in enumerate(ordered):
            values = channel.values
            cells = [
                _numeric_item(channel.channel_index + 1, f"{channel.channel_index + 1}"),
                _numeric_item(channel.cqi, f"{channel.cqi}"),
                _metric_item(values.get("activation_ratio"), 2),
                _metric_item(values.get("amplitude_z"), 1),
                _metric_item(values.get("spectrum_z"), 1),
                _metric_item(values.get("line_noise"), 1),
                _metric_item(values.get("clipping"), 3),
                _metric_item(values.get("neighbor_correlation"), 2),
                _grade_item(channel.grade),
                QTableWidgetItem(CHECK_LABELS.get(channel.worst_check, "—")),
            ]
            for column, item in enumerate(cells):
                item.setData(Qt.UserRole + 1, channel.channel_index)
                table.setItem(row, column, item)

        table.setSortingEnabled(True)
        table.resizeColumnsToContents()
        counts = result.grades
        self._channel_summary_lbl.setText(
            f"{len(result.channels)} channels — {counts[PASS]} pass, "
            f"{counts[BORDERLINE]} borderline, {counts[FAIL]} fail. "
            f"Click a row or an electrode to see its evidence."
        )
        if ordered:
            self._select_channel_row(ordered[0].channel_index)

    def _select_channel_row(self, channel_index: int):
        table = self._channel_table
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(Qt.UserRole + 1) == channel_index:
                table.selectRow(row)
                table.scrollToItem(item)
                return

    def _on_channel_selected(self):
        if self._result is None:
            return
        items = self._channel_table.selectedItems()
        if not items:
            return
        channel_index = items[0].data(Qt.UserRole + 1)
        channel = next((c for c in self._result.channels
                        if c.channel_index == channel_index), None)
        if channel is None:
            return
        self._fill_evidence_table(channel)
        self._draw_heatmap(self._result, focus=channel_index)

    def _fill_evidence_table(self, channel):
        thresholds = self._result.thresholds
        rows = [check for check in CHECKS if check in channel.states]
        table = self._evidence_table
        table.setRowCount(len(rows))

        for row, check in enumerate(rows):
            value = channel.values.get(check)
            if check == "flat":
                shown, bound = ("yes" if value else "no"), "must be no"
            else:
                pass_at, fail_at = thresholds.bounds(check)
                shown = _fmt(value, 3 if check == "clipping" else 2)
                comparison = "≥" if check in ("activation_ratio", "neighbor_correlation") else "≤"
                bound = f"{comparison} {pass_at:g} pass"
            table.setItem(row, 0, QTableWidgetItem(CHECK_LABELS[check]))
            table.setItem(row, 1, QTableWidgetItem(shown))
            table.setItem(row, 2, QTableWidgetItem(bound))
            table.setItem(row, 3, _grade_item(channel.states[check]))
            table.setItem(row, 4, QTableWidgetItem(_reading(check, channel)))

        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_method_dialog(self):
        GaQcMethodDialog(self).exec_()

    def _open_suggestion_dialog(self):
        if self._result is None or not self._result.failing:
            return

        status = global_state.get_channel_status()
        grid_channels = [channel.channel_index for channel in self._result.channels]
        seeds_selection = not any(
            channel < len(status) and status[channel] for channel in grid_channels)

        dialog = GaQcSuggestionDialog(self._result, self, seeds_selection=seeds_selection)
        if dialog.exec_() != QDialog.Accepted:
            return

        rejected = set(dialog.selected_channels())
        for channel in grid_channels:
            if channel in rejected:
                status[channel] = False
            elif seeds_selection:
                # First selection for this grid: everything that was not
                # rejected is selected, rather than left deselected forever.
                status[channel] = True
        global_state.set_channel_status(status)
        if self._main_window is not None and hasattr(self._main_window, "display_page"):
            self._main_window.display_page()

        if seeds_selection:
            summary = (f"{len(grid_channels) - len(rejected)} channels selected and "
                       f"{len(rejected)} left out in grid '{self._result.grid_key}'.")
        else:
            summary = (f"{len(rejected)} channels deselected in grid "
                       f"'{self._result.grid_key}'.")
        QMessageBox.information(
            self, "Global Amplitude QC",
            f"{summary}\n\nRun QC again to recompute the global amplitude over the "
            "channels that remain."
        )

    def _export_json(self):
        if self._result is None:
            return
        emg_file = global_state.get_emg_file()
        stem = os.path.splitext(emg_file.file_name or "qc")[0] if emg_file else "qc"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export QC Report",
            f"{stem}_{self._result.grid_key}_ga_qc.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(qc_report(self._result, self._sampling_frequency()),
                          handle, indent=4)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete",
                                f"QC report written to {os.path.basename(path)}.")

    def results(self) -> dict:
        """Every grid measured in this session, keyed by grid_key."""
        return dict(self._results_by_grid)

    def closeEvent(self, event):
        self._spinner_timer.stop()
        self._clear_thread()
        super().closeEvent(event)


# ----------------------------------------------------------------------
# Table item helpers
# ----------------------------------------------------------------------

def _fmt(value, digits: int) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:.{digits}f}"


def _numeric_item(sort_value, text: str) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setData(Qt.DisplayRole, sort_value)
    item.setText(text)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _metric_item(value, digits: int) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setData(Qt.DisplayRole, float(value) if value is not None else float("inf"))
    item.setText(_fmt(value, digits))
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _grade_item(grade: str) -> QTableWidgetItem:
    from PyQt5.QtGui import QBrush, QColor

    item = QTableWidgetItem(grade)
    background, foreground = GRADE_TEXT[grade]
    item.setBackground(QBrush(QColor(background)))
    item.setForeground(QBrush(QColor(foreground)))
    item.setTextAlignment(Qt.AlignCenter)
    return item


def _reading(check: str, channel) -> str:
    """A sentence saying what the number means for this channel."""
    values = channel.values
    if check == "activation_ratio":
        return (f"peak {_fmt(values.get('peak_amplitude_uv'), 1)} µV over rest "
                f"{_fmt(values.get('rest_amplitude_uv'), 1)} µV")
    if check == "amplitude_z":
        return "against the median and MAD of this grid"
    if check == "spectrum_z":
        return f"MNF {_fmt(values.get('mnf_hz'), 0)} Hz"
    if check == "line_noise":
        return "worst harmonic against the ring around it"
    if check == "clipping":
        return "share of samples at the amplifier rail"
    if check == "neighbor_correlation":
        return "best of its up-to-four grid neighbours, in the peak window"
    if check == "flat":
        return "no signal at all" if values.get("flat") else "carries signal"
    return ""


def _cell_patch(col: int, row: int, color: str, focused: bool):
    from matplotlib.patches import Rectangle

    return Rectangle(
        (col - 0.45, row - 0.45), 0.9, 0.9, facecolor=color,
        edgecolor=Colors.TEXT_PRIMARY if focused else "white",
        linewidth=2.0 if focused else 1.0, zorder=2,
    )
