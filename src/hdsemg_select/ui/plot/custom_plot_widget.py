import numpy as np
from PyQt5.QtCore import QRect, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy

from hdsemg_select._log.log_config import logger


class CustomPlotWidget(QWidget):
    """
    Custom lightweight plotting widget using native PyQt5 drawing.
    Replaces matplotlib to improve performance and reduce memory usage.
    """
    clicked = pyqtSignal(QPoint)  # Emitted when plot area is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Plot data (supports multiple traces)
        self.traces = []  # List of {'x': x_data, 'y': y_data, 'color': color, 'style': style, 'width': width, 'label': label}
        self.x_data = None
        self.y_data = None
        self.x_ref_data = None
        self.y_ref_data = None

        # Plot settings
        self.title = ""
        self.x_label = ""
        self.y_label = ""
        self.line_color = QColor(0, 0, 255)  # Blue
        self.ref_line_color = QColor(0, 0, 0)  # Black
        self.background_color = QColor(255, 255, 255)  # White
        self.grid_color = QColor(220, 220, 220)  # Light gray
        self.text_color = QColor(0, 0, 0)  # Black
        self.line_width = 1
        self.ref_line_width = 1
        self.ref_line_style = Qt.DashLine
        self.show_grid = False
        self.show_axes = True

        # Plot margins
        self.margin_left = 50
        self.margin_right = 10
        self.margin_top = 30
        self.margin_bottom = 40

        # Axis limits
        self.x_min = None
        self.x_max = None
        self.y_min = None
        self.y_max = None

        # Auto-scaling
        self.auto_scale_x = True
        self.auto_scale_y = True

        # Font settings
        self.title_font = QFont("Arial", 10, QFont.Bold)
        self.label_font = QFont("Arial", 8)
        self.tick_font = QFont("Arial", 7)

    def set_data(self, x_data, y_data):
        """Set the main plot data."""
        if x_data is not None and y_data is not None:
            self.x_data = np.array(x_data, dtype=float)
            self.y_data = np.array(y_data, dtype=float)

            if len(self.x_data) != len(self.y_data):
                logger.warning("x_data and y_data lengths don't match")
                self.x_data = None
                self.y_data = None
        else:
            self.x_data = None
            self.y_data = None

        self.update()

    def set_reference_data(self, x_ref_data, y_ref_data):
        """Set optional reference line data."""
        if x_ref_data is not None and y_ref_data is not None:
            self.x_ref_data = np.array(x_ref_data, dtype=float)
            self.y_ref_data = np.array(y_ref_data, dtype=float)

            if len(self.x_ref_data) != len(self.y_ref_data):
                logger.warning("x_ref_data and y_ref_data lengths don't match")
                self.x_ref_data = None
                self.y_ref_data = None
        else:
            self.x_ref_data = None
            self.y_ref_data = None

        self.update()

    def add_trace(self, x_data, y_data, color="blue", line_style=Qt.SolidLine, line_width=1, label=""):
        """Add a trace to the plot."""
        if x_data is not None and y_data is not None:
            trace = {
                'x': np.array(x_data, dtype=float),
                'y': np.array(y_data, dtype=float),
                'color': QColor(color),
                'style': line_style,
                'width': line_width,
                'label': label
            }

            if len(trace['x']) != len(trace['y']):
                logger.warning(f"x_data and y_data lengths don't match for trace '{label}'")
                return

            self.traces.append(trace)
            self.update()

    def clear_traces(self):
        """Clear all traces."""
        self.traces.clear()
        self.update()

    def set_axis_limits(self, x_min=None, x_max=None, y_min=None, y_max=None):
        """Set axis limits. None means auto-scale."""
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

        self.auto_scale_x = (x_min is None and x_max is None)
        self.auto_scale_y = (y_min is None and y_max is None)

        self.update()

    def set_colors(self, line_color=None, ref_line_color=None, background_color=None):
        """Set plot colors."""
        if line_color is not None:
            self.line_color = QColor(line_color)
        if ref_line_color is not None:
            self.ref_line_color = QColor(ref_line_color)
        if background_color is not None:
            self.background_color = QColor(background_color)
        self.update()

    def set_labels(self, title="", x_label="", y_label=""):
        """Set plot labels."""
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.update()

    def _calculate_data_bounds(self):
        """Calculate the bounds of all data for auto-scaling."""
        x_min, x_max, y_min, y_max = None, None, None, None

        # Main data bounds (backward compatibility)
        if self.x_data is not None and self.y_data is not None and len(self.x_data) > 0:
            x_min = np.nanmin(self.x_data)
            x_max = np.nanmax(self.x_data)
            y_min = np.nanmin(self.y_data)
            y_max = np.nanmax(self.y_data)

        # Multi-trace data bounds
        for trace in self.traces:
            if len(trace['x']) > 0:
                trace_x_min = np.nanmin(trace['x'])
                trace_x_max = np.nanmax(trace['x'])
                trace_y_min = np.nanmin(trace['y'])
                trace_y_max = np.nanmax(trace['y'])

                if x_min is None:
                    x_min, x_max = trace_x_min, trace_x_max
                    y_min, y_max = trace_y_min, trace_y_max
                else:
                    x_min = min(x_min, trace_x_min)
                    x_max = max(x_max, trace_x_max)
                    y_min = min(y_min, trace_y_min)
                    y_max = max(y_max, trace_y_max)

        # Reference data bounds
        if self.x_ref_data is not None and self.y_ref_data is not None and len(self.x_ref_data) > 0:
            ref_x_min = np.nanmin(self.x_ref_data)
            ref_x_max = np.nanmax(self.x_ref_data)
            ref_y_min = np.nanmin(self.y_ref_data)
            ref_y_max = np.nanmax(self.y_ref_data)

            if x_min is None:
                x_min, x_max = ref_x_min, ref_x_max
                y_min, y_max = ref_y_min, ref_y_max
            else:
                x_min = min(x_min, ref_x_min)
                x_max = max(x_max, ref_x_max)
                y_min = min(y_min, ref_y_min)
                y_max = max(y_max, ref_y_max)

        # Add some padding if bounds are equal
        if x_min is not None and x_max is not None and np.isclose(x_min, x_max):
            padding = abs(x_min) * 0.1 if x_min != 0 else 1
            x_min -= padding
            x_max += padding

        if y_min is not None and y_max is not None and np.isclose(y_min, y_max):
            padding = abs(y_min) * 0.1 if y_min != 0 else 1
            y_min -= padding
            y_max += padding

        return x_min, x_max, y_min, y_max

    def _get_plot_bounds(self):
        """Get the actual plot bounds to use."""
        data_x_min, data_x_max, data_y_min, data_y_max = self._calculate_data_bounds()

        # X bounds
        if self.auto_scale_x:
            plot_x_min = data_x_min if data_x_min is not None else 0
            plot_x_max = data_x_max if data_x_max is not None else 1
        else:
            plot_x_min = self.x_min if self.x_min is not None else (data_x_min or 0)
            plot_x_max = self.x_max if self.x_max is not None else (data_x_max or 1)

        # Y bounds
        if self.auto_scale_y:
            plot_y_min = data_y_min if data_y_min is not None else -1
            plot_y_max = data_y_max if data_y_max is not None else 1
        else:
            plot_y_min = self.y_min if self.y_min is not None else (data_y_min or -1)
            plot_y_max = self.y_max if self.y_max is not None else (data_y_max or 1)

        return plot_x_min, plot_x_max, plot_y_min, plot_y_max

    def _transform_coordinates(self, x, y):
        """Transform data coordinates to widget coordinates."""
        plot_x_min, plot_x_max, plot_y_min, plot_y_max = self._get_plot_bounds()

        plot_width = self.width() - self.margin_left - self.margin_right
        plot_height = self.height() - self.margin_top - self.margin_bottom

        if plot_x_max - plot_x_min == 0:
            widget_x = self.margin_left + plot_width // 2
        else:
            widget_x = self.margin_left + ((x - plot_x_min) / (plot_x_max - plot_x_min)) * plot_width

        if plot_y_max - plot_y_min == 0:
            widget_y = self.margin_top + plot_height // 2
        else:
            widget_y = self.height() - self.margin_bottom - ((y - plot_y_min) / (plot_y_max - plot_y_min)) * plot_height

        return int(widget_x), int(widget_y)

    def _draw_axes(self, painter):
        """Draw the plot axes and labels."""
        if not self.show_axes:
            return

        plot_x_min, plot_x_max, plot_y_min, plot_y_max = self._get_plot_bounds()

        # Draw axes lines
        pen = QPen(self.text_color, 1)
        painter.setPen(pen)

        # X axis
        x1 = self.margin_left
        x2 = self.width() - self.margin_right
        y_axis = self.height() - self.margin_bottom
        painter.drawLine(x1, y_axis, x2, y_axis)

        # Y axis
        y1 = self.margin_top
        y2 = self.height() - self.margin_bottom
        x_axis = self.margin_left
        painter.drawLine(x_axis, y1, x_axis, y2)

        # Draw labels
        painter.setFont(self.label_font)

        # X label
        if self.x_label:
            x_center = (self.width() - self.margin_right + self.margin_left) // 2
            y_label_pos = self.height() - 5
            painter.drawText(QRect(x_center - 100, y_label_pos - 15, 200, 15),
                           Qt.AlignCenter, self.x_label)

        # Y label (rotated)
        if self.y_label:
            y_center = (self.height() - self.margin_bottom + self.margin_top) // 2
            painter.save()
            painter.translate(15, y_center)
            painter.rotate(-90)
            painter.drawText(QRect(-100, -7, 200, 15), Qt.AlignCenter, self.y_label)
            painter.restore()

        # Title
        if self.title:
            painter.setFont(self.title_font)
            title_rect = QRect(0, 5, self.width(), 20)
            painter.drawText(title_rect, Qt.AlignCenter, self.title)

    def _draw_grid(self, painter):
        """Draw the plot grid."""
        if not self.show_grid:
            return

        pen = QPen(self.grid_color, 1)
        painter.setPen(pen)

        # Draw vertical grid lines (simplified)
        plot_width = self.width() - self.margin_left - self.margin_right
        for i in range(5):  # 5 vertical lines
            x = self.margin_left + (i + 1) * plot_width // 6
            painter.drawLine(x, self.margin_top, x, self.height() - self.margin_bottom)

        # Draw horizontal grid lines (simplified)
        plot_height = self.height() - self.margin_top - self.margin_bottom
        for i in range(4):  # 4 horizontal lines
            y = self.margin_top + (i + 1) * plot_height // 5
            painter.drawLine(self.margin_left, y, self.width() - self.margin_right, y)

    def _draw_traces(self, painter):
        """Draw all traces."""
        # Draw multi-traces first
        for trace in self.traces:
            if len(trace['x']) < 2:
                continue

            pen = QPen(trace['color'], trace['width'], trace['style'])
            painter.setPen(pen)

            # Convert first point
            prev_x, prev_y = self._transform_coordinates(trace['x'][0], trace['y'][0])

            # Draw line segments
            for i in range(1, len(trace['x'])):
                curr_x, curr_y = self._transform_coordinates(trace['x'][i], trace['y'][i])
                painter.drawLine(prev_x, prev_y, curr_x, curr_y)
                prev_x, prev_y = curr_x, curr_y

        # Draw main data (backward compatibility)
        self._draw_data(painter)

    def _draw_data(self, painter):
        """Draw the main data line (backward compatibility)."""
        if self.x_data is None or self.y_data is None or len(self.x_data) < 2:
            return

        pen = QPen(self.line_color, self.line_width)
        painter.setPen(pen)

        # Convert first point
        prev_x, prev_y = self._transform_coordinates(self.x_data[0], self.y_data[0])

        # Draw line segments
        for i in range(1, len(self.x_data)):
            curr_x, curr_y = self._transform_coordinates(self.x_data[i], self.y_data[i])
            painter.drawLine(prev_x, prev_y, curr_x, curr_y)
            prev_x, prev_y = curr_x, curr_y

    def _draw_reference_data(self, painter):
        """Draw the reference data line."""
        if self.x_ref_data is None or self.y_ref_data is None or len(self.x_ref_data) < 2:
            return

        pen = QPen(self.ref_line_color, self.ref_line_width, self.ref_line_style)
        painter.setPen(pen)

        # Convert first point
        prev_x, prev_y = self._transform_coordinates(self.x_ref_data[0], self.y_ref_data[0])

        # Draw line segments
        for i in range(1, len(self.x_ref_data)):
            curr_x, curr_y = self._transform_coordinates(self.x_ref_data[i], self.y_ref_data[i])
            painter.drawLine(prev_x, prev_y, curr_x, curr_y)
            prev_x, prev_y = curr_x, curr_y

    def paintEvent(self, event):
        """Main paint event handler."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Fill background
        painter.fillRect(self.rect(), QBrush(self.background_color))

        # Draw plot elements
        try:
            self._draw_grid(painter)
            self._draw_axes(painter)
            self._draw_traces(painter)
            self._draw_reference_data(painter)
        except Exception as e:
            logger.error(f"Error in CustomPlotWidget.paintEvent: {e}")
            # Draw error message
            painter.setPen(QPen(QColor(255, 0, 0)))
            painter.drawText(self.rect(), Qt.AlignCenter, "Plot Error")

    def mousePressEvent(self, event):
        """Handle mouse clicks."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(event.pos())
        super().mousePressEvent(event)

    def clear(self):
        """Clear all plot data."""
        self.x_data = None
        self.y_data = None
        self.x_ref_data = None
        self.y_ref_data = None
        self.traces.clear()
        self.update()


