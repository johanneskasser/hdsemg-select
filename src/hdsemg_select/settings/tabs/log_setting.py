# settings/tabs/log_setting.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QComboBox
)
from hdsemg_select._log.log_config import logger
import logging

from hdsemg_select.config.config_enums import Settings

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

        info_label = QLabel("Set the logging level of the application.")
        layout.addWidget(info_label)

        # Horizontal layout row for the log level selection
        h_layout = QHBoxLayout()
        label = QLabel("Log Level:")
        h_layout.addWidget(label)

        # Dropdown for selecting the log level
        self.log_level_dropdown = QComboBox()
        # Ensure the items match logging levels
        self.log_level_dropdown.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        h_layout.addWidget(self.log_level_dropdown)

        # Button to confirm the new log level
        self.set_level_button = QPushButton("Apply")
        h_layout.addWidget(self.set_level_button)

        # Label to display the current log level
        self.current_log_level_label = QLabel()
        # Initial text will be set by loadSettings
        # self.current_log_level_label.setText(f"Current: <b>{logging.getLevelName(logger.getEffectiveLevel())}</b>") # Removed, loadSettings will handle
        layout.addLayout(h_layout)

        layout.addWidget(self.current_log_level_label) # Add label below the HBox

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
            self.current_log_level_label.setText(f"Current: <b>{effective_level_name}</b>")
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