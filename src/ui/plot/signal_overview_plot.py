import numpy as np
from PyQt5.QtWidgets import QDialog, QPushButton, QHBoxLayout, QLabel, QVBoxLayout, QMessageBox, QStyle, QApplication, \
    QGroupBox, QFormLayout, QComboBox, QSizePolicy
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

    _COLORS = plt.get_cmap("tab10").colors

    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self._layout_mode = LayoutMode.ROWS
        self.setWindowTitle("Full Grid Signal Viewer")
        if not isinstance(grid_handler, GridSetupHandler):
             raise TypeError("grid_handler must be an instance of GridSetupHandler")
        self.grid_handler = grid_handler

        if not self.grid_handler.get_selected_grid():
             logger.warning("Warning: SignalPlotDialog opened, but no grid is currently selected in the handler.")
             QMessageBox.warning(self, "No Grid Selected",
                                 "Currently, there is no grid selected. Please select a grid first.")

        self._create_widgets()
        self._wire_signals()
        self.showMaximized()
        if self.grid_handler.get_selected_grid():
             self.update_plot()
        else:
             self._show_no_grid_message()

    def _create_widgets(self):
        """Erstellt die Widgets für den Dialog, einschließlich der Toolbar und des Settings-Formulars."""

        # 1) Rotate-Button (rechts oben)
        self.rotate_btn = QPushButton(
            QApplication.style().standardIcon(QStyle.SP_BrowserReload), ""
        )
        self.rotate_btn.setToolTip("Rotate view")
        self.rotate_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 2) View-Settings-Box
        box = QGroupBox("View Settings")
        box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        form = QFormLayout()
        self.layout_label = QLabel(self._layout_mode.name.title())
        self.layout_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        form.addRow("Layout:", self.layout_label)

        # Combobox für Fiber-Orientation
        self.fiber_combo = QComboBox()
        for mode in FiberMode:
            self.fiber_combo.addItem(mode.name.title(), mode)
        form.addRow("Fibers:", self.fiber_combo)

        # Apply-Button
        self.apply_btn = QPushButton(
            QApplication.style().standardIcon(QStyle.SP_DialogApplyButton),
            ""
        )
        self.apply_btn.setToolTip("Apply changes")
        self.apply_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        form.addRow(self.apply_btn)

        box.setLayout(form)

        # 3) Controls-Layout ganz oben
        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(box)
        controls.addWidget(self.rotate_btn)

        # 4) Matplotlib-Canvas + Toolbar
        self.canvas = FigureCanvas(Figure(figsize=(15, 10)))
        self.ax = self.canvas.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # 5) Gesamtes Dialog-Layout
        root = QVBoxLayout(self)
        root.addLayout(controls)  # ganz oben: Settings + Rotate (jetzt rechtsbündig)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas)

        self.setLayout(root) # Wichtig, um das Layout für den Dialog zu setzen

    def _wire_signals(self):
        self.rotate_btn.clicked.connect(self._rotate_view)

    def _rotate_view(self):
        """Flip between row and column major view and redraw"""
        if self._layout_mode == LayoutMode.ROWS:
            self._layout_mode = LayoutMode.COLS
        else:
            self._layout_mode = LayoutMode.ROWS
        self.layout_label.setText(self._layout_mode.name.title())
        self.update_plot()

    def _apply_orientation_selection(self):
        """Applies the currently selected orientation selection (combination layout/fiber)"""
        selected_fiber_mode: FiberMode = self.fiber_combo.currentData()
        selected_layout_mode = self._layout_mode

        logger.debug(f"Selected orientation: {selected_fiber_mode.name.title()} -> {selected_layout_mode.name.title()}")




    def _show_no_grid_message(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "No grid selected", ha='center', va='center',
                     transform=self.ax.transAxes, fontsize=12, color='red')
        self.ax.set_yticks([])
        self.ax.set_xticks([])
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")
        self.canvas.draw_idle()

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
        if self._layout_mode == LayoutMode.COLS:
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
                         linestyle="-" if global_state.get_channel_status(ch) else ":",
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