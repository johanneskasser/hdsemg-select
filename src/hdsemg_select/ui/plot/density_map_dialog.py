from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QPushButton, QDoubleSpinBox, QSpinBox,
    QLabel, QWidget, QSizePolicy, QStyle, QCheckBox,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle

from hdsemg_select._log.log_config import logger
from hdsemg_select.config.config_enums import Settings
from hdsemg_select.config.config_manager import config
from hdsemg_select.controller.grid_setup_handler import GridSetupHandler
from hdsemg_select.logic.density.arv import compute_arv_window, channels_to_grid, ms_to_samples
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.dialog.density_layout_builder import LayoutBuilderDialog
from hdsemg_select.ui.electrode_layout import get_display_grid
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Fonts, Styles

# Jet-style colormap: dark-blue → blue → cyan → yellow → red
_EMG_CMAP = LinearSegmentedColormap.from_list(
    "emg_jet",
    ["#00008B", "#0000FF", "#00FFFF", "#FFFF00", "#FF0000"],
)
_EMG_CMAP.set_bad("#2a2a2a", alpha=0.8)

_DEFAULT_ARV_MS = 250.0
_DEFAULT_FPS = 30
_DEFAULT_SPEED = 1.0
_SEEK_SECONDS = 2.0
_REF_MAX_POINTS = 2000  # max display points for the reference signal


