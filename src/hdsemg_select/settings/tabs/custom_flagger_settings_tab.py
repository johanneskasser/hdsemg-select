# ui/custom_flagger_settings_tab.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QFormLayout, QLineEdit, QColorDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView, QDialog, QDialogButtonBox
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

import uuid

from hdsemg_select.config.config_enums import Settings
from hdsemg_select.ui.labels.label_bean_widget import LabelBeanWidget        # your bean
from hdsemg_select.ui.theme import Colors, Spacing, BorderRadius, Styles, Fonts

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
        vbox.setSpacing(Spacing.LG)
        vbox.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        # Header
        header_label = QLabel("Custom Channel Labels")
        header_label.setStyleSheet(Styles.label_heading(size="lg"))
        vbox.addWidget(header_label)

        # ── Info
        info_label = QLabel(
            "Create custom labels that can be assigned to individual channels. "
            "Use these to mark channels with specific characteristics or conditions."
        )
        info_label.setStyleSheet(Styles.label_secondary())
        info_label.setWordWrap(True)
        vbox.addWidget(info_label)

        # ── Table
        self.table = QTableWidget(0, 3)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD};
                gridline-color: {Colors.BORDER_MUTED};
            }}
            QTableWidget::item {{
                padding: {Spacing.SM}px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.BLUE_100};
                color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Colors.BG_SECONDARY};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                padding: {Spacing.SM}px;
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
            }}
        """)
        self.table.setHorizontalHeaderLabels(["ID", "Label Name", "Preview"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        # Hide the ID column - it's only needed internally
        self.table.setColumnHidden(self.COL_ID, True)

        vbox.addWidget(self.table)

        # ── Controls
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.SM)

        self.btn_add = QPushButton("Add New Label")
        self.btn_add.setStyleSheet(Styles.button_primary())
        self.btn_add.setToolTip("Create a new custom label")

        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setStyleSheet(Styles.button_danger())
        self.btn_delete.setToolTip("Remove selected labels")

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # Info box
        info_box = QLabel("💡 Tip: Double-click a label's preview to change its color. Custom labels are saved and persist across sessions.")
        info_box.setStyleSheet(Styles.info_box(type="info"))
        info_box.setWordWrap(True)
        vbox.addWidget(info_box)

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


class _AddFlagDialog(QDialog):
    """
    Modal dialog for creating a new custom label.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Label")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # Header
        header_label = QLabel("New Custom Label")
        header_label.setStyleSheet(Styles.label_heading(size="lg"))
        layout.addWidget(header_label)

        info_label = QLabel("Enter a name and choose a color for your custom label.")
        info_label.setStyleSheet(Styles.label_secondary())
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Form
        form = QFormLayout()
        form.setSpacing(Spacing.MD)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # name
        self.name_edit = QLineEdit()
        self.name_edit.setStyleSheet(Styles.input_field())
        self.name_edit.setPlaceholderText("e.g., High Noise, Baseline Shift, etc.")
        form.addRow("Label Name:", self.name_edit)

        # colour
        self.color_btn = QPushButton("Choose Color...")
        self.color_btn.setStyleSheet(Styles.button_secondary())
        self.color_preview = QLabel(" ")
        self.color_preview.setFixedSize(80, 24)
        self.color_preview.setStyleSheet(f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: {BorderRadius.SM};")
        self._color = QColor(Colors.BLUE_500)
        self._update_color_preview()
        self.color_btn.clicked.connect(self._pick_color)

        col_layout = QHBoxLayout()
        col_layout.setSpacing(Spacing.SM)
        col_layout.addWidget(self.color_btn)
        col_layout.addWidget(self.color_preview)
        col_layout.addStretch()
        form.addRow("Label Color:", col_layout)

        layout.addLayout(form)

        # Preview
        preview_label = QLabel("Preview:")
        preview_label.setStyleSheet(Styles.label_secondary())
        layout.addWidget(preview_label)

        self.preview_bean = LabelBeanWidget("Example Label", self._color.name())
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(self.preview_bean)
        preview_layout.addStretch()
        layout.addLayout(preview_layout)

        # Update preview on name change
        self.name_edit.textChanged.connect(self._update_preview)

        layout.addStretch()

        # buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("Create Label")
        ok_button.setStyleSheet(Styles.button_primary())
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setStyleSheet(Styles.button_secondary())

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # ------- helpers
    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Choose Label Color")
        if c.isValid():
            self._color = c
            self._update_color_preview()
            self._update_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f"""
            background-color: {self._color.name()};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: {BorderRadius.SM};
        """)

    def _update_preview(self):
        """Update the preview bean with current name and color."""
        name = self.name_edit.text() or "Example Label"
        # Update the preview bean
        if hasattr(self, 'preview_bean'):
            # Remove old preview
            old_bean = self.preview_bean
            # Create new bean with updated values
            self.preview_bean = LabelBeanWidget(name, self._color.name())
            # Replace in layout
            for i in range(self.layout().count()):
                item = self.layout().itemAt(i)
                if item and isinstance(item, QHBoxLayout):
                    for j in range(item.count()):
                        widget = item.itemAt(j).widget()
                        if widget == old_bean:
                            item.removeWidget(old_bean)
                            old_bean.deleteLater()
                            item.insertWidget(j, self.preview_bean)
                            return

    # ------- API
    def values(self):
        return (self.name_edit.text(),
                self._color)                       # return QColor
