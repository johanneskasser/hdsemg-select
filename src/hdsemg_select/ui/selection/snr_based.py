from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
)

from hdsemg_select._log.log_config import logger
from hdsemg_select.select_logic.snr_calculator import SNRCalculator
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel
from hdsemg_select.ui.theme import BorderRadius, Colors, Spacing, Styles


class SNRBasedSelection:
    def __init__(self, parent):
        self.parent = parent
        self.spike_threshold = 5.0
        self.use_rest_spike = True
        self.apply_to_all_grids = False

    def open_settings_dialog(self):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("SNR / Spike Detection")
        dialog.setMinimumWidth(520)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(Spacing.LG)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        header = QLabel("SNR / Spike Artifact Detection")
        header.setStyleSheet(Styles.label_heading(size="lg"))
        main_layout.addWidget(header)

        desc = QLabel(
            "Automatically detect and deselect channels with large spike artifacts "
            "(e.g. channels with transient peaks much larger than the rest of the electrode array)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(Styles.label_secondary())
        main_layout.addWidget(desc)

        # --- Method ---
        method_group = QGroupBox("Detection Method")
        method_group.setStyleSheet(Styles.groupbox())
        method_layout = QVBoxLayout()
        method_layout.setSpacing(Spacing.SM)

        rb_amplitude = QRadioButton(
            "Global amplitude spike — peak of channel > N × median peak across all channels\n"
            "(works for any recording; does not need a rest period)"
        )
        rb_amplitude.setChecked(not self.use_rest_spike)

        rb_rest = QRadioButton(
            "Rest-period spike — peak during rest > N × global noise floor\n"
            "(more targeted; requires a clear quiet period in the recording)"
        )
        rb_rest.setChecked(self.use_rest_spike)

        method_layout.addWidget(rb_amplitude)
        method_layout.addWidget(rb_rest)
        method_group.setLayout(method_layout)
        main_layout.addWidget(method_group)

        # --- Threshold ---
        threshold_group = QGroupBox("Spike Threshold (factor N)")
        threshold_group.setStyleSheet(Styles.groupbox())
        threshold_layout = QFormLayout()
        threshold_layout.setSpacing(Spacing.MD)

        threshold_spin = QDoubleSpinBox()
        threshold_spin.setRange(1.5, 50.0)
        threshold_spin.setSingleStep(0.5)
        threshold_spin.setValue(self.spike_threshold)
        threshold_spin.setDecimals(1)
        threshold_spin.setStyleSheet(Styles.input_field())
        threshold_layout.addRow("Factor N:", threshold_spin)

        threshold_info = QLabel(
            "A channel is flagged if its peak exceeds N times the reference level. "
            "Decrease N to catch more channels; increase N to flag only extreme outliers."
        )
        threshold_info.setWordWrap(True)
        threshold_info.setStyleSheet(Styles.label_secondary())
        threshold_layout.addRow("", threshold_info)
        threshold_group.setLayout(threshold_layout)
        main_layout.addWidget(threshold_group)

        # --- Scope ---
        scope_group = QGroupBox("Scope")
        scope_group.setStyleSheet(Styles.groupbox())
        scope_layout = QVBoxLayout()
        apply_all_cb = QCheckBox("Apply to all grids")
        apply_all_cb.setChecked(self.apply_to_all_grids)
        scope_layout.addWidget(apply_all_cb)
        scope_group.setLayout(scope_layout)
        main_layout.addWidget(scope_group)

        # --- Preview ---
        preview_label = QLabel("")
        preview_label.setWordWrap(True)
        preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        preview_label.setStyleSheet(
            f"QLabel {{ padding: {Spacing.SM}px; background-color: transparent; "
            f"color: {Colors.BLUE_900}; font-family: monospace; }}"
        )
        preview_scroll = QScrollArea()
        preview_scroll.setWidget(preview_label)
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFixedHeight(110)
        preview_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Colors.BLUE_100}; "
            f"border-radius: {BorderRadius.MD}; background-color: {Colors.BLUE_50}; }}"
        )
        preview_scroll.setVisible(False)
        main_layout.addWidget(preview_scroll)

        def refresh_preview():
            factor = threshold_spin.value()
            use_rest = rb_rest.isChecked()
            data = global_state.get_effective_scaled_data()
            emg_file = global_state.get_emg_file()
            if data is None or emg_file is None:
                preview_scroll.setVisible(False)
                return
            lines = []
            for grid in emg_file.grids:
                flagged = self._detect_for_grid(
                    data, grid.emg_indices, use_rest, factor,
                    emg_file.sampling_frequency
                )
                n_valid = len([i for i in grid.emg_indices if i is not None])
                suffix = ""
                if 0 < len(flagged) <= 10:
                    suffix = f"  (ch {', '.join(str(c + 1) for c in flagged)})"
                lines.append(f"{grid.grid_key}: {len(flagged)} of {n_valid} would be flagged{suffix}")
            preview_label.setText("\n".join(lines))
            preview_scroll.setVisible(True)

        rb_amplitude.toggled.connect(lambda _: refresh_preview())
        rb_rest.toggled.connect(lambda _: refresh_preview())
        threshold_spin.valueChanged.connect(lambda _: refresh_preview())
        apply_all_cb.toggled.connect(lambda _: refresh_preview())
        refresh_preview()

        main_layout.addStretch()

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.SM)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(Styles.button_secondary())
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()

        run_btn = QPushButton("Apply && Run")
        run_btn.setStyleSheet(Styles.button_primary())
        run_btn.clicked.connect(
            lambda: self._apply_and_run(dialog, threshold_spin, rb_rest, apply_all_cb)
        )
        btn_layout.addWidget(run_btn)
        main_layout.addLayout(btn_layout)

        dialog.setLayout(main_layout)
        return dialog.exec_()

    def _apply_and_run(self, dialog, threshold_spin, rb_rest, apply_all_cb):
        self.spike_threshold = threshold_spin.value()
        self.use_rest_spike = rb_rest.isChecked()
        self.apply_to_all_grids = apply_all_cb.isChecked()
        dialog.accept()
        self.perform_selection()

    def _detect_for_grid(
        self,
        data,
        emg_indices: list,
        use_rest_spike: bool,
        threshold: float,
        fs: float,
    ) -> list:
        if use_rest_spike:
            plateau_mask = SNRCalculator.compute_plateau_mask(data, emg_indices, fs)
            active_samples = int(plateau_mask.sum())
            rest_samples = int((~plateau_mask).sum())
            if active_samples < 50 or rest_samples < 50:
                logger.info(
                    "SNR spike detection: no clear plateau (active=%d, rest=%d), "
                    "falling back to global amplitude method",
                    active_samples, rest_samples,
                )
                return SNRCalculator.detect_amplitude_spikes(data, emg_indices, threshold)
            return SNRCalculator.detect_rest_spikes(data, emg_indices, plateau_mask, threshold)
        return SNRCalculator.detect_amplitude_spikes(data, emg_indices, threshold)

    def perform_selection(self):
        emg_file = global_state.get_emg_file()
        data = global_state.get_effective_scaled_data()
        if data is None or emg_file is None:
            QMessageBox.warning(self.parent, "No Data", "Please load a file first.")
            return

        if self.apply_to_all_grids:
            grids_to_process = [(g.grid_key, g.emg_indices) for g in emg_file.grids]
        else:
            handler = self.parent.grid_setup_handler
            grids_to_process = [(
                handler.get_selected_grid(),
                handler.get_current_grid_indices(),
            )]

        channel_status = global_state.get_channel_status()
        total_flagged = 0
        summary_lines = []

        for grid_key, emg_indices in grids_to_process:
            flagged = self._detect_for_grid(
                data, emg_indices,
                self.use_rest_spike,
                self.spike_threshold,
                emg_file.sampling_frequency,
            )
            for idx in flagged:
                if idx is not None and idx < len(channel_status):
                    channel_status[idx] = False
                    labels = global_state.get_channel_labels(idx).copy()
                    artifact_label = BaseChannelLabel.ARTIFACT.value
                    if artifact_label not in labels:
                        labels.append(artifact_label)
                        global_state.update_channel_labels(idx, labels)
            total_flagged += len(flagged)
            n_valid = len([i for i in emg_indices if i is not None])
            summary_lines.append(f"{grid_key}: {len(flagged)} of {n_valid} flagged")

        global_state.set_channel_status(channel_status)
        self.parent.display_page()

        detail = "\n".join(summary_lines)
        QMessageBox.information(
            self.parent,
            "Spike Detection Complete",
            f"{detail}\n\nTotal: {total_flagged} channel(s) flagged as Artifact.",
        )
