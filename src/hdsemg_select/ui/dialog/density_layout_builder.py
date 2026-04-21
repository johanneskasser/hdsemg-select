from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QSpinBox, QComboBox, QLabel, QPushButton,
    QGridLayout, QWidget, QScrollArea, QMessageBox,
)
from PyQt5.QtCore import Qt

from hdsemg_select.config.config_enums import Settings
from hdsemg_select.config.config_manager import config
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Fonts, Styles


class LayoutBuilderDialog(QDialog):
    """Dialog for creating or editing a physical electrode grid layout.

    The user picks how many rows and columns the grid has, then assigns a
    local electrode index (or "(empty)") to each cell via comboboxes.
    On accept the layout is persisted to the config file.
    """

    def __init__(
        self,
        electrode_name: str,
        n_channels: int,
        initial: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._electrode_name = electrode_name
        self._n_channels = n_channels
        self._initial = initial or {}
        self._cell_combos: list[list[QComboBox]] = []

        self.setWindowTitle(f"Build Layout — {electrode_name}")
        self.resize(700, 500)
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self._init_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_layout(self) -> dict:
        """Return the current layout as a dict compatible with the config schema."""
        rows = self._rows_spin.value()
        cols = self._cols_spin.value()
        grid = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                text = self._cell_combos[r][c].currentText()
                row_data.append(None if text == "(empty)" else int(text) - 1)
            grid.append(row_data)
        return {"rows": rows, "cols": cols, "grid": grid}

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        # Header
        header = QLabel(f"Define physical layout for <b>{self._electrode_name}</b>")
        header.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_LG};")
        root.addWidget(header)

        hint = QLabel(
            "Set the number of rows and columns, then assign an electrode index to each cell. "
            "Leave unused cells as (empty)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        root.addWidget(hint)

        # Dimension controls
        dim_box = QGroupBox("Grid Dimensions")
        dim_box.setStyleSheet(self._groupbox_style())
        dim_layout = QHBoxLayout(dim_box)
        dim_layout.setSpacing(Spacing.MD)

        dim_layout.addWidget(QLabel("Rows:"))
        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 16)
        self._rows_spin.setValue(self._initial.get("rows", 4))
        self._rows_spin.setStyleSheet(self._spinbox_style())
        dim_layout.addWidget(self._rows_spin)

        dim_layout.addWidget(QLabel("Columns:"))
        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 16)
        self._cols_spin.setValue(self._initial.get("cols", 8))
        self._cols_spin.setStyleSheet(self._spinbox_style())
        dim_layout.addWidget(self._cols_spin)

        dim_layout.addStretch()
        root.addWidget(dim_box)

        # Scrollable cell grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: {BorderRadius.MD}; }}")
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(Spacing.XS)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll, stretch=1)

        self._rebuild_cell_grid()

        self._rows_spin.valueChanged.connect(self._rebuild_cell_grid)
        self._cols_spin.valueChanged.connect(self._rebuild_cell_grid)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(Styles.button_secondary())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Layout")
        save_btn.setStyleSheet(Styles.button_primary())
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    def _rebuild_cell_grid(self):
        rows = self._rows_spin.value()
        cols = self._cols_spin.value()

        # Snapshot current assignments before clearing
        old_grid = []
        for r_combos in self._cell_combos:
            old_row = []
            for combo in r_combos:
                old_row.append(combo.currentText())
            old_grid.append(old_row)

        # Clear grid layout
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Column header labels
        for c in range(cols):
            lbl = QLabel(str(c + 1))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Fonts.SIZE_XS};")
            self._grid_layout.addWidget(lbl, 0, c + 1)

        # Row header labels + combo cells
        options = ["(empty)"] + [str(i) for i in range(1, self._n_channels + 1)]
        self._cell_combos = []
        initial_grid = self._initial.get("grid", [])

        for r in range(rows):
            row_combos = []
            row_lbl = QLabel(str(r + 1))
            row_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Fonts.SIZE_XS};")
            self._grid_layout.addWidget(row_lbl, r + 1, 0)

            for c in range(cols):
                combo = QComboBox()
                combo.addItems(options)
                combo.setFixedWidth(72)
                combo.setStyleSheet(self._combobox_style())

                # Restore value: prefer snapshot, then initial, default to (empty)
                if r < len(old_grid) and c < len(old_grid[r]):
                    text = old_grid[r][c]
                    idx = combo.findText(text)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                elif initial_grid and r < len(initial_grid) and c < len(initial_grid[r]):
                    v = initial_grid[r][c]
                    if v is None:
                        combo.setCurrentIndex(0)
                    else:
                        idx = combo.findText(str(v + 1))
                        if idx >= 0:
                            combo.setCurrentIndex(idx)

                self._grid_layout.addWidget(combo, r + 1, c + 1)
                row_combos.append(combo)
            self._cell_combos.append(row_combos)

    def _on_save(self):
        layout = self.get_layout()
        rows, cols = layout["rows"], layout["cols"]
        grid = layout["grid"]

        # Check for duplicate assignments
        assigned = [v for row in grid for v in row if v is not None]
        if len(assigned) != len(set(assigned)):
            QMessageBox.warning(
                self,
                "Duplicate Electrodes",
                "Each electrode index may only appear once in the grid. "
                "Please fix duplicate assignments.",
            )
            return

        existing = config.get(Settings.CUSTOM_ELECTRODE_LAYOUTS, {}) or {}
        existing[self._electrode_name] = layout
        config.set(Settings.CUSTOM_ELECTRODE_LAYOUTS, existing)
        self.accept()

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
    def _spinbox_style() -> str:
        return f"""
            QSpinBox {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px {Spacing.SM}px;
                font-size: {Fonts.SIZE_BASE};
                min-width: 60px;
            }}
        """

    @staticmethod
    def _combobox_style() -> str:
        return f"""
            QComboBox {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM};
                padding: {Spacing.XS}px;
                font-size: {Fonts.SIZE_XS};
            }}
            QComboBox::drop-down {{ border: none; }}
        """
