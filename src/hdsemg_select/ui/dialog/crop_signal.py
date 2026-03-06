# crop_signal.py
import numpy as np
from PyQt5 import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector

from hdsemg_select._log.log_config import logger
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Fonts, Styles


def _normalize_desc(desc) -> str:
    """Convert any description value (str, array, nested) to a display string."""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, np.ndarray):
        if desc.size == 1:
            return _normalize_desc(desc.item())
        return " ".join(_normalize_desc(x) for x in desc.flat)
    return str(desc)


class CropSignalDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._crop_range: tuple[int, int] | None = None
        self._threshold_lines: list = []
        self._span_selector = None
        self._lower = 0
        self._upper = 0
        self._first_click: int | None = None
        self._checkboxes: dict = {}  # grid_uid -> list[QCheckBox]
        self._channel_indices: dict = {}  # grid_uid -> list[int]  (data column indices)

        self._init_ui()

    # ------------------------------------------------------------------ #
    # UI setup                                                             #
    # ------------------------------------------------------------------ #
    def _init_ui(self):
        self.setWindowTitle("Crop Signal")
        self.resize(1400, 800)
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")

        emg_file = global_state.get_emg_file()
        if emg_file is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "No file loaded.")
            QtCore.QTimer.singleShot(0, self.reject)
            return

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        main_layout.setSpacing(Spacing.LG)

        # Header
        header = QtWidgets.QLabel("Crop Signal")
        header.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_XXL}; font-weight: {Fonts.WEIGHT_BOLD};")
        instruction = QtWidgets.QLabel(
            "🖱️ Drag to select region  •  🖱️ Click twice to set start/end  •  🔍 Toolbar for zoom/pan"
        )
        instruction.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_BASE};")
        instruction.setWordWrap(True)
        main_layout.addWidget(header)
        main_layout.addWidget(instruction)

        # Content: plot (left) + sidebar (right)
        content = QtWidgets.QHBoxLayout()
        content.setSpacing(Spacing.LG)

        # --- Plot area ---
        plot_frame = QtWidgets.QFrame()
        plot_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.LG};
            }}
        """)
        plot_layout = QtWidgets.QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)

        self._figure = Figure(facecolor=Colors.BG_PRIMARY)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor(Colors.BG_PRIMARY)

        self._toolbar = NavigationToolbar(self._canvas, self)
        self._toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px;
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
        plot_layout.addWidget(self._toolbar)
        plot_layout.addWidget(self._canvas)

        # ROI info bar
        roi_bar = QtWidgets.QHBoxLayout()
        roi_bar.setSpacing(Spacing.MD)
        self._roi_start_lbl = QtWidgets.QLabel("Start: 0")
        self._roi_end_lbl = QtWidgets.QLabel("End: 0")
        self._roi_dur_lbl = QtWidgets.QLabel("Duration: 0 samples")
        for lbl in (self._roi_start_lbl, self._roi_end_lbl, self._roi_dur_lbl):
            lbl.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.TEXT_PRIMARY};
                    font-size: {Fonts.SIZE_SM};
                    font-weight: {Fonts.WEIGHT_MEDIUM};
                    background-color: {Colors.GRAY_100};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {BorderRadius.SM};
                    padding: {Spacing.XS}px {Spacing.SM}px;
                }}
            """)
        roi_bar.addWidget(self._roi_start_lbl)
        roi_bar.addWidget(self._roi_end_lbl)
        roi_bar.addWidget(self._roi_dur_lbl)
        roi_bar.addStretch()
        plot_layout.addLayout(roi_bar)
        content.addWidget(plot_frame, stretch=3)

        # --- Sidebar ---
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumWidth(350)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        panel = QtWidgets.QWidget()
        panel.setStyleSheet("background-color: transparent;")
        vbox = QtWidgets.QVBoxLayout(panel)
        vbox.setSpacing(Spacing.SM)
        vbox.setContentsMargins(0, 0, 0, 0)

        # Section header
        ref_header = QtWidgets.QLabel("Channels")
        ref_header.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_LG}; font-weight: {Fonts.WEIGHT_SEMIBOLD};")
        vbox.addWidget(ref_header)
        hint = QtWidgets.QLabel("Select channels to display in the plot:")
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        vbox.addWidget(hint)

        # Build grouped checkboxes
        description = emg_file.description
        self._build_channel_groups(vbox, emg_file, description)

        vbox.addStretch(1)

        # Buttons
        btn_layout = QtWidgets.QVBoxLayout()
        btn_layout.setSpacing(Spacing.SM)
        reset_btn = QtWidgets.QPushButton("Reset Selection")
        reset_btn.setStyleSheet(Styles.button_secondary())
        reset_btn.clicked.connect(self._reset_selection)
        btn_layout.addWidget(reset_btn)
        ok_btn = QtWidgets.QPushButton("Apply & Close")
        ok_btn.setStyleSheet(Styles.button_primary())
        ok_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(ok_btn)
        vbox.addLayout(btn_layout)

        scroll.setWidget(panel)
        content.addWidget(scroll, stretch=1)
        main_layout.addLayout(content)

        # Initialize range to full signal
        n_samples = emg_file.data.shape[0]
        # Respect existing crop from state if any
        existing = global_state.get_crop_range()
        if existing is not None:
            self._lower, self._upper = existing
        else:
            self._lower, self._upper = 0, max(0, n_samples - 1)

        # Span selector
        self._span_selector = SpanSelector(
            self._ax, self._on_span_select, 'horizontal',
            useblit=True,
            props=dict(alpha=0.3, facecolor=Colors.BLUE_500),
            interactive=True, drag_from_anywhere=True
        )
        self._canvas.mpl_connect('button_press_event', self._on_click)

        self._update_plot()
        self._update_roi_info()

    def _build_channel_groups(self, vbox, emg_file, description):
        """Build one QGroupBox per grid, listing all its channels as checkboxes."""
        seen_indices = set()

        for grid in emg_file.grids:
            uid = grid.grid_uid
            all_ch_indices = list(dict.fromkeys(
                [i for i in (grid.emg_indices or []) + (grid.ref_indices or []) if i is not None]
            ))

            if not all_ch_indices:
                continue

            box = QtWidgets.QGroupBox(f"Grid: {grid.grid_key}")
            box.setStyleSheet(Styles.groupbox())
            box_layout = QtWidgets.QVBoxLayout()
            box_layout.setSpacing(Spacing.XS)

            self._checkboxes[uid] = []
            self._channel_indices[uid] = all_ch_indices

            ref_set = set(grid.ref_indices or [])
            requested = grid.requested_path_idx
            performed = grid.performed_path_idx

            for ch_idx in all_ch_indices:
                seen_indices.add(ch_idx)
                desc_str = _normalize_desc(description[ch_idx]) if ch_idx < len(description) else f"Ch {ch_idx}"

                # Default: check ref channels that match requested/performed path
                if performed is not None and ch_idx == performed:
                    checked = True
                elif requested is not None and ch_idx == requested:
                    checked = True
                elif performed is None and requested is None and ch_idx in ref_set:
                    checked = True
                else:
                    checked = False

                cb = QtWidgets.QCheckBox(f"Ch{ch_idx} – {desc_str}")
                cb.setChecked(checked)
                cb.stateChanged.connect(self._update_plot)
                cb.setStyleSheet(f"""
                    QCheckBox {{
                        color: {Colors.TEXT_PRIMARY};
                        font-size: {Fonts.SIZE_BASE};
                        spacing: {Spacing.SM}px;
                    }}
                    QCheckBox::indicator {{
                        width: 16px; height: 16px;
                        border-radius: {BorderRadius.SM};
                        border: 1px solid {Colors.BORDER_DEFAULT};
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {Colors.BLUE_600};
                        border-color: {Colors.BLUE_600};
                    }}
                """)
                box_layout.addWidget(cb)
                self._checkboxes[uid].append(cb)

            box.setLayout(box_layout)
            vbox.addWidget(box)

        # Channels not belonging to any grid
        all_ch_count = len(description) if description is not None else 0
        orphan_indices = [i for i in range(all_ch_count) if i not in seen_indices]
        if orphan_indices:
            box = QtWidgets.QGroupBox("Other Channels")
            box.setStyleSheet(Styles.groupbox())
            box_layout = QtWidgets.QVBoxLayout()
            uid = "__other__"
            self._checkboxes[uid] = []
            self._channel_indices[uid] = orphan_indices
            for ch_idx in orphan_indices:
                desc_str = _normalize_desc(description[ch_idx]) if ch_idx < all_ch_count else f"Ch {ch_idx}"
                cb = QtWidgets.QCheckBox(f"Ch{ch_idx} – {desc_str}")
                cb.setChecked(False)
                cb.stateChanged.connect(self._update_plot)
                box_layout.addWidget(cb)
                self._checkboxes[uid].append(cb)
            box.setLayout(box_layout)
            vbox.addWidget(box)

    # ------------------------------------------------------------------ #
    # Plot                                                                 #
    # ------------------------------------------------------------------ #
    def _update_plot(self):
        self._threshold_lines.clear()
        self._ax.clear()
        self._ax.set_facecolor(Colors.BG_PRIMARY)

        scaled = global_state.get_scaled_data()
        if scaled is None:
            self._canvas.draw_idle()
            return

        emg_file = global_state.get_emg_file()
        if emg_file is None:
            self._canvas.draw_idle()
            return

        for uid, cbs in self._checkboxes.items():
            ch_indices = self._channel_indices.get(uid, [])
            for cb, ch_idx in zip(cbs, ch_indices):
                if cb.isChecked() and ch_idx < scaled.shape[1]:
                    desc = _normalize_desc(
                        emg_file.description[ch_idx]
                        if ch_idx < len(emg_file.description) else f"Ch{ch_idx}"
                    )
                    self._ax.plot(scaled[:, ch_idx], label=f"Ch{ch_idx}: {desc}", linewidth=1.2)

        self._ax.set_xlabel("Sample Index", fontsize=11)
        self._ax.set_ylabel("Amplitude", fontsize=11)
        self._ax.legend(loc='upper right', framealpha=0.9, fontsize=8)
        self._ax.grid(True, alpha=0.3, linestyle='--')

        # Recreate span selector (ax was cleared); disconnect old one first
        if self._span_selector is not None:
            self._span_selector.disconnect_events()
        self._span_selector = SpanSelector(
            self._ax, self._on_span_select, 'horizontal',
            useblit=True,
            props=dict(alpha=0.3, facecolor=Colors.BLUE_500),
            interactive=True, drag_from_anywhere=True
        )
        self._draw_threshold_lines()
        self._canvas.draw_idle()

    def _draw_threshold_lines(self):
        self._threshold_lines.clear()

        if self._first_click is not None:
            line = self._ax.axvline(self._first_click, color=Colors.BLUE_600, linestyle='--', linewidth=2)
            self._threshold_lines.append(line)
        elif self._lower != 0 or self._upper != 0:
            l1 = self._ax.axvline(self._lower, color=Colors.GREEN_600, linestyle='-', linewidth=2, alpha=0.7)
            l2 = self._ax.axvline(self._upper, color=Colors.GREEN_600, linestyle='-', linewidth=2, alpha=0.7)
            span = self._ax.axvspan(self._lower, self._upper, alpha=0.15, color=Colors.GREEN_500)
            self._threshold_lines.extend([l1, l2, span])

        self._canvas.draw_idle()

    # ------------------------------------------------------------------ #
    # Interaction                                                          #
    # ------------------------------------------------------------------ #
    def _on_span_select(self, xmin, xmax):
        self._first_click = None
        self._lower = int(xmin)
        self._upper = int(xmax)
        self._update_roi_info()
        self._draw_threshold_lines()

    def _on_click(self, event):
        if event.inaxes != self._ax or event.button != 1:
            return
        if self._toolbar.mode != '':
            return
        if event.xdata is None:
            return
        x = int(event.xdata)
        if self._first_click is None:
            self._first_click = x
            self._draw_threshold_lines()
        else:
            self._lower = min(self._first_click, x)
            self._upper = max(self._first_click, x)
            self._first_click = None
            self._update_roi_info()
            self._draw_threshold_lines()

    def _update_roi_info(self):
        dur = self._upper - self._lower
        self._roi_start_lbl.setText(f"Start: {self._lower}")
        self._roi_end_lbl.setText(f"End: {self._upper}")
        self._roi_dur_lbl.setText(f"Duration: {dur} samples")

    def _reset_selection(self):
        data = global_state.get_emg_file()
        if data is not None:
            n = data.data.shape[0]
            self._lower, self._upper = 0, max(0, n - 1)
        self._first_click = None
        self._update_roi_info()
        self._update_plot()

    def _on_apply(self):
        self._crop_range = (self._lower, self._upper)
        logger.info("Crop range selected: %s", self._crop_range)
        self.accept()

    def get_crop_range(self) -> tuple[int, int] | None:
        return self._crop_range
