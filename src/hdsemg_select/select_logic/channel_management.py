from PyQt5.QtCore import Qt
from hdsemg_select.controller.file_management import _build_channel_status
from hdsemg_select.state.state import global_state

def update_channel_status_single(channel_status, idx, state):
    channel_status[idx] = (state == Qt.Checked)

def select_all_channels(channel_status, select):
    if not select:
        return _build_channel_status(len(channel_status), global_state.get_emg_file().grids)
    return [select] * len(channel_status)

def count_selected_channels(channel_status):
    return sum(channel_status)
