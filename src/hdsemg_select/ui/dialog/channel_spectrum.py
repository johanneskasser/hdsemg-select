from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib import pyplot as plt
from hdsemg_select.state.state import global_state

from hdsemg_select.select_logic.data_processing import welchPS


class ChannelSpectrum:
    def __init__(self, parent):
        self.parent = parent

    def view_channel_spectrum(self, channel_idx):
        y = global_state.get_emg_file().data[:, channel_idx]
        fs = global_state.get_emg_file().sampling_frequency
        xf, yf = welchPS(y, fs)

        self.spectrum_window = QMainWindow(self.parent)
        self.spectrum_window.setWindowTitle(f"Channel {channel_idx + 1} - Frequency Spectrum")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(xf, yf)
        ax.set_title(f"Channel {channel_idx + 1} Frequency Spectrum")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power")
        ax.set_xlim(0, 600)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self.spectrum_window)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.spectrum_window.setCentralWidget(central_widget)
        self.spectrum_window.show()