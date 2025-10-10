from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QIcon
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QSizePolicy, QPushButton
from hdsemg_select._log.log_config import logger
from hdsemg_select.state.enum.layout_mode_enums import LayoutMode, FiberMode
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.icons.custom_icon_enum import CustomIcon
from hdsemg_select.ui.plot.signal_overview_plot import open_signal_plot_dialog
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles


class ElectrodeWidget(QWidget):
    signal_overview_plot_applied = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_orientation = None
        self.parent = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(80, Spacing.MD, Spacing.MD, 80)  # Extra space on left and bottom for fiber arrow
        self.grid_label = QLabel("")

        rotate_button = QPushButton("Rotate View")
        rotate_button.setStyleSheet(Styles.button_primary())
        rotate_button.setToolTip("Rotate the application view to switch between parallel and perpendicular fiber orientations.")
        rotate_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        rotate_button.setIcon(self.style().standardIcon(QPushButton().style().SP_BrowserReload))
        rotate_button.clicked.connect(self._on_rotate_btn_pressed)
        self.layout.addWidget(rotate_button)

        self.grid_layout = QGridLayout()
        self.grid_layout.addWidget(self.grid_label)
        self.layout.addLayout(self.grid_layout)

        # Stretch to make label ~10% and grid ~90%
        self.layout.setStretch(0, 1)
        self.layout.setStretch(1, 9)

        self.grid_shape = (1, 1)
        self.electrode_labels = []

        # Highlight info
        self.fiber_orientation = None
        self.highlight_index = 0  # which row/column is currently highlighted

        open_signal_overview_btn = QPushButton("Open Signal Overview")
        open_signal_overview_btn.setIcon(QIcon(CustomIcon.EXTEND.value))
        open_signal_overview_btn.setStyleSheet(Styles.button_secondary())
        open_signal_overview_btn.setToolTip("Open signal overview window to visualize the selected grid in more detail and examine Action Potentials.")
        open_signal_overview_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        open_signal_overview_btn.clicked.connect(self.open_signal_overview)
        self.layout.addWidget(open_signal_overview_btn)

    def set_grid_shape(self, grid_shape):
        self.grid_shape = grid_shape
        rows, cols = self.grid_shape

        self.grid_label.setText(f"{rows}x{cols} grid")

        # Clear existing labels
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.electrode_labels = []
        font = QFont()
        font.setPointSize(8)
        for r in range(rows):
            row_labels = []
            for c in range(cols):
                lbl = QLabel()
                lbl.setFixedSize(20, 20)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFont(font)
                # Keep them transparent so we can show highlight behind them
                lbl.setStyleSheet(f"background-color: {Colors.BG_PRIMARY}; border: 1px solid {Colors.BORDER_DEFAULT};")
                self.grid_layout.addWidget(lbl, r, c)
                row_labels.append(lbl)
            self.electrode_labels.append(row_labels)

        self.update()

    def label_electrodes(self):
        rows, cols = self.grid_shape
        max_channels = rows * cols
        channel_indices = list(range(1, max_channels + 1))
        logger.debug(channel_indices)

        for i, ch in enumerate(channel_indices):
            r = i // cols  # row-major: integer division gives the row index
            c = i % cols  # modulo gives the column index
            self.electrode_labels[r][c].setText(str(ch))

    def update_all(self, channel_status, channel_indices):
        if not self.electrode_labels:
            return
        for grid_idx, ch_idx in enumerate(channel_indices):
            selected = channel_status[ch_idx]
            self.update_electrode(grid_idx, selected)

    def update_electrode(self, grid_idx, selected):
        if not self.electrode_labels:
            return
        r, c = self.map_channel_to_grid(grid_idx)
        if selected:
            # When selected, we can give a distinct style
            self.electrode_labels[r][c].setStyleSheet(f"background-color: {Colors.GREEN_500}; border: 1px solid {Colors.GREEN_700};")
        else:
            self.electrode_labels[r][c].setStyleSheet(f"background-color: {Colors.BG_PRIMARY}; border: 1px solid {Colors.BORDER_DEFAULT};")

    def map_channel_to_grid(self, grid_idx):
        # Column major mapping
        rows, cols = self.grid_shape
        r = grid_idx % rows
        c = grid_idx // rows
        return r, c

    def set_orientation_highlight(self, orientation, current_page=0):
        """
        orientation: "parallel" or "perpendicular" or None
        current_page: the highlighted row (if parallel) or column (if perpendicular)
        """
        if not isinstance(orientation, FiberMode):
            raise ValueError(f"Orientation must be a FiberMode enum value. Got: {type(orientation)}")

        self.fiber_orientation = orientation
        self.grid_orientation = global_state.get_layout_for_fiber(self.fiber_orientation)
        self.highlight_index = current_page
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.electrode_labels:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rows, cols = self.grid_shape

        # Pick out the first & last electrode label for overall bounds
        first_lbl = self.electrode_labels[0][0]
        last_lbl = self.electrode_labels[rows - 1][cols - 1]
        first_rect = first_lbl.geometry()
        last_rect = last_lbl.geometry()

        # Semi-transparent yellow for highlighting current row/column
        highlight_color = QColor(255, 255, 0, 90)

        # 1) Highlight a full ROW
        if self.grid_orientation == LayoutMode.ROWS and 0 <= self.highlight_index < rows:
            r = self.highlight_index
            a = self.electrode_labels[r][0].geometry()
            b = self.electrode_labels[r][cols - 1].geometry()
            span = QRect(
                a.left(),
                a.top(),
                b.right() - a.left(),
                a.height()
            )
            painter.fillRect(span, highlight_color)

        # 2) Highlight a full COLUMN
        elif self.grid_orientation == LayoutMode.COLUMNS and 0 <= self.highlight_index < cols:
            c = self.highlight_index
            a = self.electrode_labels[0][c].geometry()
            b = self.electrode_labels[rows - 1][c].geometry()
            span = QRect(
                a.left(),
                a.top(),
                a.width(),
                b.bottom() - a.top()
            )
            painter.fillRect(span, highlight_color)

        # 3) Draw the rounded‐rect outline around the entire grid
        padding = 10
        outline = QRect(
            first_rect.left() - padding,
            first_rect.top() - padding,
            (last_rect.right() - first_rect.left()) + 2 * padding,
            (last_rect.bottom() - first_rect.top()) + 2 * padding
        )

        # Use design system colors
        border_color = QColor(Colors.BORDER_DEFAULT.lstrip('#'))
        pen = QPen(border_color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(outline, 15, 15)

        # 4) Draw the little tab under the sticker
        tab_w = outline.width() * 0.3
        tab_h = 30
        tab_x = outline.left() + (outline.width() - tab_w) / 2
        tab_y = outline.bottom()
        tab_rect = QRect(int(tab_x), int(tab_y), int(tab_w), tab_h)
        painter.drawRoundedRect(tab_rect, 10, 10)

        # 5) Draw the muscle fiber direction indicator
        if self.grid_orientation is not None:
            arrow_color = QColor(Colors.BLUE_600.lstrip('#'))
            pen_arrow = QPen(arrow_color, 3)
            painter.setPen(pen_arrow)

            if self.grid_orientation == LayoutMode.ROWS:
                # Horizontal arrow BELOW the grid for ROWS (muscle fibers run horizontally)
                arrow_start_y = tab_rect.bottom() + 15
                arrow_y = arrow_start_y
                arrow_start_x = outline.left() + 20
                arrow_end_x = outline.right() - 20

                # Draw horizontal line
                painter.drawLine(int(arrow_start_x), int(arrow_y), int(arrow_end_x), int(arrow_y))
                # Draw arrowheads at both ends
                painter.drawLine(int(arrow_start_x), int(arrow_y), int(arrow_start_x + 10), int(arrow_y - 5))
                painter.drawLine(int(arrow_start_x), int(arrow_y), int(arrow_start_x + 10), int(arrow_y + 5))
                painter.drawLine(int(arrow_end_x), int(arrow_y), int(arrow_end_x - 10), int(arrow_y - 5))
                painter.drawLine(int(arrow_end_x), int(arrow_y), int(arrow_end_x - 10), int(arrow_y + 5))

                # Label centered below arrow
                painter.setFont(QFont("Arial", 10, QFont.Bold))
                label = "Muscle Fiber Direction"
                label_width = painter.fontMetrics().horizontalAdvance(label)
                label_x = outline.left() + (outline.width() - label_width) / 2
                label_y = arrow_start_y + 35
                painter.drawText(int(label_x), int(label_y), label)

            elif self.grid_orientation == LayoutMode.COLUMNS:
                # Vertical arrow LEFT of the grid for COLUMNS (muscle fibers run vertically)
                arrow_x = outline.left() - 40
                arrow_start_y = outline.top() + 20
                arrow_end_y = outline.bottom() - 20

                # Draw vertical line
                painter.drawLine(int(arrow_x), int(arrow_start_y), int(arrow_x), int(arrow_end_y))
                # Draw arrowheads at both ends
                painter.drawLine(int(arrow_x), int(arrow_start_y), int(arrow_x - 5), int(arrow_start_y + 10))
                painter.drawLine(int(arrow_x), int(arrow_start_y), int(arrow_x + 5), int(arrow_start_y + 10))
                painter.drawLine(int(arrow_x), int(arrow_end_y), int(arrow_x - 5), int(arrow_end_y - 10))
                painter.drawLine(int(arrow_x), int(arrow_end_y), int(arrow_x + 5), int(arrow_end_y - 10))

                # Label rotated and positioned to the left of arrow
                painter.setFont(QFont("Arial", 10, QFont.Bold))
                painter.save()
                painter.translate(arrow_x - 15, (outline.top() + outline.bottom()) / 2)
                painter.rotate(-90)
                painter.drawText(-60, 0, "Muscle Fiber Direction")
                painter.restore()

    def open_signal_overview(self):
        """Open the Signal Overview Plot"""
        logger.info("Open Signal Overview Plot")
        dlg = open_signal_plot_dialog(self.parent.grid_setup_handler, self)
        dlg.orientation_applied.connect(self.signal_overview_plot_applied) # when the plot fires, immediatley re-emit it

    def _on_rotate_btn_pressed(self):
        """
        Rotate the view to switch between parallel and perpendicular fiber orientations.
        This will toggle the orientation and update the highlight accordingly.
        """
        current_orientation = self.fiber_orientation
        current_orientation = FiberMode.PARALLEL if current_orientation == FiberMode.PERPENDICULAR else FiberMode.PERPENDICULAR
        selected_grid = self.parent.grid_setup_handler.get_selected_grid()
        logger.debug(f"Rotating view from {self.fiber_orientation.name} to {current_orientation.name} orientation")

        self.parent.apply_grid_selection(selected_grid, current_orientation)

