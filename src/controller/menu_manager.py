# menu_manager.py
from functools import partial

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QMenu, QLabel  # Import QMenu

from controller.file_management import save_selection
from state.state import global_state
from version import __version__


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

        start_action = QAction("Start", parent_window)
        start_action.setStatusTip("Start automatic channel selection based on thresholds")
        start_action.triggered.connect(parent_window.automatic_selection.perform_selection)
        self.amplitude_menu.addAction(start_action)

        settings_action = QAction("Settings", parent_window)
        settings_action.setStatusTip("Configure thresholds for automatic selection")
        # This action likely needs access to the settings dialog instance
        settings_action.triggered.connect(parent_window.automatic_selection.open_settings_dialog)
        self.amplitude_menu.addAction(settings_action)

        auto_select_menu.addSeparator()  # Add a separator before the new flag action

        # New Action: Suggest Artifact Flags
        self.suggest_flags_action = QAction("Suggest Artifact Flags...", parent_window)
        self.suggest_flags_action.setStatusTip("Automatically suggest ECG, Noise, or Artifact flags")
        self.suggest_flags_action.setEnabled(False)  # Enabled when data is loaded
        # Connect to the parent window's new method
        self.suggest_flags_action.triggered.connect(parent_window.run_auto_flagger)
        auto_select_menu.addAction(self.suggest_flags_action)

        return auto_select_menu  # Return the created menu

    def _add_version_to_statusbar(self, parent_window):
        version_label = QLabel(
            f"hdsemg-select | University of Applied Sciences Vienna - Department Physiotherapy | Version: {__version__}")
        version_label.setStyleSheet("padding-right: 10px;")
        parent_window.statusBar().addPermanentWidget(version_label)

    def _perform_save_selection(self, parent_window):
        """
        Collects necessary data from global_state and calls the save_selection function.
        """
        # Retrieve all required data from the global_state singleton
        data = global_state.get_data()
        time = global_state.get_time()
        description = global_state.get_description()
        sampling_frequency = global_state.get_sampling_frequency()
        channel_status = global_state.get_channel_status()
        file_name = global_state.get_file_name()
        grid_info = global_state.get_grid_info()
        channel_labels = global_state.get_channel_labels()
        output_file = global_state.get_output_file()

        save_selection(
            parent=parent_window,
            output_file=output_file,
            data=data,
            time=time,
            description=description,
            sampling_frequency=sampling_frequency,
            channel_status=channel_status,
            file_name=file_name,
            grid_info=grid_info,
            channel_labels=channel_labels  # Pass the collected labels
        )

    # Methods to access the created actions/menus if needed by the parent window
    def get_save_action(self):
        return self.save_action

    def get_change_grid_action(self):
        return self.change_grid_action

    def get_amplitude_menu(self):
        return self.amplitude_menu

    def get_suggest_flags_action(self):  # New getter
        return self.suggest_flags_action
