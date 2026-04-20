from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QHBoxLayout, QFrame, QScrollArea, QWidget, QButtonGroup, QRadioButton,
)

from hdsemg_select.state.enum.layout_mode_enums import FiberMode, LayoutMode
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Fonts, Styles


class GridCard(QFrame):
    """Selectable card representing one grid."""

    selected = pyqtSignal(str)  # emits grid_key

    def __init__(self, grid, parent=None):
        super().__init__(parent)
        self._grid_key = grid.grid_key
        self._is_selected = False

        self.setCursor(Qt.PointingHandCursor)
        self.setLineWidth(1)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.SM)

        self._radio = QRadioButton()
        self._radio.setFocusPolicy(Qt.NoFocus)
        self._radio.toggled.connect(self._on_radio_toggled)
        layout.addWidget(self._radio)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Primary line: muscle name (if available) or grid key
        primary_text = grid.muscle if grid.muscle else grid.grid_key
        self._primary = QLabel(primary_text)
        self._primary.setStyleSheet(
            f"font-size: {Fonts.SIZE_BASE}; font-weight: {Fonts.WEIGHT_SEMIBOLD}; color: {Colors.TEXT_PRIMARY};"
        )
        text_layout.addWidget(self._primary)

        # Secondary line: dimensions · IED · grid_key (when muscle shown on primary)
        parts = [f"{grid.rows}×{grid.cols}", f"{grid.ied_mm} mm IED"]
        if grid.muscle:
            parts.append(grid.grid_key)
        subtitle = " · ".join(parts)
        self._secondary = QLabel(subtitle)
        self._secondary.setStyleSheet(
            f"font-size: {Fonts.SIZE_SM}; color: {Colors.TEXT_MUTED};"
        )
        text_layout.addWidget(self._secondary)

        layout.addLayout(text_layout)
        layout.addStretch()

        self._update_style()

    # ------------------------------------------------------------------

    @property
    def grid_key(self) -> str:
        return self._grid_key

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._radio.blockSignals(True)
        self._radio.setChecked(selected)
        self._radio.blockSignals(False)
        self._update_style()

    def _on_radio_toggled(self, checked: bool):
        if checked:
            self.selected.emit(self._grid_key)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._radio.setChecked(True)
        super().mousePressEvent(event)

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet(
                f"QFrame {{ background-color: {Colors.BLUE_50};"
                f" border: 1px solid {Colors.BLUE_500};"
                f" border-radius: {BorderRadius.MD}; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: {Colors.BG_PRIMARY};"
                f" border: 1px solid {Colors.BORDER_DEFAULT};"
                f" border-radius: {BorderRadius.MD}; }}"
                f"QFrame:hover {{ border-color: {Colors.GRAY_400}; }}"
            )


class GridCardSelector(QWidget):
    """Scrollable list of GridCard items with single selection."""

    selection_changed = pyqtSignal(str)  # emits grid_key

    def __init__(self, grids, selected_key: str | None, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameStyle(QFrame.NoFrame)
        scroll.setMaximumHeight(260)

        container = QWidget()
        self._card_layout = QVBoxLayout(container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(Spacing.XS)

        self._cards: list[GridCard] = []
        self._selected_key: str | None = None

        for grid in grids:
            card = GridCard(grid)
            card.selected.connect(self._on_card_selected)
            self._cards.append(card)
            self._card_layout.addWidget(card)

        self._card_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if selected_key:
            self._select(selected_key)
        elif self._cards:
            self._select(self._cards[0].grid_key)

    def current_key(self) -> str | None:
        return self._selected_key

    def _on_card_selected(self, grid_key: str):
        self._select(grid_key)
        self.selection_changed.emit(grid_key)

    def _select(self, grid_key: str):
        self._selected_key = grid_key
        for card in self._cards:
            card.set_selected(card.grid_key == grid_key)


class GridOrientationDialog(QDialog):
    def __init__(self, parent, apply_callback):
        super().__init__(parent)
        self.setWindowTitle("Select Grid and Orientation")
        self.setMinimumWidth(400)
        self.apply_callback = apply_callback

        grids = global_state.get_emg_file().grids
        if not grids:
            return

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # --- Grid selector ---
        grid_label = QLabel("Select Grid:")
        grid_label.setStyleSheet(
            f"font-size: {Fonts.SIZE_BASE}; font-weight: {Fonts.WEIGHT_SEMIBOLD};"
        )
        layout.addWidget(grid_label)

        currently_selected = parent.grid_setup_handler.get_selected_grid()
        self._grid_selector = GridCardSelector(grids, currently_selected)
        layout.addWidget(self._grid_selector)

        # --- Orientation selector ---
        orientation_label = QLabel("Orientation (parallel to fibers):")
        orientation_label.setStyleSheet(
            f"font-size: {Fonts.SIZE_BASE}; font-weight: {Fonts.WEIGHT_SEMIBOLD};"
        )
        tooltip_text = (
            "Are the HD-sEMG matrix n rows or m columns aligned in "
            "<b>parallel</b> with the muscle fibers?"
        )
        orientation_label.setToolTip(tooltip_text)

        info_icon = QLabel()
        info_icon.setPixmap(
            self.style().standardIcon(self.style().SP_MessageBoxInformation).pixmap(16, 16)
        )
        info_icon.setToolTip(tooltip_text)

        orientation_label_layout = QHBoxLayout()
        orientation_label_layout.addWidget(orientation_label)
        orientation_label_layout.addWidget(info_icon)
        orientation_label_layout.addStretch(1)
        layout.addLayout(orientation_label_layout)

        self.orientation_combo = QComboBox()
        self.orientation_combo.setStyleSheet(Styles.combobox())
        self.orientation_combo.addItem("Rows parallel to fibers", LayoutMode.ROWS)
        self.orientation_combo.addItem("Columns parallel to fibers", LayoutMode.COLUMNS)

        currently_selected_layout = global_state.get_layout_for_fiber(FiberMode.PARALLEL)
        if currently_selected_layout:
            self.orientation_combo.setCurrentIndex(
                self.orientation_combo.findData(currently_selected_layout)
            )
        else:
            self.orientation_combo.setCurrentIndex(LayoutMode.COLUMNS)

        layout.addWidget(self.orientation_combo)

        # --- OK button ---
        ok_button = QPushButton("Apply")
        ok_button.setStyleSheet(Styles.button_primary())
        ok_button.clicked.connect(self.on_ok)
        layout.addWidget(ok_button)

    def on_ok(self):
        selected_grid = self._grid_selector.current_key()
        if selected_grid is None:
            return
        selected_layout_mode = self.orientation_combo.currentData()
        selected_fiber_mode = FiberMode.PARALLEL
        if global_state.get_layout_for_fiber(selected_fiber_mode) == selected_layout_mode:
            self.apply_callback(selected_grid, selected_fiber_mode, self, orientation_changed=False)
        else:
            global_state.set_fiber_layout(selected_fiber_mode, selected_layout_mode)
            self.apply_callback(selected_grid, selected_fiber_mode, self, orientation_changed=True)
