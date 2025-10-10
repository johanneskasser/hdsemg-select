from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QCheckBox, QGroupBox, QFormLayout
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtCore import Qt
from hdsemg_select._log.log_config import logger
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles


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
        dialog.setWindowTitle("Automatic Channel Selection")
        dialog.setMinimumWidth(500)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(Spacing.LG)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # Header with description
        header_label = QLabel("Automatic Channel Selection")
        header_label.setStyleSheet(Styles.label_heading(size="lg"))
        main_layout.addWidget(header_label)

        description_label = QLabel(
            "Automatically select channels based on amplitude thresholds. "
            "Channels with signal amplitudes outside the specified range will be deselected and marked as bad channels."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet(Styles.label_secondary())
        main_layout.addWidget(description_label)

        # Auto-compute section
        auto_group = QGroupBox("Quick Setup")
        auto_group.setStyleSheet(Styles.groupbox())
        auto_layout = QVBoxLayout()
        auto_layout.setSpacing(Spacing.SM)

        auto_checkbox = QCheckBox("Automatically compute recommended thresholds")
        auto_checkbox.setToolTip("Calculate thresholds based on 80% of average min/max amplitudes across all channels in the current grid")
        auto_layout.addWidget(auto_checkbox)

        auto_info = QLabel("This will analyze all channels in the current grid and suggest optimal threshold values.")
        auto_info.setStyleSheet(Styles.label_secondary())
        auto_info.setWordWrap(True)
        auto_layout.addWidget(auto_info)

        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)

        # Threshold settings section
        threshold_group = QGroupBox("Threshold Settings")
        threshold_group.setStyleSheet(Styles.groupbox())
        threshold_layout = QFormLayout()
        threshold_layout.setSpacing(Spacing.MD)
        threshold_layout.setLabelAlignment(Qt.AlignRight)

        # Lower threshold
        lower_container = QHBoxLayout()
        lower_input = QLineEdit()
        lower_input.setStyleSheet(Styles.input_field())
        lower_input.setValidator(QIntValidator(-1000000, 1000000))
        lower_input.setText(str(self.lower_threshold))
        lower_input.setPlaceholderText("Minimum amplitude")
        lower_container.addWidget(lower_input)
        lower_unit = QLabel("μV")
        lower_unit.setStyleSheet(Styles.label_secondary())
        lower_container.addWidget(lower_unit)
        threshold_layout.addRow("Lower Threshold:", lower_container)

        # Upper threshold
        upper_container = QHBoxLayout()
        upper_input = QLineEdit()
        upper_input.setStyleSheet(Styles.input_field())
        upper_input.setValidator(QIntValidator(-1000000, 1000000))
        upper_input.setText(str(self.upper_threshold))
        upper_input.setPlaceholderText("Maximum amplitude")
        upper_container.addWidget(upper_input)
        upper_unit = QLabel("μV")
        upper_unit.setStyleSheet(Styles.label_secondary())
        upper_container.addWidget(upper_unit)
        threshold_layout.addRow("Upper Threshold:", upper_container)

        threshold_info = QLabel("Channels with peak amplitudes between these values will be selected. Others will be marked as bad channels.")
        threshold_info.setStyleSheet(Styles.label_secondary())
        threshold_info.setWordWrap(True)
        threshold_layout.addRow("", threshold_info)

        threshold_group.setLayout(threshold_layout)
        main_layout.addWidget(threshold_group)

        # Status label for feedback
        status_label = QLabel("")
        status_label.setStyleSheet(f"""
            QLabel {{
                padding: {Spacing.SM}px;
                border-radius: {BorderRadius.MD};
                background-color: {Colors.BLUE_50};
                color: {Colors.BLUE_900};
            }}
        """)
        status_label.setWordWrap(True)
        status_label.setVisible(False)
        main_layout.addWidget(status_label)

        # When checkbox is checked, compute and update thresholds automatically
        def on_checkbox_state_changed(state):
            if auto_checkbox.isChecked():
                lower, upper = self.auto_compute_thresholds()
                if lower == 0 and upper == 0:
                    status_label.setText("⚠ Unable to compute thresholds. Please ensure data is loaded and a grid is selected.")
                    status_label.setStyleSheet(f"""
                        QLabel {{
                            padding: {Spacing.SM}px;
                            border-radius: {BorderRadius.MD};
                            background-color: {Colors.YELLOW_50};
                            color: {Colors.YELLOW_600};
                        }}
                    """)
                    status_label.setVisible(True)
                else:
                    lower_input.setText(str(lower))
                    upper_input.setText(str(upper))
                    status_label.setText(f"✓ Recommended thresholds computed: {lower} μV to {upper} μV")
                    status_label.setStyleSheet(f"""
                        QLabel {{
                            padding: {Spacing.SM}px;
                            border-radius: {BorderRadius.MD};
                            background-color: {Colors.GREEN_50};
                            color: {Colors.GREEN_800};
                        }}
                    """)
                    status_label.setVisible(True)
            else:
                status_label.setVisible(False)

        auto_checkbox.stateChanged.connect(on_checkbox_state_changed)

        # Validate inputs on change
        def validate_inputs():
            try:
                lower = int(lower_input.text()) if lower_input.text() else 0
                upper = int(upper_input.text()) if upper_input.text() else 0

                if lower >= upper:
                    status_label.setText("⚠ Lower threshold must be less than upper threshold")
                    status_label.setStyleSheet(f"""
                        QLabel {{
                            padding: {Spacing.SM}px;
                            border-radius: {BorderRadius.MD};
                            background-color: {Colors.RED_50};
                            color: {Colors.RED_700};
                        }}
                    """)
                    status_label.setVisible(True)
                    apply_button.setEnabled(False)
                else:
                    if not auto_checkbox.isChecked():
                        status_label.setVisible(False)
                    apply_button.setEnabled(True)
            except ValueError:
                apply_button.setEnabled(False)

        lower_input.textChanged.connect(validate_inputs)
        upper_input.textChanged.connect(validate_inputs)

        main_layout.addStretch()

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(Spacing.SM)

        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet(Styles.button_secondary())
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        button_layout.addStretch()

        # Apply and Run button
        apply_button = QPushButton("Apply && Run Selection")
        apply_button.setStyleSheet(Styles.button_primary())
        apply_button.setToolTip("Save thresholds and immediately perform automatic channel selection")
        apply_button.clicked.connect(lambda: self.apply_and_run(dialog, lower_input, upper_input))
        button_layout.addWidget(apply_button)

        main_layout.addLayout(button_layout)

        dialog.setLayout(main_layout)

        # Initial validation
        validate_inputs()

        return dialog.exec_()

    def apply_and_run(self, dialog, lower_input, upper_input):
        """Save thresholds and immediately run the automatic selection."""
        try:
            self.lower_threshold = int(lower_input.text())
            self.upper_threshold = int(upper_input.text())

            if self.lower_threshold >= self.upper_threshold:
                QMessageBox.warning(self.parent, "Invalid Thresholds",
                                    "Lower threshold must be less than upper threshold.")
                return

            dialog.accept()
            # Immediately perform the selection
            self.perform_selection()

        except ValueError:
            QMessageBox.warning(self.parent, "Invalid Input", "Please enter valid integer thresholds.")

    def save_thresholds(self, dialog, lower_input, upper_input):
        """Save thresholds without running selection (legacy method for compatibility)."""
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
