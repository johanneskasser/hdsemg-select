# settings/tabs/log_setting.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QComboBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt
from hdsemg_select._log.log_config import logger
import logging

from hdsemg_select.config.config_enums import Settings
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles

class LoggingSettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self._connect_signals() # Connect signals after UI is built


    def initUI(self):
        """
        Initializes the UI elements for the logging settings tab.
        """
        layout = QVBoxLayout(self) # Use 'self' as the parent for the layout
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        # Header
        header_label = QLabel("Logging Configuration")
        header_label.setStyleSheet(Styles.label_heading(size="lg"))
        layout.addWidget(header_label)

        info_label = QLabel(
            "Control the verbosity of application logging. "
            "Higher levels show fewer messages. Use DEBUG for troubleshooting and ERROR for production."
        )
        info_label.setStyleSheet(Styles.label_secondary())
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Log level selection group
        log_group = QGroupBox("Log Level")
        log_group.setStyleSheet(Styles.groupbox())
        log_layout = QFormLayout(log_group)
        log_layout.setSpacing(Spacing.MD)
        log_layout.setLabelAlignment(Qt.AlignRight)
        log_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Dropdown for selecting the log level
        level_container = QHBoxLayout()
        level_container.setSpacing(Spacing.SM)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.setStyleSheet(Styles.combobox())
        # Ensure the items match logging levels
        self.log_level_dropdown.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        level_container.addWidget(self.log_level_dropdown, 1)

        # Button to confirm the new log level
        self.set_level_button = QPushButton("Apply")
        self.set_level_button.setStyleSheet(Styles.button_primary())
        self.set_level_button.setToolTip("Apply the selected log level immediately")
        level_container.addWidget(self.set_level_button)

        log_layout.addRow("Logging Level:", level_container)

        # Label to display the current log level
        self.current_log_level_label = QLabel()
        self.current_log_level_label.setStyleSheet(Styles.label_secondary())
        log_layout.addRow("Current Level:", self.current_log_level_label)

        layout.addWidget(log_group)

        # Info about log levels
        level_info_box = QLabel(
            "<b>Log Levels:</b><br>"
            "• <b>DEBUG</b>: Detailed diagnostic information<br>"
            "• <b>INFO</b>: General informational messages<br>"
            "• <b>WARNING</b>: Warning messages for potential issues<br>"
            "• <b>ERROR</b>: Error messages for failures<br>"
            "• <b>CRITICAL</b>: Critical errors only"
        )
        level_info_box.setStyleSheet(Styles.info_box(type="info"))
        level_info_box.setWordWrap(True)
        layout.addWidget(level_info_box)

        layout.addStretch(1) # Push content to top


    def _connect_signals(self):
        """Connects signals to slots."""
        # Connect button click to the apply method
        self.set_level_button.clicked.connect(self._apply_log_level)


    def _apply_log_level(self):
        """Applies the selected log level to the logger and updates the label."""
        selected_text = self.log_level_dropdown.currentText()
        self._set_logger_level(selected_text)


    def _set_logger_level(self, level_text: str):
        """Sets the logger and handler levels."""
        try:
            new_level = getattr(logging, level_text.upper()) # Get level from string
            logger.setLevel(new_level)
            # Optionally update handlers - depends on your logging setup
            for handler in logger.handlers:
                 handler.setLevel(new_level)

            effective_level_name = logging.getLevelName(logger.getEffectiveLevel())
            self.current_log_level_label.setText(f"<b>{effective_level_name}</b>")
            # Ensure dropdown reflects the level that was just set (useful if loading sets it)
            index = self.log_level_dropdown.findText(level_text.upper())
            if index != -1:
                self.log_level_dropdown.setCurrentIndex(index)

        except AttributeError:
            # Handle cases where selected_text is not a valid level name
            print(f"Warning: Invalid log level selected: {level_text}")
            pass # Or log an error


    def loadSettings(self, config_manager) -> None:
        """Loads logging settings from ConfigManager and updates UI/logger."""
        # Get the default level from the *current* logger setup if not in config
        default_level_name = logging.getLevelName(logger.getEffectiveLevel())
        saved_level_text = config_manager.get(Settings.LOG_LEVEL, default_level_name)

        # Set the dropdown to the saved level
        index = self.log_level_dropdown.findText(saved_level_text.upper())
        if index != -1:
            self.log_level_dropdown.setCurrentIndex(index)
        else:
             # If saved level is invalid, fall back to default and set dropdown
             self.log_level_dropdown.setCurrentText(default_level_name.upper())
             saved_level_text = default_level_name # Use default for setting logger

        # Apply the loaded/default level to the actual logger
        self._set_logger_level(saved_level_text)


    def saveSettings(self, config_manager) -> None:
        """Saves logging settings from UI elements to ConfigManager."""
        # Save the current selection in the dropdown
        selected_level_text = self.log_level_dropdown.currentText()
        config_manager.set(Settings.LOG_LEVEL, selected_level_text)