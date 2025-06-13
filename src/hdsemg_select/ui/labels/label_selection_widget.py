# ui/label_selection_widget.py
from functools import partial

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QCheckBox, QPushButton,
                             QScrollArea, QHBoxLayout, QMenu)


class LabelSelectionWidget(QWidget):
    """
    A widget for selecting multiple labels from a list of checkboxes.
    This widget is intended to be used within a QMenu or a custom dropdown.
    """
    labels_applied = pyqtSignal(list)  # Emits the list of selected label objects

    def __init__(self, available_labels: list, current_labels: list, parent=None):
        super().__init__(parent)
        self.available_labels = available_labels
        # Work with copies to manage state within the widget instance
        self.interim_selected_labels = [lbl for lbl in current_labels if
                                        any(avail_lbl["id"] == lbl["id"] for avail_lbl in available_labels)]

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setMaximumHeight(250)  # Prevent excessively tall dropdown

        self.checkbox_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_widget)
        self.checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox_layout.setSpacing(3)

        self.checkboxes = {}

        for label_obj in self.available_labels:
            label_id = label_obj.get("id")
            label_name = label_obj.get("name", "")
            checkbox = QCheckBox(label_name)
            # Ensure label_id is compared correctly
            checkbox.setChecked(any(item.get("id") == label_id for item in self.interim_selected_labels))
            checkbox.stateChanged.connect(partial(self._update_interim_selected_labels, label_obj))
            self.checkbox_layout.addWidget(checkbox)
            self.checkboxes[label_id] = checkbox

        self.checkbox_layout.addStretch()  # Pushes checkboxes to the top
        self.scroll_area.setWidget(self.checkbox_widget)
        self.main_layout.addWidget(self.scroll_area, 1)  # Scroll area takes available space

        # --- Buttons ---
        self.button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._apply_changes)

        self.button_layout.addStretch()
        self.button_layout.addWidget(self.apply_button)
        self.main_layout.addLayout(self.button_layout)

        # Adjust size hint for better initial display in menu
        self.checkbox_widget.adjustSize()
        min_width = max(200, self.checkbox_widget.width() + 20)
        if self.scroll_area.verticalScrollBar().isVisible():
            min_width += self.scroll_area.verticalScrollBar().sizeHint().width()
        self.setMinimumWidth(min_width)
        self.adjustSize()

    def _update_interim_selected_labels(self, label_obj: dict, state: int):
        label_id = label_obj.get("id")
        if state == Qt.Checked:
            # Add if not already present (by ID)
            if not any(item.get("id") == label_id for item in self.interim_selected_labels):
                self.interim_selected_labels.append(label_obj)
        else:
            # Remove if present (by ID)
            self.interim_selected_labels = [l for l in self.interim_selected_labels if l.get("id") != label_id]

    def _apply_changes(self):
        # Ensure only unique labels based on ID are emitted
        unique_labels_dict = {label["id"]: label for label in self.interim_selected_labels}
        sorted_labels = sorted(unique_labels_dict.values(), key=lambda x: str(x.get("id")))
        self.labels_applied.emit(sorted_labels)

        # Close the containing QMenu
        parent_widget = self.parentWidget()
        while parent_widget:
            if isinstance(parent_widget, QMenu):
                parent_widget.hide()
                break
            parent_widget = parent_widget.parentWidget()

    def get_selected_labels(self) -> list:
        """Returns the list of labels currently selected in the checkboxes."""
        unique_labels_dict = {label["id"]: label for label in self.interim_selected_labels}
        return sorted(unique_labels_dict.values(), key=lambda x: str(x.get("id")))
