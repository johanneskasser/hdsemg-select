import json
import os

import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from pathlib import Path
from hdsemg_shared import save_selection_to_mat, load_file, extract_grid_info

from select_logic.data_processing import compute_upper_quartile, scale_data
from state.state import global_state
from _log.log_config import logger
from ui.dialog.manual_grid_input import manual_grid_input


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

            # Extract grid info and proceed, store in state
            global_state.set_grid_info(extract_grid_info(global_state.get_description()))
            global_state.set_channel_status(_build_channel_status(global_state.get_channel_count(), global_state.get_grid_info()))

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

def save_selection(parent, output_file, data, time, description, sampling_frequency, channel_status, file_name, grid_info, channel_labels):
    """
    Saves the channel selection, data, and labels to both a .mat and a .json file.

    :param parent: The parent Qt widget (for dialogs).
    :param output_file: Optional pre-determined output file path. If None, a Save dialog is shown.
    :param data: The EMG data array.
    :param time: The time vector.
    :param description: The channel description strings.
    :param sampling_frequency: The data sampling frequency.
    :param channel_status: List/array of booleans for selection status.
    :param file_name: The name of the original file.
    :param grid_info: Dictionary of grid information.
    :param channel_labels: Dictionary of channel indices to labels.
    """

    if output_file:
        # If output_file is provided, derive both paths from it
        base_path_without_ext, _ = os.path.splitext(output_file)
        mat_file_path = f"{base_path_without_ext}.mat"
        json_file_path = f"{base_path_without_ext}.json"
        base_path = base_path_without_ext # Store base name for message
    else:
        # If no output_file, open save dialog. User selects one path, we derive the other.
        options = QFileDialog.Options()
        # Suggest a default filename based on the original file name if available
        default_filename = file_name if file_name else "selection"
        # Start dialog with .mat filter as a common default for data
        file_dialog_path, selected_filter = QFileDialog.getSaveFileName(
            parent,
            "Save Selection (MAT and JSON)",
            default_filename,
            "MATLAB Files (*.mat);;JSON Files (*.json);;All Files (*)",
            options=options
        )

        if not file_dialog_path:
            return # User cancelled

        # Derive both .mat and .json paths from the user's chosen path
        base_path_without_ext, _ = os.path.splitext(file_dialog_path)
        mat_file_path = f"{base_path_without_ext}.mat"
        json_file_path = f"{base_path_without_ext}.json"
        base_path = base_path_without_ext # Store base name for message


    save_success = True
    messages = []

    # Save .mat file
    try:
        # Ensure we only save if data is available for the .mat file
        if data is not None and time is not None and description is not None:
            data_mat, description_mat = clean_data_and_description_signal(channel_status, data, description)
            save_selection_to_mat(mat_file_path, data_mat, time, description_mat, sampling_frequency, channel_status, file_name)
            messages.append(f"Saved .mat to {Path(mat_file_path).name}")
        else:
             messages.append(".mat file skipped (data not available)")
             logger.warning(f"Warning: .mat save skipped, missing data (data={data is not None}, time={time is not None}, description={description is not None})")

    except Exception as e:
        save_success = False
        messages.append(f"Error saving .mat: {e}")
        logger.error(f"Error saving .mat file {mat_file_path}: {e}")


    # Save .json file
    try:
        # Ensure we have basic info to save JSON
        if channel_status is not None and description is not None and grid_info is not None and channel_labels is not None:
            json_save_success = save_selection_to_json(json_file_path, file_name, grid_info, channel_status, description, channel_labels)
            if json_save_success:
                 messages.append(f"Saved .json to {Path(json_file_path).name}")
            else:
                 save_success = False # save_selection_to_json already logger.ed error
                 messages.append(f"Error saving .json")
        else:
            messages.append(".json file skipped (info not available)")
            logger.warning(f"Warning: .json save skipped, missing info (status={channel_status is not None}, desc={description is not None}, grid={grid_info is not None}, labels={channel_labels is not None})")

    except Exception as e:
        save_success = False
        messages.append(f"Error saving .json: {e}")
        logger.error(f"Error saving .json file {json_file_path}: {e}")


    # Show combined success/failure message
    if save_success:
        QMessageBox.information(
            parent,
            "Save Complete",
            "\n".join(messages), # Join all save messages
            QMessageBox.Ok
        )
    else:
         QMessageBox.warning(
            parent,
            "Save Partially Complete or Failed",
            "Some files may not have been saved correctly:\n" + "\n".join(messages),
            QMessageBox.Ok
         )

