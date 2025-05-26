from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
                             QSpinBox, QDoubleSpinBox, QDialogButtonBox, QMessageBox, QSpacerItem,
                             QSizePolicy)  # Added QMessageBox


class DifferentialFilterSettingsDialog(QDialog):
    def __init__(self, current_params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Differential Filter Settings")
        self.setMinimumWidth(450)
        self.setModal(True)  # Make it modal

        self.params = current_params.copy()

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)

        # Filter Order (n)
        self.order_spinbox = QSpinBox()
        self.order_spinbox.setRange(1, 10)
        self.order_spinbox.setValue(int(self.params.get('n', 4)))
        form_layout.addRow(QLabel("<b>Filter Order (n):</b>"), self.order_spinbox)

        order_help = QLabel(
            "Determines the steepness of the filter's frequency cutoff. Higher orders "
            "(e.g., 4-8) provide a sharper transition but can introduce more phase "
            "distortion or ringing. A common value for Butterworth filters is 4."
        )
        order_help.setWordWrap(True)
        form_layout.addRow(order_help)
        form_layout.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))


        # Lower Cutoff Frequency (low)
        self.low_freq_spinbox = QDoubleSpinBox()
        self.low_freq_spinbox.setRange(0.1, 2000.0)  # Adjusted max based on typical EMG Nyquist
        self.low_freq_spinbox.setDecimals(1)
        self.low_freq_spinbox.setSuffix(" Hz")
        self.low_freq_spinbox.setValue(self.params.get('low', 20.0))
        form_layout.addRow(QLabel("<b>Lower Cutoff Frequency:</b>"), self.low_freq_spinbox)

        low_freq_help = QLabel(
            "Signals below this frequency will be attenuated (reduced). This helps remove "
            "DC offset and very low-frequency noise like movement artifacts. "
            "Common values for sEMG are between 10 Hz and 30 Hz."
        )
        low_freq_help.setWordWrap(True)
        form_layout.addRow(low_freq_help)
        form_layout.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Upper Cutoff Frequency (up)
        self.up_freq_spinbox = QDoubleSpinBox()
        self.up_freq_spinbox.setRange(1.0, 5000.0)
        self.up_freq_spinbox.setDecimals(1)
        self.up_freq_spinbox.setSuffix(" Hz")
        self.up_freq_spinbox.setValue(self.params.get('up', 450.0))
        form_layout.addRow(QLabel("<b>Upper Cutoff Frequency:</b>"), self.up_freq_spinbox)

        up_freq_help = QLabel(
            "Signals above this frequency will be attenuated. This helps remove "
            "high-frequency noise. For sEMG, most useful signal power is below "
            "400-500 Hz. Setting this too low might remove important signal components."
        )
        up_freq_help.setWordWrap(True)
        form_layout.addRow(up_freq_help)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept_values)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.low_freq_spinbox.valueChanged.connect(self._validate_frequencies)
        self.up_freq_spinbox.valueChanged.connect(self._validate_frequencies)
        self._validate_frequencies()

    def _validate_frequencies(self):
        low = self.low_freq_spinbox.value()
        up = self.up_freq_spinbox.value()
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button:  # Ok button might not exist yet during init if called early
            if up <= low:
                self.up_freq_spinbox.setStyleSheet("background-color: #FFCCCC;")
                ok_button.setEnabled(False)
                self.up_freq_spinbox.setToolTip("Upper cutoff must be greater than lower cutoff.")
            else:
                self.up_freq_spinbox.setStyleSheet("")
                ok_button.setEnabled(True)
                self.up_freq_spinbox.setToolTip("")

    def accept_values(self):
        low = self.low_freq_spinbox.value()
        up = self.up_freq_spinbox.value()
        if up <= low:  # This should be prevented by _validate_frequencies disabling OK
            QMessageBox.warning(self, "Invalid Frequencies",
                                "Upper cutoff frequency must be greater than the lower cutoff frequency.")
            return

        self.params['n'] = self.order_spinbox.value()  # n is int for butter order
        self.params['low'] = low
        self.params['up'] = up
        super().accept()

    def get_parameters(self) -> dict | None:
        if self.result() == QDialog.Accepted:
            return self.params
        return None
