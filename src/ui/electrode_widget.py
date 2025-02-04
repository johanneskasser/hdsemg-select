from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QSizePolicy
from log.log_config import logger


class ElectrodeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.grid_label = QLabel("")

        self.grid_layout = QGridLayout()
        self.grid_layout.addWidget(self.grid_label)
        self.layout.addLayout(self.grid_layout)

        # Stretch to make label ~10% and grid ~90%
        self.layout.setStretch(0, 1)
        self.layout.setStretch(1, 9)

        self.grid_shape = (1, 1)
        self.electrode_labels = []

        # Highlight info
        self.highlight_orientation = None  # "parallel" or "perpendicular" or None
        self.highlight_index = 0  # which row/column is currently highlighted

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
                lbl.setStyleSheet("background-color: white; border: 1px solid gray;")
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
            self.electrode_labels[r][c].setStyleSheet("background-color: green; border: 1px solid black;")
        else:
            self.electrode_labels[r][c].setStyleSheet("background-color: white; border: 1px solid gray;")

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
        self.highlight_orientation = orientation
        self.highlight_index = current_page
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rows, cols = self.grid_shape
        label_width = 20
        label_height = 20
        spacing_x = self.grid_layout.horizontalSpacing() or 0
        spacing_y = self.grid_layout.verticalSpacing() or 0

        # Calculate total width/height of the electrode grid
        total_width = cols * (label_width + spacing_x) - spacing_x
        total_height = rows * (label_height + spacing_y) - spacing_y

        grid_layout_pos = self.grid_layout.geometry().topLeft()
        offset_x = grid_layout_pos.x()
        offset_y = grid_layout_pos.y()

        padding = 10
        rect = QRect(offset_x - padding, offset_y - padding,
                     total_width + 2 * padding, total_height + 2 * padding)

        # Draw highlight behind the row or column before drawing the outline
        yellow = QColor("yellow")
        yellow.setAlpha(90)
        if self.highlight_orientation == "perpendicular":
            # Highlight a specific row
            if 0 <= self.highlight_index < rows:
                highlight_y = offset_y + self.highlight_index * (label_height + spacing_y)
                highlight_rect = QRect(offset_x, highlight_y, total_width, label_height + 3)
                painter.fillRect(highlight_rect, yellow)

        elif self.highlight_orientation == "parallel":
            # Highlight a specific column
            if 0 <= self.highlight_index < cols:
                highlight_x = offset_x + self.highlight_index * (label_width + spacing_x)
                highlight_rect = QRect(highlight_x, offset_y, label_width + 5, total_height)
                painter.fillRect(highlight_rect, yellow)

        # Now draw the sticker outline
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 15, 15)

        # Draw the tab at the bottom
        tab_width = total_width * 0.3
        tab_height = 30
        tab_x = rect.left() + (rect.width() - tab_width) / 2
        tab_y = rect.bottom()
        tab_rect = QRect(int(tab_x), int(tab_y), int(tab_width), int(tab_height))
        painter.drawRoundedRect(tab_rect, 10, 10)

        # Draw the muscle fiber direction arrow
        arrow_x = rect.left() - 40
        pen_arrow = QPen(Qt.black, 3)
        painter.setPen(pen_arrow)
        # vertical line
        painter.drawLine(arrow_x, rect.top(), arrow_x, rect.bottom())
        # arrow head at the top
        painter.drawLine(arrow_x, rect.top(), arrow_x - 5, rect.top() + 10)
        painter.drawLine(arrow_x, rect.top(), arrow_x + 5, rect.top() + 10)

        # Add text "Muscle Fiber"
        painter.setPen(Qt.black)
        painter.setFont(QFont("Arial", 10))
        painter.save()
        painter.translate(arrow_x - 10, (rect.top() + rect.bottom()) / 2)
        painter.rotate(-90)
        painter.drawText(-50, 0, "Muscle Fiber")
        painter.restore()