def save_selection_to_json(file_path: str,
                           file_name: str,
                           grid_info: dict,
                           channel_status: list,
                           description: np.ndarray,
                           channel_labels: dict) -> bool:
    """
    Saves the selection information (including channel labels) to a JSON file.

    Parameters
    ----------
    file_path : str
        Path where the JSON file should be saved.
    file_name : str
        Name of the original file.
    grid_info : dict
        Dictionary containing info about all extracted grids.
    channel_status : list[bool]
        Boolean list indicating channel selection status.
    description : np.ndarray
        Array of channel description strings (shape: n-channels × 1).
    channel_labels : dict[int, list[dict]]
        Mapping channel index → list of label-dicts
        (each dict contains at least a 'name' key).

    Returns
    -------
    bool
        True on success, False on failure.
    """

    label_names = {
        idx: [lbl["name"] for lbl in lbl_list]
        for idx, lbl_list in (channel_labels or {}).items()
    }

    grids_out = []

    if isinstance(grid_info, dict):
        for grid_key, info in grid_info.items():

            # ––– Sanity-Check –––
            must_have = {"rows", "cols", "ied_mm", "indices",
                         "reference_signals"}
            if not must_have.issubset(info):
                logger.debug("Skipping grid %s: missing keys (%s)",
                             grid_key, must_have - set(info))
                continue

            rows      = info["rows"]
            cols      = info["cols"]
            scale     = info.get("ied_mm")   # may be None
            indices   = info["indices"]
            ref_list  = info["reference_signals"]

            # ---------- Channels ----------
            ch_objects = []
            if isinstance(indices, (list, np.ndarray)):
                for ch_idx in indices:
                    if ch_idx is None:
                        continue  # placeholder in some grids

                    is_selected = bool(channel_status[ch_idx])

                    # description might be numpy bytes / string
                    if (isinstance(description, np.ndarray)
                            and ch_idx < description.shape[0]):
                        ch_descr = description[ch_idx, 0].item()
                    else:
                        ch_descr = f"Channel {ch_idx + 1}"

                    ch_objects.append({
                        "channel_index":   int(ch_idx),
                        "channel_number":  int(ch_idx + 1),
                        "selected":        is_selected,
                        "description":     str(ch_descr),
                        "labels":          label_names.get(ch_idx, [])
                    })

            # ---------- Reference Signals ----------
            ref_objects = []
            for ref in ref_list:
                ref_idx  = ref.get("index")
                ref_name = ref.get("name", f"Ref {ref_idx + 1}")

                if ref_idx is None or ref_idx >= len(channel_status):
                    continue  # inconsistent index, skip

                ref_objects.append({
                    "ref_index":   int(ref_idx),
                    "ref_number":  int(ref_idx + 1),
                    "name":        str(ref_name),
                    "selected":    bool(channel_status[ref_idx]),
                    "labels":      label_names.get(ref_idx, [])
                })

            grids_out.append({
                "grid_key":  grid_key,
                "rows":      rows,
                "columns":   cols,
                "inter_electrode_distance_mm": scale,
                "channels":  ch_objects,
                "reference_signals": ref_objects
            })
    else:
        logger.warning("grid_info is not a dict but %s", type(grid_info))

    all_channels_summary = []
    for i, sel in enumerate(channel_status):
        if isinstance(description, np.ndarray) and i < description.shape[0]:
            ch_descr = description[i, 0].item()
        else:
            ch_descr = f"Channel {i + 1}"

        all_channels_summary.append({
            "channel_index":  i,
            "channel_number": i + 1,
            "selected":       bool(sel),
            "description":    str(ch_descr),
            "labels":         label_names.get(i, [])
        })

    layout_association = {
        fiber.name.lower(): layout.name.lower()
        for fiber, layout in global_state.get_layout().items()
    }

    result_layout_association = {
        "layout_mapping": layout_association,
        "set_by_user": str(global_state.is_fiber_to_layout_user_set())
    }
    result = {
        "filename":               file_name or "unknown",
        "layout":                 result_layout_association,
        "total_channels_summary": all_channels_summary,
        "grids":                  grids_out
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
        return True
    except OSError as exc:
        logger.error("Cannot write JSON %s: %s", file_path, exc)
        return False

def clean_data_and_description_signal(channel_status, data, description):
    if data.ndim != 2:
        raise ValueError("data must be a 2D array")
    if data.shape[1] != len(channel_status):
        raise ValueError("Length of 'channel_status' has to match the number of channels in 'data'")

    data = data[:, channel_status]
    description = description[channel_status, :]

    return data, description

def _build_channel_status(n_channels, grid_info):
    channel_status = [False] * n_channels

    for grid in grid_info.values():
        for ref in grid.get("reference_signals", []):
            idx = ref.get("index")
            if idx is not None and 0 <= idx < n_channels:
                channel_status[idx] = True

    return channel_status
