from functools import partial

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont, QKeySequence
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QScrollArea, QGridLayout, \
    QPushButton, QStyle, QCheckBox, QAction, QFileDialog, QMessageBox, QDialog, QComboBox
from hdsemg_shared import load_file, extract_grid_info
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from _log.log_config import logger
from controller.file_management import save_selection
from select_logic.channel_management import select_all_channels, update_channel_status_single, count_selected_channels
from select_logic.data_processing import compute_upper_quartile, scale_data
from select_logic.plotting import create_channel_figure
from settings.settings_dialog import SettingsDialog
from ui.channel_details import ChannelDetailWindow
from ui.channel_spectrum import ChannelSpectrum
from ui.electrode_widget import ElectrodeWidget
from ui.manual_grid_input import manual_grid_input
from ui.selection.amplitude_based import AutomaticAmplitudeSelection
from version import __version__

import resources_rc

from state.state import global_state


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

        # Local UI-specific variables or variables not part of the global state
        self.current_page = 0
        self.items_per_page = 16
        self.total_pages = 0
        self.checkboxes = []
        self.channels_per_row = 4

        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.orientation = None
        self.rows = 0
        self.cols = 0
        self.selected_grid = None

        self.upper_quartile = None
        self.global_min = None
        self.global_max = None
        self.ylim = None
        self.channel_flags = []


        # Create the main layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        # Outer horizontal layout: electrode representation on the left, vertical line, and main UI on the right
        self.outer_layout = QHBoxLayout(self.main_widget)
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

        # Create the menu bar
        self.automatic_selection = AutomaticAmplitudeSelection(self)
        self.create_menus()

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

        version_label = QLabel(
            f"hdsemg-select | University of Applied Sciences Vienna - Department Physiotherapy | Version: {__version__}")
        version_label.setStyleSheet("padding-right: 10px;")
        self.statusBar().addPermanentWidget(version_label)


    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open...", self)
        open_action.setStatusTip("Open a .mat file")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)

        save_action = QAction("Save Selection", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.setStatusTip("Save current channel selection")
        save_action.triggered.connect(partial(
            save_selection,
            self,  # parent
            self.output_file,
            global_state.get_data(), # Use getter
            global_state.get_time(), # Use getter
            global_state.get_description(), # Use getter
            global_state.get_sampling_frequency(), # Use getter
            global_state.get_channel_status(), # Use getter
            global_state.get_file_name(), # Use getter
            global_state.get_grid_info() # Use getter
        ))
        save_action.setEnabled(False)
        file_menu.addAction(save_action)

        app_settings_menu = QAction("Settings", self)
        app_settings_menu.setStatusTip("Open application settings")
        app_settings_menu.triggered.connect(self.openAppSettings)
        file_menu.addAction(app_settings_menu)


        self.save_action = save_action  # store reference to enable/disable

        # Grid Menu
        grid_menu = menubar.addMenu("Grid")

        change_grid_action = QAction("Change Grid/Orientation...", self)
        change_grid_action.setShortcut(QKeySequence("Ctrl+C"))
        change_grid_action.setStatusTip("Change the currently selected grid or orientation")
        change_grid_action.triggered.connect(self.select_grid_and_orientation)
        change_grid_action.setEnabled(False)
        grid_menu.addAction(change_grid_action)

        self.change_grid_action = change_grid_action  # store reference

        # Automatic Selection Menu
        auto_select_menu = menubar.addMenu("Automatic Selection")

        amplitude_menu = auto_select_menu.addMenu("Amplitude Based")
        amplitude_menu.setEnabled(False)

        self.amplidude_menu = amplitude_menu  # store reference

        start_action = QAction("Start", self)
        start_action.setStatusTip("Start automatic channel selection based on thresholds")
        start_action.triggered.connect(self.automatic_selection.perform_selection)
        amplitude_menu.addAction(start_action)

        settings_action = QAction("Settings", self)
        settings_action.setStatusTip("Configure thresholds for automatic selection")
        settings_action.triggered.connect(self.automatic_selection.open_settings_dialog)
        amplitude_menu.addAction(settings_action)

    def load_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "MAT Files (*.mat)", options=options)
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path):
        """
        Loads a file from the provided path (bypassing the file dialog).
        """
        if file_path:
            # Store file_path in state
            global_state.set_file_path(file_path)
            logger.info(f"Loading file {global_state.get_file_path()}") # Use getter

            # Load data and other info, store in state
            data, time, description, sampling_frequency, file_name, file_size = load_file(file_path)
            global_state.set_data(data)
            global_state.set_time(time)
            global_state.set_description(description)
            global_state.set_sampling_frequency(sampling_frequency)
            global_state.set_file_name(file_name)
            global_state.set_file_size(file_size)


            logger.debug(f"Original Data Min: {np.min(global_state.get_data())}") # Use getter
            logger.debug(f"Original Data Max: {np.max(global_state.get_data())}") # Use getter

            # Perform amplitude scaling, store scaled data in state
            self.upper_quartile = compute_upper_quartile(global_state.get_data()) # Use getter
            global_state.set_scaled_data(scale_data(global_state.get_data(), self.upper_quartile)) # Use getter

            logger.debug(f"Scaled Data Min: {np.min(global_state.get_scaled_data())}") # Use getter
            logger.debug(f"Scaled Data Max: {np.max(global_state.get_scaled_data())}") # Use getter

            # Initialize channel count and status, store in state
            global_state.set_channel_count(global_state.get_data().shape[1]) # Use getter
            global_state.set_channel_status([False] * global_state.get_channel_count()) # Use getter

            # Extract grid info and proceed, store in state
            global_state.set_grid_info(extract_grid_info(global_state.get_description())) # Use getter
            if not global_state.get_grid_info(): # Use getter
                QMessageBox.warning(
                    self, "Grid Info Missing",
                    "Automatic grid extraction failed. Please provide grid sizes manually."
                )
                # Store manual grid info in state
                manual_grid = manual_grid_input(
                    global_state.get_channel_count(), # Use getter
                    global_state.get_time(), # Use getter
                    global_state.get_scaled_data() # Use getter
                )
                global_state.set_grid_info(manual_grid)

                if not global_state.get_grid_info(): # Use getter
                    QMessageBox.information(
                        self, "Returning to Start State",
                        "Grid entry failed."
                    )
                    self.reset_to_start_state()
                    return

            # Allow changing grid/orientation after first load
            self.change_grid_action.setEnabled(True)
            self.amplidude_menu.setEnabled(True)

            self.select_grid_and_orientation()
            self.electrode_widget.setHidden(False)
            self.setWindowTitle(f"hdsemg-select - Amplitude over Time - {global_state.get_file_name()}") # Use getter

    def select_grid_and_orientation(self):
        if not global_state.get_grid_info(): # Use getter
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Grid and Orientation")
        layout = QVBoxLayout()

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        grid_combo = QComboBox()
        for grid_key in global_state.get_grid_info().keys(): # Use getter
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
            self.apply_grid_selection(selected_grid, orientation, dialog)

        ok_button.clicked.connect(on_ok)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def apply_grid_selection(self, selected_grid, orientation, dialog):
        self.selected_grid = selected_grid
        self.orientation = orientation

        # Access grid info from state
        grid_info = global_state.get_grid_info()

        self.rows = grid_info[self.selected_grid]["rows"]
        self.cols = grid_info[self.selected_grid]["cols"]
        indices = grid_info[self.selected_grid]["indices"]


        # Validate the grid shape
        if len(indices) != grid_info[self.selected_grid]["electrodes"]:
            QMessageBox.critical(
                self, "Grid Error",
                f"Grid shape mismatch: Cannot reshape {len(indices)} indices into "
                f"({self.rows}, {self.cols}). Please check the grid configuration. If this file has already been through the channel selection process it cannot be opened again (future implementation)."
            )
            dialog.reject()
            return

        # Adjust indices if electrodes are less than rows * cols
        max_channels = self.rows * self.cols
        grid_channels = grid_info[self.selected_grid]["electrodes"]
        if grid_channels < max_channels:
            logger.debug(
                f"Grid {self.selected_grid} has {grid_channels} channels but {self.selected_grid} is {max_channels}. So I am filling the last with None.")
            indices = indices + [None] * (max_channels - len(indices))

        full_grid_array = np.array(indices).reshape(self.rows, self.cols)
        if self.orientation == "perpendicular":
            self.current_grid_indices = full_grid_array.flatten(order='C').tolist()
            self.items_per_page = self.cols # Items per page depends on display orientation
        else:
            self.current_grid_indices = full_grid_array.flatten(order='F').tolist()
            self.items_per_page = self.rows # Items per page depends on display orientation

        # Remove placeholder channels (None) from the final list
        self.current_grid_indices = [ch for ch in self.current_grid_indices if ch is not None]

        if len(self.current_grid_indices) > max_channels:
             # This check seems redundant after removing None, but keeping it for safety
            self.current_grid_indices = self.current_grid_indices[:max_channels]

        self.grid_channel_map = {ch_idx: i for i, ch_idx in enumerate(self.current_grid_indices)}
        self.total_pages = int(np.ceil(len(self.current_grid_indices) / self.items_per_page))
        self.current_page = 0
        dialog.accept()

        self.electrode_widget.set_grid_shape((self.rows, self.cols))
        self.electrode_widget.label_electrodes()
        self.electrode_widget.set_orientation_highlight(self.orientation, self.current_page)

        self.display_page()
        self.save_action.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.grid_label.setText(f"{self.rows}x{self.cols} grid - {self.orientation}")
        self.grid_label.setHidden(False)


    def toggle_select_all(self):
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
        self.display_page()
        self.update_info_label()

    def clear_grid_display(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def display_page(self):
        self.page_label.setText(f"Page {self.current_page + 1}/{self.total_pages}")
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < self.total_pages - 1)

        self.clear_grid_display()
        self.checkboxes = []

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page

        # Access grid info and scaled data from state
        grid_info = global_state.get_grid_info()
        scaled_data = global_state.get_scaled_data()
        time_data = global_state.get_time() # Need time data too

        end_electrode_per_grid_idx = start_idx + grid_info[self.selected_grid]["electrodes"]
        page_channels = self.current_grid_indices[start_idx:end_idx]
        grid_electrode_channels = self.current_grid_indices[start_idx:end_electrode_per_grid_idx]

        # Ensure we don't try to index with None if placeholder was added but not removed correctly (shouldn't happen now)
        valid_grid_electrode_channels = [ch for ch in grid_electrode_channels if ch is not None]

        # Calculate global min/max based on the data included in the selected grid
        # Use scaled data from state
        if valid_grid_electrode_channels:
             data_for_grid = scaled_data[:, valid_grid_electrode_channels]
             self.global_min = np.min(data_for_grid)
             self.global_max = np.max(data_for_grid)
        else:
             # Handle case with no valid channels in the selected grid (shouldn't happen if file loaded)
             self.global_min = -1 # sensible defaults
             self.global_max = 1
             logger.warning("No valid channels found for the selected grid slice.")


        # Use calculated min/max for ylim
        self.ylim = (self.global_min - 0.1 * abs(self.global_min) if self.global_min is not None else -1.1,
                     self.global_max + 0.1 * abs(self.global_max) if self.global_max is not None else 1.1)


        # Access channel status from state
        channel_status = global_state.get_channel_status()

        for page_pos, channel_idx in enumerate(page_channels):
            if channel_idx is None: # Skip placeholder channels if they somehow remain
                continue

            ch_number = channel_idx + 1
            # Use time and scaled data from state
            figure = create_channel_figure(time_data, scaled_data[:, channel_idx], channel_idx, self.ylim)
            canvas = FigureCanvas(figure)

            ui_col = page_pos % self.channels_per_row
            ui_plot_row = (page_pos // self.channels_per_row) * 2

            self.grid_layout.addWidget(canvas, ui_plot_row, ui_col)

            control_layout = QHBoxLayout()
            checkbox = QCheckBox(f"Ch {ch_number}", self)
            # Use channel status from state
            checkbox.setChecked(channel_status[channel_idx])
            checkbox.stateChanged.connect(partial(self.handle_single_channel_update, channel_idx))
            control_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)

            view_button = QPushButton()
            view_button.setIcon(QIcon(":/resources/extend.png"))
            view_button.setToolTip("View Time Series")
            view_button.setFixedSize(30, 30)
            view_button.clicked.connect(partial(self.view_channel_in_detail, channel_idx))
            control_layout.addWidget(view_button)

            spectrum_button = QPushButton()
            spectrum_button.setIcon(QIcon(":/resources/frequency.png"))
            spectrum_button.setToolTip("View Frequency Spectrum")
            spectrum_button.setFixedSize(30, 30)
            spectrum_button.clicked.connect(partial(self.view_channel_spectrum, channel_idx))
            control_layout.addWidget(spectrum_button)

            control_widget = QWidget()
            control_widget.setLayout(control_layout)
            self.grid_layout.addWidget(control_widget, ui_plot_row + 1, ui_col)

        self.update_info_label()
        # Use channel status from state
        self.electrode_widget.update_all(channel_status, self.current_grid_indices)
        self.electrode_widget.set_orientation_highlight(self.orientation, self.current_page)


    def handle_single_channel_update(self, idx, state):
        # Update channel status in state (modifies list in place)
        update_channel_status_single(global_state.get_channel_status(), idx, state)
        self.update_info_label()
        if idx in self.grid_channel_map:
            grid_idx = self.grid_channel_map[idx]
            self.electrode_widget.set_orientation_highlight(self.orientation, self.current_page)
            # Use channel status from state
            self.electrode_widget.update_electrode(grid_idx, global_state.get_channel_status()[idx])

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_page()

    def view_channel_in_detail(self, channel_idx):
        # Use data from state
        self.detail_window = ChannelDetailWindow(self, global_state.get_data(), channel_idx)
        self.detail_window.show()

    def update_info_label(self):
        # Use channel status, file size, file name, channel count, and sampling frequency from state
        selected_count = count_selected_channels(global_state.get_channel_status())
        file_size = global_state.get_file_size()
        file_size_kb = file_size / 1024 if file_size else 0
        info_text = (
            f"File: {global_state.get_file_name() if global_state.get_file_name() else 'None'} ({file_size_kb:.2f} KB)\n"
            f"Total Channels: {global_state.get_channel_count()}\n"
            f"Sampling Frequency: {global_state.get_sampling_frequency() if global_state.get_sampling_frequency() else 'N/A'}\n"
            f"Selected Channels: {selected_count}"
        )
        self.info_label.setText(info_text)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        else:
            super().keyPressEvent(event)

    def view_channel_spectrum(self, channel_idx):
        if not hasattr(self, 'channel_spectrum'):
            self.channel_spectrum = ChannelSpectrum(self)
        # ChannelSpectrum likely needs time, scaled_data, and sampling_frequency
        # Ensure ChannelSpectrum uses getters from global_state internally, or pass them here if needed.
        # Assuming ChannelSpectrum accesses state directly via global_state.
        self.channel_spectrum.view_channel_spectrum(channel_idx)

    def openAppSettings(self):
        if self.app_settings_dialog.exec_():
            logger.debug(f"Settings Dialog closed and accepted")
        else:
            logger.debug("Settings Dialog closed")

    def reset_to_start_state(self):
        # Reset the global state singleton
        global_state.reset()

        # Reset local UI-specific variables
        self.current_page = 0
        self.total_pages = 0
        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.orientation = None
        self.rows = 0
        self.cols = 0
        self.selected_grid = None
        self.upper_quartile = None
        self.global_min = None
        self.global_max = None
        self.ylim = None


        self.info_label.setText("No file loaded. Use File -> Open... to load a file.")
        self.grid_label.setHidden(True)
        self.select_all_checkbox.setEnabled(False)
        self.select_all_checkbox.setChecked(False)
        self.electrode_widget.setHidden(True)
        self.setWindowTitle("hdsemg-select")
        self.clear_grid_display()

        self.amplidude_menu.setEnabled(False)
        self.save_action.setEnabled(False)
        self.change_grid_action.setEnabled(False)