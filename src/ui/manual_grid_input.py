import logging
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialog,
    QMessageBox, QCheckBox, QScrollArea, QWidget, QProgressBar
)
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import QThread, pyqtSignal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import numpy as np

logger = logging.getLogger("hdsemg")


def manual_grid_input(total_channels, time, scaled_data):
    dialog = QDialog()
    dialog.setWindowTitle("Enter Grid Information")
    layout = QVBoxLayout()

    grid_label = QLabel("Enter Grid Sizes and Reference Signals:")
    layout.addWidget(grid_label)

    # Grid entry section
    grid_entries_layout = QVBoxLayout()
    add_grid_entry(grid_entries_layout)  # Add the first grid entry row
    layout.addLayout(grid_entries_layout)

    add_grid_button = QPushButton("+")
    add_grid_button.setToolTip("Add another grid size entry")
    add_grid_button.clicked.connect(lambda: add_grid_entry(grid_entries_layout))
    layout.addWidget(add_grid_button)

    # Button to open the channel selection widget
    channel_selection_button = QPushButton("View Raw Channels")
    channel_selection_button.setToolTip("Open interactive channel selection Viewer [BETA]")
    channel_selection_button.clicked.connect(lambda: open_all_channels_overview(total_channels, scaled_data, time))
    layout.addWidget(channel_selection_button)

    # Dialog buttons
    button_layout = QHBoxLayout()
    ok_button = QPushButton("OK")
    ok_button.setToolTip("Confirm grid sizes")
    ok_button.clicked.connect(dialog.accept)
    button_layout.addWidget(ok_button)

    cancel_button = QPushButton("Cancel")
    cancel_button.clicked.connect(dialog.reject)
    button_layout.addWidget(cancel_button)

    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    if dialog.exec_() == QDialog.Accepted:
        return collect_manual_grid_info(grid_entries_layout, total_channels)
    else:
        return {}


def add_grid_entry(grid_entries_layout):
    grid_row = QHBoxLayout()

    rows_input = QLineEdit()
    rows_input.setPlaceholderText("Rows")
    rows_input.setValidator(QIntValidator(1, 100))  # Accept integers between 1 and 100
    rows_input.setToolTip("Enter the number of rows for the grid")
    grid_row.addWidget(rows_input)

    x_label = QLabel("x")
    grid_row.addWidget(x_label)

    cols_input = QLineEdit()
    cols_input.setPlaceholderText("Columns")
    cols_input.setValidator(QIntValidator(1, 100))  # Accept integers between 1 and 100
    cols_input.setToolTip("Enter the number of columns for the grid")
    grid_row.addWidget(cols_input)

    ref_label = QLabel("|")
    grid_row.addWidget(ref_label)

    ref_input = QLineEdit()
    ref_input.setPlaceholderText("References")
    ref_input.setValidator(QIntValidator(1, 100))
    ref_input.setToolTip("Enter the number of reference signals for the grid")
    grid_row.addWidget(ref_input)

    grid_entries_layout.addLayout(grid_row)


def collect_manual_grid_info(grid_entries_layout, total_channels):
    grids = {}
    total_channel_count = 0

    for i in range(grid_entries_layout.count()):
        layout = grid_entries_layout.itemAt(i)
        if isinstance(layout, QHBoxLayout):
            rows_input = layout.itemAt(0).widget()
            cols_input = layout.itemAt(2).widget()
            ref_input = layout.itemAt(4).widget()

            try:
                rows = int(rows_input.text())
                cols = int(cols_input.text())
                refs = int(ref_input.text())
                grid_key = f"{rows}x{cols}"
                num_channels = rows * cols + refs
                electrodes = rows * cols

                total_channel_count += num_channels

                if total_channel_count > total_channels:
                    QMessageBox.warning(None, "Invalid Input",
                                        f"The total number of channels ({total_channel_count}) exceeds the total available channels in the file ({total_channels}).")
                    return {}

                if grid_key not in grids:
                    grids[grid_key] = {"rows": rows, "cols": cols, "indices": list(range(electrodes)), "reference_signals": refs, "electrodes": electrodes}
            except ValueError:
                QMessageBox.warning(None, "Invalid Input", "Please ensure all grid sizes and reference signals per grid are valid.")
                return {}

    return grids


class LoadChannelsThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    canceled = pyqtSignal()

    def __init__(self, total_channels, scaled_data, time):
        super().__init__()
        self.total_channels = total_channels
        self.scaled_data = scaled_data
        self.time = time
        self._is_canceled = False

    def run(self):
        for i in range(self.total_channels):
            if self._is_canceled:
                self.canceled.emit()
                return
            self.msleep(50)  # Simulate loading delay
            self.progress.emit(int((i + 1) / self.total_channels * 100))
        self.finished.emit()

    def cancel(self):
        self._is_canceled = True


def open_all_channels_overview(total_channels, scaled_data, time):
    # Confirmation dialog
    confirm_dialog = QMessageBox()
    confirm_dialog.setIcon(QMessageBox.Warning)
    confirm_dialog.setWindowTitle(f"Loading {total_channels} channels")
    confirm_dialog.setText("Loading all channels is a resource-intensive operation.")
    confirm_dialog.setInformativeText("Do you want to continue?")
    confirm_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    confirm_dialog.setDefaultButton(QMessageBox.No)
    if confirm_dialog.exec_() == QMessageBox.No:
        return

    # Progress dialog setup
    progress_dialog = QDialog()
    progress_dialog.setWindowTitle("Loading Channels")
    layout = QVBoxLayout()
    label = QLabel("Loading channels, please wait...")
    layout.addWidget(label)

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    layout.addWidget(progress_bar)

    cancel_button = QPushButton("Cancel")
    layout.addWidget(cancel_button)

    progress_dialog.setLayout(layout)

    # Thread to load channels
    load_thread = LoadChannelsThread(total_channels, scaled_data, time)

    # Connect signals
    load_thread.progress.connect(progress_bar.setValue)
    load_thread.finished.connect(progress_dialog.accept)
    load_thread.canceled.connect(progress_dialog.reject)
    cancel_button.clicked.connect(load_thread.cancel)

    load_thread.start()
    progress_dialog.exec_()

    if load_thread.isRunning():
        load_thread.wait()

    if not load_thread._is_canceled:
        # Create a dialog for the overview
        overview_dialog = QDialog()
        overview_dialog.setWindowTitle("All Channels Overview")
        layout = QVBoxLayout()
        hlayout = QHBoxLayout()
        pltLayout = QVBoxLayout()

        # Create the figure and canvas
        fig = plt.figure(figsize=(10, 6))
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, overview_dialog)

        pltLayout.addWidget(toolbar)
        pltLayout.addWidget(canvas)

        ax = fig.add_subplot(111)

        # Plot all channels initially
        lines = []
        for i in range(total_channels):
            line, = ax.plot(time, scaled_data[:, i], label=f"Channel {i + 1}", alpha=0.6)
            lines.append(line)

        ax.set_title("All Channels Overview")
        ax.set_xlabel("Time")
        ax.set_ylabel("Amplitude")
        hlayout.addLayout(pltLayout)

        # Create checkboxes for each channel
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        for i in range(total_channels):
            checkbox = QCheckBox(f"Ch {i + 1}")
            checkbox.setChecked(True)
            checkbox.setToolTip(f"Toggle visibility for Channel {i + 1}")

            # Toggle visibility when checkbox is toggled
            def toggle_channel_visibility(state, line=lines[i]):
                line.set_visible(state == 2)
                canvas.draw()

            checkbox.stateChanged.connect(toggle_channel_visibility)
            scroll_layout.addWidget(checkbox)

        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        hlayout.addWidget(scroll_area)

        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(overview_dialog.accept)
        layout.addLayout(hlayout)
        layout.addWidget(close_button)

        overview_dialog.setLayout(layout)
        overview_dialog.exec_()
