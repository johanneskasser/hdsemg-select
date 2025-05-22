import numpy as np
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QDialog, QPushButton, QHBoxLayout, QLabel, QVBoxLayout, QMessageBox, QStyle, QApplication, \
    QGroupBox, QFormLayout, QComboBox, QSizePolicy, QWidget, QGridLayout
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from controller.grid_setup_handler import GridSetupHandler
from state.enum.layout_mode_enums import LayoutMode, FiberMode
from state.state import global_state
from _log.log_config import logger

def _normalize_trace(trace: np.ndarray, max_amp: float = 1.1) -> np.ndarray:
    """Skaliert *trace*, um eine Spitzenamplitude von *max_amp* (a.u.) zu haben."""
    # Sicherstellen, dass trace nicht leer ist
    if trace.size == 0:
        return trace
    peak = np.max(np.abs(trace))
    if peak is None or np.isclose(peak, 0.0) or np.isnan(peak):
        return np.copy(trace)
    return trace * (max_amp / peak)

class SignalPlotDialog(QDialog):
    """
    Vollbild-EMG-Viewer für das aktuell im GridSetupHandler ausgewählte Grid.
    Zeigt alle Kanäle des Grids über die gesamte Signallänge an,
    mit interaktivem Zoom/Pan über die Matplotlib-Toolbar und Kanalindizes auf der Y-Achse.
    """
    orientation_applied = pyqtSignal()

    _COLORS = plt.get_cmap("tab10").colors

    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self.currently_selected_fiber_mode = grid_handler.get_orientation()

        flags = self.windowFlags()
        flags |= Qt.Window
        flags |= Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self._layout_mode = global_state.get_layout_for_fiber(self.currently_selected_fiber_mode)
        logger.debug(f"SignalPlotDialog initialized with layout mode: {self._layout_mode.name.title()}")
        self.setWindowTitle("Full Grid Signal Viewer")
        if not isinstance(grid_handler, GridSetupHandler):
             raise TypeError("grid_handler must be an instance of GridSetupHandler")
        self.grid_handler = grid_handler

        if not self.grid_handler.get_selected_grid():
             logger.warning("Warning: SignalPlotDialog opened, but no grid is currently selected in the handler.")
             QMessageBox.warning(self, "No Grid Selected",
                                 "Currently, there is no grid selected. Please select a grid first.")

        self._create_widgets()
        self.showMaximized()
        if self.grid_handler.get_selected_grid():
             self.update_plot()
        else:
             self._show_no_grid_message()

    def _create_widgets(self):
        """Creates the widgets for the dialog, including toolbar and settings form."""

        # -- Rotate button (upper right) --
        self.rotate_btn = QPushButton(
            QApplication.style().standardIcon(QStyle.SP_BrowserReload), ""
        )
        self.rotate_btn.setToolTip("Rotate view")
        self.rotate_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # -- Top controls layout --
        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(self._create_view_settings())

        # -- Matplotlib canvas + toolbar --
        self.canvas = FigureCanvas(Figure(figsize=(15, 10)))
        self.ax = self.canvas.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # -- Main dialog layout --
        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas)
        self.setLayout(root)

    def _create_view_settings(self):
        box = QGroupBox("View Settings")
        box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        # horizontal layout: [toggle button] are <b>parallel</b> to muscle fibers.
        hl = QHBoxLayout()
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(6)

        # Info icon
        info = QPushButton()
        info.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info.setFixedSize(20, 20)
        info.setToolTip("Choose whether Rows or Columns run parallel to fibers")
        info.clicked.connect(lambda: QMessageBox.information(
            self, "Orientation Info",
            "Toggle to select which grid axis (Rows or Columns) is parallel to the muscle fibers."
        ))

        # The toggle button itself
        rows, cols = self.grid_handler.get_rows(), self.grid_handler.get_cols()
        self.layout_toggle = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), "")
        self.layout_toggle.setCheckable(True)
        # initial state: if current layout is ROWS, show “n Rows” (unchecked)
        if self._layout_mode == LayoutMode.ROWS:
            self.layout_toggle.setChecked(False)
            self.layout_toggle.setText(f"{rows} Rows")
        else:
            self.layout_toggle.setChecked(True)
            self.layout_toggle.setText(f"{cols} Columns")
        self.layout_toggle.clicked.connect(self._on_layout_toggled)

        # Static label
        lbl = QLabel("are <b>parallel</b> to muscle fibers.")
        lbl.setTextFormat(Qt.RichText)

        # assemble
        hl.addWidget(info)
        hl.addWidget(self.layout_toggle)
        hl.addWidget(lbl)
        hl.addStretch()

        box.setLayout(hl)
        box.setMaximumHeight(box.sizeHint().height())
        return box

    def _on_layout_toggled(self):
        # flip internal layout_mode
        rows, cols = self.grid_handler.get_rows(), self.grid_handler.get_cols()
        if self.layout_toggle.isChecked():
            self._layout_mode = LayoutMode.COLUMNS
            self.layout_toggle.setText(f"{cols} Columns")
        else:
            self._layout_mode = LayoutMode.ROWS
            self.layout_toggle.setText(f"{rows} Rows")
        self.update_plot()

    def _rotate_view(self):
        """Flip between row and column major view and redraw"""
        if self._layout_mode == LayoutMode.ROWS:
            self._layout_mode = LayoutMode.COLUMNS
        else:
            self._layout_mode = LayoutMode.ROWS
        self.layout_label.setText(self._layout_mode.name.title())
        self.update_plot()

    def _apply_orientation_selection(self):
        """Applies the currently selected orientation selection (combination layout/fiber)"""
        selected_fiber_mode: FiberMode = FiberMode.PARALLEL # default
        selected_layout_mode = self._layout_mode

        if global_state.get_layout_for_fiber(selected_fiber_mode) == selected_layout_mode:
            # no change needed
            logger.debug("No change in layout mode needed.")
            return False

        logger.debug(f"Selected orientation: {selected_fiber_mode.name.title()} -> {selected_layout_mode.name.title()}")

        global_state.set_fiber_layout(selected_fiber_mode, selected_layout_mode)

        self.orientation_applied.emit()
        return True

    def _show_no_grid_message(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "No grid selected", ha='center', va='center',
                     transform=self.ax.transAxes, fontsize=12, color='red')
        self.ax.set_yticks([])
        self.ax.set_xticks([])
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")
        self.canvas.draw_idle()

    def closeEvent(self, a0):
        if self._apply_orientation_selection():
            QMessageBox.information(self, "Orientation selection updated successfully", f"<b>{self._layout_mode.name.title()}</b> are <b>parallel</b> to muscle fibers.")
        super().closeEvent(a0)

    def update_plot(self):
        """Aktualisiert den Plot, um alle Kanäle des aktuell ausgewählten Grids anzuzeigen."""
        logger.debug("Updating Signal Plot Dialog...")
        selected_grid_name = self.grid_handler.get_selected_grid()
        if not selected_grid_name:
            self._show_no_grid_message()
            logger.warning("Plot update skipped: No grid selected.")
            return

        # --- get and validate channel indices ---
        ch_indices = self.grid_handler.get_current_grid_indices()
        if not ch_indices:
            self.ax.clear()
            self.ax.text(0.5, 0.5,
                         f"No channels found for grid '{selected_grid_name}'",
                         ha='center', va='center',
                         transform=self.ax.transAxes,
                         fontsize=12, color='orange')
            self.ax.set_yticks([]);
            self.ax.set_xticks([])
            self.ax.set_xlabel("");
            self.ax.set_ylabel("")
            self.canvas.draw_idle()
            logger.warning(f"Plot update skipped: No channels for grid '{selected_grid_name}'.")
            return

        # --- grab data + timebase + sanity checks ---
        data = global_state.get_data()
        fs = global_state.get_sampling_frequency()
        if data is None or data.ndim != 2 or data.size == 0:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "No valid signal data available",
                         ha='center', va='center',
                         transform=self.ax.transAxes,
                         fontsize=12, color='red')
            self.canvas.draw_idle()
            logger.warning("Plot update skipped: No valid signal data.")
            return
        if fs is None or not isinstance(fs, (int, float)) or fs <= 0:
            logger.error(f"Invalid sampling frequency: {fs}. Cannot plot.")
            QMessageBox.critical(self, "Error",
                                 f"Invalid sampling frequency ({fs}).")
            return

        time = global_state.get_time()
        data = np.asarray(data, dtype=float)
        n_channels_total = data.shape[1]

        # --- reshape & rotate channel layout ---
        rows = self.grid_handler.get_rows()
        cols = self.grid_handler.get_cols()
        try:
            grid_arr = np.array(ch_indices).reshape(cols, rows)
        except ValueError:
            grid_arr = np.array(ch_indices)[None, :]
        if self._layout_mode == LayoutMode.ROWS:
            grid_arr = grid_arr.T
        ch_indices = grid_arr.flatten().tolist()
        rows, cols = grid_arr.shape

        separator_interval = cols

        # --- plotting ---
        self.ax.clear()
        offset = 0.0
        valid_ch_plot = []

        for i, ch in enumerate(ch_indices):
            if ch is None or not (0 <= ch < n_channels_total):
                logger.warning(f"Invalid channel index {ch} skipped.")
                continue
            valid_ch_plot.append(ch)
            trace = data[:, ch]
            if trace.shape[0] != time.shape[0]:
                logger.error(f"Sample mismatch Ch {ch}.")
                valid_ch_plot.pop()
                continue
            normalized = (_normalize_trace(trace)
                          if not np.all(np.isnan(trace))
                          else np.zeros_like(time))
            self.ax.plot(time,
                         normalized + offset,
                         color=self._COLORS[i % len(self._COLORS)],
                         linestyle="-" if global_state.get_channel_status(ch) else "--",
                         linewidth=1.0)
            # draw separator lines
            if (i + 1) % separator_interval == 0 and (i + 1) < len(ch_indices):
                self.ax.axhline(offset + 0.5,
                                color='black', linewidth=1.5, alpha=0.4)
            offset += 1.0

        # --- finalize axes ---
        n_plotted = len(valid_ch_plot)
        if n_plotted:
            self.ax.set_ylim(-0.5, n_plotted - 0.5)
            yt = np.arange(n_plotted)
            labels = [str(c + 1) for c in valid_ch_plot]
            self.ax.set_yticks(yt)
            self.ax.set_yticklabels(labels, fontsize=8)
        else:
            self.ax.set_ylim(-0.5, 0.5)
            self.ax.set_yticks([])

        if time.size:
            self.ax.set_xlim(time[0], time[-1])
        else:
            self.ax.set_xlim(0, 1)

        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(f"Channel Index (Grid: {selected_grid_name})")

        try:
            self.canvas.figure.tight_layout()
        except Exception as e:
            logger.warning(f"Tight layout failed: {e}")

        self.canvas.draw_idle()
        logger.debug("Signal Plot update complete.")


def open_signal_plot_dialog(grid_handler: GridSetupHandler, parent=None) -> SignalPlotDialog:
    """
    Erstellt und zeigt den 'Full Grid Signal Viewer'-Dialog an.
    """
    if not isinstance(grid_handler, GridSetupHandler):
        raise TypeError("grid_handler must be an instance of GridSetupHandler")
    dlg = SignalPlotDialog(grid_handler, parent)
    return dlg