class NavigationWidget(QWidget):
    """Simple navigation controls for the custom plot widget."""

    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()
    reset_zoom_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.reset_btn = QPushButton("Reset")

        self.zoom_in_btn.clicked.connect(self.zoom_in_requested.emit)
        self.zoom_out_btn.clicked.connect(self.zoom_out_requested.emit)
        self.reset_btn.clicked.connect(self.reset_zoom_requested.emit)

        layout.addWidget(self.zoom_in_btn)
        layout.addWidget(self.zoom_out_btn)
        layout.addWidget(self.reset_btn)
        layout.addStretch()


class CustomPlotCanvas(QWidget):
    """
    Container widget that combines CustomPlotWidget with navigation controls.
    This can be used as a drop-in replacement for matplotlib FigureCanvas.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plot_widget = CustomPlotWidget(self)
        self.navigation = NavigationWidget(self)

        layout.addWidget(self.navigation)
        layout.addWidget(self.plot_widget)

        # Connect navigation signals
        self.navigation.zoom_in_requested.connect(self._zoom_in)
        self.navigation.zoom_out_requested.connect(self._zoom_out)
        self.navigation.reset_zoom_requested.connect(self._reset_zoom)

        # Store original bounds for reset
        self._original_bounds = None

    def _zoom_in(self):
        """Zoom in by 50%."""
        x_min, x_max, y_min, y_max = self.plot_widget._get_plot_bounds()

        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2

        x_range = (x_max - x_min) * 0.25  # Zoom by 50%
        y_range = (y_max - y_min) * 0.25

        self.plot_widget.set_axis_limits(
            x_center - x_range, x_center + x_range,
            y_center - y_range, y_center + y_range
        )

    def _zoom_out(self):
        """Zoom out by 50%."""
        x_min, x_max, y_min, y_max = self.plot_widget._get_plot_bounds()

        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2

        x_range = (x_max - x_min) * 1.0  # Zoom out by 100%
        y_range = (y_max - y_min) * 1.0

        self.plot_widget.set_axis_limits(
            x_center - x_range, x_center + x_range,
            y_center - y_range, y_center + y_range
        )

    def _reset_zoom(self):
        """Reset zoom to show all data."""
        self.plot_widget.set_axis_limits(None, None, None, None)

    def draw(self):
        """Trigger a repaint (compatibility with matplotlib API)."""
        self.plot_widget.update()

    def draw_idle(self):
        """Trigger a repaint when idle (compatibility with matplotlib API)."""
        self.plot_widget.update()

    @property
    def figure(self):
        """Provide figure-like access for compatibility."""
        return self

    def clear(self):
        """Clear the plot."""
        self.plot_widget.clear()

    def tight_layout(self):
        """Compatibility method (no-op for our custom widget)."""
        pass