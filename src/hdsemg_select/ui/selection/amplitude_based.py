from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QCheckBox
from PyQt5.QtGui import QIntValidator
from hdsemg_select._log.log_config import logger
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel


class AutomaticAmplitudeSelection:
    def __init__(self, parent):
        self.parent = parent
        self.lower_threshold = 0  # Default lower threshold (in μV)
        self.upper_threshold = 0  # Default upper threshold (in μV)

    def auto_compute_thresholds(self):
        """
        Compute the average of the maximum and minimum amplitudes across all grid channels
        and set thresholds at 80% of these averages.
        """
        data = global_state.get_emg_file().data
        scaled_data = global_state.get_scaled_data()
        if data is None or not self.parent.grid_setup_handler.current_grid_indices:
            return 0, 0
        max_values = []
        min_values = []
        for i in self.parent.grid_setup_handler.current_grid_indices:
            channel_data = scaled_data[:, i]
            max_values.append(channel_data.max())
            min_values.append(channel_data.min())
        avg_max = sum(max_values) / len(max_values)
        avg_min = sum(min_values) / len(min_values)
        lower = int(avg_min * 0.8)
        upper = int(avg_max * 0.8)
        logger.info(f"Computed thresholds: lower={lower}μV, upper={upper}μV")
        return lower, upper

    def open_settings_dialog(self):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Automatic Selection Settings")

        layout = QVBoxLayout()

        # Checkbox to trigger automatic computation
        auto_checkbox = QCheckBox("Automatically compute thresholds")
        layout.addWidget(auto_checkbox)

        # Label to clarify the scale
        info_label = QLabel("Provide thresholds in μV to set the amplitude range for automatic selection.")
        layout.addWidget(info_label)

        # Lower threshold layout with unit label
        lower_label = QLabel("Lower Threshold:")
        layout.addWidget(lower_label)

        lower_layout = QHBoxLayout()
        lower_input = QLineEdit()
        lower_input.setValidator(QIntValidator(0, 1000000))
        lower_input.setText(str(self.lower_threshold))
        lower_layout.addWidget(lower_input)
        lower_unit = QLabel("μV")
        lower_layout.addWidget(lower_unit)
        layout.addLayout(lower_layout)

        # Upper threshold layout with unit label
        upper_label = QLabel("Upper Threshold:")
        layout.addWidget(upper_label)

        upper_layout = QHBoxLayout()
        upper_input = QLineEdit()
        upper_input.setValidator(QIntValidator(0, 1000000))
        upper_input.setText(str(self.upper_threshold))
        upper_layout.addWidget(upper_input)
        upper_unit = QLabel("μV")
        upper_layout.addWidget(upper_unit)
        layout.addLayout(upper_layout)

        # When checkbox is checked, compute and update thresholds automatically.
        def on_checkbox_state_changed(state):
            if auto_checkbox.isChecked():
                lower, upper = self.auto_compute_thresholds()
                lower_input.setText(str(lower))
                upper_input.setText(str(upper))
        auto_checkbox.stateChanged.connect(on_checkbox_state_changed)

        button_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(lambda: self.save_thresholds(dialog, lower_input, upper_input))
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        return dialog.exec_()

    def save_thresholds(self, dialog, lower_input, upper_input):
        try:
            self.lower_threshold = int(lower_input.text())
            self.upper_threshold = int(upper_input.text())

            if self.lower_threshold >= self.upper_threshold:
                QMessageBox.warning(self.parent, "Invalid Thresholds",
                                    "Lower threshold must be less than upper threshold.")
                return

            dialog.accept()
        except ValueError:
            QMessageBox.warning(self.parent, "Invalid Input", "Please enter valid integer thresholds.")

    def is_threshold_valid(self):
        """
        Check if the thresholds are valid (lower < upper).
        """
        if self.lower_threshold >= self.upper_threshold:
            return False
        return True

    def perform_selection(self):
        """
        Perform automatic selection based on amplitude thresholds for each channel.
        If the maximum amplitude of a channel (in μV) is between lower_threshold and upper_threshold,
        that channel is selected.
        """
        data = global_state.get_emg_file().data
        scaled_data = global_state.get_scaled_data()
        if data is None:
            QMessageBox.warning(self.parent, "No Data", "Please load a file first.")
            return

        selected_count = 0
        deselected_count = 0
        channel_status = global_state.get_channel_status()

        for i in self.parent.grid_setup_handler.current_grid_indices:
            channel_data = scaled_data[:, i]
            max_amplitude = channel_data.max()  # in μV
            min_amplitude = channel_data.min()

            if self.upper_threshold <= max_amplitude and self.lower_threshold >= min_amplitude:
                channel_status[i] = True
                selected_count += 1
            else:
                channel_status[i] = False
                deselected_count += 1
                # Also display the Bad Channel label
                # current labels for that channel
                labels = global_state.get_channel_labels(i).copy()

                # add the new label only if it is not present yet
                if BaseChannelLabel.BAD_CHANNEL.value not in labels:
                    labels.append(BaseChannelLabel.BAD_CHANNEL.value)
                    global_state.update_channel_labels(i, labels)

        # Update the global state with the new channel status
        global_state.set_channel_status(channel_status)

        self.parent.display_page()
        QMessageBox.information(
            self.parent, f"Automatic Selection of grid {self.parent.grid_setup_handler.selected_grid} complete",
            f"{selected_count} channels selected, {deselected_count} channels deselected."
        )
