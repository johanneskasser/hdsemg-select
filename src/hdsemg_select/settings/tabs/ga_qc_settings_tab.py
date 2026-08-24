"""Settings tab for the Global Amplitude QC step.

Two halves, and the split is the point: the **definition** decides how the
global amplitude is computed, the **thresholds** decide where a measured
number becomes a verdict. Both are stored per file in the selection JSON,
so a result can always be re-derived from the numbers that produced it.
"""

from dataclasses import replace

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHeaderView, QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from hdsemg_select.select_logic import ga_qc_config
from hdsemg_select.select_logic.ga_qc_config import QCSettings
from hdsemg_select.select_logic.global_amplitude_qc import (
    CHECK_LABELS, CHECKS, QCThresholds,
)
from hdsemg_select.ui.theme import Colors, Spacing, Styles

_BOUND_KEYS = {
    "activation_ratio": ("activation_pass", "activation_fail"),
    "amplitude_z": ("amplitude_z_pass", "amplitude_z_fail"),
    "spectrum_z": ("spectrum_z_pass", "spectrum_z_fail"),
    "line_noise": ("line_noise_pass", "line_noise_fail"),
    "clipping": ("clipping_pass", "clipping_fail"),
    "neighbor_correlation": ("neighbor_pass", "neighbor_fail"),
}

#: Decimals each bound is edited with, so a clipping fraction stays usable.
_DECIMALS = {"clipping": 4}


