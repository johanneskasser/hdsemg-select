from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QPushButton, QLabel,
    QFileDialog, QMessageBox, QSizePolicy,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from hdsemg_select.controller.grid_setup_handler import GridSetupHandler
from hdsemg_select.select_logic.fiber_trajectory import FiberTrajectoryAnalyzer, FiberTrajectoryResult
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.electrode_layout import get_display_grid
from hdsemg_select.ui.theme import Colors
from hdsemg_select.version import __version__

_LITERATURE_TEXT = (
    "Method: Pairwise XCorr + delay plane fitting  |  "
    "Farina & Merletti, J Neurosci Methods 134:199-208, 2004"
)
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# ------------------------------------------------------------------
# Background worker
# ------------------------------------------------------------------

class _AnalysisWorker(QObject):
    finished = pyqtSignal(object)   # FiberTrajectoryResult
    error = pyqtSignal(str)

    def __init__(
        self,
        analyzer: FiberTrajectoryAnalyzer,
        signals: np.ndarray,
        grid,
        display_grid: np.ndarray,
        fs: float,
    ):
        super().__init__()
        self._analyzer = analyzer
        self._signals = signals
        self._grid = grid
        self._display_grid = display_grid
        self._fs = fs

    def run(self):
        try:
            result = self._analyzer.analyze(
                self._signals, self._grid, self._display_grid, self._fs
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ------------------------------------------------------------------
# Dialog
# ------------------------------------------------------------------

class FiberTrajectoryDialog(QDialog):
    """Fiber trajectory analysis dialog.

    Estimates muscle fiber angle, conduction velocity, innervation zone,
    and grid alignment quality from HD-sEMG electrode array data.
    Analysis runs in a background thread to keep the UI responsive.
    """

    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self._grid_handler = grid_handler
        self._result: Optional[FiberTrajectoryResult] = None
        self._grid_key: Optional[str] = None
        self._display_grid: Optional[np.ndarray] = None
        self._emg_indices: list = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[_AnalysisWorker] = None
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(80)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        flags = self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle("Fiber Trajectory Analysis")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self.resize(900, 600)

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

        body = QHBoxLayout()
        body.setSpacing(8)
        body.addLayout(self._build_grid_panel(), stretch=55)
        body.addLayout(self._build_results_panel(), stretch=45)
        root.addLayout(body, stretch=1)

    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        grid_lbl = QLabel("Grid:")
        grid_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._grid_combo = QComboBox()
        self._grid_combo.setMinimumWidth(160)
        self._grid_combo.currentTextChanged.connect(self._on_grid_changed)

        self._window_lbl = QLabel("")
        self._window_lbl.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")

        self._run_btn = QPushButton("▶  Run Analysis")
        self._run_btn.setMinimumWidth(130)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BLUE_600}; color: white; "
            f"border-radius: 4px; padding: 5px 14px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.BLUE_700}; }}"
            f"QPushButton:disabled {{ background-color: {Colors.BORDER_DEFAULT}; "
            f"color: {Colors.TEXT_MUTED}; }}"
        )
        self._run_btn.clicked.connect(self._start_analysis)
        self._run_btn.setEnabled(False)

        self._auto_btn = QPushButton("Auto Detect")
        self._auto_btn.setMinimumWidth(110)
        self._auto_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BG_PRIMARY}; color: {Colors.BLUE_600}; "
            f"border: 1px solid {Colors.BLUE_500}; border-radius: 4px; "
            f"padding: 5px 14px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.BLUE_50}; }}"
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; "
            f"border-color: {Colors.BORDER_DEFAULT}; }}"
        )
        self._auto_btn.setToolTip(
            "Run analysis and suggest whether rows or columns are parallel to the fibers"
        )
        self._auto_btn.clicked.connect(self._start_auto_detect)
        self._auto_btn.setEnabled(False)

        self._export_btn = QPushButton("Export JSON")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_json)

        bar.addWidget(grid_lbl)
        bar.addWidget(self._grid_combo)
        bar.addSpacing(8)
        bar.addWidget(self._window_lbl)
        bar.addStretch()
        bar.addWidget(self._auto_btn)
        bar.addWidget(self._run_btn)
        bar.addWidget(self._export_btn)
        return bar

    def _build_grid_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)
        lbl = QLabel("Electrode Grid + Trajectory")
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; text-transform: uppercase; "
            f"letter-spacing: 0.05em; color: {Colors.TEXT_MUTED};"
        )
        layout.addWidget(lbl)
        fig = Figure(figsize=(4, 4), facecolor=Colors.BG_PRIMARY)
        self._grid_ax = fig.add_subplot(111)
        self._grid_canvas = FigureCanvas(fig)
        self._grid_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._grid_canvas, stretch=1)
        self._draw_empty_grid()
        return layout

    def _build_results_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        cards_box = QGroupBox("Results")
        cards_layout = QHBoxLayout(cards_box)
        cards_layout.setSpacing(6)
        self._angle_card = self._make_metric_card("—", "Fiber angle")
        self._cv_card = self._make_metric_card("—", "Conduction velocity")
        self._iz_card = self._make_metric_card("—", "IZ position")
        self._r2_card = self._make_metric_card("—", "Alignment (R²)")
        for card in (self._angle_card, self._cv_card, self._iz_card, self._r2_card):
            cards_layout.addWidget(card)
        layout.addWidget(cards_box)

        search_lbl = QLabel("Angle search  (R² vs θ)")
        search_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; text-transform: uppercase; "
            f"letter-spacing: 0.05em; color: {Colors.TEXT_MUTED};"
        )
        layout.addWidget(search_lbl)
        fig2 = Figure(figsize=(4, 2.2), facecolor=Colors.BG_PRIMARY)
        self._search_ax = fig2.add_subplot(111)
        self._search_canvas = FigureCanvas(fig2)
        self._search_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._search_canvas, stretch=1)
        self._draw_empty_search()

        ref_lbl = QLabel(_LITERATURE_TEXT)
        ref_lbl.setWordWrap(True)
        ref_lbl.setStyleSheet(
            f"font-size: 10px; font-style: italic; color: {Colors.TEXT_MUTED}; "
            f"border-left: 3px solid {Colors.BLUE_500}; padding-left: 6px;"
        )
        layout.addWidget(ref_lbl)
        return layout

    @staticmethod
    def _make_metric_card(value: str, label: str) -> QGroupBox:
        box = QGroupBox()
        box.setStyleSheet(
            f"QGroupBox {{ background-color: {Colors.BG_PRIMARY}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 8px; }}"
        )
        vl = QVBoxLayout(box)
        vl.setSpacing(2)
        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet("font-size: 20px; font-weight: 700;")
        val_lbl.setObjectName("value")
        sub_lbl = QLabel(label)
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")
        vl.addWidget(val_lbl)
        vl.addWidget(sub_lbl)
        return box

    # ------------------------------------------------------------------
    # Grid helpers
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
        self._display_grid = None
        self._emg_indices = []
        self._grid_key = None
        emg_file = global_state.get_emg_file()
        idx = self._grid_combo.currentIndex()
        if not emg_file or idx < 0 or not emg_file.grids:
            self._set_buttons_enabled(False)
            return
        grid_key = self._grid_combo.itemData(idx)
        grid = emg_file.get_grid(grid_key=grid_key)
        if grid is None:
            self._set_buttons_enabled(False)
            return
        self._grid_key = grid_key
        self._emg_indices = list(grid.emg_indices)
        electrode_name = self._grid_handler._extract_electrode_name(grid.emg_indices)
        display_grid = get_display_grid(electrode_name, grid.rows, grid.cols)
        if display_grid is None:
            display_grid = np.arange(
                grid.rows * grid.cols, dtype=float
            ).reshape(grid.rows, grid.cols)
        self._display_grid = display_grid
        self._set_buttons_enabled(True)
        self._update_window_label()

    def _set_buttons_enabled(self, enabled: bool):
        self._run_btn.setEnabled(enabled)
        self._auto_btn.setEnabled(enabled)

    def _update_window_label(self):
        crop = global_state.get_crop_range()
        if crop is not None:
            emg_file = global_state.get_emg_file()
            fs = float(emg_file.sampling_frequency) if emg_file else 1.0
            t_start = crop[0] / fs
            t_end = crop[1] / fs
            self._window_lbl.setText(f"Window: crop {t_start:.2f}s – {t_end:.2f}s")
            self._window_lbl.setToolTip(
                "Analysing the cropped signal window.\n"
                "Change it via Signal → Crop Signal… (Ctrl+R)."
            )
        else:
            self._window_lbl.setText("Window: full signal")
            self._window_lbl.setToolTip(
                "No crop range set — the full signal will be analysed.\n"
                "Use Signal → Crop Signal… (Ctrl+R) to restrict to a contraction burst."
            )

    def _get_signals(self) -> Optional[np.ndarray]:
        return global_state.get_effective_emg_data()

    # ------------------------------------------------------------------
    # Background analysis
    # ------------------------------------------------------------------

    def _start_analysis(self, auto_detect: bool = False):
        emg_file = global_state.get_emg_file()
        if emg_file is None or self._display_grid is None:
            return
        signals = self._get_signals()
        if signals is None:
            return
        grid = emg_file.get_grid(grid_key=self._grid_key)
        if grid is None:
            return

        self._analysis_is_auto_detect = auto_detect
        self._current_grid_obj = grid

        self._set_controls_busy(True)
        self._spinner_idx = 0
        self._spinner_timer.start()

        worker = _AnalysisWorker(
            FiberTrajectoryAnalyzer(),
            signals,
            grid,
            self._display_grid,
            float(emg_file.sampling_frequency),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_analysis_done)
        worker.error.connect(self._on_analysis_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        # Clear our reference BEFORE deleteLater so closeEvent never touches a dead object
        thread.finished.connect(self._clear_thread)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _start_auto_detect(self):
        self._start_analysis(auto_detect=True)

    def _clear_thread(self):
        self._thread = None
        self._worker = None

    def _on_analysis_done(self, result: FiberTrajectoryResult):
        self._spinner_timer.stop()
        self._set_controls_busy(False)
        self._run_btn.setText("▶  Run Analysis")
        self._result = result
        self._update_metrics(result)
        self._draw_grid_overlay(result, self._current_grid_obj)
        self._draw_angle_search(result)
        self._export_btn.setEnabled(True)

        if self._analysis_is_auto_detect:
            self._show_auto_detect_suggestion(result)

    def _on_analysis_error(self, message: str):
        self._spinner_timer.stop()
        self._set_controls_busy(False)
        self._run_btn.setText("▶  Run Analysis")
        QMessageBox.warning(self, "Analysis Error", message)

    def _set_controls_busy(self, busy: bool):
        self._run_btn.setEnabled(not busy)
        self._auto_btn.setEnabled(not busy)
        self._grid_combo.setEnabled(not busy)
        if not busy:
            self._update_window_label()

    def _tick_spinner(self):
        frame = _SPINNER_FRAMES[self._spinner_idx % len(_SPINNER_FRAMES)]
        self._run_btn.setText(f"{frame}  Analyzing…")
        self._spinner_idx += 1

    # ------------------------------------------------------------------
    # Auto Detect suggestion
    # ------------------------------------------------------------------

    def _show_auto_detect_suggestion(self, result: FiberTrajectoryResult):
        angle = result.fiber_angle_deg
        r2 = result.r_squared
        cv = result.conduction_velocity_ms

        # Determine grid-axis alignment
        # angle is measured from column axis: 0° = parallel to columns, ±90° = parallel to rows
        abs_angle = abs(angle)
        if abs_angle <= 20:
            axis_label = "columns"
            orient_hint = "Columns parallel to fibers"
            aligned = True
        elif abs_angle >= 70:
            axis_label = "rows"
            orient_hint = "Rows parallel to fibers"
            aligned = True
        else:
            axis_label = None
            orient_hint = None
            aligned = False

        quality = "good" if r2 >= 0.80 else ("moderate" if r2 >= 0.60 else "poor")
        reliability_note = ""
        if r2 < 0.60:
            reliability_note = (
                "\n\n⚠️  R²={:.2f} — angle estimate is unreliable. "
                "Consider checking signal quality or using a crop range around "
                "a clean contraction burst.".format(r2)
            )

        if aligned:
            msg = (
                f"Detected fiber angle: <b>{angle:.1f}°</b>  "
                f"(CV: {cv:.2f} m/s, R²: {r2:.2f} — {quality})<br><br>"
                f"Fibers run approximately parallel to the <b>{axis_label}</b>.<br>"
                f"Suggested grid orientation: <b>{orient_hint}</b>."
                f"{reliability_note.replace(chr(10), '<br>')}"
                "<br><br>Would you like to open Grid Orientation settings to confirm?"
            )
            box = QMessageBox(self)
            box.setWindowTitle("Auto Detect — Grid Alignment")
            box.setTextFormat(Qt.RichText)
            box.setText(msg)
            open_btn = box.addButton("Open Grid Orientation…", QMessageBox.AcceptRole)
            box.addButton("Close", QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() == open_btn:
                parent = self.parent()
                if parent and hasattr(parent, "select_grid_and_orientation"):
                    parent.select_grid_and_orientation()
        else:
            msg = (
                f"Detected fiber angle: <b>{angle:.1f}°</b>  "
                f"(CV: {cv:.2f} m/s, R²: {r2:.2f} — {quality})<br><br>"
                f"Fibers run at an <b>oblique angle</b> to the electrode grid. "
                f"This is normal for muscles like Vastus Medialis Oblique — "
                f"no axis alignment change is needed."
                f"{reliability_note.replace(chr(10), '<br>')}"
            )
            box = QMessageBox(self)
            box.setWindowTitle("Auto Detect — Grid Alignment")
            box.setTextFormat(Qt.RichText)
            box.setText(msg)
            box.exec_()

    # ------------------------------------------------------------------
    # Result rendering
    # ------------------------------------------------------------------

    def _update_metrics(self, r: FiberTrajectoryResult):
        self._set_card(self._angle_card, f"{r.fiber_angle_deg:.1f}°", Colors.GREEN_600)
        self._set_card(self._cv_card, f"{r.conduction_velocity_ms:.2f} m/s", Colors.BLUE_600)
        if r.iz_position_m is not None:
            self._set_card(self._iz_card, f"{r.iz_position_m * 1000:.1f} mm", "#b45309")
            self._iz_card.setToolTip("")
        else:
            self._set_card(self._iz_card, "n/d", Colors.TEXT_MUTED)
            self._iz_card.setToolTip(
                "No innervation zone detected.\n\n"
                "The IZ is identified by a sign reversal in adjacent-electrode delays.\n"
                "If none is found, the IZ is likely outside the electrode grid —\n"
                "this is a normal result when the grid covers only one propagation side."
            )
        color = (Colors.GREEN_600 if r.r_squared >= 0.85
                 else ("#b45309" if r.r_squared >= 0.70 else "#dc2626"))
        self._set_card(self._r2_card, f"R²={r.r_squared:.2f}", color)
        if r.r_squared < 0.70:
            self._r2_card.setToolTip(
                "Poor alignment — results may be unreliable. "
                "Ensure the grid is placed parallel to the muscle fibers."
            )

    @staticmethod
    def _set_card(box: QGroupBox, text: str, color: str):
        val_lbl = box.findChild(QLabel, "value")
        if val_lbl:
            val_lbl.setText(text)
            val_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")

    def _draw_grid_overlay(self, r: FiberTrajectoryResult, grid):
        ax = self._grid_ax
        ax.clear()
        ax.set_facecolor(Colors.BG_PRIMARY)
        dg = self._display_grid
        rows, cols = dg.shape
        ied = grid.ied_mm

        xs, ys = [], []
        for row in range(rows):
            for col in range(cols):
                if not np.isnan(dg[row, col]):
                    xs.append(col * ied)
                    ys.append(row * ied)
        ax.scatter(xs, ys, c=Colors.BLUE_500, s=60, zorder=3,
                   edgecolors=Colors.BLUE_700, linewidths=0.5)

        angle_rad = np.radians(r.fiber_angle_deg)
        cx = (cols - 1) * ied / 2
        cy = (rows - 1) * ied / 2

        if r.iz_position_m is not None:
            iz_mm = r.iz_position_m * 1000
            perp_rad = np.radians(r.fiber_angle_deg + 90)
            iz_cx = cx + iz_mm * np.sin(angle_rad)
            iz_cy = cy + iz_mm * np.cos(angle_rad)
            half = max(rows, cols) * ied / 2 + ied
            ax.plot(
                [iz_cx - half * np.cos(perp_rad), iz_cx + half * np.cos(perp_rad)],
                [iz_cy - half * np.sin(perp_rad), iz_cy + half * np.sin(perp_rad)],
                color="#b45309", linewidth=1.5, linestyle="--", zorder=4,
                label="Innervation zone",
            )
            for row in range(rows):
                for col in range(cols):
                    if np.isnan(dg[row, col]):
                        continue
                    proj_m = (row * np.sin(angle_rad) + col * np.cos(angle_rad)) * grid.ied_mm * 1e-3
                    if abs(proj_m - r.iz_position_m) <= grid.ied_mm * 1e-3 * 0.6:
                        ax.scatter(col * ied, row * ied, c="#f59e0b", s=70, zorder=5,
                                   edgecolors="#b45309", linewidths=0.8)

        half = max(rows, cols) * ied / 2 + ied
        dx, dy = half * np.cos(angle_rad), half * np.sin(angle_rad)
        ax.annotate("", xy=(cx + dx, cy + dy), xytext=(cx - dx, cy - dy),
                    arrowprops=dict(arrowstyle="->", color=Colors.GREEN_600, lw=2.0))
        ax.plot([cx - dx, cx + dx], [cy - dy, cy + dy],
                color=Colors.GREEN_600, linewidth=2.0, zorder=4, label="Fiber trajectory")

        ax.set_aspect("equal")
        ax.set_xlim(-ied, (cols + 0.5) * ied)
        ax.set_ylim(-ied, (rows + 0.5) * ied)
        ax.set_xlabel("Column (mm)")
        ax.set_ylabel("Row (mm)")
        ax.legend(fontsize=8, loc="upper right")
        ax.tick_params(labelsize=8)
        ax.figure.tight_layout(pad=0.5)
        self._grid_canvas.draw()

    def _draw_angle_search(self, r: FiberTrajectoryResult):
        ax = self._search_ax
        ax.clear()
        ax.set_facecolor(Colors.BG_PRIMARY)
        ax.plot(r.search_angles, r.search_r2, color=Colors.BLUE_500, linewidth=1.5)
        ax.axvline(r.fiber_angle_deg, color=Colors.GREEN_600, linewidth=1.5,
                   linestyle="--", label=f"θ={r.fiber_angle_deg:.1f}°")
        ax.scatter([r.fiber_angle_deg], [r.r_squared], color=Colors.GREEN_600, s=40, zorder=5)
        ax.set_xlabel("Angle (°)", fontsize=8)
        ax.set_ylabel("R²", fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=8)
        ax.tick_params(labelsize=7)
        ax.figure.tight_layout(pad=0.5)
        self._search_canvas.draw()

    def _draw_empty_grid(self):
        ax = self._grid_ax
        ax.clear()
        ax.set_facecolor(Colors.BG_PRIMARY)
        ax.text(0.5, 0.5, "Run analysis to see results",
                ha="center", va="center", transform=ax.transAxes,
                color=Colors.TEXT_MUTED, fontsize=10)
        ax.set_axis_off()
        self._grid_canvas.draw()

    def _draw_empty_search(self):
        ax = self._search_ax
        ax.clear()
        ax.set_facecolor(Colors.BG_PRIMARY)
        ax.text(0.5, 0.5, "—", ha="center", va="center",
                transform=ax.transAxes, color=Colors.TEXT_MUTED, fontsize=10)
        ax.set_axis_off()
        self._search_canvas.draw()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_json(self):
        if self._result is None:
            return
        r = self._result
        default_name = f"fiber_trajectory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Fiber Trajectory Results", default_name, "JSON files (*.json)"
        )
        if not path:
            return
        emg_file = global_state.get_emg_file()
        crop = global_state.get_crop_range()
        payload = {
            "software": f"hdsemg-select v{__version__}",
            "timestamp": datetime.now().isoformat(),
            "grid_key": self._grid_key,
            "signal_window": {
                "mode": "crop_range" if crop is not None else "full_signal",
                "crop_start": int(crop[0]) if crop else None,
                "crop_end": int(crop[1]) if crop else None,
                "sampling_frequency": float(emg_file.sampling_frequency) if emg_file else None,
            },
            "results": {
                "fiber_angle_deg": r.fiber_angle_deg,
                "conduction_velocity_ms": r.conduction_velocity_ms,
                "iz_position_m": r.iz_position_m,
                "r_squared": r.r_squared,
            },
            "angle_search": {
                "angles_deg": r.search_angles.tolist(),
                "r2_values": r.search_r2.tolist(),
            },
            "pairwise": {
                "delays_ms": r.pairwise_delays_ms.tolist(),
                "positions_m": r.pairwise_distances_m.tolist(),
            },
            "literature": _LITERATURE_TEXT,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        QMessageBox.information(self, "Export", f"Results saved to:\n{os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    self._thread.quit()
                    self._thread.wait(2000)
            except RuntimeError:
                pass  # C++ object already deleted — thread finished naturally
            self._thread = None
        super().closeEvent(event)
