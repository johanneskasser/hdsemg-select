# ui/custom_flagger_settings_tab.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QFormLayout, QLineEdit, QColorDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

import uuid

from hdsemg_select.config.config_enums import Settings
from hdsemg_select.ui.labels.label_bean_widget import LabelBeanWidget        # your bean

class CustomFlaggerSettingsTab(QWidget):
    """
    Tab that lets the user create / delete colour-coded flags and assign them
    to channels.  Persists via ConfigManager, matching AutoFlaggerSettingsTab.
    """
    COL_ID, COL_NAME, COL_COLOR = range(3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    # ---------- UI ---------- #
    def _init_ui(self):
        vbox = QVBoxLayout(self)

        # ── Info
        vbox.addWidget(QLabel(
            "Define custom flags which can be added to each individual channel.\n"
        ))

        # ── Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Preview"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        vbox.addWidget(self.table)

        # ── Controls
        btn_row = QHBoxLayout()
        self.btn_add    = QPushButton("Add")
        self.btn_delete = QPushButton("Delete")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # connect
        self.btn_add.clicked.connect(self._on_add)
        self.btn_delete.clicked.connect(self._on_delete)

        vbox.addStretch(1)

    # ---------- Public API ---------- #
    def loadSettings(self, cfg):
        """
        Populate table from ConfigManager.
        """
        self.table.setRowCount(0)

        flags = cfg.get(Settings.CUSTOM_FLAGS, [])
        for f in flags:
            self._insert_row(f["id"], f["name"], f["color"])


    def saveSettings(self, cfg):
        """
        Gather data from UI and write back.
        """
        flags = []
        for r in range(self.table.rowCount()):
            fid      = self.table.item(r, self.COL_ID).text()
            name     = self.table.item(r, self.COL_NAME).text()
            color    = self.table.item(r, self.COL_COLOR).data(Qt.UserRole)

            flags.append(dict(id=fid, name=name, color=color.name()))

        cfg.set(Settings.CUSTOM_FLAGS, flags)

    # ---------- Internals ---------- #
    def _on_add(self):
        """
        Interactive dialog to add a flag.
        """
        dlg = _AddFlagDialog(self)
        if not dlg.exec_():
            name, color = dlg.values()
            self._insert_row(str(uuid.uuid4()), name, color)


    def _on_delete(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows:
            return
        if QMessageBox.question(self, "Delete", "Delete selected flags?") != QMessageBox.Yes:
            return
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)

    def _insert_row(self, fid, name, color_str):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # id
        self.table.setItem(row, self.COL_ID, QTableWidgetItem(str(fid)))

        # name
        self.table.setItem(row, self.COL_NAME, QTableWidgetItem(name))

        # color preview – show as bean
        bean = LabelBeanWidget(name, color_str)
        bean_item = QTableWidgetItem()
        bean_item.setData(Qt.UserRole, QColor(color_str))
        self.table.setItem(row, self.COL_COLOR, bean_item)
        self.table.setCellWidget(row, self.COL_COLOR, bean)


class _AddFlagDialog(QMessageBox):
    """
    Simple modal pop-up collecting name / color.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Flag")

        # name
        self.name_edit = QLineEdit()

        # colour
        self.color_btn = QPushButton("Pick…")
        self.color_preview = QLabel(" ")
        self.color_preview.setFixedSize(40, 20)
        self._color = QColor("lightblue")
        self._update_color_preview()
        self.color_btn.clicked.connect(self._pick_color)

        # layout
        form = QFormLayout()
        form.addRow("Name:", self.name_edit)

        col_layout = QHBoxLayout()
        col_layout.addWidget(self.color_btn)
        col_layout.addWidget(self.color_preview)
        col_layout.addStretch()
        form.addRow("Color:", col_layout)

        self.layout().addLayout(form, 0, 0)

        # buttons
        self.addButton("Create", QMessageBox.AcceptRole)
        self.addButton("Cancel",  QMessageBox.RejectRole)

    # ------- helpers
    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Flag Color")
        if c.isValid():
            self._color = c
            self._update_color_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f"background:{self._color.name()};")

    # ------- API
    def values(self):
        return (self.name_edit.text(),
                self._color)                       # return QColor
