import numpy as np
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QPushButton, QHBoxLayout, QLabel, QVBoxLayout, QMessageBox, QStyle, QApplication, \
    QGroupBox, QComboBox, QSizePolicy, QWidget
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from hdsemg_select.controller.grid_setup_handler import GridSetupHandler
from hdsemg_select.state.enum.layout_mode_enums import LayoutMode, FiberMode
from hdsemg_select.state.state import global_state
from hdsemg_select._log.log_config import logger
from hdsemg_shared.preprocessing.differential import to_differential

from hdsemg_select.ui.dialog.differential_filter_settings_dialog import DifferentialFilterSettingsDialog
from hdsemg_select.ui.icons.custom_icon_enum import CustomIcon, set_button_icon


def _normalize_trace(trace: np.ndarray, max_amp: float = 1.1) -> np.ndarray:
    """Skaliert *trace*, um eine Spitzenamplitude von *max_amp* (a.u.) zu haben."""
    if trace.size == 0:
        return trace
    peak = np.max(np.abs(trace))
    if peak is None or np.isclose(peak, 0.0) or np.isnan(peak):
        return np.copy(trace)
    return trace * (max_amp / peak)


class SignalPlotDialog(QDialog):
    orientation_applied = pyqtSignal()
    _COLORS = plt.get_cmap("tab10").colors

    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self.currently_selected_fiber_mode = grid_handler.get_orientation()

        self._plot_generation_count = 0

        # Initialize differential filter parameters
        self._differential_filter_params = {'n': 4, 'low': 20.0, 'up': 450.0}

        flags = self.windowFlags()
        flags |= Qt.Window
        flags |= Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self._layout_mode = global_state.get_layout_for_fiber(self.currently_selected_fiber_mode)
        self._signal_mode = "MP"  # Default signal mode: Monopolar
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
        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(self._create_view_settings())

        self.canvas = FigureCanvas(Figure(figsize=(15, 10)))
        self.ax = self.canvas.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self)

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas)
        self.setLayout(root)

    def _create_view_settings(self):
        box = QGroupBox("View Settings")
        box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        # --- Orientation Toggle ---
        orientation_layout = QHBoxLayout()
        info_orient = QPushButton()
        info_orient.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_orient.setFixedSize(20, 20)
        info_orient.setToolTip("Choose whether Rows or Columns run parallel to fibers")
        info_orient.clicked.connect(lambda: QMessageBox.information(
            self, "Orientation Info",
            "Toggle to select which grid axis (Rows or Columns) is parallel to the muscle fibers."
        ))

        rows, cols = self.grid_handler.get_rows(), self.grid_handler.get_cols()
        self.layout_toggle = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), "")
        self.layout_toggle.setCheckable(True)
        if self._layout_mode == LayoutMode.ROWS:
            self.layout_toggle.setChecked(False)
            self.layout_toggle.setText(f"{rows} Rows")
        else:
            self.layout_toggle.setChecked(True)
            self.layout_toggle.setText(f"{cols} Columns")
        self.layout_toggle.clicked.connect(self._on_layout_toggled)

        lbl_orient = QLabel("are <b>parallel</b> to muscle fibers.")
        lbl_orient.setTextFormat(Qt.RichText)

        orientation_layout.addWidget(info_orient)
        orientation_layout.addWidget(self.layout_toggle)
        orientation_layout.addWidget(lbl_orient)
        orientation_layout.addStretch()

        main_layout.addLayout(orientation_layout)

        # --- Separator Line ---
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        separator.setStyleSheet("background-color: #c0c0c0;")
        main_layout.addWidget(separator)

        # --- Filter Settings ---
        filter_layout = QHBoxLayout()
        lbl_signal_type = QLabel("Signal Type:")
        self.signal_mode_combo = QComboBox()
        self.signal_mode_combo.addItems(["Monopolar (MP)", "Single Differential (SD)", "Double Differential (DD)"])
        self.signal_mode_combo.currentTextChanged.connect(self._on_signal_mode_changed)

        self.filter_settings_btn = QPushButton()
        self.filter_settings_btn.setIcon(QIcon(CustomIcon.SETTINGS.value))
        self.filter_settings_btn.setToolTip("Configure parameters for SD and DD filters (Butterworth Bandpass)")
        self.filter_settings_btn.clicked.connect(self._open_filter_settings_dialog)
        self.filter_settings_btn.setEnabled(False)  # Enabled by _on_signal_mode_changed

        filter_layout.addWidget(lbl_signal_type)
        filter_layout.addWidget(self.signal_mode_combo)
        filter_layout.addStretch()
        filter_layout.addWidget(self.filter_settings_btn)

        main_layout.addLayout(filter_layout)

        box.setLayout(main_layout)
        box.setMaximumHeight(box.sizeHint().height() + 10)
        return box

    def _on_layout_toggled(self):
        rows, cols = self.grid_handler.get_rows(), self.grid_handler.get_cols()
        if self.layout_toggle.isChecked():
            self._layout_mode = LayoutMode.COLUMNS
            self.layout_toggle.setText(f"{cols} Columns")
        else:
            self._layout_mode = LayoutMode.ROWS
            self.layout_toggle.setText(f"{rows} Rows")
        self.update_plot()

    def _on_signal_mode_changed(self, text: str):
        if "Monopolar" in text:
            self._signal_mode = "MP"
            self.filter_settings_btn.setEnabled(False)
        elif "Single Differential" in text:
            self._signal_mode = "SD"
            self.filter_settings_btn.setEnabled(True)
        elif "Double Differential" in text:
            self._signal_mode = "DD"
            self.filter_settings_btn.setEnabled(True)
        self.update_plot()

    def _apply_orientation_selection(self):
        selected_fiber_mode: FiberMode = FiberMode.PARALLEL
        selected_layout_mode = self._layout_mode
        if global_state.get_layout_for_fiber(selected_fiber_mode) == selected_layout_mode:
            return False
        global_state.set_fiber_layout(selected_fiber_mode, selected_layout_mode)
        self.orientation_applied.emit()
        return True

    def _show_no_grid_message(self, message="No grid selected"):
        self.ax.clear()
        self.ax.text(0.5, 0.5, message, ha='center', va='center',
                     transform=self.ax.transAxes, fontsize=12, color='red')
        self.ax.set_yticks([])
        self.ax.set_xticks([])
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")
        self.canvas.draw_idle()

    def closeEvent(self, a0):
        if self._apply_orientation_selection():
            QMessageBox.information(self, "Orientation selection updated successfully",
                                    f"<b>{self._layout_mode.name.title()}</b> are <b>parallel</b> to muscle fibers.")
        super().closeEvent(a0)

    def update_plot(self):
        """ Updates the plot based on the current grid and signal mode."""
        # Store the current plot orientation
        stored_xlim = None
        stored_ylim = None
        if self._plot_generation_count > 0 and self.ax and self.ax.lines:
            stored_xlim = self.ax.get_xlim()
            stored_ylim = self.ax.get_ylim()
            logger.debug(f"Stored xlim: {stored_xlim}, ylim: {stored_ylim}")

        logger.debug(f"Updating Signal Plot Dialog. Mode: {self._signal_mode}, Layout: {self._layout_mode.name}")
        selected_grid_name = self.grid_handler.get_selected_grid()
        if not selected_grid_name:
            self._show_no_grid_message()
            logger.warning("Plot update skipped: No grid selected.")
            return

        ch_indices_orig = self.grid_handler.get_current_grid_indices()
        if not ch_indices_orig:
            self._show_no_grid_message(f"No channels found for grid '{selected_grid_name}'")
            logger.warning(f"Plot update skipped: No channels for grid '{selected_grid_name}'.")
            return

        source_data = global_state.get_emg_file().data
        fs = global_state.get_emg_file().sampling_frequency

        if source_data is None or source_data.ndim != 2 or source_data.size == 0:
            self._show_no_grid_message("No valid signal data available")
            logger.warning("Plot update skipped: No valid signal data.")
            return
        if fs is None or not isinstance(fs, (int, float)) or fs <= 0:
            logger.error(f"Invalid sampling frequency: {fs}. Cannot plot.")
            QMessageBox.critical(self, "Error", f"Invalid sampling frequency ({fs}).")
            return

        time_vector = global_state.get_emg_file().time
        if time_vector is None or time_vector.size == 0:
            self._show_no_grid_message("Time vector not available or empty.")
            logger.warning("Plot update skipped: Time vector not available.")
            return

        source_data = np.asarray(source_data, dtype=float)
        n_channels_total_in_file = source_data.shape[1]

        # --- Reshape channel layout based on _layout_mode ---
        rows_orig = self.grid_handler.get_rows()
        cols_orig = self.grid_handler.get_cols()
        grid_arr_tmp = self.grid_handler.reshape_grid(ch_indices_orig, cols_orig, rows_orig, pad_value=None)
        if grid_arr_tmp is None:
            logger.error(
                f"Error reshaping grid indices into ({cols_orig},{rows_orig}). "
                f"Indices: {ch_indices_orig}"
            )
            self._show_no_grid_message(
                f"Error in grid configuration for '{selected_grid_name}'."
            )
            return

        grid_arr_indices = grid_arr_tmp
        if self._layout_mode == LayoutMode.ROWS:
            grid_arr_indices = grid_arr_indices.T  # Now shape (rows_orig, cols_orig)

        traces_to_plot = []
        labels_for_plot = []
        original_mp_indices_for_status = []  # For MP mode linestyle

        # --- Data Preparation based on Signal Mode ---
        num_fiber_lines = grid_arr_indices.shape[0]
        num_mp_along_fiber = grid_arr_indices.shape[1]

        if self._signal_mode == "MP":
            for r_idx in range(num_fiber_lines):
                for c_idx in range(num_mp_along_fiber):
                    ch_idx = grid_arr_indices[r_idx, c_idx]
                    if ch_idx is not None and 0 <= ch_idx < n_channels_total_in_file:
                        if source_data[:, ch_idx].shape[0] != time_vector.shape[0]:
                            logger.error(
                                f"Sample mismatch for MP Ch {ch_idx + 1}. Data: {source_data[:, ch_idx].shape[0]}, Time: {time_vector.shape[0]}")
                            continue
                        traces_to_plot.append(source_data[:, ch_idx])
                        labels_for_plot.append(f"{ch_idx + 1}")  # Original label style
                        original_mp_indices_for_status.append(ch_idx)
            if not traces_to_plot:
                self._show_no_grid_message(f"No valid MP channels to display for '{selected_grid_name}'.")
                return

        else:  # SD or DD
            min_ch_for_sd = 2
            min_ch_for_dd = 3  # (needs 2 SD channels, which needs 3 MP channels)

            if self._signal_mode == "SD" and num_mp_along_fiber < min_ch_for_sd:
                self._show_no_grid_message(
                    f"Not enough channels along fibers ({num_mp_along_fiber}) for SD. Need at least {min_ch_for_sd}.")
                return
            if self._signal_mode == "DD" and num_mp_along_fiber < min_ch_for_dd:
                self._show_no_grid_message(
                    f"Not enough channels along fibers ({num_mp_along_fiber}) for DD. Need at least {min_ch_for_dd}.")
                return

            for line_idx in range(num_fiber_lines):
                mp_indices_this_line = grid_arr_indices[line_idx, :]

                valid_mp_data_this_line = []
                for ch_idx in mp_indices_this_line:
                    if ch_idx is not None and 0 <= ch_idx < n_channels_total_in_file:
                        if source_data[:, ch_idx].shape[0] != time_vector.shape[0]:
                            logger.error(
                                f"Sample mismatch for MP Ch {ch_idx + 1} in line {line_idx + 1}. Data: {source_data[:, ch_idx].shape[0]}, Time: {time_vector.shape[0]}")
                            # Skip this channel, potentially making the line unusable for SD/DD
                            continue
                        valid_mp_data_this_line.append(source_data[:, ch_idx])

                if not valid_mp_data_this_line or len(valid_mp_data_this_line) < (
                min_ch_for_sd if self._signal_mode == "SD" else min_ch_for_dd):
                    continue  # Not enough valid MP channels in this line

                mp_mat_this_line = np.array(valid_mp_data_this_line)  # Shape: (n_valid_mp_in_line, T)

                if self._signal_mode == "SD":
                    if mp_mat_this_line.shape[0] >= min_ch_for_sd:
                        sd_filtered, _ = to_differential([mp_mat_this_line], fs, self._differential_filter_params)
                        if sd_filtered and sd_filtered[0].shape[0] > 0:
                            sd_data_for_line = sd_filtered[0]
                            for sd_ch_idx in range(sd_data_for_line.shape[0]):
                                traces_to_plot.append(sd_data_for_line[sd_ch_idx, :])
                                labels_for_plot.append(f"L{line_idx + 1}:SD{sd_ch_idx + 1}")

                elif self._signal_mode == "DD":
                    if mp_mat_this_line.shape[0] >= min_ch_for_dd:  # Need 3 MP for at least 1 DD
                        # First differential (SD)
                        sd_filtered, _ = to_differential([mp_mat_this_line], fs, self._differential_filter_params)
                        if sd_filtered and sd_filtered[0].shape[
                            0] >= min_ch_for_sd:  # Need at least 2 SD channels for DD
                            sd_mat_for_dd = sd_filtered[0]
                            # Second differential (DD)
                            dd_filtered, _ = to_differential([sd_mat_for_dd], fs, self._differential_filter_params)
                            if dd_filtered and dd_filtered[0].shape[0] > 0:
                                dd_data_for_line = dd_filtered[0]
                                for dd_ch_idx in range(dd_data_for_line.shape[0]):
                                    traces_to_plot.append(dd_data_for_line[dd_ch_idx, :])
                                    labels_for_plot.append(f"L{line_idx + 1}:DD{dd_ch_idx + 1}")

            if not traces_to_plot:
                self._show_no_grid_message(
                    f"No {self._signal_mode} channels could be computed for '{selected_grid_name}'. Check channel count per fiber line.")
                return

        # --- Plotting ---
        self.ax.clear()
        offset = 0.0

        if not traces_to_plot:  # Should be caught earlier, but as a safeguard
            self._show_no_grid_message(f"No data to plot for {self._signal_mode} mode.")
            return

        for i, trace_data in enumerate(traces_to_plot):
            if trace_data.shape[0] != time_vector.shape[0]:
                logger.warning(
                    f"Plotting trace {i} with mismatched length. Trace: {trace_data.shape[0]}, Time: {time_vector.shape[0]}. Skipping.")
                # Potentially add a NaN trace of correct length or skip
                empty_trace = np.full_like(time_vector, np.nan)
                normalized = np.zeros_like(time_vector)  # Plot flat line
            else:
                normalized = (_normalize_trace(trace_data)
                              if not np.all(np.isnan(trace_data)) else np.zeros_like(time_vector))

            linestyle = "-"
            if self._signal_mode == "MP":
                # original_mp_indices_for_status should align with traces_to_plot for MP mode
                ch_original_idx = original_mp_indices_for_status[i]
                linestyle = "-" if global_state.get_channel_status(ch_original_idx) else "--"

            self.ax.plot(time_vector,
                         normalized + offset,
                         color=self._COLORS[i % len(self._COLORS)],
                         linestyle=linestyle,
                         linewidth=1.0)

            # Separator lines
            if self._signal_mode == "MP":
                # num_mp_along_fiber is the number of channels per original fiber line in the view
                if (i + 1) % num_mp_along_fiber == 0 and (i + 1) < len(traces_to_plot):
                    self.ax.axhline(offset + 0.55, color='black', linewidth=1.5, alpha=0.4)
            elif i > 0:  # For SD/DD
                current_label_prefix = labels_for_plot[i].split(':')[0]  # e.g., "L1" from "L1:SD1"
                prev_label_prefix = labels_for_plot[i - 1].split(':')[0]
                if current_label_prefix != prev_label_prefix:
                    self.ax.axhline(offset - 0.45, color='black', linewidth=1.5, alpha=0.4)
            offset += 1.0

        if traces_to_plot:
            self._plot_generation_count += 1 #increment plot generation count

        # --- Finalize Axes ---
        n_plotted = len(traces_to_plot)
        if n_plotted > 0:
            self.ax.set_ylim(-0.5, n_plotted - 0.5)
            yt = np.arange(n_plotted)
            self.ax.set_yticks(yt)
            self.ax.set_yticklabels(labels_for_plot, fontsize=8)
        else:  # Should not happen if checks above are correct
            self.ax.set_ylim(-0.5, 0.5)
            self.ax.set_yticks([])

        if time_vector.size > 0:
            self.ax.set_xlim(time_vector[0], time_vector[-1])
        else:
            self.ax.set_xlim(0, 1)

        # Reapply stored limits if available
        if stored_xlim is not None:
            logger.debug(f"Reapplying stored xlim: {stored_xlim}")
            self.ax.set_xlim(stored_xlim)
        if stored_ylim is not None:
            # Only apply stored_ylim if there are items to plot, to avoid odd states
            if n_plotted > 0:
                logger.debug(f"Applying stored ylim: {stored_ylim}")
                self.ax.set_ylim(stored_ylim)
            elif stored_xlim is None:  # If xlim was also not stored (e.g. very first empty plot)
                self.ax.set_ylim(-0.5, 0.5)

        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(
            f"{self._signal_mode} Channel (Grid: {selected_grid_name} - {self._layout_mode.name.title()} along fibers)")

        try:
            self.canvas.figure.tight_layout()
        except Exception as e:
            logger.warning(f"Tight layout failed: {e}")

        self.canvas.draw_idle()
        logger.debug(f"Signal Plot update complete for {self._signal_mode} mode.")

    def _open_filter_settings_dialog(self):
        # Pass a copy of current params, so original is not modified if dialog is cancelled
        dialog = DifferentialFilterSettingsDialog(dict(self._differential_filter_params), self)
        if dialog.exec_() == QDialog.Accepted:
            new_params = dialog.get_parameters()
            if new_params:  # Should always be true if accepted
                if self._differential_filter_params != new_params:
                    self._differential_filter_params = new_params
                    logger.info(f"Differential filter parameters updated: {self._differential_filter_params}")
                    if self._signal_mode in ["SD", "DD"]:
                        self.update_plot()  # Re-plot if SD/DD mode is active
                else:
                    logger.info("Differential filter parameters unchanged.")
        else:
            logger.info("Differential filter settings dialog cancelled.")


def open_signal_plot_dialog(grid_handler: GridSetupHandler, parent=None) -> SignalPlotDialog:
    if not isinstance(grid_handler, GridSetupHandler):
        raise TypeError("grid_handler must be an instance of GridSetupHandler")
    dlg = SignalPlotDialog(grid_handler, parent)
    return dlg

