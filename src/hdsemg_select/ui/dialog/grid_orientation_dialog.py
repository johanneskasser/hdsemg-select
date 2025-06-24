from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout

from hdsemg_select.state.enum.layout_mode_enums import FiberMode, LayoutMode
from hdsemg_select.state.state import global_state


class GridOrientationDialog(QDialog):
    def __init__(self, parent, apply_callback):
        super().__init__(parent)
        self.setWindowTitle("Select Grid and Orientation")
        self.apply_callback = apply_callback

        grids = global_state.get_emg_file().grids
        if not grids:
            return

        layout = QVBoxLayout(self)

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        self.grid_combo = QComboBox()
        for grid in grids:
            self.grid_combo.addItem(grid.grid_key)

        currently_selected_grid = parent.grid_setup_handler.get_selected_grid()
        if currently_selected_grid:
            self.grid_combo.setCurrentIndex(self.grid_combo.findText(currently_selected_grid))
        else:
            self.grid_combo.setCurrentIndex(0)

        layout.addWidget(self.grid_combo)

        orientation_label = QLabel("Orientation (parallel to fibers):")
        tooltip_text = "Are the HD-sEMG matrix n rows or m columns aligned in <b>parallel</b> with the muscle fibers?"
        orientation_label.setToolTip(tooltip_text)
        info_icon = QLabel()
        info_icon.setPixmap(self.style().standardIcon(self.style().SP_MessageBoxInformation).pixmap(16, 16))
        info_icon.setToolTip(tooltip_text)
        orientation_label_layout = QHBoxLayout()
        orientation_label_layout.addWidget(orientation_label)
        orientation_label_layout.addWidget(info_icon)
        orientation_label_layout.addStretch(1)
        layout.addLayout(orientation_label_layout)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Rows parallel to fibers", LayoutMode.ROWS)
        self.orientation_combo.addItem("Columns parallel to fibers", LayoutMode.COLUMNS)

        currently_selected_layout = global_state.get_layout_for_fiber(FiberMode.PARALLEL)
        if currently_selected_layout:
            self.orientation_combo.setCurrentIndex(self.orientation_combo.findData(currently_selected_layout))
        else:
            self.orientation_combo.setCurrentIndex(LayoutMode.COLUMNS) # default to columns if not set

        layout.addWidget(self.orientation_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.on_ok)
        layout.addWidget(ok_button)

    def on_ok(self):
        selected_grid = self.grid_combo.currentText()
        selected_layout_mode = self.orientation_combo.currentData()
        selected_fiber_mode = FiberMode.PARALLEL
        if global_state.get_layout_for_fiber(selected_fiber_mode) == selected_layout_mode:
            self.apply_callback(selected_grid, selected_fiber_mode, self, orientation_changed=False)
        else:
            global_state.set_fiber_layout(selected_fiber_mode, selected_layout_mode)
            self.apply_callback(selected_grid, selected_fiber_mode, self, orientation_changed=True)


