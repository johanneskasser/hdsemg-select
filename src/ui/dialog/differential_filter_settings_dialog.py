from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QDialogButtonBox, QSpacerItem, QSizePolicy
)


class DifferentialFilterSettingsDialog(QDialog):
    """
    Settings dialog for single-differential EMG band-pass filtering.
    Ensures the parameters comply with the MATLAB-identical Python backend:
        • order (n)  even ≥ 2
        • low  <  up
    """

    def __init__(self, current_params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Differential Filter Settings")
        self.setMinimumWidth(450)
        self.setModal(True)

        self.params = current_params.copy()  # work on a copy

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.order_spinbox = QSpinBox()
        self.order_spinbox.setRange(2, 20)  # reasonable upper bound
        self.order_spinbox.setSingleStep(2)  # even numbers only
        default_n = int(self.params.get("n", 4))
        # snap to nearest even number just in case
        self.order_spinbox.setValue(default_n if default_n % 2 == 0 else default_n + 1)
        self.order_spinbox.setToolTip("Must be an even integer (2, 4, 6 …).")
        form_layout.addRow(QLabel("<b>Filter Order (n):</b>"), self.order_spinbox)

        order_help = QLabel(
            "Even order is required because the filter is applied forward & backward "
            "(zero-phase).  The effective order is doubled by this operation."
        )
        order_help.setWordWrap(True)
        form_layout.addRow(order_help)
        form_layout.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # ----------------------------- Lower cut-off
        self.low_freq_spinbox = QDoubleSpinBox()
        self.low_freq_spinbox.setRange(0.1, 5000.0)
        self.low_freq_spinbox.setDecimals(1)
        self.low_freq_spinbox.setSuffix(" Hz")
        self.low_freq_spinbox.setValue(self.params.get("low", 20.0))
        form_layout.addRow(QLabel("<b>Lower Cutoff Frequency:</b>"), self.low_freq_spinbox)

        low_freq_help = QLabel(
            "Frequencies below this value are attenuated (movement artefacts, DC drift). "
            "Typical surface EMG values lie between 10 Hz and 30 Hz."
        )
        low_freq_help.setWordWrap(True)
        form_layout.addRow(low_freq_help)
        form_layout.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.up_freq_spinbox = QDoubleSpinBox()
        self.up_freq_spinbox.setRange(1.0, 5000.0)
        self.up_freq_spinbox.setDecimals(1)
        self.up_freq_spinbox.setSuffix(" Hz")
        self.up_freq_spinbox.setValue(self.params.get("up", 450.0))
        form_layout.addRow(QLabel("<b>Upper Cutoff Frequency:</b>"), self.up_freq_spinbox)

        up_freq_help = QLabel(
            "Frequencies above this value are attenuated (high-frequency noise). "
            "For surface EMG, most energy is below 400–500 Hz."
        )
        up_freq_help.setWordWrap(True)
        form_layout.addRow(up_freq_help)

        layout.addLayout(form_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept_values)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # live validators
        self.low_freq_spinbox.valueChanged.connect(self._validate_inputs)
        self.up_freq_spinbox.valueChanged.connect(self._validate_inputs)
        self.order_spinbox.valueChanged.connect(self._validate_inputs)
        self._validate_inputs()  # initial state

    def _validate_inputs(self):
        """Enable / disable <OK> and colour errors inline."""
        low = self.low_freq_spinbox.value()
        up = self.up_freq_spinbox.value()
        n = self.order_spinbox.value()
        ok_b = self.button_box.button(QDialogButtonBox.Ok)

        freq_valid = up > low
        order_valid = (n % 2 == 0) and n >= 2

        # style feedback
        self.up_freq_spinbox.setStyleSheet("" if freq_valid else "background:#FFCCCC;")
        self.order_spinbox.setStyleSheet("" if order_valid else "background:#FFCCCC;")

        # tooltip feedback
        self.up_freq_spinbox.setToolTip("" if freq_valid
                                        else "Upper cutoff must be greater than lower cutoff.")
        self.order_spinbox.setToolTip("" if order_valid
                                      else "Filter order must be an even integer ≥ 2.")

        ok_b.setEnabled(freq_valid and order_valid)

    def accept_values(self):
        """Store values and close the dialog."""
        self.params["n"] = self.order_spinbox.value()
        self.params["low"] = self.low_freq_spinbox.value()
        self.params["up"] = self.up_freq_spinbox.value()
        super().accept()

    def get_parameters(self) -> dict | None:
        """Return parameters if the user pressed OK, else None."""
        return self.params if self.result() == QDialog.Accepted else None
