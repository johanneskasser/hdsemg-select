# main_window.py
from functools import partial

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont, QKeySequence
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QScrollArea, QGridLayout, \
    QPushButton, QStyle, QCheckBox, QAction, QFileDialog, QMessageBox, QDialog, QComboBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from _log.log_config import logger
from select_logic.channel_management import select_all_channels, update_channel_status_single, count_selected_channels
from select_logic.plotting import create_channel_figure
from settings.settings_dialog import SettingsDialog
from ui.channel_details import ChannelDetailWindow
from ui.channel_spectrum import ChannelSpectrum
from ui.electrode_widget import ElectrodeWidget
from ui.selection.amplitude_based import AutomaticAmplitudeSelection

import resources_rc

from state.state import global_state

from controller.menu_manager import MenuManager
from controller.file_management import FileManager
from controller.grid_setup_handler import GridSetupHandler


class ChannelSelector(QMainWindow):
    def __init__(self, input_file=None, output_file=None):
        super().__init__()
        self.setWindowTitle("hdsemg-select")
        self.setWindowIcon(QIcon(":/resources/icon.png"))
        self.setGeometry(100, 100, 1200, 800)
        self.app_settings_dialog = SettingsDialog()

        # Save startup parameters (if any)
        self.input_file = input_file
        self.output_file = output_file

        # Instantiate handlers
        self.menu_manager = MenuManager()
        self.file_handler = FileManager()
        self.grid_setup_handler = GridSetupHandler()

        # Local UI-specific variables or variables not part of the global state
        # These are now managed by grid_setup_handler, but ChannelSelector
        # stores/uses the values obtained from the handler.
        # self.current_page = 0 # Managed by grid_setup_handler
        # self.items_per_page = 16 # Managed by grid_setup_handler
        # self.total_pages = 0 # Managed by grid_setup_handler
        self.checkboxes = [] # UI element references, not state or grid setup
        self.channels_per_row = 4 # UI layout setting, not state or grid setup

        # These are managed/calculated by grid_setup_handler, ChannelSelector gets them via getters
        # self.current_grid_indices = [] # Managed by grid_setup_handler
        # self.grid_channel_map = {} # Managed by grid_setup_handler
        # self.orientation = None # Managed by grid_setup_handler
        # self.rows = 0 # Managed by grid_setup_handler
        # self.cols = 0 # Managed by grid_setup_handler
        # self.selected_grid = None # Managed by grid_setup_handler

        # These are display/plotting parameters derived from scaled data
        self.upper_quartile = None # Managed by file_handler, but stored here for display logic
        self.global_min = None
        self.global_max = None
        self.ylim = None
        self.channel_flags = [] # Seems unused in provided code? Kept for now if it's used elsewhere.


        # Create the main layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        # Outer horizontal layout: electrode representation on the left, vertical line, and main UI on the right
        self.outer_layout = QHBoxLayout(self.main_widget)
        # electrode_widget depends on rows/cols calculated by grid_setup_handler, update its usage later
        self.electrode_widget = ElectrodeWidget()
        self.outer_layout.addWidget(self.electrode_widget)
        self.electrode_widget.setHidden(True)

        # Add a vertical line separator
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        self.outer_layout.addWidget(line)

        # Right side vertical layout
        self.layout = QVBoxLayout()
        self.outer_layout.addLayout(self.layout)

        # Header layout
        self.header_layout = QHBoxLayout()
        self.layout.addLayout(self.header_layout)

        # File info label
        self.info_label = QLabel("No file loaded. Use File -> Open... to load a .mat file.")
        self.header_layout.addWidget(self.info_label)

        # Scroll area for channel plots
        self.scroll_area = QScrollArea(self)
        self.scroll_widget = QWidget()
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.layout.addLayout(self.pagination_layout)

        self.prev_button = QPushButton()
        self.prev_button.setToolTip("Previous")
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.prev_button.clicked.connect(self.prev_page)
        self.pagination_layout.addWidget(self.prev_button)

        self.page_label = QLabel("Page 1/1")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.pagination_layout.addWidget(self.page_label)

        self.next_button = QPushButton()
        self.next_button.setToolTip("Next")
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.next_button.clicked.connect(self.next_page)
        self.pagination_layout.addWidget(self.next_button)

        # Create the menu bar using the MenuManager
        self.automatic_selection = AutomaticAmplitudeSelection(self) # Keep AutomaticSelection here
        self.create_menus() # This method now delegates to MenuManager

        self.grid_label = QLabel("")
        self.grid_label.setAlignment(Qt.AlignCenter)
        self.grid_label.setHidden(True)
        font = QFont()
        font.setPointSize(10)
        self.grid_label.setFont(font)
        self.header_layout.addWidget(self.grid_label)

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        self.select_all_checkbox.setEnabled(False)
        self.header_layout.addWidget(self.select_all_checkbox)

        # Version label is now added by MenuManager
        # version_label = QLabel(...) # Removed
        # self.statusBar().addPermanentWidget(version_label) # Removed


    def create_menus(self):
        """Delegates menu creation to the MenuManager."""
        menubar = self.menuBar()
        self.menu_manager.create_menus(menubar, self)

        # Get references to actions/menus created by the manager to control their enabled state
        self.save_action = self.menu_manager.get_save_action()
        self.change_grid_action = self.menu_manager.get_change_grid_action()
        self.amplidude_menu = self.menu_manager.get_amplitude_menu()


    def load_file(self):
        """Opens a file dialog and triggers file loading."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "MAT Files (*.mat)", options=options)
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path):
        """
        Loads a file from the provided path using the FileManager.
        """
        # Delegate file processing to the FileManager
        success = self.file_handler.process_file(file_path, self) # Pass self for parent window context

        if success:
            # Update UI elements enabled/disabled state based on successful load and processing
            self.change_grid_action.setEnabled(True)
            self.amplidude_menu.setEnabled(True)

            # Trigger grid selection after successful file processing
            self.select_grid_and_orientation()

            self.electrode_widget.setHidden(False)
            self.setWindowTitle(f"hdsemg-select - Amplitude over Time - {global_state.get_file_name()}") # Use getter
        else:
            # File processing failed (message box already shown by FileManager)
            # Ensure UI is reset or stays in a no-file state
            self.reset_to_start_state()


    def select_grid_and_orientation(self):
        """Opens dialog to select grid and orientation."""
        # Access grid info from state to populate the dialog
        grid_info = global_state.get_grid_info()
        if not grid_info:
            return # Should not happen if load_file_path succeeded, but safety check

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Grid and Orientation")
        layout = QVBoxLayout()

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        grid_combo = QComboBox()
        for grid_key in grid_info.keys():
            grid_combo.addItem(grid_key)
        layout.addWidget(grid_combo)

        orientation_label = QLabel("Select Orientation:")
        layout.addWidget(orientation_label)

        orientation_combo = QComboBox()
        orientation_combo.addItem("Parallel to fibers", "parallel")
        orientation_combo.addItem("Perpendicular to fibers", "perpendicular")
        layout.addWidget(orientation_combo)

        ok_button = QPushButton("OK")

        def on_ok():
            selected_grid = grid_combo.currentText()
            orientation = orientation_combo.currentData()
            # Call method to apply selection logic
            self.apply_grid_selection(selected_grid, orientation, dialog)

        ok_button.clicked.connect(on_ok)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        # Use exec_() to make the dialog modal
        dialog.exec_()


    def apply_grid_selection(self, selected_grid, orientation, dialog):
        """Applies the selected grid and orientation using the GridSetupHandler."""

        # Delegate the calculation and logic to the handler
        success = self.grid_setup_handler.apply_selection(selected_grid, orientation, self) # Pass self for parent window context

        if success:
            # Update local UI state from the handler's calculated values
            # self.selected_grid = self.grid_setup_handler.get_selected_grid() # Redundant, already passed
            # self.orientation = self.grid_setup_handler.get_orientation() # Redundant, already passed
            self.rows = self.grid_setup_handler.get_rows()
            self.cols = self.grid_setup_handler.get_cols()
            # self.current_grid_indices = self.grid_setup_handler.get_current_grid_indices() # Used in display_page, get it there
            # self.grid_channel_map = self.grid_setup_handler.get_grid_channel_map() # Used in handle_single_channel_update, get it there
            self.items_per_page = self.grid_setup_handler.get_items_per_page()
            self.total_pages = self.grid_setup_handler.get_total_pages()
            self.grid_setup_handler.set_current_page(0) # Ensure page resets on grid change


            dialog.accept() # Accept the dialog now that application logic succeeded

            # Update UI elements based on new grid setup
            self.electrode_widget.set_grid_shape((self.rows, self.cols))
            self.electrode_widget.label_electrodes()
            # electrode_widget requires current_page, orientation, and the index mapping. Get orientation from handler.
            self.electrode_widget.set_orientation_highlight(self.grid_setup_handler.get_orientation(), self.grid_setup_handler.get_current_page())


            self.display_page() # Refresh the display

            # Enable relevant actions
            self.save_action.setEnabled(True)
            self.select_all_checkbox.setEnabled(True)
            # Update grid label using values from handler
            self.grid_label.setText(f"{self.rows}x{self.cols} grid - {self.grid_setup_handler.get_orientation()}")
            self.grid_label.setHidden(False)
        else:
            # Grid setup failed (message box already shown by handler)
            dialog.reject()
            # Optionally reset to a clearer state if grid selection is fundamental
            # self.reset_to_start_state() # Maybe too harsh? Depends on desired behavior.
            pass


    def toggle_select_all(self):
        """Toggles selection status for all channels."""
        # Get channel status from state
        channel_status = global_state.get_channel_status()

        if self.select_all_checkbox.isChecked():
            # Update status in state
            global_state.set_channel_status(select_all_channels(channel_status, True))
            self.select_all_checkbox.setText("Deselect All")
        else:
            # Update status in state
            global_state.set_channel_status(select_all_channels(channel_status, False))
            self.select_all_checkbox.setText("Select All")

        self.display_page() # Refresh display to show changes
        self.update_info_label() # Update selected count label

    def clear_grid_display(self):
        """Clears all widgets from the channel grid layout."""
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def display_page(self):
        """Displays the channels for the current page."""
        # Get display/paging parameters from GridSetupHandler
        current_page = self.grid_setup_handler.get_current_page()
        total_pages = self.grid_setup_handler.get_total_pages()
        items_per_page = self.grid_setup_handler.get_items_per_page()
        current_grid_indices = self.grid_setup_handler.get_current_grid_indices()
        rows = self.grid_setup_handler.get_rows() # Needed for potential full grid calculations
        cols = self.grid_setup_handler.get_cols() # Needed for potential full grid calculations
        selected_grid_key = self.grid_setup_handler.get_selected_grid() # Needed for grid info lookup


        self.page_label.setText(f"Page {current_page + 1}/{total_pages}")
        self.prev_button.setEnabled(current_page > 0)
        self.next_button.setEnabled(current_page < total_pages - 1)

        self.clear_grid_display()
        self.checkboxes = [] # Clear list of checkboxes for the previous page

        start_idx = current_page * items_per_page
        end_idx = start_idx + items_per_page

        # Get state data
        grid_info = global_state.get_grid_info() # Needed to find electrode count for grid
        scaled_data = global_state.get_scaled_data()
        time_data = global_state.get_time()
        channel_status = global_state.get_channel_status()


        # Calculate min/max for the *entire* grid data to ensure consistent scaling
        # Get the indices for the entire selected grid from grid_info
        if selected_grid_key and grid_info and selected_grid_key in grid_info:
            full_grid_indices_flat = [ch for ch in grid_info[selected_grid_key]["indices"] if ch is not None]

            if full_grid_indices_flat and scaled_data is not None:
                data_for_grid = scaled_data[:, full_grid_indices_flat]
                self.global_min = np.min(data_for_grid)
                self.global_max = np.max(data_for_grid)
            else:
                 self.global_min = -1
                 self.global_max = 1
                 if scaled_data is None:
                      logger.warning("Scaled data is None when trying to calculate global min/max.")
                 if not full_grid_indices_flat and selected_grid_key:
                     logger.warning(f"No valid indices found for grid '{selected_grid_key}' to calculate global min/max.")

        else:
             # No grid selected or grid info missing
             self.global_min = -1
             self.global_max = 1
             logger.warning("Grid info or selected grid missing, using default ylim.")


        # Use calculated min/max for ylim
        # Add a small buffer to the limits
        buffer = 0.1 * (abs(self.global_max) + abs(self.global_min)) if self.global_min is not None and self.global_max is not None else 0.2
        self.ylim = (self.global_min - buffer if self.global_min is not None else -1.1,
                     self.global_max + buffer if self.global_max is not None else 1.1)


        # Get the channels for the current page based on current_grid_indices
        page_channels = current_grid_indices[start_idx:end_idx]

        for page_pos, channel_idx in enumerate(page_channels):
            # channel_idx should not be None here because we filtered current_grid_indices

            ch_number = channel_idx + 1
            # Use time and scaled data from state
            # create_channel_figure needs time, scaled_data slice, channel_idx, ylim
            figure = create_channel_figure(time_data, scaled_data[:, channel_idx], channel_idx, self.ylim)
            canvas = FigureCanvas(figure)

            # Calculate row/col for the QGridLayout display
            ui_col = page_pos % self.channels_per_row
            ui_plot_row = (page_pos // self.channels_per_row) * 2

            self.grid_layout.addWidget(canvas, ui_plot_row, ui_col)

            control_layout = QHBoxLayout()
            checkbox = QCheckBox(f"Ch {ch_number}", self)
            # Use channel status from state
            if channel_idx < len(channel_status): # Safety check
                 checkbox.setChecked(channel_status[channel_idx])
            else:
                 logger.warning(f"Channel index {channel_idx} out of bounds for channel_status list (len {len(channel_status)}).")
                 checkbox.setEnabled(False) # Disable checkbox if status is unavailable

            # Connect checkbox signal to handler method
            checkbox.stateChanged.connect(partial(self.handle_single_channel_update, channel_idx))
            control_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox) # Store reference to the checkbox

            view_button = QPushButton()
            view_button.setIcon(QIcon(":/resources/extend.png"))
            view_button.setToolTip("View Time Series")
            view_button.setFixedSize(30, 30)
            # Connect button signal to view method
            view_button.clicked.connect(partial(self.view_channel_in_detail, channel_idx))
            control_layout.addWidget(view_button)

            spectrum_button = QPushButton()
            spectrum_button.setIcon(QIcon(":/resources/frequency.png"))
            spectrum_button.setToolTip("View Frequency Spectrum")
            spectrum_button.setFixedSize(30, 30)
            # Connect button signal to view method
            spectrum_button.clicked.connect(partial(self.view_channel_spectrum, channel_idx))
            control_layout.addWidget(spectrum_button)

            control_widget = QWidget()
            control_widget.setLayout(control_layout)
            self.grid_layout.addWidget(control_widget, ui_plot_row + 1, ui_col)

        self.update_info_label() # Update info label after refreshing display
        # Update electrode widget highlights based on channel status and current grid indices
        # electrode_widget needs channel_status and the list of indices being displayed/represented
        self.electrode_widget.update_all(channel_status, self.grid_setup_handler.get_current_grid_indices())
        # Update orientation highlight
        self.electrode_widget.set_orientation_highlight(
             self.grid_setup_handler.get_orientation(),
             self.grid_setup_handler.get_current_page() # Use handler's current page
        )


    def handle_single_channel_update(self, idx, state):
        """Handles state change for a single channel checkbox."""
        # Update channel status in state (modifies list in place)
        channel_status = global_state.get_channel_status()
        if idx < len(channel_status): # Safety check
            update_channel_status_single(channel_status, idx, state)
        else:
             logger.warning(f"Attempted to update status for channel index {idx} which is out of bounds.")
             return # Exit if index is invalid

        self.update_info_label() # Update selected count label

        # Update electrode widget highlight for the specific channel
        grid_channel_map = self.grid_setup_handler.get_grid_channel_map()
        if idx in grid_channel_map:
            grid_idx = grid_channel_map[idx]
            # Use channel status from state
            self.electrode_widget.set_orientation_highlight(
                self.grid_setup_handler.get_orientation(),
                self.grid_setup_handler.get_current_page()
            )
            self.electrode_widget.update_electrode(grid_idx, channel_status[idx])
        else:
             logger.debug(f"Channel index {idx} not found in current grid map.")


    def prev_page(self):
        """Navigates to the previous page."""
        if self.grid_setup_handler.get_current_page() > 0:
            self.grid_setup_handler.decrement_page() # Update page in handler
            self.display_page() # Refresh display

    def next_page(self):
        """Navigates to the next page."""
        if self.grid_setup_handler.get_current_page() < self.grid_setup_handler.get_total_pages() - 1:
            self.grid_setup_handler.increment_page() # Update page in handler
            self.display_page() # Refresh display

    def view_channel_in_detail(self, channel_idx):
        """Opens a detailed time series view for a channel."""
        # Use data from state
        if global_state.get_data() is not None:
             self.detail_window = ChannelDetailWindow(self, global_state.get_data(), channel_idx)
             self.detail_window.show()
        else:
             logger.warning("Cannot view channel detail: No data loaded.")


    def update_info_label(self):
        """Updates the information label in the header."""
        # Use channel status, file size, file name, channel count, and sampling frequency from state
        selected_count = count_selected_channels(global_state.get_channel_status())
        file_size = global_state.get_file_size()
        file_size_kb = file_size / 1024 if file_size is not None else 0
        info_text = (
            f"File: {global_state.get_file_name() if global_state.get_file_name() else 'None'} ({file_size_kb:.2f} KB)\n"
            f"Total Channels: {global_state.get_channel_count()}\n"
            f"Sampling Frequency: {global_state.get_sampling_frequency() if global_state.get_sampling_frequency() is not None else 'N/A'}\n"
            f"Selected Channels: {selected_count}"
        )
        self.info_label.setText(info_text)

    def keyPressEvent(self, event):
        """Handles keyboard shortcuts for navigation."""
        key = event.key()
        if key == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        else:
            super().keyPressEvent(event)

    def view_channel_spectrum(self, channel_idx):
        """Opens a frequency spectrum view for a channel."""
        # ChannelSpectrum likely needs data from global state (scaled_data, sampling_frequency, time)
        # Ensure ChannelSpectrum uses getters from global_state internally or pass necessary data.
        # Assuming ChannelSpectrum uses global_state directly.
        if global_state.get_scaled_data() is not None and global_state.get_sampling_frequency() is not None:
            if not hasattr(self, 'channel_spectrum'):
                self.channel_spectrum = ChannelSpectrum(self)
            self.channel_spectrum.view_channel_spectrum(channel_idx)
        else:
            logger.warning("Cannot view spectrum: Data or sampling frequency not available.")


    def openAppSettings(self):
        """Opens the application settings dialog."""
        # Settings dialog might need/set values from global state or other sources.
        # It's instantiated in __init__ and managed here.
        if self.app_settings_dialog.exec_():
            logger.debug("Settings Dialog closed and accepted")
        else:
            logger.debug("Settings Dialog closed")

    def reset_to_start_state(self):
        """Resets the application state and UI to the initial state."""
        # Reset the global state singleton
        global_state.reset()

        # Reset local UI-specific variables managed directly by ChannelSelector
        self.checkboxes = []
        self.upper_quartile = None
        self.global_min = None
        self.global_max = None
        self.ylim = None
        self.channel_flags = []


        # Reset local variables managed by handlers (via resetting the handler instances or calling their reset)
        # It's cleaner to reset the handlers themselves if they hold significant state
        # Let's add a reset method to GridSetupHandler
        self.grid_setup_handler = GridSetupHandler() # Re-instantiate or call a reset method

        self.info_label.setText("No file loaded. Use File -> Open... to load a file.")
        self.grid_label.setHidden(True)
        self.select_all_checkbox.setEnabled(False)
        self.select_all_checkbox.setChecked(False)
        self.electrode_widget.setHidden(True)
        self.setWindowTitle("hdsemg-select")
        self.clear_grid_display() # Clear the visual grid layout

        # Disable menus/actions that require a file/grid loaded
        if self.amplidude_menu: self.amplidude_menu.setEnabled(False)
        if self.save_action: self.save_action.setEnabled(False)
        if self.change_grid_action: self.change_grid_action.setEnabled(False)