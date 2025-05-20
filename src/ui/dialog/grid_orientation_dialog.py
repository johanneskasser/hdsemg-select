from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton

from state.enum.layout_mode_enums import FiberMode
from state.state import global_state


class GridOrientationDialog(QDialog):
    def __init__(self, parent, apply_callback):
        super().__init__(parent)
        self.setWindowTitle("Select Grid and Orientation")
        self.apply_callback = apply_callback

        grid_info = global_state.get_grid_info()
        if not grid_info:
            return

        layout = QVBoxLayout(self)

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        self.grid_combo = QComboBox()
        for grid_key in grid_info.keys():
            self.grid_combo.addItem(grid_key)

        currently_selected_grid = parent.grid_setup_handler.get_selected_grid()
        if currently_selected_grid:
            self.grid_combo.setCurrentIndex(self.grid_combo.findText(currently_selected_grid))
        else:
            self.grid_combo.setCurrentIndex(0)

        layout.addWidget(self.grid_combo)

        orientation_label = QLabel("Select Orientation:")
        layout.addWidget(orientation_label)

        self.orientation_combo = QComboBox()
        # Assuming FiberMode is imported
        self.orientation_combo.addItem("Parallel to fibers", FiberMode.PARALLEL)
        self.orientation_combo.addItem("Perpendicular to fibers", FiberMode.PERPENDICULAR)

        currently_selected_orientation = parent.grid_setup_handler.get_orientation()
        if currently_selected_orientation:
            self.orientation_combo.setCurrentIndex(self.orientation_combo.findData(currently_selected_orientation))
        else:
            self.orientation_combo.setCurrentIndex(0)

        layout.addWidget(self.orientation_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.on_ok)
        layout.addWidget(ok_button)

    def on_ok(self):
        selected_grid = self.grid_combo.currentText()
        orientation = self.orientation_combo.currentData()
        self.apply_callback(selected_grid, orientation, self)


