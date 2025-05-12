# ui/label_bean_widget.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel


class LabelBeanWidget(QLabel):
    """
    A custom QLabel widget styled to resemble a "bean" with rounded edges and a background color.

    Attributes:
        label_text (str): The text displayed on the label.
        color (str): The background color of the label. Defaults to "lightblue".
    """

    def __init__(self, label_text: str, color: str = "lightblue", parent=None):
        """
        Initializes the LabelBeanWidget with the given text, color, and optional parent widget.

        Args:
            label_text (str): The text to display on the label.
            color (str): The background color of the label. Defaults to "lightblue".
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(label_text, parent)
        self.label_text = label_text
        self.color = color

        # Center-align the text within the label
        self.setAlignment(Qt.AlignCenter)

        # Set the minimum and maximum height of the label
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)

        # Set padding inside the label
        self.setContentsMargins(5, 1, 5, 1)

        # Apply a stylesheet for the bean appearance
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color};
                color: black; /* Text color */
                border: 1px solid grey; /* Optional border */
                border-radius: 10px; /* Half of height for rounded ends */
                padding: 1px 5px; /* Padding */
                margin: 0 2px; /* Margin between beans */
            }}
        """)

        # Set a tooltip to display the full label text
        self.setToolTip(label_text)
