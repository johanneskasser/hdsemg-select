"""Confirm which QC-failing channels to deselect.

QC never changes a selection on its own: it proposes, the researcher
decides, and every measured value is stored in the JSON either way.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from hdsemg_select.select_logic.global_amplitude_qc import CHECK_LABELS
from hdsemg_select.ui.theme import Colors, Fonts


class GaQcSuggestionDialog(QDialog):
    """Lists the failing channels with the reason each was flagged."""

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self._result = result
        self._failing = list(result.failing)

        self.setWindowTitle("Suggested Deselection")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self.resize(660, 580)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        banner = QLabel(
            f"QC found <b>{len(self._failing)} channels</b> in grid "
            f"'{self._result.grid_key}' that fail at least one check. Nothing is "
            f"deselected until you confirm, and every measured value is stored in the "
            f"JSON whichever way you decide."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"background-color: {Colors.YELLOW_50}; border: 1px solid {Colors.YELLOW_600}; "
            f"border-radius: 6px; padding: 10px 12px; color: {Colors.YELLOW_600}; "
            f"font-size: {Fonts.SIZE_SM};"
        )
        root.addWidget(banner)

        self._table = QTableWidget(len(self._failing), 4)
        self._table.setHorizontalHeaderLabels(["", "Channel", "CQI", "Why it was flagged"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        for row, channel in enumerate(sorted(self._failing, key=lambda c: c.cqi)):
            tick = QTableWidgetItem()
            tick.setFlags(tick.flags() | Qt.ItemIsUserCheckable)
            tick.setCheckState(Qt.Checked)
            tick.setData(Qt.UserRole + 1, channel.channel_index)
            self._table.setItem(row, 0, tick)
            self._table.setItem(row, 1, QTableWidgetItem(f"Ch {channel.channel_index + 1}"))
            cqi = QTableWidgetItem(f"{channel.cqi}")
            cqi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 2, cqi)
            self._table.setItem(row, 3, QTableWidgetItem(_reason(channel)))

        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.itemChanged.connect(lambda _: self._update_count())
        root.addWidget(self._table, stretch=1)

        note = QLabel(
            "Deselected channels keep their data in the .mat file — the JSON records the "
            "selection. Re-running QC after deselecting recomputes the global amplitude "
            "over the channels that remain."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: {Fonts.SIZE_XS}; color: {Colors.TEXT_MUTED};")
        root.addWidget(note)

        footer = QHBoxLayout()
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"font-size: {Fonts.SIZE_SM}; color: {Colors.TEXT_SECONDARY};")
        footer.addWidget(self._count_lbl)

        toggle = QPushButton("Toggle all")
        toggle.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BG_PRIMARY}; "
            f"color: {Colors.BLUE_600}; border: 1px solid {Colors.BLUE_500}; "
            f"border-radius: 6px; padding: 8px 14px; }}"
        )
        toggle.clicked.connect(self._toggle_all)
        footer.addWidget(toggle)
        footer.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self._apply_btn = buttons.addButton("Deselect channels", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        root.addLayout(footer)

        self._update_count()

    def _toggle_all(self):
        target = Qt.Unchecked if self.selected_channels() else Qt.Checked
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            self._table.item(row, 0).setCheckState(target)
        self._table.blockSignals(False)
        self._update_count()

    def _update_count(self):
        chosen = len(self.selected_channels())
        self._count_lbl.setText(f"{chosen} of {len(self._failing)} ticked")
        self._apply_btn.setText(
            "Deselect channels" if chosen == 0 else f"Deselect {chosen} channels")
        self._apply_btn.setEnabled(chosen > 0)

    def selected_channels(self) -> list:
        """The channel indices the user left ticked."""
        chosen = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                chosen.append(int(item.data(Qt.UserRole + 1)))
        return chosen


def _reason(channel) -> str:
    """Why this channel failed, in the researcher's terms."""
    check = channel.worst_check
    if check is None:
        return "fails an enabled check"
    label = CHECK_LABELS.get(check, check)
    if check == "flat":
        return "Flat — no signal at all"
    value = channel.values.get(check)
    if value is None:
        return f"{label} — not measurable"
    digits = 3 if check == "clipping" else 2
    return f"{label} {value:.{digits}f}"