class DensityMapDialog(QDialog):
    """Animated ARV heatmap over the physical electrode grid.

    The reference signal subplot below the heatmap doubles as a scrubber:
    click or drag to seek to any position in the recording.
    """

    def __init__(self, grid_handler: GridSetupHandler, parent=None):
        super().__init__(parent)
        self._grid_handler = grid_handler

        flags = self.windowFlags()
        flags |= Qt.Window
        flags |= Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self.setWindowTitle("Density Map — ARV Heatmap")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")

        # Playback state
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._cursor_sample: int = 0
        self._playing: bool = False
        self._speed: float = _DEFAULT_SPEED
        self._fps: int = _DEFAULT_FPS

        # Data cache
        self._data: Optional[np.ndarray] = None
        self._data_id: Optional[int] = None
        self._fs: float = 2048.0
        self._n_samples: int = 0

        # Grid / layout cache
        self._grid_key: Optional[str] = None
        self._display_grid: Optional[np.ndarray] = None
        self._emg_indices: list = []
        self._electrode_name: str = ""
        self._n_grid_channels: int = 0
        self._grid_max_amplitude: float = 1.0

        # Reference signal cache
        self._ref_idx: Optional[int] = None
        self._ref_data: Optional[np.ndarray] = None   # downsampled signal
        self._ref_time: Optional[np.ndarray] = None   # downsampled time axis
        self._ref_dragging: bool = False

        # Matplotlib handles
        self._image = None
        self._colorbar = None
        self._ax = None
        self._cbar_ax = None
        self._ref_ax = None
        self._cursor_line = None
        self._ch_num_texts: list = []
        self._sel_patches: list = []
        self._click_cid = None
        self._ref_press_cid = None
        self._ref_drag_cid = None
        self._ref_release_cid = None

        self._build_ui()
        self._populate_grid_selector()
        self._load_data()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_grid(self):
        """Rebuild the physical layout for the currently selected grid key."""
        self._resolve_grid_layout()
        self._reset_plot()

    def invalidate(self):
        """Called by main window when the file or grid selection changes."""
        self._timer.stop()
        self._playing = False
        self._data = None
        self._data_id = None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        root.setSpacing(Spacing.SM)

        main_split = QHBoxLayout()
        main_split.setSpacing(Spacing.MD)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setFixedWidth(270)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(Spacing.SM)

        # Grid selector group
        grid_box = QGroupBox("Grid")
        grid_box.setStyleSheet(self._groupbox_style())
        grid_box_layout = QVBoxLayout(grid_box)
        self._grid_combo = QComboBox()
        self._grid_combo.setStyleSheet(self._combobox_style())
        self._grid_combo.currentTextChanged.connect(self._on_grid_changed)
        grid_box_layout.addWidget(self._grid_combo)
        self._edit_layout_btn = QPushButton("Edit Layout…")
        self._edit_layout_btn.setStyleSheet(Styles.button_secondary())
        self._edit_layout_btn.clicked.connect(self._open_layout_builder)
        grid_box_layout.addWidget(self._edit_layout_btn)
        sidebar_layout.addWidget(grid_box)

        # Reference signal group
        ref_box = QGroupBox("Reference Signal")
        ref_box.setStyleSheet(self._groupbox_style())
        ref_box_layout = QVBoxLayout(ref_box)
        self._ref_combo = QComboBox()
        self._ref_combo.setStyleSheet(self._combobox_style())
        self._ref_combo.currentIndexChanged.connect(self._on_ref_changed)
        ref_box_layout.addWidget(self._ref_combo)
        sidebar_layout.addWidget(ref_box)

        # ARV Window group
        arv_box = QGroupBox("ARV Window")
        arv_box.setStyleSheet(self._groupbox_style())
        arv_box_layout = QVBoxLayout(arv_box)
        arv_row = QHBoxLayout()
        self._arv_spin = QDoubleSpinBox()
        self._arv_spin.setRange(10.0, 2000.0)
        self._arv_spin.setSingleStep(10.0)
        self._arv_spin.setDecimals(0)
        self._arv_spin.setSuffix(" ms")
        self._arv_spin.setValue(config.get(Settings.DENSITY_ARV_WINDOW_MS, _DEFAULT_ARV_MS))
        self._arv_spin.setStyleSheet(self._spinbox_style())
        self._arv_spin.valueChanged.connect(self._on_arv_changed)
        arv_row.addWidget(self._arv_spin)
        arv_row.addStretch()
        arv_box_layout.addLayout(arv_row)
        sidebar_layout.addWidget(arv_box)

        # Scale group
        scale_box = QGroupBox("Scale")
        scale_box.setStyleSheet(self._groupbox_style())
        scale_box_layout = QVBoxLayout(scale_box)
        scale_row = QHBoxLayout()
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.001, 100.0)
        self._scale_spin.setDecimals(3)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setSuffix(" mV")
        self._scale_spin.setValue(1.0)  # overwritten by _resolve_grid_layout
        self._scale_spin.setStyleSheet(self._spinbox_style())
        self._scale_spin.valueChanged.connect(self._on_scale_changed)
        scale_row.addWidget(self._scale_spin)
        scale_row.addStretch()
        scale_box_layout.addLayout(scale_row)
        sidebar_layout.addWidget(scale_box)

        # Playback settings group
        pb_box = QGroupBox("Playback")
        pb_box.setStyleSheet(self._groupbox_style())
        pb_box_layout = QVBoxLayout(pb_box)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.5×", "1×", "2×", "4×"])
        self._speed_combo.setCurrentIndex(1)
        self._speed_combo.setStyleSheet(self._combobox_style())
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self._speed_combo)
        speed_row.addStretch()
        pb_box_layout.addLayout(speed_row)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS:"))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(10, 60)
        self._fps_spin.setValue(config.get(Settings.DENSITY_PLAYBACK_FPS, _DEFAULT_FPS))
        self._fps_spin.setStyleSheet(self._spinbox_style())
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        pb_box_layout.addLayout(fps_row)
        sidebar_layout.addWidget(pb_box)

        # Display options group
        disp_box = QGroupBox("Display Options")
        disp_box.setStyleSheet(self._groupbox_style())
        disp_box_layout = QVBoxLayout(disp_box)

        self._smooth_check = QCheckBox("Smooth interpolation")
        self._smooth_check.setStyleSheet(self._checkbox_style())
        self._smooth_check.stateChanged.connect(self._on_smooth_changed)
        disp_box_layout.addWidget(self._smooth_check)

        self._ch_num_check = QCheckBox("Channel numbers")
        self._ch_num_check.setStyleSheet(self._checkbox_style())
        self._ch_num_check.stateChanged.connect(self._on_ch_num_changed)
        disp_box_layout.addWidget(self._ch_num_check)

        self._sel_check = QCheckBox("Selection status")
        self._sel_check.setToolTip("Overlay selection state; click a cell to toggle it")
        self._sel_check.setStyleSheet(self._checkbox_style())
        self._sel_check.stateChanged.connect(self._on_sel_changed)
        disp_box_layout.addWidget(self._sel_check)

        sidebar_layout.addWidget(disp_box)
        sidebar_layout.addStretch()
        main_split.addWidget(sidebar)

        # --- Plot area ---
        plot_area = QVBoxLayout()
        self._figure = Figure(facecolor=Colors.BG_PRIMARY)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._toolbar = NavigationToolbar(self._canvas, self)
        self._toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
            }}
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px;
            }}
            QToolButton:hover {{
                background-color: {Colors.GRAY_100};
                border-color: {Colors.BORDER_DEFAULT};
            }}
        """)
        plot_area.addWidget(self._toolbar)
        plot_area.addWidget(self._canvas, stretch=1)
        main_split.addLayout(plot_area, stretch=1)
        root.addLayout(main_split, stretch=1)

        # --- Transport bar (no slider — reference plot is the scrubber) ---
        transport = QWidget()
        transport.setFixedHeight(48)
        transport.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD};
            }}
        """)
        transport_layout = QHBoxLayout(transport)
        transport_layout.setContentsMargins(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS)
        transport_layout.setSpacing(Spacing.SM)

        icon_size = 20
        self._rewind_btn = QPushButton()
        self._rewind_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self._rewind_btn.setFixedSize(icon_size + 8, icon_size + 8)
        self._rewind_btn.setToolTip("Rewind 2 s")
        self._rewind_btn.clicked.connect(self._on_rewind)
        transport_layout.addWidget(self._rewind_btn)

        self._play_btn = QPushButton()
        self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._play_btn.setFixedSize(icon_size + 8, icon_size + 8)
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.clicked.connect(self._on_play_pause)
        transport_layout.addWidget(self._play_btn)

        self._forward_btn = QPushButton()
        self._forward_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self._forward_btn.setFixedSize(icon_size + 8, icon_size + 8)
        self._forward_btn.setToolTip("Forward 2 s")
        self._forward_btn.clicked.connect(self._on_forward)
        transport_layout.addWidget(self._forward_btn)

        transport_layout.addStretch()

        self._time_label = QLabel("t = 0.000 s / 0.000 s")
        self._time_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_SM}; font-family: monospace;"
        )
        self._time_label.setFixedWidth(200)
        transport_layout.addWidget(self._time_label)

        root.addWidget(transport)
        self.resize(1100, 750)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _populate_grid_selector(self):
        emg_file = global_state.get_emg_file()
        self._grid_combo.blockSignals(True)
        self._grid_combo.clear()
        if emg_file and emg_file.grids:
            for grid in emg_file.grids:
                self._grid_combo.addItem(grid.grid_key)
            current = self._grid_handler.get_selected_grid()
            if current and self._grid_combo.findText(current) >= 0:
                self._grid_combo.setCurrentText(current)
        self._grid_combo.blockSignals(False)

    def _populate_ref_selector(self):
        """Populate the reference signal dropdown for the currently selected grid."""
        self._ref_combo.blockSignals(True)
        self._ref_combo.clear()

        emg_file = global_state.get_emg_file()
        key = self._grid_combo.currentText()
        if not emg_file or not key:
            self._ref_combo.blockSignals(False)
            return

        grid_obj = emg_file.get_grid(grid_key=key)
        if grid_obj is None:
            self._ref_combo.blockSignals(False)
            return

        descriptions = emg_file.description  # numpy array or dict — don't use truthiness

        def _to_str(name) -> str:
            while isinstance(name, np.ndarray):
                name = name.item() if name.size == 1 else name.flat[0]
            return str(name)

        def _desc(idx) -> str:
            try:
                return _to_str(descriptions[idx])
            except (IndexError, TypeError, KeyError):
                return str(idx)

        ref_signals = list(grid_obj.ref_indices or [])
        per_path_idx = getattr(grid_obj, 'performed_path_idx', None)
        req_path_idx = getattr(grid_obj, 'requested_path_idx', None)

        already_added: set = set()

        if per_path_idx is not None and per_path_idx in ref_signals:
            self._ref_combo.addItem(f"Performed Path – {_desc(per_path_idx)}", per_path_idx)
            already_added.add(per_path_idx)

        if (req_path_idx is not None
                and req_path_idx in ref_signals
                and req_path_idx not in already_added):
            self._ref_combo.addItem(f"Requested Path – {_desc(req_path_idx)}", req_path_idx)
            already_added.add(req_path_idx)

        for sig in ref_signals:
            if sig not in already_added:
                self._ref_combo.addItem(_desc(sig), int(sig))

        self._ref_combo.blockSignals(False)
        self._resolve_ref_signal()

    def _resolve_ref_signal(self):
        """Downsample the selected reference channel for display."""
        self._ref_data = None
        self._ref_time = None
        self._ref_idx = None

        idx = self._ref_combo.currentData()
        if idx is None:
            return

        # Use scaled data (same source as main window ref overlay)
        data = global_state.get_effective_scaled_data()
        if data is None:
            data = global_state.get_effective_emg_data()
        if data is None or idx >= data.shape[1]:
            return

        raw = data[:, int(idx)]
        n = len(raw)
        stride = max(1, n // _REF_MAX_POINTS)
        self._ref_data = raw[::stride]
        self._ref_time = np.arange(len(self._ref_data)) * stride / self._fs
        self._ref_idx = int(idx)

    def _load_data(self):
        data = global_state.get_effective_emg_data()
        if data is None:
            self._data = None
            self._n_samples = 0
            self._show_no_data_placeholder("No file loaded.")
            return

        self._data = data
        self._data_id = id(data)
        self._n_samples = data.shape[0]

        emg_file = global_state.get_emg_file()
        self._fs = float(emg_file.sampling_frequency) if emg_file else 2048.0

        self._cursor_sample = 0
        self._resolve_grid_layout()
        self._populate_ref_selector()
        self._reset_plot()

    def _compute_grid_max(self) -> float:
        """99.5th-percentile absolute value across the current grid's channels."""
        if self._data is None or not self._emg_indices:
            return 1.0
        valid_cols = [i for i in self._emg_indices if i < self._data.shape[1]]
        if not valid_cols:
            return 1.0
        val = float(np.percentile(np.abs(self._data[:, valid_cols]), 99.5))
        return max(val, 0.001)

    def _resolve_grid_layout(self):
        """Determine physical layout and emg_indices for the selected grid key."""
        key = self._grid_combo.currentText()
        self._grid_key = key
        self._display_grid = None
        self._emg_indices = []
        self._electrode_name = ""
        self._n_grid_channels = 0

        emg_file = global_state.get_emg_file()
        if not emg_file or not key:
            return

        grid = emg_file.get_grid(grid_key=key)
        if grid is None:
            return

        self._emg_indices = list(grid.emg_indices)
        self._n_grid_channels = len(self._emg_indices)
        self._electrode_name = self._grid_handler._extract_electrode_name(grid.emg_indices)
        self._display_grid = get_display_grid(self._electrode_name, grid.rows, grid.cols)

        self._grid_max_amplitude = self._compute_grid_max()
        self._scale_spin.blockSignals(True)
        self._scale_spin.setValue(self._grid_max_amplitude)
        self._scale_spin.blockSignals(False)

    # ------------------------------------------------------------------
    # Plot management
    # ------------------------------------------------------------------

    def _disconnect_mpl_events(self):
        for attr in ('_click_cid', '_ref_press_cid', '_ref_drag_cid', '_ref_release_cid'):
            cid = getattr(self, attr, None)
            if cid is not None:
                try:
                    self._canvas.mpl_disconnect(cid)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _reset_plot(self):
        self._disconnect_mpl_events()
        self._ch_num_texts = []
        self._sel_patches = []
        self._figure.clear()
        self._image = None
        self._colorbar = None
        self._ax = None
        self._cbar_ax = None
        self._ref_ax = None
        self._cursor_line = None

        if self._display_grid is None:
            self._show_no_layout_placeholder()
            self._set_transport_enabled(False)
            return

        if self._data is None:
            self._show_no_data_placeholder("No data available.")
            self._set_transport_enabled(False)
            return

        # Two rows: heatmap (tall) + reference signal (short).
        # Two columns: axes + narrow colorbar — so both rows share the same left edge.
        gs = GridSpec(
            2, 2,
            figure=self._figure,
            height_ratios=[3, 1],
            width_ratios=[20, 1],
            hspace=0.45,
            wspace=0.05,
        )
        self._ax = self._figure.add_subplot(gs[0, 0])
        self._cbar_ax = self._figure.add_subplot(gs[0, 1])
        self._ref_ax = self._figure.add_subplot(gs[1, :])

        for ax in (self._ax, self._cbar_ax, self._ref_ax):
            ax.set_facecolor(Colors.BG_PRIMARY)
        self._figure.patch.set_facecolor(Colors.BG_PRIMARY)

        # --- Heatmap ---
        arv = compute_arv_window(
            self._data,
            self._cursor_sample,
            ms_to_samples(self._arv_spin.value(), self._fs),
        )
        grid_vals = channels_to_grid(arv, self._display_grid, self._emg_indices)
        masked = np.ma.masked_invalid(grid_vals)

        interp = "bilinear" if self._smooth_check.isChecked() else "nearest"
        self._image = self._ax.imshow(
            masked,
            cmap=_EMG_CMAP,
            vmin=0.0,
            vmax=self._scale_spin.value(),
            aspect="equal",
            interpolation=interp,
            origin="upper",
        )
        self._colorbar = self._figure.colorbar(self._image, cax=self._cbar_ax)
        self._colorbar.set_label("ARV (mV)", color=Colors.TEXT_SECONDARY)
        self._colorbar.ax.yaxis.set_tick_params(color=Colors.TEXT_SECONDARY)
        for lbl in self._colorbar.ax.get_yticklabels():
            lbl.set_color(Colors.TEXT_SECONDARY)
        self._ax.set_xlabel("Column", color=Colors.TEXT_SECONDARY)
        self._ax.set_ylabel("Row", color=Colors.TEXT_SECONDARY)
        self._ax.tick_params(colors=Colors.TEXT_SECONDARY)
        self._ax.set_title(
            self._electrode_name or self._grid_key,
            color=Colors.TEXT_PRIMARY,
            fontsize=10,
        )

        self._update_channel_annotations()
        self._update_selection_overlay()
        self._click_cid = self._canvas.mpl_connect('button_press_event', self._on_canvas_click)

        # --- Reference signal ---
        self._draw_ref_plot()

        self._canvas.draw_idle()
        self._set_transport_enabled(True)
        self._update_time_label()

    def _draw_ref_plot(self):
        """Draw the reference signal in _ref_ax and add the cursor line."""
        ax = self._ref_ax
        ax.clear()
        ax.set_facecolor(Colors.BG_PRIMARY)

        t_total = self._n_samples / self._fs if self._fs > 0 else 0.0

        if self._ref_data is not None and self._ref_time is not None:
            ax.plot(self._ref_time, self._ref_data,
                    color=Colors.BLUE_500, linewidth=0.8, alpha=0.9)
            ax.set_xlim(0, t_total)
            label = self._ref_combo.currentText() or "Reference"
            ax.set_ylabel(label, color=Colors.TEXT_SECONDARY, fontsize=7)
        else:
            ax.text(0.5, 0.5, "No reference signal selected",
                    ha="center", va="center", fontsize=9,
                    color=Colors.TEXT_MUTED, transform=ax.transAxes)
            ax.set_xlim(0, max(t_total, 1))

        ax.set_xlabel("Time (s)", color=Colors.TEXT_SECONDARY, fontsize=8)
        ax.tick_params(colors=Colors.TEXT_SECONDARY, labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor(Colors.BORDER_DEFAULT)

        # Cursor line — drawn on top; stored so we can update its x only
        t_cursor = self._cursor_sample / self._fs if self._fs > 0 else 0.0
        self._cursor_line = ax.axvline(
            x=t_cursor, color="#FF4444", linewidth=1.5, zorder=5
        )

        # Mouse interaction for scrubbing
        self._ref_press_cid = self._canvas.mpl_connect(
            'button_press_event', self._on_ref_press
        )
        self._ref_drag_cid = self._canvas.mpl_connect(
            'motion_notify_event', self._on_ref_drag
        )
        self._ref_release_cid = self._canvas.mpl_connect(
            'button_release_event', self._on_ref_release
        )

    def _show_no_layout_placeholder(self):
        ax = self._figure.add_subplot(111)
        ax.set_facecolor(Colors.BG_PRIMARY)
        self._figure.patch.set_facecolor(Colors.BG_PRIMARY)
        name = self._electrode_name or self._grid_key or "unknown"
        ax.text(
            0.5, 0.5,
            f"No physical layout found for '{name}'.\n\nClick 'Edit Layout…' in the sidebar\nto define a custom layout.",
            ha="center", va="center", fontsize=11,
            color=Colors.TEXT_SECONDARY,
            transform=ax.transAxes,
            wrap=True,
        )
        ax.set_axis_off()
        self._canvas.draw_idle()

    def _show_no_data_placeholder(self, msg: str):
        ax = self._figure.add_subplot(111)
        ax.set_facecolor(Colors.BG_PRIMARY)
        self._figure.patch.set_facecolor(Colors.BG_PRIMARY)
        ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=11,
                color=Colors.TEXT_SECONDARY, transform=ax.transAxes)
        ax.set_axis_off()
        self._canvas.draw_idle()

    def _set_transport_enabled(self, enabled: bool):
        self._play_btn.setEnabled(enabled)
        self._rewind_btn.setEnabled(enabled)
        self._forward_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Display overlays (channel numbers, selection status)
    # ------------------------------------------------------------------

    def _update_channel_annotations(self):
        for t in self._ch_num_texts:
            try:
                t.remove()
            except ValueError:
                pass
        self._ch_num_texts = []

        if not self._ch_num_check.isChecked() or self._ax is None or self._display_grid is None:
            self._canvas.draw_idle()
            return

        rows, cols = self._display_grid.shape
        for r in range(rows):
            for c in range(cols):
                local = self._display_grid[r, c]
                if np.isnan(local):
                    continue
                idx = int(local)
                if idx >= len(self._emg_indices):
                    continue
                ch_num = self._emg_indices[idx] + 1
                t = self._ax.text(
                    c, r, str(ch_num),
                    ha="center", va="center",
                    fontsize=7, color="white",
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="black", alpha=0.45),
                )
                self._ch_num_texts.append(t)
        self._canvas.draw_idle()

    def _update_selection_overlay(self):
        for p in self._sel_patches:
            try:
                p.remove()
            except (ValueError, AttributeError):
                pass
        self._sel_patches = []

        if not self._sel_check.isChecked() or self._ax is None or self._display_grid is None:
            self._canvas.draw_idle()
            return

        channel_status = global_state.get_channel_status()
        rows, cols = self._display_grid.shape
        for r in range(rows):
            for c in range(cols):
                local = self._display_grid[r, c]
                if np.isnan(local):
                    continue
                idx = int(local)
                if idx >= len(self._emg_indices):
                    continue
                data_col = self._emg_indices[idx]
                if data_col >= len(channel_status):
                    continue
                selected = bool(channel_status[data_col])
                color = Colors.GREEN_500 if selected else "#DD2200"
                rect = Rectangle(
                    (c - 0.5, r - 0.5), 1.0, 1.0,
                    fill=True, facecolor=color, alpha=0.25,
                    linewidth=2, edgecolor=color,
                )
                self._ax.add_patch(rect)
                self._sel_patches.append(rect)
        self._canvas.draw_idle()

    def _on_canvas_click(self, event):
        """Toggle channel selection when the user clicks a heatmap cell."""
        if not self._sel_check.isChecked():
            return
        if event.inaxes is not self._ax or event.xdata is None or event.ydata is None:
            return
        if self._display_grid is None:
            return

        col = int(round(event.xdata))
        row = int(round(event.ydata))
        n_rows, n_cols = self._display_grid.shape
        if not (0 <= row < n_rows and 0 <= col < n_cols):
            return

        local = self._display_grid[row, col]
        if np.isnan(local):
            return

        idx = int(local)
        if idx >= len(self._emg_indices):
            return

        data_col = self._emg_indices[idx]
        channel_status = global_state.get_channel_status()
        if data_col >= len(channel_status):
            return

        new_state = not bool(channel_status[data_col])
        parent = self.parent()
        if parent is not None and hasattr(parent, 'handle_single_channel_update'):
            parent.handle_single_channel_update(
                data_col, Qt.Checked if new_state else Qt.Unchecked
            )
        else:
            channel_status[data_col] = new_state

        self._update_selection_overlay()

    # ------------------------------------------------------------------
    # Reference signal scrubbing
    # ------------------------------------------------------------------

    def _on_ref_press(self, event):
        if event.button != 1:
            return
        if event.inaxes is not self._ref_ax:
            return
        if self._toolbar.mode:  # don't interfere with pan/zoom
            return
        self._ref_dragging = True
        if event.xdata is not None:
            self._seek_to_time(event.xdata)

    def _on_ref_drag(self, event):
        if not self._ref_dragging:
            return
        if event.inaxes is not self._ref_ax:
            return
        if event.xdata is not None:
            self._seek_to_time(event.xdata)

    def _on_ref_release(self, event):
        self._ref_dragging = False

    def _seek_to_time(self, t: float):
        if self._fs <= 0 or self._n_samples == 0:
            return
        sample = int(round(t * self._fs))
        self._cursor_sample = max(0, min(sample, self._n_samples - 1))
        self._update_cursor_line()
        self._render_frame()

    def _update_cursor_line(self):
        if self._cursor_line is None:
            return
        t = self._cursor_sample / self._fs if self._fs > 0 else 0.0
        self._cursor_line.set_xdata([t, t])

    # ------------------------------------------------------------------
    # Timer / playback
    # ------------------------------------------------------------------

    def _on_timer_tick(self):
        current_data = global_state.get_effective_emg_data()
        if current_data is None:
            self._timer.stop()
            self._playing = False
            self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            return

        if id(current_data) != self._data_id:
            self._data = current_data
            self._data_id = id(current_data)
            self._n_samples = current_data.shape[0]
            self._cursor_sample = 0
            self._resolve_ref_signal()
            if self._ref_ax is not None:
                self._draw_ref_plot()

        step = max(1, int(self._fs / self._fps * self._speed))
        self._cursor_sample = min(self._cursor_sample + step, self._n_samples - 1)

        if self._cursor_sample >= self._n_samples - 1:
            self._timer.stop()
            self._playing = False
            self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        self._update_cursor_line()
        self._render_frame()

    def _render_frame(self):
        if self._image is None or self._data is None or self._display_grid is None:
            return

        arv = compute_arv_window(
            self._data,
            self._cursor_sample,
            ms_to_samples(self._arv_spin.value(), self._fs),
        )
        grid_vals = channels_to_grid(arv, self._display_grid, self._emg_indices)
        masked = np.ma.masked_invalid(grid_vals)
        self._image.set_data(masked)
        self._image.set_clim(0.0, self._scale_spin.value())
        self._update_time_label()
        self._canvas.draw_idle()

    def _update_time_label(self):
        t_current = self._cursor_sample / self._fs if self._fs > 0 else 0.0
        t_total = self._n_samples / self._fs if self._fs > 0 else 0.0
        self._time_label.setText(f"t = {t_current:.3f} s / {t_total:.3f} s")

    # ------------------------------------------------------------------
    # Transport controls
    # ------------------------------------------------------------------

    def _on_play_pause(self):
        if not self._playing:
            if self._cursor_sample >= self._n_samples - 1:
                self._cursor_sample = 0
                self._update_cursor_line()
            self._fps = self._fps_spin.value()
            self._timer.start(max(1, 1000 // self._fps))
            self._playing = True
            self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self._timer.stop()
            self._playing = False
            self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def _on_rewind(self):
        seek = int(_SEEK_SECONDS * self._fs)
        self._cursor_sample = max(0, self._cursor_sample - seek)
        self._update_cursor_line()
        self._render_frame()

    def _on_forward(self):
        seek = int(_SEEK_SECONDS * self._fs)
        self._cursor_sample = min(self._n_samples - 1, self._cursor_sample + seek)
        self._update_cursor_line()
        self._render_frame()

    # ------------------------------------------------------------------
    # Settings controls
    # ------------------------------------------------------------------

    def _on_grid_changed(self, key: str):
        self._grid_key = key
        self._resolve_grid_layout()
        self._populate_ref_selector()
        self._reset_plot()

    def _on_ref_changed(self, _index: int):
        self._resolve_ref_signal()
        if self._ref_ax is not None:
            self._draw_ref_plot()
            self._canvas.draw_idle()

    def _on_arv_changed(self, _value: float):
        config.set(Settings.DENSITY_ARV_WINDOW_MS, _value)
        self._render_frame()

    def _on_scale_changed(self, _value: float):
        if self._image is not None:
            self._image.set_clim(0.0, _value)
            self._canvas.draw_idle()

    def _on_speed_changed(self, text: str):
        try:
            self._speed = float(text.replace("×", ""))
        except ValueError:
            self._speed = 1.0

    def _on_fps_changed(self, value: int):
        self._fps = value
        config.set(Settings.DENSITY_PLAYBACK_FPS, value)
        if self._playing:
            self._timer.start(max(1, 1000 // self._fps))

    def _on_smooth_changed(self, state: int):
        if self._image is None:
            return
        self._image.set_interpolation("bilinear" if state == Qt.Checked else "nearest")
        self._canvas.draw_idle()

    def _on_ch_num_changed(self, _state: int):
        self._update_channel_annotations()

    def _on_sel_changed(self, _state: int):
        self._update_selection_overlay()

    def _open_layout_builder(self):
        key = self._grid_combo.currentText()
        existing_layouts = config.get(Settings.CUSTOM_ELECTRODE_LAYOUTS, {}) or {}
        initial = existing_layouts.get(self._electrode_name or key)
        name = self._electrode_name or key
        dlg = LayoutBuilderDialog(
            electrode_name=name,
            n_channels=self._n_grid_channels or 64,
            initial=initial,
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            logger.info("Custom layout saved for '%s'", name)
            self.refresh_grid()

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _groupbox_style() -> str:
        return f"""
            QGroupBox {{
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
                font-size: {Fonts.SIZE_SM};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD};
                margin-top: 8px;
                padding-top: {Spacing.SM}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {Spacing.SM}px;
                padding: 0 {Spacing.XS}px;
            }}
        """

    @staticmethod
    def _combobox_style() -> str:
        return f"""
            QComboBox {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px {Spacing.SM}px;
                font-size: {Fonts.SIZE_BASE};
            }}
            QComboBox::drop-down {{ border: none; }}
        """

    @staticmethod
    def _spinbox_style() -> str:
        return f"""
            QDoubleSpinBox, QSpinBox {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px {Spacing.SM}px;
                font-size: {Fonts.SIZE_BASE};
            }}
        """

    @staticmethod
    def _checkbox_style() -> str:
        return f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {Fonts.SIZE_BASE};
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 3px;
                background-color: {Colors.BG_PRIMARY};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.BLUE_500};
                border-color: {Colors.BLUE_500};
            }}
        """