class GaQcSettingsTab(QWidget):
    """Defaults for the QC dialog: the definition, the windows, the thresholds."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def initUI(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        header = QLabel("Global Amplitude Quality Control")
        header.setStyleSheet(Styles.label_heading(size="lg"))
        layout.addWidget(header)

        intro = QLabel(
            "Defaults for the QC dialog. The definition below decides how the global "
            "amplitude is computed; the thresholds decide where a measured number "
            "becomes a verdict. Both are stored per file in the selection JSON, so a "
            "result can always be re-derived from the numbers that produced it."
        )
        intro.setStyleSheet(Styles.label_secondary())
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._definition_group())
        layout.addWidget(self._windowing_group())
        layout.addWidget(self._verdict_group())
        layout.addWidget(self._channel_group())

        restore = QPushButton("Restore defaults")
        restore.setStyleSheet(Styles.button_secondary())
        restore.clicked.connect(self._restore_defaults)
        layout.addWidget(restore)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _definition_group(self) -> QGroupBox:
        group, form = self._group("Global amplitude definition")

        self.derivation_combo = self._combo(["MP", "SD", "DD"])
        form.addRow("Derivation:", self.derivation_combo)
        self._help(form, "MP monopolar, SD single differential, DD double differential. "
                         "Differencing runs on the raw signal, before filtering.")

        self.method_combo = self._combo(["RMS", "ARV"])
        form.addRow("Method:", self.method_combo)
        self._help(form, "RMS squares each channel, ARV rectifies it. The root is taken "
                         "last, across the grid - never per channel.")

        self.axis_combo = self._combo(["columns", "rows"])
        form.addRow("Difference along:", self.axis_combo)
        self._help(form, "Point this along the muscle fibres. Fiber Trajectory Analysis "
                         "measures which way they actually run.")

        self.bpf_low_spin = self._spin(1.0, 400.0, 1.0, 1)
        self.bpf_high_spin = self._spin(50.0, 2000.0, 10.0, 1)
        form.addRow("Band-pass low [Hz]:", self.bpf_low_spin)
        form.addRow("Band-pass high [Hz]:", self.bpf_high_spin)
        self._help(form, "Second-order zero-lag Butterworth with exact corners. "
                         "30 – 450 Hz reproduces the MATLAB original.")

        self.smooth_spin = self._spin(1.0, 100.0, 1.0, 1)
        form.addRow("Smoothing [Hz]:", self.smooth_spin)
        self._help(form, "Zero-phase boxcar equivalent, applied per channel before the "
                         "reduction across the grid.")

        self.line_freq_spin = self._spin(40.0, 70.0, 10.0, 0)
        form.addRow("Mains frequency [Hz]:", self.line_freq_spin)
        self._help(form, "50 Hz in Europe, 60 Hz in North America. The first two "
                         "harmonics are tested alongside it.")
        return group

    def _windowing_group(self) -> QGroupBox:
        group, form = self._group("Windowing")

        self.rest_below_spin = self._spin(0.1, 50.0, 0.5, 1)
        form.addRow("Rest below [% of peak force]:", self.rest_below_spin)
        self._help(form, "Performed path under this share of the trial's own force span "
                         "counts as rest - a fraction of the trial's peak, not of an MVC, "
                         "so it needs no calibration file.")

        self.min_rest_spin = self._spin(0.1, 30.0, 0.5, 1)
        form.addRow("Minimum rest [s]:", self.min_rest_spin)
        self._help(form, "Shorter rest stretches are ignored, so a brief dip inside a "
                         "contraction cannot become the noise floor.")

        self.peak_window_spin = self._spin(20.0, 5000.0, 50.0, 0)
        form.addRow("Peak window [ms]:", self.peak_window_spin)
        self._help(form, "Width of the window placed at the highest global amplitude "
                         "inside the contraction.")

        self.fallback_spin = self._spin(0.5, 30.0, 0.5, 1)
        form.addRow("Fallback rest [s]:", self.fallback_spin)
        self._help(form, "Used at both ends of the trial when the grid has no reference "
                         "signal. The JSON records that the windows came from here.")
        return group

    def _verdict_group(self) -> QGroupBox:
        group, form = self._group("Grid verdict")

        self.grid_pass_spin = self._spin(1.0, 20.0, 0.1, 2)
        form.addRow("Activation ratio pass:", self.grid_pass_spin)
        self._help(form, "Peak-window mean over the resting floor. Below this the grid is "
                         "reported as failing the activation check.")

        self.grid_borderline_spin = self._spin(1.0, 20.0, 0.1, 2)
        form.addRow("Borderline from:", self.grid_borderline_spin)
        self._help(form, "Between the two the grid is reported as borderline rather than "
                         "failing outright.")

        self.min_fraction_spin = self._spin(0.0, 100.0, 5.0, 0)
        form.addRow("Minimum channels [%]:", self.min_fraction_spin)
        self._help(form, "A verdict on a grid whose channels have mostly been deselected "
                         "is not a verdict on the grid.")
        return group

    def _channel_group(self) -> QGroupBox:
        group = QGroupBox("Channel thresholds and weights")
        group.setStyleSheet(Styles.groupbox())
        layout = QVBoxLayout(group)
        layout.setSpacing(Spacing.SM)

        self.channel_table = QTableWidget(len(CHECKS), 5)
        self.channel_table.setHorizontalHeaderLabels(
            ["On", "Metric", "Pass at", "Fail at", "Weight"])
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.channel_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.channel_table.setMinimumHeight(30 + 30 * len(CHECKS))

        self._check_boxes, self._bound_spins, self._weight_spins = {}, {}, {}
        for row, check in enumerate(CHECKS):
            box = QCheckBox()
            box.setChecked(True)
            holder = QWidget()
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignCenter)
            holder_layout.addWidget(box)
            self._check_boxes[check] = box
            self.channel_table.setCellWidget(row, 0, holder)

            name = QTableWidgetItem(CHECK_LABELS[check])
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            self.channel_table.setItem(row, 1, name)

            if check == "flat":
                for column, text in ((2, "no"), (3, "yes"), (4, "fatal")):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.channel_table.setItem(row, column, item)
                continue

            decimals = _DECIMALS.get(check, 2)
            step = 10 ** -decimals * 10
            pass_spin = self._spin(0.0, 1000.0, step, decimals)
            fail_spin = self._spin(0.0, 1000.0, step, decimals)
            weight_spin = self._spin(0.0, 1.0, 0.05, 2)
            self._bound_spins[check] = (pass_spin, fail_spin)
            self._weight_spins[check] = weight_spin
            self.channel_table.setCellWidget(row, 2, pass_spin)
            self.channel_table.setCellWidget(row, 3, fail_spin)
            self.channel_table.setCellWidget(row, 4, weight_spin)

        self.channel_table.resizeColumnsToContents()
        self.channel_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.channel_table)

        note = QLabel(
            "A channel's grade is the worst state among the enabled checks. Weights only "
            "rank the list; they never change a grade. Neighbour correlation is measured "
            "inside the peak window - over a whole trial it collapses toward zero for "
            "good channels too."
        )
        note.setWordWrap(True)
        note.setStyleSheet(Styles.label_secondary())
        layout.addWidget(note)
        return group

    # ------------------------------------------------------------------
    # Small builders
    # ------------------------------------------------------------------

    @staticmethod
    def _group(title: str):
        group = QGroupBox(title)
        group.setStyleSheet(Styles.groupbox())
        form = QFormLayout(group)
        form.setSpacing(Spacing.MD)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        return group, form

    @staticmethod
    def _combo(items) -> QComboBox:
        combo = QComboBox()
        combo.setStyleSheet(Styles.combobox())
        combo.addItems(items)
        return combo

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setStyleSheet(Styles.input_field())
        spin.setDecimals(decimals)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        return spin

    @staticmethod
    def _help(form: QFormLayout, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet(Styles.label_secondary())
        label.setWordWrap(True)
        form.addRow("", label)

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def loadSettings(self, _config=None) -> None:
        """Fill the widgets from the stored settings.

        The signature takes the config manager for symmetry with the other
        settings tabs; the values themselves come through ga_qc_config, which
        owns the mapping and the defaults.
        """
        self._apply(ga_qc_config.load())

    def _apply(self, settings: QCSettings) -> None:
        thresholds = settings.thresholds or QCThresholds()

        self.derivation_combo.setCurrentText(settings.derivation)
        self.method_combo.setCurrentText(settings.method)
        self.axis_combo.setCurrentText(
            "columns" if settings.diff_direction == "cols" else "rows")
        self.bpf_low_spin.setValue(settings.bpf_low_hz)
        self.bpf_high_spin.setValue(settings.bpf_high_hz)
        self.smooth_spin.setValue(settings.smooth_hz)
        self.line_freq_spin.setValue(settings.line_freq_hz)

        self.rest_below_spin.setValue(settings.rest_below_pct)
        self.min_rest_spin.setValue(settings.min_rest_s)
        self.peak_window_spin.setValue(settings.peak_window_ms)
        self.fallback_spin.setValue(settings.fallback_s)

        self.grid_pass_spin.setValue(thresholds.grid_pass)
        self.grid_borderline_spin.setValue(thresholds.grid_borderline)
        self.min_fraction_spin.setValue(thresholds.min_channel_fraction * 100.0)

        for check, box in self._check_boxes.items():
            box.setChecked(bool(thresholds.enabled.get(check, True)))
        for check, (pass_spin, fail_spin) in self._bound_spins.items():
            pass_key, fail_key = _BOUND_KEYS[check]
            pass_spin.setValue(getattr(thresholds, pass_key))
            fail_spin.setValue(getattr(thresholds, fail_key))
        for check, spin in self._weight_spins.items():
            spin.setValue(float(thresholds.weights.get(check, 0.0)))

    def saveSettings(self, _config=None) -> None:
        """Write the widgets back through ga_qc_config."""
        ga_qc_config.save(self._collect())

    def _collect(self) -> QCSettings:
        bounds = {}
        for check, (pass_spin, fail_spin) in self._bound_spins.items():
            pass_key, fail_key = _BOUND_KEYS[check]
            bounds[pass_key] = pass_spin.value()
            bounds[fail_key] = fail_spin.value()

        thresholds = replace(
            QCThresholds(),
            grid_pass=self.grid_pass_spin.value(),
            grid_borderline=self.grid_borderline_spin.value(),
            min_channel_fraction=self.min_fraction_spin.value() / 100.0,
            weights={check: spin.value() for check, spin in self._weight_spins.items()},
            enabled={check: box.isChecked() for check, box in self._check_boxes.items()},
            **bounds,
        )
        return QCSettings(
            derivation=self.derivation_combo.currentText(),
            method=self.method_combo.currentText(),
            diff_direction="cols" if self.axis_combo.currentText() == "columns" else "rows",
            bpf_low_hz=self.bpf_low_spin.value(),
            bpf_high_hz=self.bpf_high_spin.value(),
            smooth_hz=self.smooth_spin.value(),
            line_freq_hz=self.line_freq_spin.value(),
            rest_below_pct=self.rest_below_spin.value(),
            min_rest_s=self.min_rest_spin.value(),
            peak_window_ms=self.peak_window_spin.value(),
            fallback_s=self.fallback_spin.value(),
            thresholds=thresholds,
        )

    def _restore_defaults(self) -> None:
        self._apply(QCSettings(thresholds=QCThresholds()))
