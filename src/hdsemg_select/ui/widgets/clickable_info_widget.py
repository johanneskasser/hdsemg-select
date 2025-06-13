from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel


class ClickableGridInfoWidget(QFrame):
    """
    A QFrame that displays grid information, is always square,
    and emits a signal when clicked.
    """
    clicked = pyqtSignal()

    def __init__(self, parent=None, width=250, height=60, boarder=True):
        super().__init__(parent)
        self.setFixedSize(width, height) # Fixed size for the widget
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain) # Add a simple border
        self.setLineWidth(1) if boarder else self.setLineWidth(0)

        self.setCursor(Qt.PointingHandCursor)  # Cursor bei Hover auf Zeiger setzen

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(5, 5, 5, 5)

        self.text_label = QLabel("")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True) # Allow text to wrap if it's too long
        self._layout.addWidget(self.text_label)

        self.setLayout(self._layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def setText(self, text):
        self.text_label.setText(text)
        self.text_label.setHidden(False)

    def clearText(self):
        self.text_label.setText("")
        self.text_label.setHidden(True)

    def setFont(self, font):
        self.text_label.setFont(font)

