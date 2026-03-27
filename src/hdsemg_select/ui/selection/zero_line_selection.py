from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QGroupBox, QFormLayout, QDoubleSpinBox, QCheckBox,
    QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt

from hdsemg_select._log.log_config import logger
from hdsemg_select.select_logic.zero_line_detector import ZeroLineDetector
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles


class ZeroLineSelection:
    """
    Automatic zero-line (dead channel) detection using sliding-window relative RMS.

    A channel is flagged as bad if a significant fraction of its signal windows
    fall below a threshold relative to the grid's median RMS — catching both
    fully-dead channels and channels that get cut off mid-recording.
    """

    # Default parameter values
    _DEFAULTS = {
        "window_size_ms": 200.0,
        "relative_threshold": 8.5,    # stored as % in UI, converted to fraction for detector
        "min_dead_fraction": 10.0,    # stored as % in UI
        "min_dead_run_fraction": 20.0, # stored as % in UI
    }

    def __init__(self, parent):
        self.parent = parent
        self.window_size_ms = self._DEFAULTS["window_size_ms"]
        self.relative_threshold_pct = self._DEFAULTS["relative_threshold"]
        self.min_dead_fraction_pct = self._DEFAULTS["min_dead_fraction"]
        self.min_dead_run_fraction_pct = self._DEFAULTS["min_dead_run_fraction"]
        self.apply_to_all_grids = False

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------

    def _build_settings(self, relative_threshold_pct, min_dead_fraction_pct,
                        min_dead_run_fraction_pct, window_size_ms):
        return {
            "window_size_ms": window_size_ms,
            "relative_threshold": relative_threshold_pct / 100.0,
            "min_dead_fraction": min_dead_fraction_pct / 100.0,
            "min_dead_run_fraction": min_dead_run_fraction_pct / 100.0,
        }

    def _run_detection(self, settings: dict, grid_indices: list | None = None) -> dict | None:
        """Run detector and return {ch_idx: is_good}, or None on error.

        If grid_indices is None, uses current_grid_indices from grid_setup_handler.
        """
        scaled_data = global_state.get_scaled_data()
        emg_file = global_state.get_emg_file()

        if scaled_data is None or emg_file is None:
            return None

        if grid_indices is None:
            grid_indices = self.parent.grid_setup_handler.current_grid_indices
            if not grid_indices:
                return None

        fs = emg_file.sampling_frequency
        detector = ZeroLineDetector()
        return detector.detect(scaled_data, fs, grid_indices, settings)

    def perform_selection(self):
        """Run detection with current settings and update channel_status."""
        scaled_data = global_state.get_scaled_data()
        if scaled_data is None:
            QMessageBox.warning(self.parent, "No Data", "Please load a file first.")
            return

        settings = self._build_settings(
            self.relative_threshold_pct,
            self.min_dead_fraction_pct,
            self.min_dead_run_fraction_pct,
            self.window_size_ms,
        )

        if self.apply_to_all_grids:
            emg_file = global_state.get_emg_file()
            grids_to_process = {g.grid_key: g.emg_indices for g in emg_file.grids}
        else:
            grids_to_process = {
                self.parent.grid_setup_handler.selected_grid:
                    self.parent.grid_setup_handler.current_grid_indices
            }

        channel_status = global_state.get_channel_status()
        total_selected = total_flagged = 0
        summary_lines = []

        for grid_key, indices in grids_to_process.items():
            results = self._run_detection(settings, indices)
            if results is None:
                logger.warning(f"Zero-line detection failed for grid '{grid_key}', skipping.")
                continue

            grid_selected = grid_flagged = 0
            for ch_idx, is_good in results.items():
                channel_status[ch_idx] = is_good
                if is_good:
                    grid_selected += 1
                else:
                    grid_flagged += 1
                    labels = global_state.get_channel_labels(ch_idx).copy()
                    if BaseChannelLabel.ZERO_LINE.value not in labels:
                        labels.append(BaseChannelLabel.ZERO_LINE.value)
                        global_state.update_channel_labels(ch_idx, labels)

            total_selected += grid_selected
            total_flagged += grid_flagged
            if self.apply_to_all_grids:
                summary_lines.append(
                    f"{grid_key}: {grid_selected} selected, {grid_flagged} flagged"
                )

        global_state.set_channel_status(channel_status)
        self.parent.display_page()

        if self.apply_to_all_grids:
            detail = "\n".join(summary_lines)
            QMessageBox.information(
                self.parent,
                "Zero Line Detection — All Grids",
                f"{detail}\n\nTotal: {total_selected} selected, {total_flagged} flagged as zero-line.",
            )
        else:
            grid_name = self.parent.grid_setup_handler.selected_grid or "current grid"
            QMessageBox.information(
                self.parent,
                f"Zero Line Detection — {grid_name}",
                f"{total_selected} channels selected, {total_flagged} flagged as zero-line.",
            )

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def open_settings_dialog(self):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Zero Line Detection")
        dialog.setMinimumWidth(480)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(Spacing.LG)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # Header
        header = QLabel("Zero Line Detection")
        header.setStyleSheet(Styles.label_heading(size="lg"))
        main_layout.addWidget(header)

        description = QLabel(
            "Detects channels that are dead, cut off mid-recording, or intermittently "
            "silent. Uses a sliding-window RMS approach relative to the grid's median — "
            "no absolute amplitude threshold needed."
        )
        description.setWordWrap(True)
        description.setStyleSheet(Styles.label_secondary())
        main_layout.addWidget(description)

        # --- Parameter group ---
        param_group = QGroupBox("Detection Parameters")
        param_group.setStyleSheet(Styles.groupbox())
        form = QFormLayout()
        form.setSpacing(Spacing.MD)
        form.setLabelAlignment(Qt.AlignRight)

        def _spin(value, lo, hi, step, suffix, tooltip):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            sb.setDecimals(1)
            sb.setValue(value)
            sb.setSuffix(suffix)
            sb.setToolTip(tooltip)
            return sb

        spin_window = _spin(
            self.window_size_ms, 10.0, 2000.0, 50.0, " ms",
            "Size of each analysis window. Larger = smoother, but misses short dropouts.",
        )
        spin_rel_thr = _spin(
            self.relative_threshold_pct, 0.1, 50.0, 0.5, " %",
            "A window is considered dead if its RMS is below this fraction of the grid's "
            "median RMS. Increase to catch channels that are merely weak.",
        )
        spin_dead_frac = _spin(
            self.min_dead_fraction_pct, 0.1, 100.0, 1.0, " %",
            "A channel is flagged if more than this fraction of its windows are dead. "
            "Lower = stricter (flags channels with even brief silent periods).",
        )
        spin_dead_run = _spin(
            self.min_dead_run_fraction_pct, 0.1, 100.0, 1.0, " %",
            "A channel is also flagged if the longest consecutive silent stretch exceeds "
            "this fraction of the total recording duration. Catches abrupt cutoffs.",
        )

        form.addRow("Window size:", spin_window)
        form.addRow("Dead-window threshold:", spin_rel_thr)
        form.addRow("Max dead fraction:", spin_dead_frac)
        form.addRow("Max consecutive dead run:", spin_dead_run)

        param_group.setLayout(form)
        main_layout.addWidget(param_group)

        # --- Scope group ---
        scope_group = QGroupBox("Scope")
        scope_group.setStyleSheet(Styles.groupbox())
        scope_layout = QVBoxLayout()
        scope_layout.setSpacing(Spacing.SM)

        apply_to_all_grids_cb = QCheckBox("Apply to all grids")
        apply_to_all_grids_cb.setChecked(self.apply_to_all_grids)
        apply_to_all_grids_cb.setToolTip(
            "Run detection on every grid in the file, not just the currently selected one."
        )
        scope_layout.addWidget(apply_to_all_grids_cb)
        scope_group.setLayout(scope_layout)
        main_layout.addWidget(scope_group)

        # --- Preview label (inside a scroll area so it never clips) ---
        preview_label = QLabel("")
        preview_label.setWordWrap(True)
        preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        preview_label.setStyleSheet(f"""
            QLabel {{
                padding: {Spacing.SM}px;
                background-color: transparent;
                color: {Colors.BLUE_900};
                font-family: monospace;
            }}
        """)

        preview_scroll = QScrollArea()
        preview_scroll.setWidget(preview_label)
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFixedHeight(130)
        preview_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {Colors.BLUE_100};
                border-radius: {BorderRadius.MD};
                background-color: {Colors.BLUE_50};
            }}
        """)
        preview_scroll.setVisible(False)
        main_layout.addWidget(preview_scroll)

        # --- Preview helper ---
        def _format_preview_text(results_by_grid):
            lines = []
            total_bad = total_ch = 0
            for grid_key, results in results_by_grid.items():
                bad = [ch + 1 for ch, ok in results.items() if not ok]
                n = len(results)
                total_bad += len(bad)
                total_ch += n
                ch_str = (
                    f"  (ch {', '.join(map(str, bad))})"
                    if 0 < len(bad) <= 10
                    else ""
                )
                lines.append(f"{grid_key}: {len(bad)} of {n} flagged{ch_str}")
            lines.append("─" * 35)
            lines.append(f"Total: {total_bad} of {total_ch} channels would be flagged")
            return "\n".join(lines)

        def update_preview():
            settings = self._build_settings(
                spin_rel_thr.value(),
                spin_dead_frac.value(),
                spin_dead_run.value(),
                spin_window.value(),
            )
            if apply_to_all_grids_cb.isChecked():
                emg_file = global_state.get_emg_file()
                if emg_file is None:
                    preview_scroll.setVisible(False)
                    return
                results_by_grid = {}
                for grid in emg_file.grids:
                    r = self._run_detection(settings, grid.emg_indices)
                    if r is not None:
                        results_by_grid[grid.grid_key] = r
                if not results_by_grid:
                    preview_scroll.setVisible(False)
                    return
                preview_label.setText(_format_preview_text(results_by_grid))
                preview_scroll.setVisible(True)
            else:
                results = self._run_detection(settings)
                if results is None:
                    preview_scroll.setVisible(False)
                    return
                n_bad = sum(1 for v in results.values() if not v)
                n_total = len(results)
                preview_label.setText(
                    f"Preview: {n_bad} of {n_total} channels in the current grid would be flagged."
                )
                preview_scroll.setVisible(True)

        for spin in (spin_window, spin_rel_thr, spin_dead_frac, spin_dead_run):
            spin.valueChanged.connect(update_preview)
        apply_to_all_grids_cb.toggled.connect(update_preview)

        # Initial preview
        update_preview()

        main_layout.addStretch()

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(Spacing.SM)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(Styles.button_secondary())
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        apply_btn = QPushButton("Apply && Run Detection")
        apply_btn.setStyleSheet(Styles.button_primary())
        apply_btn.setToolTip("Save settings and immediately run zero-line detection on the selected scope")

        def apply_and_run():
            self.window_size_ms = spin_window.value()
            self.relative_threshold_pct = spin_rel_thr.value()
            self.min_dead_fraction_pct = spin_dead_frac.value()
            self.min_dead_run_fraction_pct = spin_dead_run.value()
            self.apply_to_all_grids = apply_to_all_grids_cb.isChecked()
            dialog.accept()
            self.perform_selection()

        apply_btn.clicked.connect(apply_and_run)
        button_layout.addWidget(apply_btn)

        main_layout.addLayout(button_layout)
        dialog.setLayout(main_layout)

        return dialog.exec_()
