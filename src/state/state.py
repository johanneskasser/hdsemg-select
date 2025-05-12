from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

from _log.log_config import logger

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
        self._grid_info = {}
        self._data = None
        self._time = None
        self._file_name = None
        self._file_path = None
        self._file_size = None
        self._channel_count = 0
        self._scaled_data = None
        self._description = None
        self._sampling_frequency = None
        self._channel_labels = {}
        self._input_file = None
        self._output_file = None



    # Getters
    def get_channel_status(self, idx = None) -> list:
        if idx is None:
            return self._channel_status
        else:
            if idx in self._channel_status:
                return self._channel_status[idx]
            else:
                logger.debug(f"Channel index {idx} not found in channel status. Creating an empty list.")
                self._channel_status[idx] = []
                return self._channel_status[idx]

    def get_grid_info(self) -> dict:
        return self._grid_info

    def get_data(self):
        return self._data

    def get_time(self):
        return self._time

    def get_file_name(self) -> str:
        return self._file_name

    def get_file_path(self) -> str:
        return self._file_path

    def get_file_size(self):
        return self._file_size

    def get_channel_count(self) -> int:
        return self._channel_count

    def get_scaled_data(self):
        return self._scaled_data

    def get_description(self):
        return self._description

    def get_sampling_frequency(self):
        return self._sampling_frequency

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
    def set_channel_status(self, value: list):
        self._channel_status = value

    def set_grid_info(self, value: dict):
        self._grid_info = value

    def set_data(self, value):
        self._data = value

    def set_time(self, value):
        self._time = value

    def set_file_name(self, value: str):
        self._file_name = value

    def set_file_path(self, value: str):
        self._file_path = value

    def set_file_size(self, value):
        self._file_size = value

    def set_channel_count(self, value: int):
        self._channel_count = value

    def set_scaled_data(self, value):
        self._scaled_data = value

    def set_description(self, value):
        self._description = value

    def set_sampling_frequency(self, value):
        self._sampling_frequency = value

    def get_input_file(self):
        return self._input_file

    def set_input_file(self, value):
        self._input_file = value

    def get_output_file(self):
        return self._output_file

    def set_output_file(self, value):
        self._output_file = value

    # New Method to update labels for a specific channel
    def update_channel_labels(self, channel_idx: int, labels: list):
        if not isinstance(labels, list):
            raise ValueError("Labels must be a list")
        if channel_idx < 0 or channel_idx >= self._channel_count:
            # Handle potential out of bounds if channel_count is zero or incorrect
            if self._channel_count > 0:
                logger.warning(
                    f"Attempted to update labels for channel index {channel_idx}, but channel count is {self._channel_count}. Ignoring.")
                return

        if labels:
            self._channel_labels[channel_idx] = labels
        elif channel_idx in self._channel_labels:
            del self._channel_labels[channel_idx]

        # Emit signal to notify that channel labels have changed
        self.channel_labels_changed.emit(channel_idx, labels)

global_state = State()