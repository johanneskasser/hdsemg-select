from PyQt5.QtGui import QIcon, QPalette, QColor
from hdsemg_select.ui.theme import Colors


def get_palette() -> QPalette: 
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(Colors.BG_PRIMARY))
    palette.setColor(QPalette.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(Colors.BG_SECONDARY))
    palette.setColor(QPalette.AlternateBase, QColor(Colors.BG_TERTIARY))
    palette.setColor(QPalette.ToolTipBase, QColor(Colors.BG_PRIMARY))
    palette.setColor(QPalette.ToolTipText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(Colors.BG_SECONDARY))
    palette.setColor(QPalette.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.BrightText, QColor(Colors.RED_600))
    palette.setColor(QPalette.Link, QColor(Colors.BLUE_600))
    palette.setColor(QPalette.Highlight, QColor(Colors.BLUE_600))
    palette.setColor(QPalette.HighlightedText, QColor(Colors.BG_PRIMARY))
    return palette