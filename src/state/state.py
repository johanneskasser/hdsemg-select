class State:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
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



    # Getters
    def get_channel_status(self) -> list:
        return self._channel_status

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

global_state = State()