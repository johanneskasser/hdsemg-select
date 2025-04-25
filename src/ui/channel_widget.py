# ui/channel_widget.py
from functools import partial

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QStyle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure  # Import Figure
from PyQt5.QtCore import pyqtSignal

from ui.label_bean_widget import LabelBeanWidget

import resources_rc


class ChannelWidget(QWidget):
    channel_status_changed = pyqtSignal(int, int)  # channel_idx, state (Qt.Checked/Unchecked)
    view_detail_requested = pyqtSignal(int)  # channel_idx
    view_spectrum_requested = pyqtSignal(int)  # channel_idx
    edit_labels_requested = pyqtSignal(int)  # channel_idx

    def __init__(self, channel_idx: int, time_data, scaled_data_slice, ylim: tuple,
                 initial_status: bool, initial_labels: list, parent=None):
        super().__init__(parent)
        self.channel_idx = channel_idx
        self.channel_number = channel_idx + 1
        self.time_data = time_data
        self.scaled_data_slice = scaled_data_slice
        self.ylim = ylim
        self._current_labels = initial_labels  # Store current labels

        # --- Layout ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)  # Add some margin around the widget
        self.main_layout.setSpacing(5)  # Space between plot and controls

        # --- Plot Area ---
        self.figure = Figure(figsize=(4, 2), dpi=100)  # Adjust figure size as needed
        self.canvas = FigureCanvas(self.figure)
        self.main_layout.addWidget(self.canvas)

        self._draw_plot()  # Draw the initial plot

        # --- Controls Area ---
        self.controls_layout = QVBoxLayout()  # Vertical layout for labels above buttons
        self.main_layout.addLayout(self.controls_layout)

        # --- Labels Layout ---
        self.labels_h_layout = QHBoxLayout()  # Horizontal layout for labels and '+' button
        self.labels_h_layout.setContentsMargins(0, 0, 0, 0)
        self.labels_h_layout.setSpacing(3)
        self.controls_layout.addLayout(self.labels_h_layout)

        self.label_widgets = []  # List to keep track of label bean widgets

        self.labels_h_layout.addStretch(1)  # Push '+' button to the right

        self.add_label_button = QPushButton("+")
        self.add_label_button.setFixedSize(24, 24)  # Make it small and square
        self.add_label_button.setToolTip(f"Edit labels for Channel {self.channel_number}")
        # Connect button to emit signal
        self.add_label_button.clicked.connect(partial(self.edit_labels_requested.emit, self.channel_idx))
        self.labels_h_layout.addWidget(self.add_label_button)

        self.update_labels_display(initial_labels)  # Display initial labels
        # --- Buttons Layout ---
        self.buttons_h_layout = QHBoxLayout()  # Horizontal layout for checkbox and view buttons
        self.buttons_h_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_h_layout.setSpacing(5)
        self.controls_layout.addLayout(self.buttons_h_layout)

        self.checkbox = QCheckBox(f"Ch {self.channel_number}")
        self.checkbox.setChecked(initial_status)
        # Connect checkbox to emit signal
        self.checkbox.stateChanged.connect(partial(self.channel_status_changed.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.checkbox)

        self.buttons_h_layout.addStretch(1)  # Push buttons to the right

        self.view_button = QPushButton()
        self.view_button.setIcon(QIcon(":/resources/extend.png"))
        self.view_button.setToolTip("View Time Series")
        self.view_button.setFixedSize(30, 30)
        # Connect button to emit signal
        self.view_button.clicked.connect(partial(self.view_detail_requested.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.view_button)

        self.spectrum_button = QPushButton()
        self.spectrum_button.setIcon(QIcon(":/resources/frequency.png"))
        self.spectrum_button.setToolTip("View Frequency Spectrum")
        self.spectrum_button.setFixedSize(30, 30)
        # Connect button to emit signal
        self.spectrum_button.clicked.connect(partial(self.view_spectrum_requested.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.spectrum_button)

    def _draw_plot(self):
        """Draws the time series plot on the canvas."""
        if self.time_data is None or self.scaled_data_slice is None:
            # Handle case where data is not available
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No data", horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw()
            return

        # Clear previous plot
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        ax.plot(self.time_data, self.scaled_data_slice)
        ax.set_ylim(self.ylim)
        ax.axis('off')  # Hide axes for a cleaner look

        # Adjust layout to prevent axis labels/titles overlapping
        self.figure.tight_layout(pad=0)

        self.canvas.draw()

    def update_labels_display(self, labels: list):
        """Updates the visual display of labels (beans) for this channel."""
        self._current_labels = labels  # Store the new labels

        # Clear existing label widgets (keep the '+' button)
        for widget in self.label_widgets:
            self.labels_h_layout.removeWidget(widget)
            widget.deleteLater()
        self.label_widgets = []

        # Mapping labels to colors
        label_colors = {
            "ECG": "salmon",
            "Noise 50 Hz": "gold",
            "Noise 60 Hz": "gold",
            "Artifact": "orange",
            "Bad Channel": "red",
        }

        # Add new label bean widgets
        for label in sorted(labels):  # Sort labels alphabetically for consistency
            color = label_colors.get(label, "lightblue")  # Default color if label not in map
            bean = LabelBeanWidget(label, color=color)
            # Insert beans before the stretch and the '+' button
            self.labels_h_layout.insertWidget(self.labels_h_layout.count() - 2, bean)
            self.label_widgets.append(bean)

        if labels:
            self.add_label_button.setToolTip(f"Edit labels for Channel {self.channel_number}:\n" + ", ".join(labels))
        else:
            self.add_label_button.setToolTip(f"Add labels for Channel {self.channel_number}")

    def update_channel_status(self, status: bool):
        """Updates the checkbox state programmatically."""
        # Use blockSignals to prevent the signal from firing again when setting programmatically
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(status)
        self.checkbox.blockSignals(False)