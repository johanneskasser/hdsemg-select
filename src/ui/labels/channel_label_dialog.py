# ui/channel_label_dialog.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox, QCheckBox

from state.state import global_state
from config.config_manager import config


class ChannelLabelDialog(QDialog):
    """
        A dialog for selecting labels for a specific channel.

        Attributes:
            channel_idx (int): Index of the channel for which labels are being selected.
            current_labels (list): List of currently selected labels.
            selected_labels (list): List of labels selected by the user.
            available_labels (list): List of all available labels.
            checkboxes (dict): Dictionary storing checkboxes for each label.
        """

    def __init__(self, channel_idx: int, current_labels: list, parent=None):
        super().__init__(parent)
        self.channel_idx = channel_idx
        self.current_labels = current_labels
        self.selected_labels = list(current_labels) # Work on a copy

        self.setWindowTitle(f"Labels for Channel {channel_idx + 1}")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label_info = QLabel(f"Select labels for Channel {channel_idx + 1}:")
        self.layout.addWidget(self.label_info)

        self.labels_layout = QVBoxLayout() # Use a layout for checkboxes
        self.layout.addLayout(self.labels_layout)

        self.available_labels = config.get_available_channel_labels()
        self.checkboxes = {} # Store checkboxes to access their state

        for label in self.available_labels:
            checkbox = QCheckBox(label.get("name", ""))
            checkbox.setChecked(any(item.get("id") == label.get("id") for item in self.selected_labels))
            checkbox.stateChanged.connect(partial(self._update_selected_labels, label))
            self.labels_layout.addWidget(checkbox)
            self.checkboxes[label.get("id")] = checkbox # Store reference


        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _update_selected_labels(self, label: str, state: int):
        if state == Qt.Checked:
            if label not in self.selected_labels:
                self.selected_labels.append(label)
        else:
            if label in self.selected_labels:
                self.selected_labels.remove(label)

    def get_selected_labels(self) -> list:
        """Returns the list of labels selected by the user."""
        unique_labels = {}
        for label in self.selected_labels:
            unique_labels[label["id"]] = label
        return sorted(unique_labels.values(), key=lambda x: str(x["id"]))

# Need functools.partial and Qt for the checkbox connection
from functools import partial
from PyQt5.QtCore import Qt, pyqtSignal
