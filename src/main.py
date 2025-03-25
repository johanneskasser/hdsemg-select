import argparse
import logging
import sys
from functools import partial
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from log.log_config import setup_logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog, QGridLayout,
    QWidget, QScrollArea, QCheckBox, QHBoxLayout, QLabel, QStyle, QMessageBox, QDialog, QComboBox, QFrame, QAction
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from logic.data_processing import welchPS
from ui.manual_grid_input import manual_grid_input
from ui.selection.amplitude_based import AutomaticAmplitudeSelection
from logic.channel_management import update_channel_status_single, select_all_channels, count_selected_channels
from logic.data_processing import compute_upper_quartile, scale_data
from logic.file_io import load_mat_file, save_selection_to_json, save_selection_to_mat
from logic.grid import extract_grid_info, grid_json_setup
from logic.plotting import create_channel_figure
from ui.electrode_widget import ElectrodeWidget

import resources_rc


class ChannelSelector(QMainWindow):
    def __init__(self, input_file=None, output_file=None):
        super().__init__()
        self.setWindowTitle("HDsEMG Channel Selector")
        self.setWindowIcon(QIcon(":/resources/icon.png"))
        self.setGeometry(100, 100, 1200, 800)

        # Save startup parameters (if any)
        self.input_file = input_file
        self.output_file = output_file

        # State variables
        self.current_page = 0
        self.items_per_page = 16
        self.total_pages = 0
        self.checkboxes = []
        self.channel_status = []
        self.grid_info = {}
        self.data = None
        self.time = None
        self.file_name = None
        self.file_path = None
        self.file_size = None
        self.channel_count = 0
        self.channels_per_row = 4

        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.orientation = None
        self.rows = 0
        self.cols = 0
        self.selected_grid = None  # store currently selected grid key

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
        grid_json_setup()

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
        save_action.triggered.connect(self.save_selection)
        save_action.setEnabled(False)
        file_menu.addAction(save_action)

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
            self.file_path = file_path
            logger.info(f"Loading file {self.file_path}")
            (self.data, self.time, self.description,
             self.sampling_frequency, self.file_name, self.file_size) = load_mat_file(file_path)

            logger.debug(f"Original Data Min: {np.min(self.data)}")
            logger.debug(f"Original Data Max: {np.max(self.data)}")

            # Perform amplitude scaling
            self.upper_quartile = compute_upper_quartile(self.data)
            self.scaled_data = scale_data(self.data, self.upper_quartile)

            logger.debug(f"Scaled Data Min: {np.min(self.scaled_data)}")
            logger.debug(f"Scaled Data Max: {np.max(self.scaled_data)}")

            # Initialize channel status
            self.channel_count = self.data.shape[1]
            self.channel_status = [False] * self.channel_count

            # Extract grid info and proceed
            self.grid_info = extract_grid_info(self.description)
            if not self.grid_info:
                QMessageBox.warning(
                    self, "Grid Info Missing",
                    "Automatic grid extraction failed. Please provide grid sizes manually."
                )
                self.grid_info = manual_grid_input(self.channel_count, self.time, self.scaled_data)
                if not self.grid_info:
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
            self.setWindowTitle(f"HDsEMG Channel Selector - Amplitude over Time - {self.file_name}")

    def select_grid_and_orientation(self):
        if not self.grid_info:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Grid and Orientation")
        layout = QVBoxLayout()

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        grid_combo = QComboBox()
        for grid_key in self.grid_info.keys():
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

        self.rows = self.grid_info[self.selected_grid]["rows"]
        self.cols = self.grid_info[self.selected_grid]["cols"]
        indices = self.grid_info[self.selected_grid]["indices"]

        # Validate the grid shape
        if len(indices) != self.grid_info[self.selected_grid]["electrodes"]:
            QMessageBox.critical(
                self, "Grid Error",
                f"Grid shape mismatch: Cannot reshape {len(indices)} indices into "
                f"({self.rows}, {self.cols}). Please check the grid configuration. If this file has already been through the channel selection process it cannot be opened again (future implementation)."
            )
            dialog.reject()
            return

        # Adjust indices if electrodes are less than rows * cols
        max_channels = self.rows * self.cols
        grid_channels = self.grid_info[self.selected_grid]["electrodes"]
        if grid_channels < max_channels:
            logger.debug(f"Grid {self.selected_grid} has {grid_channels} channels but {self.selected_grid} is {max_channels}. So I am filling the last with None.")
            indices = indices + [None] * (max_channels - len(indices))

        full_grid_array = np.array(indices).reshape(self.rows, self.cols)
        if self.orientation == "perpendicular":
            self.current_grid_indices = full_grid_array.flatten(order='C').tolist()
            self.items_per_page = self.cols
        else:
            self.current_grid_indices = full_grid_array.flatten(order='F').tolist()
            self.items_per_page = self.rows

        # Remove placeholder channels (None) from the final list
        self.current_grid_indices = [ch for ch in self.current_grid_indices if ch is not None]

        if len(self.current_grid_indices) > max_channels:
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
        if self.select_all_checkbox.isChecked():
            self.channel_status = select_all_channels(self.channel_status, True)
            self.select_all_checkbox.setText("Deselect All")
        else:
            self.channel_status = select_all_channels(self.channel_status, False)
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
        end_electrode_per_grid_idx = start_idx + self.grid_info[self.selected_grid]["electrodes"]
        page_channels = self.current_grid_indices[start_idx:end_idx]
        grid_electrode_channels = self.current_grid_indices[start_idx:end_electrode_per_grid_idx]

        data_for_grid = self.scaled_data[:, grid_electrode_channels]

        self.global_min = np.min(data_for_grid)
        self.global_max = np.max(data_for_grid)

        self.ylim = (self.global_min - 0.1 * abs(self.global_min),
                     self.global_max + 0.1 * abs(self.global_max))

        for page_pos, channel_idx in enumerate(page_channels):
            ch_number = channel_idx + 1
            figure = create_channel_figure(self.time, self.scaled_data[:, channel_idx], channel_idx, self.ylim)
            canvas = FigureCanvas(figure)

            ui_col = page_pos % self.channels_per_row
            ui_plot_row = (page_pos // self.channels_per_row) * 2

            self.grid_layout.addWidget(canvas, ui_plot_row, ui_col)

            control_layout = QHBoxLayout()
            checkbox = QCheckBox(f"Ch {ch_number}", self)
            checkbox.setChecked(self.channel_status[channel_idx])
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
        self.electrode_widget.update_all(self.channel_status, self.current_grid_indices)
        self.electrode_widget.set_orientation_highlight(self.orientation, self.current_page)

    def handle_single_channel_update(self, idx, state):
        update_channel_status_single(self.channel_status, idx, state)
        self.update_info_label()
        if idx in self.grid_channel_map:
            grid_idx = self.grid_channel_map[idx]
            self.electrode_widget.set_orientation_highlight(self.orientation, self.current_page)
            self.electrode_widget.update_electrode(grid_idx, self.channel_status[idx])

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_page()

    def view_channel_in_detail(self, channel_idx):
        self.detail_window = QMainWindow(self)
        self.detail_window.setWindowTitle(f"Channel {channel_idx + 1} - Detailed View")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(self.data[:, channel_idx])
        ax.set_title(f"Channel {channel_idx + 1}")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude (μV)")

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self.detail_window)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.detail_window.setCentralWidget(central_widget)
        self.detail_window.show()

    def update_info_label(self):
        selected_count = count_selected_channels(self.channel_status)
        file_size_kb = self.file_size / 1024 if self.file_size else 0
        info_text = (
            f"File: {self.file_name if self.file_name else 'None'} ({file_size_kb:.2f} KB)\n"
            f"Total Channels: {self.channel_count}\n"
            f"Sampling Frequency: {self.sampling_frequency if self.sampling_frequency else 'N/A'}\n"
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
        y = self.data[:, channel_idx]
        fs = self.sampling_frequency
        xf, yf = welchPS(y, fs)

        self.spectrum_window = QMainWindow(self)
        self.spectrum_window.setWindowTitle(f"Channel {channel_idx + 1} - Frequency Spectrum")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(xf, yf)
        ax.set_title(f"Channel {channel_idx + 1} Frequency Spectrum")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power")
        ax.set_xlim(0, 600)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self.spectrum_window)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.spectrum_window.setCentralWidget(central_widget)
        self.spectrum_window.show()

    def save_selection(self):
        # If output_file was provided at startup, bypass the file dialog.
        if self.output_file:
            file_path = self.output_file
            # In this example we assume outputFile is a .mat file.
            save_selection_to_mat(file_path, self.data, self.time, self.description, self.sampling_frequency,
                                    self.channel_status, self.file_name, self.grid_info)
            QMessageBox.information(
                self,
                "Success",
                f"Selection saved successfully to {Path(file_path).name}.",
                QMessageBox.Ok
            )
            self.close()  # Close the application after saving.
        else:
            options = QFileDialog.Options()
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save File",
                "",
                "JSON Files (*.json);;MATLAB Files (*.mat)",
                options=options
            )
            if file_path:
                if selected_filter.startswith("JSON") or file_path.endswith(".json"):
                    save_selection_to_json(file_path, self.file_name, self.grid_info, self.channel_status, self.description)
                elif selected_filter.startswith("MATLAB") or file_path.endswith(".mat"):
                    save_selection_to_mat(file_path, self.data, self.time, self.description, self.sampling_frequency,
                                          self.channel_status, self.file_name, self.grid_info)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Selection saved successfully to {Path(file_path).name}.",
                    QMessageBox.Ok
                )

    def reset_to_start_state(self):
        self.file_path = None
        self.data = None
        self.time = None
        self.description = None
        self.file_name = None
        self.file_size = None
        self.sampling_frequency = None
        self.channel_count = 0
        self.channel_status = []
        self.grid_info = {}
        self.current_page = 0
        self.total_pages = 0
        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.orientation = None
        self.rows = 0
        self.cols = 0
        self.selected_grid = None

        self.info_label.setText("No file loaded. Use File -> Open... to load a .mat file.")
        self.grid_label.setHidden(True)
        self.select_all_checkbox.setEnabled(False)
        self.select_all_checkbox.setChecked(False)
        self.electrode_widget.setHidden(True)
        self.setWindowTitle("HDsEMG Channel Selector")
        self.clear_grid_display()

        self.amplidude_menu.setEnabled(False)
        self.save_action.setEnabled(False)
        self.change_grid_action.setEnabled(False)


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger("hdsemg")

    # Parse command-line arguments for inputFile and outputFile.
    parser = argparse.ArgumentParser(description="HDsEMG Channel Selector")
    parser.add_argument("--inputFile", type=str, help="File to be opened upon startup")
    parser.add_argument("--outputFile", type=str, help="Destination .mat file for saving the selection")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = ChannelSelector(input_file=args.inputFile, output_file=args.outputFile)
    window.showMaximized()

    # If an input file was specified, load it automatically.
    if args.inputFile:
        window.load_file_path(args.inputFile)

    sys.exit(app.exec_())
