from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtGui import QIntValidator

class AutomaticSelection:
    def __init__(self, parent):
        self.parent = parent
        self.lower_threshold = 0  # Default lower threshold
        self.upper_threshold = 0  # Default upper threshold

    def open_settings_dialog(self):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Automatic Selection Settings")

        layout = QVBoxLayout()

        lower_label = QLabel("Lower Threshold:")
        layout.addWidget(lower_label)

        lower_input = QLineEdit()
        lower_input.setValidator(QIntValidator(0, 1000000))
        lower_input.setText(str(self.lower_threshold))
        layout.addWidget(lower_input)

        upper_label = QLabel("Upper Threshold:")
        layout.addWidget(upper_label)

        upper_input = QLineEdit()
        upper_input.setValidator(QIntValidator(0, 1000000))
        upper_input.setText(str(self.upper_threshold))
        layout.addWidget(upper_input)

        button_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(lambda: self.save_thresholds(dialog, lower_input, upper_input))
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def save_thresholds(self, dialog, lower_input, upper_input):
        try:
            self.lower_threshold = int(lower_input.text())
            self.upper_threshold = int(upper_input.text())

            if self.lower_threshold >= self.upper_threshold:
                QMessageBox.warning(self.parent, "Invalid Thresholds", "Lower threshold must be less than upper threshold.")
                return

            dialog.accept()
        except ValueError:
            QMessageBox.warning(self.parent, "Invalid Input", "Please enter valid integer thresholds.")

    def perform_selection(self):
        """
        Perform automatic selection based on amplitude thresholds for specified indices.

        Parameters:
            indices (list or None): List of indices to apply the selection to. If None, applies to all indices.
        """
        if self.parent.data is None:
            QMessageBox.warning(self.parent, "No Data", "Please load a file first.")
            return

        selected_count = 0
        deselected_count = 0

        for i in self.parent.current_grid_indices:
            channel_data = self.parent.scaled_data[:, i]
            max_amplitude = channel_data.max()

            if self.lower_threshold <= max_amplitude <= self.upper_threshold:
                self.parent.channel_status[i] = True
                selected_count += 1
            else:
                self.parent.channel_status[i] = False
                deselected_count += 1

        self.parent.display_page()
        QMessageBox.information(
            self.parent, f"Automatic Selection of grid {self.parent.selected_grid} complete",
            f"{selected_count} channels selected, {deselected_count} channels deselected."
        )

