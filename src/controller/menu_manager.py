# menu_manager.py
from functools import partial
from PyQt5.QtWidgets import QAction, QFileDialog, QLabel
from PyQt5.QtGui import QKeySequence
from controller.file_management import save_selection
from state.state import global_state
from version import __version__ # Assuming version is accessible here

class MenuManager:
    def __init__(self):
        self.save_action = None
        self.change_grid_action = None
        self.amplitude_menu = None # Renamed from amplidude_menu for clarity

    def create_menus(self, menubar, parent_window):
        """Creates and adds menus to the given menubar."""
        self._create_file_menu(menubar, parent_window)
        self._create_grid_menu(menubar, parent_window)
        self._create_auto_select_menu(menubar, parent_window)
        self._add_version_to_statusbar(parent_window)


    def _create_file_menu(self, menubar, parent_window):
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open...", parent_window)
        open_action.setStatusTip("Open a .mat file")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        # Connect to the parent window's method
        open_action.triggered.connect(parent_window.load_file)
        file_menu.addAction(open_action)

        self.save_action = QAction("Save Selection", parent_window)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.setStatusTip("Save current channel selection")
        # Use partial to pass current state via getters at the time of triggering
        self.save_action.triggered.connect(partial(
            save_selection,
            parent_window,  # parent
            parent_window.output_file, # Access output_file from parent window
            global_state.get_data(),
            global_state.get_time(),
            global_state.get_description(),
            global_state.get_sampling_frequency(),
            global_state.get_channel_status(),
            global_state.get_file_name(),
            global_state.get_grid_info()
        ))
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)

        app_settings_menu = QAction("Settings", parent_window)
        app_settings_menu.setStatusTip("Open application settings")
        # Connect to the parent window's method
        app_settings_menu.triggered.connect(parent_window.openAppSettings)
        file_menu.addAction(app_settings_menu)


    def _create_grid_menu(self, menubar, parent_window):
        grid_menu = menubar.addMenu("Grid")

        self.change_grid_action = QAction("Change Grid/Orientation...", parent_window)
        self.change_grid_action.setShortcut(QKeySequence("Ctrl+C"))
        self.change_grid_action.setStatusTip("Change the currently selected grid or orientation")
        # Connect to the parent window's method
        self.change_grid_action.triggered.connect(parent_window.select_grid_and_orientation)
        self.change_grid_action.setEnabled(False)
        grid_menu.addAction(self.change_grid_action)

    def _create_auto_select_menu(self, menubar, parent_window):
        auto_select_menu = menubar.addMenu("Automatic Selection")

        # Assuming automatic_selection is an attribute of parent_window
        self.amplitude_menu = auto_select_menu.addMenu("Amplitude Based")
        self.amplitude_menu.setEnabled(False)

        start_action = QAction("Start", parent_window)
        start_action.setStatusTip("Start automatic channel selection based on thresholds")
        start_action.triggered.connect(parent_window.automatic_selection.perform_selection)
        self.amplitude_menu.addAction(start_action)

        settings_action = QAction("Settings", parent_window)
        settings_action.setStatusTip("Configure thresholds for automatic selection")
        settings_action.triggered.connect(parent_window.automatic_selection.open_settings_dialog)
        self.amplitude_menu.addAction(settings_action)

    def _add_version_to_statusbar(self, parent_window):
         version_label = QLabel(
            f"hdsemg-select | University of Applied Sciences Vienna - Department Physiotherapy | Version: {__version__}")
         version_label.setStyleSheet("padding-right: 10px;")
         parent_window.statusBar().addPermanentWidget(version_label)

    # Methods to access the created actions if needed by the parent window
    def get_save_action(self):
        return self.save_action

    def get_change_grid_action(self):
        return self.change_grid_action

    def get_amplitude_menu(self):
        return self.amplitude_menu