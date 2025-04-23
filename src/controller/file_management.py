import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from pathlib import Path
from hdsemg_shared import save_selection_to_mat, save_selection_to_json, load_file, extract_grid_info

from select_logic.data_processing import compute_upper_quartile, scale_data
from state.state import global_state
from _log.log_config import logger
from ui.manual_grid_input import manual_grid_input


class FileManager:
    def __init__(self):
        self.upper_quartile = None

    def process_file(self, file_path, parent_window):
        """
        Loads, processes the file, updates global state, and handles initial grid info.
        Returns True on success, False on failure.
        """
        if not file_path:
            return False

        try:
            global_state.set_file_path(file_path)
            logger.info(f"Loading file {global_state.get_file_path()}")

            # Load data and other info
            data, time, description, sampling_frequency, file_name, file_size = load_file(file_path)

            # Store loaded data in state
            global_state.set_data(data)
            global_state.set_time(time)
            global_state.set_description(description)
            global_state.set_sampling_frequency(sampling_frequency)
            global_state.set_file_name(file_name)
            global_state.set_file_size(file_size)

            logger.debug(f"Original Data Min: {np.min(global_state.get_data())}")
            logger.debug(f"Original Data Max: {np.max(global_state.get_data())}")

            # Perform amplitude scaling, store scaled data in state
            self.upper_quartile = compute_upper_quartile(global_state.get_data())
            global_state.set_scaled_data(scale_data(global_state.get_data(), self.upper_quartile))

            logger.debug(f"Scaled Data Min: {np.min(global_state.get_scaled_data())}")
            logger.debug(f"Scaled Data Max: {np.max(global_state.get_scaled_data())}")

            # Initialize channel count and status, store in state
            global_state.set_channel_count(global_state.get_data().shape[1])
            global_state.set_channel_status([False] * global_state.get_channel_count())

            # Extract grid info and proceed, store in state
            global_state.set_grid_info(extract_grid_info(global_state.get_description()))

            if not global_state.get_grid_info():
                QMessageBox.warning(
                    parent_window, "Grid Info Missing",
                    "Automatic grid extraction failed. Please provide grid sizes manually."
                )
                # Store manual grid info in state
                manual_grid = manual_grid_input(
                    global_state.get_channel_count(),
                    global_state.get_time(),
                    global_state.get_scaled_data()
                )
                global_state.set_grid_info(manual_grid)

                if not global_state.get_grid_info():
                    QMessageBox.information(
                        parent_window, "File Loading Failed",
                        "Grid information could not be determined."
                    )
                    # Reset state if grid info failed
                    global_state.reset()
                    return False  # Indicate failure

            return True  # Indicate success

        except Exception as e:
            logger.error(f"Error loading or processing file: {e}", exc_info=True)
            QMessageBox.critical(
                parent_window, "Loading Error",
                f"An error occurred while loading the file:\n{e}"
            )
            global_state.reset()  # Reset state on any loading error
            return False  # Indicate failure

def save_selection(parent, output_file, data, time, description, sampling_frequency, channel_status, file_name, grid_info):

    if output_file:
        file_path = output_file
        save_selection_to_mat(file_path, data, time, description, sampling_frequency, channel_status, file_name)
        QMessageBox.information(
            parent,
            "Success",
            f"Selection saved successfully to {Path(file_path).name}.",
            QMessageBox.Ok
        )
        parent.close()
    else:
        options = QFileDialog.Options()
        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent,
            "Save File",
            "",
            "JSON Files (*.json);;MATLAB Files (*.mat)",
            options=options
        )
        if file_path:
            if selected_filter.startswith("JSON") or file_path.endswith(".json"):
                save_selection_to_json(file_path, file_name, grid_info, channel_status, description)
            elif selected_filter.startswith("MATLAB") or file_path.endswith(".mat"):
                save_selection_to_mat(file_path, data, time, description, sampling_frequency, channel_status, file_name)
            QMessageBox.information(
                parent,
                "Success",
                f"Selection saved successfully to {Path(file_path).name}.",
                QMessageBox.Ok
            )