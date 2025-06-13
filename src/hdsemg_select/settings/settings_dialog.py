from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout,
    QDialogButtonBox
)

from .tabs.custom_flagger_settings_tab import CustomFlaggerSettingsTab
# Import the new tab classes
from .tabs.log_setting import LoggingSettingsTab
from .tabs.auto_flagger_settings_tab import AutoFlaggerSettingsTab

from hdsemg_select.config.config_manager import config

class SettingsDialog(QDialog):
    settingsAccepted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent) # Use super() for modern Python
        self.setWindowTitle("Settings")
        self.resize(400, 400) # Increased size slightly for more content
        self.initUI()
        # Load settings *after* UI is initialized
        self.loadSettings()


    def initUI(self):
        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create instances of the tab widgets
        self.logging_tab_widget = LoggingSettingsTab(self.tab_widget) # Parent is tab_widget
        self.auto_flag_tab_widget = AutoFlaggerSettingsTab(self.tab_widget) # Parent is tab_widget
        self.custom_flag_tab_widget = CustomFlaggerSettingsTab(self.tab_widget)

        # Add tab widgets to the tab widget
        self.tab_widget.addTab(self.logging_tab_widget, "Logging")
        self.tab_widget.addTab(self.auto_flag_tab_widget, "Automatic Channel Flagging Settings")
        self.tab_widget.addTab(self.custom_flag_tab_widget, "Custom Channel Flags")

        # Add standard dialog buttons (OK and Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # Connect accepted/rejected signals
        self.button_box.accepted.connect(self.accept) # This will call our overridden accept()
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def loadSettings(self) -> None:
        """Loads settings into all tab widgets."""
        # Pass the config manager instance to the tab widgets
        self.logging_tab_widget.loadSettings(config)
        self.auto_flag_tab_widget.loadSettings(config)
        self.custom_flag_tab_widget.loadSettings(config)

    def saveSettings(self) -> None:
        """Saves settings from all tab widgets."""
        # Pass the config manager instance to the tab widgets
        self.logging_tab_widget.saveSettings(config)
        self.auto_flag_tab_widget.saveSettings(config)
        self.custom_flag_tab_widget.saveSettings(config)

    def accept(self) -> None:
        """Overrides the accept method to save settings before closing."""
        self.saveSettings()
        # Emit a custom signal if needed elsewhere
        self.settingsAccepted.emit()
        # Call the base class accept method to close the dialog
        super().accept()