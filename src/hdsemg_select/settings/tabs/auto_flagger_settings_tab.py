from PyQt5.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget, QCheckBox
from PyQt5.QtCore import Qt
from hdsemg_select.config.config_enums import Settings
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles

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
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        # Header
        header_label = QLabel("Automatic Channel Flagging")
        header_label.setStyleSheet(Styles.label_heading(size="lg"))
        layout.addWidget(header_label)

        info_label = QLabel("Configure thresholds for automatic detection of noise and artifacts in channel data. "
                           "Channels exceeding these thresholds will be automatically flagged during analysis.")
        info_label.setStyleSheet(Styles.label_secondary())
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Group box for thresholds
        thresholds_group = QGroupBox("Detection Thresholds")
        thresholds_group.setStyleSheet(Styles.groupbox())
        thresholds_layout = QFormLayout(thresholds_group)
        thresholds_layout.setSpacing(Spacing.MD)
        thresholds_layout.setLabelAlignment(Qt.AlignRight)
        thresholds_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.noise_freq_threshold_spinbox = QDoubleSpinBox()
        self.noise_freq_threshold_spinbox.setStyleSheet(Styles.input_field())
        self.noise_freq_threshold_spinbox.setRange(0.1, 100.0)
        self.noise_freq_threshold_spinbox.setSingleStep(0.1)
        self.noise_freq_threshold_spinbox.setToolTip("Ratio of peak power at target frequency to average power.\nHigher values = stricter detection.")
        thresholds_layout.addRow("Noise Frequency Ratio:", self.noise_freq_threshold_spinbox)

        # Add help text
        noise_help = QLabel("Peak power ratio compared to average power (e.g., 2.0 = peak is 2x average)")
        noise_help.setStyleSheet(Styles.label_secondary())
        noise_help.setWordWrap(True)
        thresholds_layout.addRow("", noise_help)

        self.artifact_variance_threshold_spinbox = QDoubleSpinBox()
        self.artifact_variance_threshold_spinbox.setStyleSheet(Styles.input_field())
        self.artifact_variance_threshold_spinbox.setRange(0.0, 1e-6)
        self.artifact_variance_threshold_spinbox.setSingleStep(1e-10)
        self.artifact_variance_threshold_spinbox.setDecimals(12)
        self.artifact_variance_threshold_spinbox.setToolTip("Maximum acceptable variance for channel signals.\nLower values = stricter artifact detection.")
        thresholds_layout.addRow("Artifact Variance Limit:", self.artifact_variance_threshold_spinbox)

        variance_help = QLabel("Maximum signal variance before flagging as artifact (scientific notation)")
        variance_help.setStyleSheet(Styles.label_secondary())
        variance_help.setWordWrap(True)
        thresholds_layout.addRow("", variance_help)

        self.noise_freq_band_spinbox = QDoubleSpinBox()
        self.noise_freq_band_spinbox.setStyleSheet(Styles.input_field())
        self.noise_freq_band_spinbox.setRange(0.1, 10.0)
        self.noise_freq_band_spinbox.setSingleStep(0.1)
        self.noise_freq_band_spinbox.setSuffix(" Hz")
        self.noise_freq_band_spinbox.setToolTip("Frequency band (±Hz) around target frequency for peak detection.\nWider band = more tolerant detection.")
        thresholds_layout.addRow("Frequency Band Width:", self.noise_freq_band_spinbox)

        band_help = QLabel("Width of frequency window for noise detection (e.g., ±1.0 Hz)")
        band_help.setStyleSheet(Styles.label_secondary())
        band_help.setWordWrap(True)
        thresholds_layout.addRow("", band_help)

        layout.addWidget(thresholds_group)

        # Group box for frequency checks
        freq_check_group = QGroupBox("Power Line Noise Detection")
        freq_check_group.setStyleSheet(Styles.groupbox())
        freq_check_layout = QVBoxLayout(freq_check_group)
        freq_check_layout.setSpacing(Spacing.SM)

        freq_info = QLabel("Enable detection of common power line interference frequencies:")
        freq_info.setStyleSheet(Styles.label_secondary())
        freq_info.setWordWrap(True)
        freq_check_layout.addWidget(freq_info)

        self.check_50hz_checkbox = QCheckBox("Check for 50 Hz Noise (Europe, Asia, Africa, Australia)")
        self.check_50hz_checkbox.setToolTip("Detect power line interference at 50 Hz and harmonics")
        freq_check_layout.addWidget(self.check_50hz_checkbox)

        self.check_60hz_checkbox = QCheckBox("Check for 60 Hz Noise (North America, parts of Asia)")
        self.check_60hz_checkbox.setToolTip("Detect power line interference at 60 Hz and harmonics")
        freq_check_layout.addWidget(self.check_60hz_checkbox)

        layout.addWidget(freq_check_group)

        # Info box
        info_box = QLabel("💡 Tip: Start with default values and adjust based on your specific signal characteristics and noise levels.")
        info_box.setStyleSheet(Styles.info_box(type="info"))
        info_box.setWordWrap(True)
        layout.addWidget(info_box)

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