from PyQt5.QtWidgets import QFileDialog, QMessageBox
from pathlib import Path
from hdsemg_shared import save_selection_to_mat, save_selection_to_json


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