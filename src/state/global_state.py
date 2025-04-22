# global_state.py
class GlobalState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # state variables
        self.input_file = None
        self.output_file = None
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
        self.selected_grid = None

        self._initialized = True

# make a module‐level singleton
global_state = GlobalState()
