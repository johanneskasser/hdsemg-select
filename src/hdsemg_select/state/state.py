from typing import Dict

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
import numpy as np
from hdsemg_shared.fileio.file_io import EMGFile

from hdsemg_select._log.log_config import logger
from hdsemg_select.state.enum.layout_mode_enums import FiberMode, LayoutMode


class State(QObject):
    channel_labels_changed = pyqtSignal(int, list)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            QObject.__init__(cls._instance)      # initialise QObject
            cls._instance.reset()
        return cls._instance

    def reset(self):
        self._channel_status = []
        self._file_path = None
        self._scaled_data = None
        self._emg_file = None
        self._channel_labels = {}
        self._input_file = None
        self._output_file = None
        self.max_amplitude = None
        # default fallback
        self._fiber_to_layout: Dict[FiberMode, LayoutMode] = {
            FiberMode.PARALLEL: LayoutMode.COLUMNS,
            FiberMode.PERPENDICULAR: LayoutMode.ROWS
        }
        self._fiber_to_layout_user_set = False # dirty flag to check if the layout was set by the user - important for the json metdata



    # Getters
    def get_channel_status(self, idx = None) -> list:
        if idx is None:
            return self._channel_status
        else:
            if 0 <= idx < len(self._channel_status):
                return self._channel_status[idx]
            else:
                logger.debug(f"Channel index {idx} not found in channel status. Creating an empty list.")
                self._channel_status[idx] = []
                return self._channel_status[idx]

    def get_emg_file(self) -> EMGFile:
        return self._emg_file

    def get_max_amplitude(self):
        return self.max_amplitude

    def get_file_path(self) -> str:
        return self._file_path

    def get_scaled_data(self):
        return self._scaled_data

    def get_channel_labels(self, idx: int = None):
        if idx is None:
            return self._channel_labels
        else:
            if idx in self._channel_labels:
                return self._channel_labels[idx]
            else:
                logger.debug(f"Channel index {idx} not found in channel labels. Creating an empty list.")
                self._channel_labels[idx] = []
                return self._channel_labels[idx]

    # Setters
    def set_emg_file(self, emg_file: EMGFile):
        if not isinstance(emg_file, EMGFile):
            raise ValueError(f"Expected EMGFile instance, got {type(emg_file)}")
        self._emg_file = emg_file

    def set_channel_status(self, value: list):
        self._channel_status = value

    def set_grid_info(self, value: dict):
        self._grid_info = value

    def set_file_path(self, value: str):
        self._file_path = value

    def set_scaled_data(self, value):
        all_emg_idx = [idx for cfg in self._emg_file.grids for idx in cfg.emg_indices]
        self.max_amplitude = np.abs(value[:, all_emg_idx]).max()
        self._scaled_data = value

    def get_input_file(self):
        return self._input_file

    def set_input_file(self, value):
        self._input_file = value

    def get_output_file(self):
        return self._output_file

    def set_output_file(self, value):
        self._output_file = value

    def update_channel_labels(self, channel_idx: int, labels: list):
        if not isinstance(labels, list):
            raise ValueError("Labels must be a list")
        if channel_idx < 0 or channel_idx >= self._emg_file.channel_count:
            # Handle potential out of bounds if channel_count is zero or incorrect
            if self._emg_file.channel_count > 0:
                logger.warning(
                    f"Attempted to update labels for channel index {channel_idx}, but channel count is {self._emg_file.channel_count}. Ignoring.")
                return

        if labels:
            self._channel_labels[channel_idx] = labels
        elif channel_idx in self._channel_labels:
            del self._channel_labels[channel_idx]

        # Emit signal to notify that channel labels have changed
        self.channel_labels_changed.emit(channel_idx, labels)

    def set_fiber_layout(self,
                         fiber_mode: FiberMode,
                         layout_mode: LayoutMode) -> None:
        """Set fiber_mode→layout_mode and inverts automatically for other fiber mode."""
        # 1) Validate
        if not isinstance(fiber_mode, FiberMode):
            raise ValueError(f"fiber_mode must be FiberMode, got {type(fiber_mode)}")
        if not isinstance(layout_mode, LayoutMode):
            raise ValueError(f"layout_mode must be LayoutMode, got {type(layout_mode)}")

        # 2) find other fiber and layout mode
        other_fiber = next(f for f in FiberMode if f is not fiber_mode)
        other_layout = next(l for l in LayoutMode if l is not layout_mode)

        # 3) save
        self._fiber_to_layout[fiber_mode] = layout_mode
        self._fiber_to_layout[other_fiber] = other_layout
        self._fiber_to_layout_user_set = True

    def get_layout_for_fiber(self, fiber_mode: FiberMode) -> LayoutMode:
        """Liefert den zugehörigen LayoutMode; ValueError, falls nicht gesetzt."""
        if not isinstance(fiber_mode, FiberMode):
            raise ValueError(f"fiber_mode must be FiberMode, got {type(fiber_mode)}")
        try:
            return self._fiber_to_layout[fiber_mode]
        except KeyError:
            raise KeyError(f"No layout assigned yet for {fiber_mode}")

    def get_layout(self):
        """Returns the whole dict."""
        return self._fiber_to_layout

    def is_fiber_to_layout_user_set(self):
        return self._fiber_to_layout_user_set

global_state = State()