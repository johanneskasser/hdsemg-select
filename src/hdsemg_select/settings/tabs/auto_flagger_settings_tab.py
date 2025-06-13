from PyQt5.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget, QCheckBox
from hdsemg_select.config.config_enums import Settings

def validate_auto_flagger_settings(settings: dict) -> None:
    """
    Raise ValueError when a required key is missing *or* its value is None.
    """
    required = [
        Settings.AUTO_FLAGGER_NOISE_FREQ_THRESHOLD.name,
        Settings.AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD.name,
        Settings.AUTO_FLAGGER_CHECK_50HZ.name,
        Settings.AUTO_FLAGGER_CHECK_60HZ.name,
        Settings.AUTO_FLAGGER_NOISE_FREQ_BAND_HZ.name,
    ]

    missing_or_none = [
        k for k in required
        if k not in settings or settings[k] is None
    ]

    if missing_or_none:
        raise ValueError(
            f"missing/None: {', '.join(missing_or_none)}"
        )

class AutoFlaggerSettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self) -> None:
        """Creates and returns the widget for the Auto-Flagger settings tab."""
        layout = QVBoxLayout(self) # Use 'self' as the parent for the layout

        info_label = QLabel("Configure settings for the automatic artifact flagging.")
        layout.addWidget(info_label)

        # Group box for thresholds
        thresholds_group = QGroupBox("Thresholds")
        thresholds_layout = QFormLayout(thresholds_group)

        self.noise_freq_threshold_spinbox = QDoubleSpinBox()
        self.noise_freq_threshold_spinbox.setRange(0.1, 100.0)
        self.noise_freq_threshold_spinbox.setSingleStep(0.1)
        self.noise_freq_threshold_spinbox.setToolTip("Ratio of peak power at target frequency to average power.")
        thresholds_layout.addRow("Noise Frequency Threshold:", self.noise_freq_threshold_spinbox)

        self.artifact_variance_threshold_spinbox = QDoubleSpinBox()
        self.artifact_variance_threshold_spinbox.setRange(0.0, 1e-6)
        self.artifact_variance_threshold_spinbox.setSingleStep(1e-10)
        self.artifact_variance_threshold_spinbox.setDecimals(12)
        self.artifact_variance_threshold_spinbox.setToolTip("Variance threshold for general artifacts.")
        thresholds_layout.addRow("Artifact Variance Threshold:", self.artifact_variance_threshold_spinbox)

        self.noise_freq_band_spinbox = QDoubleSpinBox()
        self.noise_freq_band_spinbox.setRange(0.1, 10.0)
        self.noise_freq_band_spinbox.setSingleStep(0.1)
        self.noise_freq_band_spinbox.setToolTip("Frequency band (+/- Hz) around target frequency for peak detection.")
        thresholds_layout.addRow("Noise Frequency Band (Hz):", self.noise_freq_band_spinbox)

        layout.addWidget(thresholds_group)

        # Group box for frequency checks
        freq_check_group = QGroupBox("Frequency Checks")
        freq_check_layout = QVBoxLayout(freq_check_group)

        self.check_50hz_checkbox = QCheckBox("Check for 50 Hz Noise")
        freq_check_layout.addWidget(self.check_50hz_checkbox)

        self.check_60hz_checkbox = QCheckBox("Check for 60 Hz Noise")
        freq_check_layout.addWidget(self.check_60hz_checkbox)

        layout.addWidget(freq_check_group)

        layout.addStretch(1)


    def loadSettings(self, config_manager) -> None:
        """Loads settings from ConfigManager and updates UI elements."""
        # Define default values if they don't exist in the config
        default_noise_freq_threshold = 2.0
        default_artifact_variance_threshold = 1e-9
        default_noise_freq_band_hz = 1.0
        default_check_50hz = True
        default_check_60hz = True

        self.noise_freq_threshold_spinbox.setValue(
            config_manager.get(Settings.AUTO_FLAGGER_NOISE_FREQ_THRESHOLD, default_noise_freq_threshold)
        )
        self.artifact_variance_threshold_spinbox.setValue(
            config_manager.get(Settings.AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD, default_artifact_variance_threshold)
        )
        self.noise_freq_band_spinbox.setValue(
            config_manager.get(Settings.AUTO_FLAGGER_NOISE_FREQ_BAND_HZ, default_noise_freq_band_hz)
        )
        self.check_50hz_checkbox.setChecked(
            config_manager.get(Settings.AUTO_FLAGGER_CHECK_50HZ, default_check_50hz)
        )
        self.check_60hz_checkbox.setChecked(
            config_manager.get(Settings.AUTO_FLAGGER_CHECK_60HZ, default_check_60hz)
        )


    def saveSettings(self, config_manager) -> None:
        """Saves settings from UI elements to ConfigManager."""
        config_manager.set(Settings.AUTO_FLAGGER_NOISE_FREQ_THRESHOLD, self.noise_freq_threshold_spinbox.value())
        config_manager.set(Settings.AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD, self.artifact_variance_threshold_spinbox.value())
        config_manager.set(Settings.AUTO_FLAGGER_NOISE_FREQ_BAND_HZ, self.noise_freq_band_spinbox.value())
        config_manager.set(Settings.AUTO_FLAGGER_CHECK_50HZ, self.check_50hz_checkbox.isChecked())
        config_manager.set(Settings.AUTO_FLAGGER_CHECK_60HZ, self.check_60hz_checkbox.isChecked())