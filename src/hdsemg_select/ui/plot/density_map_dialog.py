from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QPushButton, QDoubleSpinBox, QSpinBox,
    QSlider, QLabel, QWidget, QSizePolicy, QStyle,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

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


class DensityMapDialog(QDialog):
    """Animated ARV heatmap over the physical electrode grid.

    Shows intensity (Average Rectified Value) per electrode cell as a
    Blue→Cyan→Yellow→Red colour map.  Playback is driven by a QTimer.
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

        # Grid / layout cache (for the currently selected grid key)
        self._grid_key: Optional[str] = None
        self._display_grid: Optional[np.ndarray] = None
        self._emg_indices: list = []
        self._electrode_name: str = ""
        self._n_grid_channels: int = 0

        # Matplotlib image handle (set on first render)
        self._image = None
        self._colorbar = None
        self._ax = None

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

        # Main split: sidebar + plot
        main_split = QHBoxLayout()
        main_split.setSpacing(Spacing.MD)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
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
        self._scale_spin.setSuffix(" (max)")
        default_scale = config.get(Settings.DENSITY_SCALE_MAX_MV, None)
        if default_scale is None:
            default_scale = max(0.001, global_state.max_amplitude or 1.0)
        self._scale_spin.setValue(default_scale)
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

        # --- Transport bar ---
        transport = QWidget()
        transport.setFixedHeight(52)
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

        self._time_slider = QSlider(Qt.Horizontal)
        self._time_slider.setRange(0, 0)
        self._time_slider.valueChanged.connect(self._on_slider_changed)
        transport_layout.addWidget(self._time_slider, stretch=1)

        self._time_label = QLabel("t = 0.000 s / 0.000 s")
        self._time_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_SM}; font-family: monospace;")
        self._time_label.setFixedWidth(200)
        transport_layout.addWidget(self._time_label)

        root.addWidget(transport)
        self.resize(1100, 700)

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
            # Pre-select the grid currently active in the handler
            current = self._grid_handler.get_selected_grid()
            if current and self._grid_combo.findText(current) >= 0:
                self._grid_combo.setCurrentText(current)
        self._grid_combo.blockSignals(False)

    def _load_data(self):
        data = global_state.get_effective_emg_data()
        if data is None:
            self._data = None
            self._n_samples = 0
            self._time_slider.setRange(0, 0)
            self._show_no_data_placeholder("No file loaded.")
            return

        self._data = data
        self._data_id = id(data)
        self._n_samples = data.shape[0]

        emg_file = global_state.get_emg_file()
        self._fs = float(emg_file.sampling_frequency) if emg_file else 2048.0

        self._time_slider.setRange(0, max(0, self._n_samples - 1))
        self._cursor_sample = 0
        self._time_slider.setValue(0)

        self._resolve_grid_layout()
        self._reset_plot()

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

        # Extract electrode name the same way GridSetupHandler does
        self._electrode_name = self._grid_handler._extract_electrode_name(grid.emg_indices)

        display_grid = get_display_grid(self._electrode_name, grid.rows, grid.cols)
        self._display_grid = display_grid

    # ------------------------------------------------------------------
    # Plot management
    # ------------------------------------------------------------------

    def _reset_plot(self):
        self._figure.clear()
        self._image = None
        self._colorbar = None
        self._ax = None

        if self._display_grid is None:
            self._show_no_layout_placeholder()
            self._set_transport_enabled(False)
            return

        if self._data is None:
            self._show_no_data_placeholder("No data available.")
            self._set_transport_enabled(False)
            return

        self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor(Colors.BG_PRIMARY)
        self._figure.patch.set_facecolor(Colors.BG_PRIMARY)

        # Render first frame
        arv = compute_arv_window(
            self._data,
            self._cursor_sample,
            ms_to_samples(self._arv_spin.value(), self._fs),
        )
        grid_vals = channels_to_grid(arv, self._display_grid, self._emg_indices)
        masked = np.ma.masked_invalid(grid_vals)

        self._image = self._ax.imshow(
            masked,
            cmap=_EMG_CMAP,
            vmin=0.0,
            vmax=self._scale_spin.value(),
            aspect="equal",
            interpolation="nearest",
            origin="upper",
        )
        self._colorbar = self._figure.colorbar(self._image, ax=self._ax)
        self._colorbar.set_label("ARV", color=Colors.TEXT_SECONDARY)
        self._ax.set_xlabel("Column", color=Colors.TEXT_SECONDARY)
        self._ax.set_ylabel("Row", color=Colors.TEXT_SECONDARY)
        self._ax.tick_params(colors=Colors.TEXT_SECONDARY)
        self._ax.set_title(
            f"{self._electrode_name or self._grid_key}",
            color=Colors.TEXT_PRIMARY,
            fontsize=10,
        )

        self._canvas.draw_idle()
        self._set_transport_enabled(True)
        self._update_time_label()

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
        self._time_slider.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Timer / playback
    # ------------------------------------------------------------------

    def _on_timer_tick(self):
        # Detect crop/data change
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
            self._time_slider.setRange(0, max(0, self._n_samples - 1))

        step = max(1, int(self._fs / self._fps * self._speed))
        self._cursor_sample = min(self._cursor_sample + step, self._n_samples - 1)

        if self._cursor_sample >= self._n_samples - 1:
            self._timer.stop()
            self._playing = False
            self._play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        self._time_slider.blockSignals(True)
        self._time_slider.setValue(self._cursor_sample)
        self._time_slider.blockSignals(False)

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
                self._time_slider.setValue(0)
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
        self._time_slider.blockSignals(True)
        self._time_slider.setValue(self._cursor_sample)
        self._time_slider.blockSignals(False)
        self._render_frame()

    def _on_forward(self):
        seek = int(_SEEK_SECONDS * self._fs)
        self._cursor_sample = min(self._n_samples - 1, self._cursor_sample + seek)
        self._time_slider.blockSignals(True)
        self._time_slider.setValue(self._cursor_sample)
        self._time_slider.blockSignals(False)
        self._render_frame()

    def _on_slider_changed(self, value: int):
        self._cursor_sample = value
        self._render_frame()

    # ------------------------------------------------------------------
    # Settings controls
    # ------------------------------------------------------------------

    def _on_grid_changed(self, key: str):
        self._grid_key = key
        self._resolve_grid_layout()
        self._reset_plot()

    def _on_arv_changed(self, _value: float):
        config.set(Settings.DENSITY_ARV_WINDOW_MS, _value)
        self._render_frame()

    def _on_scale_changed(self, _value: float):
        config.set(Settings.DENSITY_SCALE_MAX_MV, _value)
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
