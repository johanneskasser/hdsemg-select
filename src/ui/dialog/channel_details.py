from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class ChannelDetailWindow(QMainWindow):
    def __init__(self, parent, data, channel_idx, ref_signal=None):
        super().__init__(parent)
        self.setWindowTitle(f"Channel {channel_idx + 1} - Detailed View")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(data[:, channel_idx], color="blue", label="Channel Signal")
        ax.plot(ref_signal, color="black", label="Reference Signal", linestyle="--") if ref_signal is not None else None
        ax.legend(loc='upper right', frameon=False, fontsize='small') if ref_signal is not None else None
        ax.set_title(f"Channel {channel_idx + 1}")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude (μV)")

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)