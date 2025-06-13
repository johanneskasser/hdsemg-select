# ui/channel_widget.py
from functools import partial

import numpy as np
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QCheckBox, QMenu, QWidgetAction, QToolButton)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import pyqtSignal

from hdsemg_select.state.state import global_state
from hdsemg_select.config.config_manager import config # For getting available labels
from hdsemg_select.ui.labels.label_bean_widget import LabelBeanWidget
from hdsemg_select.ui.labels.label_selection_widget import LabelSelectionWidget
from hdsemg_select._log.log_config import logger

class ChannelWidget(QWidget):
    channel_status_changed = pyqtSignal(int, int)  # channel_idx, state (Qt.Checked/Unchecked)
    view_detail_requested = pyqtSignal(int)  # channel_idx
    view_spectrum_requested = pyqtSignal(int)  # channel_idx

    def __init__(self, channel_idx: int, time_data, scaled_data_slice, ylim: tuple,
                 initial_status: bool, initial_labels: list, parent=None, _overlay_ref_signal=None):
        super().__init__(parent)
        self.channel_idx = channel_idx
        self.channel_number = channel_idx + 1
        self.time_data = time_data
        self.scaled_data_slice = scaled_data_slice
        self.ylim = ylim
        self._current_labels = list(initial_labels) # Store a mutable copy
        self._overlay_ref_signal = _overlay_ref_signal

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        self.figure = Figure(figsize=(4, 2), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.main_layout.addWidget(self.canvas)
        self._draw_plot()

        self.controls_layout = QVBoxLayout()
        self.main_layout.addLayout(self.controls_layout)

        self.labels_h_layout = QHBoxLayout()
        self.labels_h_layout.setContentsMargins(0, 0, 0, 0)
        self.labels_h_layout.setSpacing(3)
        self.controls_layout.addLayout(self.labels_h_layout)

        self.label_widgets = []
        self.labels_h_layout.addStretch(1)

        self.add_label_button = QToolButton(self)
        self.add_label_button.setText("+   ")
        self.add_label_button.setFixedSize(34, 24)
        self.add_label_button.setPopupMode(QToolButton.InstantPopup) # Menu appears on click

        self.label_menu = QMenu(self) # Parent to self for lifetime management
        self.add_label_button.setMenu(self.label_menu)
        self.label_menu.aboutToShow.connect(self._prepare_label_menu) # Populate when about to show

        self.labels_h_layout.addWidget(self.add_label_button)
        self.update_labels_display(self._current_labels) # Display initial labels & update tooltip

        self.buttons_h_layout = QHBoxLayout()
        self.buttons_h_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_h_layout.setSpacing(5)
        self.controls_layout.addLayout(self.buttons_h_layout)

        self.checkbox = QCheckBox(f"Ch {self.channel_number}")
        self.checkbox.setChecked(initial_status)
        self.checkbox.stateChanged.connect(partial(self.channel_status_changed.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.checkbox)

        self.buttons_h_layout.addStretch(1)

        self.view_button = QPushButton()
        self.view_button.setIcon(QIcon(":/resources/extend.png"))
        self.view_button.setToolTip("View Time Series")
        self.view_button.setFixedSize(30, 30)
        self.view_button.clicked.connect(partial(self.view_detail_requested.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.view_button)

        self.spectrum_button = QPushButton()
        self.spectrum_button.setIcon(QIcon(":/resources/frequency.png"))
        self.spectrum_button.setToolTip("View Frequency Spectrum")
        self.spectrum_button.setFixedSize(30, 30)
        self.spectrum_button.clicked.connect(partial(self.view_spectrum_requested.emit, self.channel_idx))
        self.buttons_h_layout.addWidget(self.spectrum_button)


        global_state.channel_labels_changed.connect(self._on_label_changed)
        # Initial check for available labels to set button state
        self._check_available_labels()


    def _check_available_labels(self):
        """Disables the add label button if no labels are available."""
        available_labels = config.get_available_channel_labels()
        if not available_labels:
            self.add_label_button.setEnabled(False)
            self.add_label_button.setToolTip(f"No labels available for Channel {self.channel_number}")
        else:
            self.add_label_button.setEnabled(True)
            # Tooltip will be set/updated by update_labels_display


    def _prepare_label_menu(self):
        """
        Populates the label selection menu right before it is shown.
        """
        self.label_menu.clear()

        current_channel_labels = global_state.get_channel_labels().get(self.channel_idx, [])
        available_labels = config.get_available_channel_labels()

        if not available_labels: # Should be caught by _check_available_labels, but good as safeguard
            no_labels_action = self.label_menu.addAction("No labels available")
            no_labels_action.setEnabled(False)
            self.add_label_button.setEnabled(False)
            return
        else:
            self.add_label_button.setEnabled(True)

        label_selection_widget = LabelSelectionWidget(available_labels, current_channel_labels, self.label_menu)
        label_selection_widget.labels_applied.connect(self._apply_new_labels)

        action = QWidgetAction(self.label_menu)
        action.setDefaultWidget(label_selection_widget)
        self.label_menu.addAction(action)
        label_selection_widget.adjustSize() # Important for QWidgetAction

    def _apply_new_labels(self, new_labels: list):
        global_state.update_channel_labels(self.channel_idx, new_labels)
        logger.info(f"Labels updated for Channel {self.channel_number} ({self.channel_idx}): {new_labels}")
        # The global_state change will trigger _on_label_changed, which updates display.

    def _draw_plot(self):
        if self.time_data is None or self.scaled_data_slice is None:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No data", horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(self.time_data, self.scaled_data_slice, color="blue", linewidth=1, label=f"Ch {self.channel_number}")
        if self._overlay_ref_signal is not None:
            if len(self._overlay_ref_signal) == len(self.time_data):
                ax.plot(self.time_data, self._overlay_ref_signal * 0.9, color="black", linewidth=1, label="Reference", linestyle="--")
                ax.legend(loc='upper right', frameon=False, fontsize='small')
            else:
                logger.warning(f"Reference signal length does not match time data length for Channel {self.channel_number}")
        ax.set_ylim(self.ylim)
        ax.axis('off')
        self.figure.tight_layout(pad=0)
        self.canvas.draw()

    def update_labels_display(self, labels: list):
        self._current_labels = list(labels) # Update internal cache
        for widget in self.label_widgets:
            self.labels_h_layout.removeWidget(widget)
            widget.deleteLater()
        self.label_widgets = []

        for label in sorted(self._current_labels, key=lambda x: x.get("name", "")):
            bean = LabelBeanWidget(label.get("name"), color=label.get("color", "lightblue"))
            self.labels_h_layout.insertWidget(self.labels_h_layout.count() - 2, bean)
            self.label_widgets.append(bean)

        if self.add_label_button.isEnabled(): # Only update tooltip if button is enabled
            if self._current_labels:
                tooltip_text = f"Edit labels for Channel {self.channel_number}:\n" + \
                               ", ".join(label.get("name", "") for label in self._current_labels)
                self.add_label_button.setToolTip(tooltip_text)
            else:
                self.add_label_button.setToolTip(f"Add labels for Channel {self.channel_number}")

    def update_channel_status(self, status: bool):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(status)
        self.checkbox.blockSignals(False)

    def _on_label_changed(self, ch_idx: int, new_labels: list):
        if ch_idx == self.channel_idx:
            self.update_labels_display(new_labels)

    def set_overlay_signal(self, overlay_signal):
        """
        Set the overlay reference signal for the channel plot.
        :param overlay_signal: The reference signal to overlay on the channel plot.
        """
        self._overlay_ref_signal = overlay_signal
        self._draw_plot()
        self.canvas.draw_idle()
        self.update()

    @staticmethod
    def scale_ref_signal(ref_sig):
        """
        Centers the reference signal around 0 and scales the peak amplitude to the maximum amplitude of the data.
        """
        if ref_sig is None:
            logger.warning("No reference signal passed.")
            return None

        # 1) Remove offset
        sig_centered = ref_sig - np.mean(ref_sig)

        # 2) Max amplitude of the data
        data_max_amp = global_state.get_max_amplitude()
        if data_max_amp is None:
            logger.warning("No data available to scale reference signal!")
            return sig_centered

        peak_ref = np.max(np.abs(sig_centered))
        if peak_ref == 0 or data_max_amp == 0:
            logger.warning("Reference or Data Amplitude is 0, return unscaled signal.")
            return sig_centered

        factor = peak_ref / data_max_amp

        return sig_centered / factor


