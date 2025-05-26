from enum import Enum

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QPushButton


class CustomIcon(Enum):
    EXTEND = ":/resources/extend.png"
    FREQUENCY = ":/resources/frequency.png"
    SETTINGS = ":/resources/settings.png"

    @property
    def qicon(self) -> QIcon:
        return QIcon(self.value)

    @property
    def qpixmap(self) -> QPixmap:
        return QPixmap(self.value)

def set_button_icon(button: QPushButton, icon: CustomIcon, size: int = None):
    """
    Set the icon of a QPushButton using a CustomIcon enum.

    :param button: The QPushButton to set the icon for.
    :param icon: An instance of CustomIcon enum.
    """
    button.setIcon(icon.qicon)
    if size is not None:
        button.setIconSize(QSize(size, size))
    button.setStyleSheet("QPushButton { border: none; }")
