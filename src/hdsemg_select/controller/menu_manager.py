# menu_manager.py
from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import QAction, QMenu, QLabel, QDialog  # Import QMenu

from hdsemg_select.controller.file_management import save_selection
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.icons.custom_icon_enum import CustomIcon
from hdsemg_select.version import __version__


class MenuManager:
    def __init__(self):
        self.save_action = None
        self.change_grid_action = None
        self.amplitude_menu = None
        self.suggest_flags_action = None  # New action

    def create_menus(self, menubar, parent_window):
        """Creates and adds menus to the given menubar."""
        file_menu = self._create_file_menu(menubar, parent_window)
        grid_menu = self._create_grid_menu(menubar, parent_window)
        auto_select_menu = self._create_auto_select_menu(menubar, parent_window)  # Get reference to auto_select_menu
        self._add_version_to_statusbar(parent_window)

        # Store references to top-level menus if needed elsewhere by name lookup
        file_menu.setObjectName("File")
        grid_menu.setObjectName("Grid")
        auto_select_menu.setObjectName("Automatic Selection")
        self._init_arrow_key_navigation(parent_window)

    def _create_file_menu(self, menubar, parent_window) -> QMenu:  # Added return type hint
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open...", parent_window)
        open_action.setStatusTip("Open a .mat file")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(parent_window.load_file)
        file_menu.addAction(open_action)

        self.save_action = QAction("Save Selection", parent_window)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.setStatusTip("Save current channel selection and labels")
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(partial(self._perform_save_selection, parent_window))
        file_menu.addAction(self.save_action)

        app_settings_menu = QAction("Settings", parent_window)
        app_settings_menu.setStatusTip("Open application settings")
        app_settings_menu.setIcon(QIcon(CustomIcon.SETTINGS.value))
        app_settings_menu.triggered.connect(parent_window.openAppSettings)
        file_menu.addAction(app_settings_menu)

        return file_menu  # Return the created menu

    def _create_grid_menu(self, menubar, parent_window) -> QMenu:  # Added return type hint
        grid_menu = menubar.addMenu("Grid")

        self.change_grid_action = QAction("Change Grid/Orientation...", parent_window)
        self.change_grid_action.setShortcut(QKeySequence("Ctrl+C"))
        self.change_grid_action.setStatusTip("Change the currently selected grid or orientation")
        self.change_grid_action.setEnabled(False)
        self.change_grid_action.triggered.connect(parent_window.select_grid_and_orientation)
        grid_menu.addAction(self.change_grid_action)

        return grid_menu  # Return the created menu

    def _create_auto_select_menu(self, menubar, parent_window) -> QMenu:  # Added return type hint
        auto_select_menu = menubar.addMenu("Automatic Selection")

        self.amplitude_menu = auto_select_menu.addMenu("Amplitude Based")
        self.amplitude_menu.setEnabled(False)  # Enabled when data is loaded

        self.start_action = QAction("Start", parent_window)
        self.start_action.setStatusTip("Start automatic channel selection based on thresholds")
        self.start_action.triggered.connect(parent_window.automatic_selection.perform_selection)
        self.start_action.setEnabled(parent_window.automatic_selection.is_threshold_valid())
        self.amplitude_menu.addAction(self.start_action)

        settings_action = QAction("Settings", parent_window)
        settings_action.setStatusTip("Configure thresholds for automatic selection")
        settings_action.triggered.connect(partial(self.on_auto_settings_, parent_window))
        self.amplitude_menu.addAction(settings_action)

        auto_select_menu.addSeparator()  # Add a separator before the new flag action

        self.suggest_flags_action = QAction("Suggest Artifact Flags...", parent_window)
        self.suggest_flags_action.setStatusTip("Automatically suggest ECG, Noise, or Artifact flags")
        self.suggest_flags_action.setEnabled(False)  # Enabled when data is loaded
        # Connect to the parent window's new method
        self.suggest_flags_action.triggered.connect(parent_window.run_auto_flagger)
        auto_select_menu.addAction(self.suggest_flags_action)

        return auto_select_menu  # Return the created menu

    def on_auto_settings_(self, parent_window):
        result = parent_window.automatic_selection.open_settings_dialog()
        if result == QDialog.Accepted:
            valid = parent_window.automatic_selection.is_threshold_valid()
            self.start_action.setEnabled(valid)

    def _add_version_to_statusbar(self, parent_window):
        version_label = QLabel(
            f"hdsemg-select | University of Applied Sciences Campus Wien - Physiotherapy | Version: {__version__}")
        version_label.setStyleSheet("padding-right: 10px;")
        parent_window.statusBar().addPermanentWidget(version_label)

    def _perform_save_selection(self, parent_window):
        """
        Collects necessary data from global_state and calls the save_selection function.
        """
        # Retrieve all required data from the global_state singleton
        channel_status = global_state.get_channel_status()
        channel_labels = global_state.get_channel_labels()
        output_file = global_state.get_output_file()
        emg_file = global_state.get_emg_file()

        save_selection(
            parent=parent_window,
            output_file=output_file,
            emg_file=emg_file,
            channel_status=channel_status,
            channel_labels=channel_labels  # Pass the collected labels
        )

    def _init_arrow_key_navigation(self, parent_window):
        """
        Initializes arrow key navigation using QActions.
        These actions work as global shortcuts for the main window.
        """
        # Action for the left arrow key
        self.go_left_action = QAction('Go Left', parent_window)
        # Use Qt.Key_Left for the shortcut
        self.go_left_action.setShortcut(QKeySequence(Qt.Key_Left))
        self.go_left_action.triggered.connect(parent_window.prev_page)
        parent_window.addAction(self.go_left_action)

        self.go_right_action = QAction('Go Right', parent_window)
        self.go_right_action.setShortcut(QKeySequence(Qt.Key_Right))
        self.go_right_action.triggered.connect(parent_window.next_page)
        parent_window.addAction(self.go_right_action)

        self.select_all_action = QAction('Select All', parent_window)
        self.select_all_action.setShortcut(QKeySequence("Ctrl+A"))
        self.select_all_action.triggered.connect(partial(parent_window.toggle_select_all, True))
        parent_window.addAction(self.select_all_action)


    # Methods to access the created actions/menus if needed by the parent window
    def get_save_action(self):
        return self.save_action

    def get_change_grid_action(self):
        return self.change_grid_action

    def get_amplitude_menu(self):
        return self.amplitude_menu

    def get_suggest_flags_action(self):  # New getter
        return self.suggest_flags_action
