from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout,
    QDialogButtonBox, QWidget
)
from .tabs.log_setting import init as init_logging_widget


class SettingsDialog(QDialog):
    settingsAccepted = pyqtSignal()

    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 300)
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.logging_tab = QWidget()

        self.tab_widget.addTab(self.logging_tab, "Logging")

        self.initLoggingTab()

        # Add standard dialog buttons (OK and Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)


    def initLoggingTab(self):
        """Initialize the 'Logging' settings tab."""
        log_tab = init_logging_widget(self)
        self.logging_tab.setLayout(log_tab)
