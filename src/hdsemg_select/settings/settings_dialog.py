from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout,
    QDialogButtonBox, QLabel
)

from .tabs.custom_flagger_settings_tab import CustomFlaggerSettingsTab
# Import the new tab classes
from .tabs.log_setting import LoggingSettingsTab
from .tabs.auto_flagger_settings_tab import AutoFlaggerSettingsTab

from hdsemg_select.config.config_manager import config
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles, Fonts

class SettingsDialog(QDialog):
    settingsAccepted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent) # Use super() for modern Python
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.initUI()
        # Load settings *after* UI is initialized
        self.loadSettings()


    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Spacing.LG)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # Header
        header_label = QLabel("Application Settings")
        header_label.setStyleSheet(Styles.label_heading(size="xl"))
        main_layout.addWidget(header_label)

        description_label = QLabel("Configure application behavior, logging, and channel flagging preferences.")
        description_label.setStyleSheet(Styles.label_secondary())
        description_label.setWordWrap(True)
        main_layout.addWidget(description_label)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD};
                background-color: {Colors.BG_PRIMARY};
                padding: {Spacing.MD}px;
            }}
            QTabBar::tab {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-bottom: none;
                border-top-left-radius: {BorderRadius.MD};
                border-top-right-radius: {BorderRadius.MD};
                padding: {Spacing.SM}px {Spacing.LG}px;
                margin-right: {Spacing.XS // 2}px;
                color: {Colors.TEXT_SECONDARY};
            }}
            QTabBar::tab:selected {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
            }}
            QTabBar::tab:hover {{
                background-color: {Colors.GRAY_100};
            }}
        """)
        main_layout.addWidget(self.tab_widget)

        # Create instances of the tab widgets
        self.logging_tab_widget = LoggingSettingsTab(self.tab_widget) # Parent is tab_widget
        self.auto_flag_tab_widget = AutoFlaggerSettingsTab(self.tab_widget) # Parent is tab_widget
        self.custom_flag_tab_widget = CustomFlaggerSettingsTab(self.tab_widget)

        # Add tab widgets to the tab widget with shorter names
        self.tab_widget.addTab(self.logging_tab_widget, "Logging")
        self.tab_widget.addTab(self.auto_flag_tab_widget, "Auto-Flagging")
        self.tab_widget.addTab(self.custom_flag_tab_widget, "Custom Labels")

        # Add standard dialog buttons (OK and Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        # Style the buttons
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        ok_button.setStyleSheet(Styles.button_primary())
        cancel_button = self.button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setStyleSheet(Styles.button_secondary())

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