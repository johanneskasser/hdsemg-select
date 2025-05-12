# -*- coding: utf-8 -*-
from typing import Dict, Any, List

import numpy as np
from PyQt5.QtWidgets import QDialog, QPushButton, QHBoxLayout, QLabel, QVBoxLayout, QMessageBox
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# Import für die Navigations-Toolbar
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Stellen Sie sicher, dass diese Importe korrekt auf Ihre Projektstruktur verweisen
from controller.grid_setup_handler import GridSetupHandler
from state.state import global_state
from _log.log_config import logger # Logger importieren

def _normalize_trace(trace: np.ndarray, max_amp: float = 1.1) -> np.ndarray:
    """Skaliert *trace*, um eine Spitzenamplitude von *max_amp* (a.u.) zu haben."""
    # Sicherstellen, dass trace nicht leer ist
    if trace.size == 0:
        return trace
    peak = np.max(np.abs(trace))
    # Prüfen auf None, 0 oder NaN
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

    # ------------------------------------------------------------------ init
    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Grid Signal Viewer")
        # ... (Rest der __init__ Methode bleibt gleich) ...
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


    # ------------------------------------------------------------------ UI
    def _create_widgets(self):
        """Erstellt die Widgets für den Dialog, einschließlich der Toolbar."""
        self.refresh_btn = QPushButton("Refresh Plot")
        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(self.refresh_btn)
        self.canvas = FigureCanvas(Figure(figsize=(15, 10)))
        # Verwende add_subplot für einfacheres Layout-Management
        self.ax = self.canvas.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self)
        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas)

    # ------------------------------------------------------------------ signals & messages
    def _wire_signals(self):
        self.refresh_btn.clicked.connect(self.update_plot)

    def _show_no_grid_message(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "No grid selected", ha='center', va='center',
                     transform=self.ax.transAxes, fontsize=12, color='red')
        self.ax.set_yticks([])
        self.ax.set_xticks([])
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ Plotting
    def update_plot(self):
        """Aktualisiert den Plot, um alle Kanäle des aktuell ausgewählten Grids anzuzeigen."""
        logger.debug("Updating Signal Plot Dialog...")
        selected_grid_name = self.grid_handler.get_selected_grid()
        if not selected_grid_name:
            self._show_no_grid_message()
            logger.warning("Plot update skipped: No grid selected.")
            return

        ch_indices = self.grid_handler.get_current_grid_indices()
        if not ch_indices:
            # ... (Fehlermeldung Code) ...
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"No channels found for grid '{selected_grid_name}'", ha='center', va='center', transform=self.ax.transAxes, fontsize=12, color='orange')
            self.ax.set_yticks([]); self.ax.set_xticks([]); self.ax.set_xlabel(""); self.ax.set_ylabel("")
            self.canvas.draw_idle()
            logger.warning(f"Plot update skipped: No channels for grid '{selected_grid_name}'.")
            return

        data = global_state.get_data()
        fs = global_state.get_sampling_frequency()

        if data is None or data.ndim != 2 or data.shape[0] == 0 or data.shape[1] == 0:
            # ... (Fehlermeldung Code) ...
            self.ax.clear()
            self.ax.text(0.5, 0.5, "No valid signal data available", ha='center', va='center', transform=self.ax.transAxes, fontsize=12, color='red')
            self.ax.set_yticks([]); self.ax.set_xticks([]); self.ax.set_xlabel(""); self.ax.set_ylabel("")
            self.canvas.draw_idle()
            logger.warning("Plot update skipped: No valid signal data.")
            return

        if fs is None or not isinstance(fs, (int, float)) or fs <= 0:
             logger.error(f"Invalid sampling frequency: {fs}. Cannot calculate time axis.")
             QMessageBox.critical(self, "Error", f"Invalid sampling frequency ({fs}). Cannot plot signals.")
             return

        # --- Korrekte Dimensionsannahme und Zeitberechnung ---
        n_channels_total = data.shape[1] # Annahme: Kanäle in erster Dimension
        n_samples = data.shape[0]
        logger.debug(f"Data shape: {data.shape} (Channels: {n_channels_total}, Samples: {n_samples})")
        logger.debug(f"Sampling frequency: {fs}")

        data = np.asarray(data, dtype=float)
        time = global_state.get_time()
        if time.size > 0:
             logger.debug(f"Calculated time axis: Start={time[0]:.4f} s, End={time[-1]:.4f} s")
        else:
             logger.debug("Calculated time axis is empty.")


        orientation = self.grid_handler.get_orientation()
        rows = self.grid_handler.get_rows()
        cols = self.grid_handler.get_cols()
        separator_interval = cols if orientation == "perpendicular" else rows

        self.ax.clear()
        offset = 0.0
        valid_ch_indices_plot_order = []

        # Iteriere durch die Kanalindizes und plotte
        for i, ch in enumerate(ch_indices):
            # Korrekte Prüfung gegen n_channels_total
            if ch is None or ch < 0 or ch >= n_channels_total:
                logger.warning(f"Skipping invalid channel index {ch} (>= {n_channels_total}?) at plot index {i}.")
                continue

            valid_ch_indices_plot_order.append(ch)

            # Korrekte Indizierung für trace
            trace = data[:, ch]
            if trace.shape[0] != time.shape[0]:
                 logger.error(f"Shape mismatch for Ch {ch}: Data has {trace.shape[0]} samples, Time has {time.shape[0]} points. Skipping plot for this channel.")
                 valid_ch_indices_plot_order.pop() # Entfernen, da nicht geplottet
                 continue

            if np.all(np.isnan(trace)):
                logger.warning(f"Channel {ch} contains only NaNs. Plotting flat line.")
                normalized_trace = np.zeros_like(time)
            else:
                 normalized_trace = _normalize_trace(trace)

            trace_with_offset = normalized_trace + offset

            is_sel = global_state.get_channel_status(ch) # Prüfen, ob die Funktion existiert
            linestyle = "-" if is_sel else ":"
            color = self._COLORS[i % len(self._COLORS)]

            self.ax.plot(time, trace_with_offset, color=color, linestyle=linestyle, linewidth=1.0)

            # Trennlinien
            if (i + 1) % separator_interval == 0 and (i + 1) < len(ch_indices):
                # Verwende axhline für Trennlinien
                self.ax.axhline(offset + 0.5, color='black', linewidth=1.5, alpha=0.4)

            offset += 1.0
        # --- SCHLEIFENENDE ---

        # === Y-Tick Logik NACH der Schleife platzieren ===
        num_plotted_channels = len(valid_ch_indices_plot_order)
        if num_plotted_channels > 0:
            self.ax.set_ylim(-0.5, num_plotted_channels - 0.5) # Y-Limits basierend auf Anzahl geplotteter Kanäle

            yticks_pos = np.arange(num_plotted_channels)
            yticks_labels = [str(ch) for ch in valid_ch_indices_plot_order]
            self.ax.set_yticks(yticks_pos)
            self.ax.set_yticklabels(yticks_labels, fontsize=8) # Kleinere Schriftgröße
            logger.debug(f"Set {num_plotted_channels} Y-ticks.")
        else:
            self.ax.set_ylim(-0.5, 0.5) # Fallback
            self.ax.set_yticks([]) # Keine Ticks, wenn nichts geplottet wurde
        # === Ende Y-Tick Logik ===

        # X-Achsen-Limit setzen
        if time.size > 0:
            self.ax.set_xlim(time[0], time[-1])
        else:
            self.ax.set_xlim(0, 1)

        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(f"Channel Index (Grid: {selected_grid_name})")
        try:
            # Verwende tight_layout ohne rect oder passe add_subplot/figure margins an
            self.canvas.figure.tight_layout()
        except Exception as e:
             logger.warning(f"Could not apply tight_layout: {e}")

        self.canvas.draw_idle()
        logger.debug("Signal Plot update complete.")


# --- API Funktion (unverändert) ---
def open_signal_plot_dialog(grid_handler: GridSetupHandler, parent=None) -> SignalPlotDialog:
    """
    Erstellt und zeigt den 'Full Grid Signal Viewer'-Dialog an.
    """
    if not isinstance(grid_handler, GridSetupHandler):
        raise TypeError("grid_handler must be an instance of GridSetupHandler")
    dlg = SignalPlotDialog(grid_handler, parent)
    return dlg