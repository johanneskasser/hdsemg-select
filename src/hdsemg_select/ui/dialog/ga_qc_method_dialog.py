"""The "About the method" dialog behind the QC dialog's info button.

Everything that explains *why* the numbers are computed the way they are
lives here rather than as notes crowding the analysis itself.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from hdsemg_select.ui.theme import Colors, Fonts

_SECTIONS = [
    (
        "How the global amplitude is defined",
        "1  band-pass each channel      15 – 450 Hz, zero-lag\n"
        "2  square each channel         x²      (ARV: |x|)\n"
        "3  smooth each channel         15 Hz equivalent, zero-lag\n"
        "4  mean across the channels    → mean square over the grid\n"
        "5  square-root, LAST           → A(t)  [µV]",
        "The root comes <b>last</b>, after the mean across the grid - that is what makes "
        "mean_space(RMS²) = mean_time(RMS²) hold. Rooting per channel first would make the "
        "result depend on how many channels survived the selection, by a factor of 0.94 at "
        "4 channels to 0.995 at 48. An MVC trial and a tracking trial rarely keep the same "
        "channels, and their ratio is the reported %MVC.",
    ),
    (
        "MP, SD and DD",
        None,
        "Differencing runs on the raw signal, before filtering. SD and DD walk along one "
        "grid axis - point that along the muscle fibres. <b>Signal ▸ Fiber Trajectory "
        "Analysis</b> measures which way they actually run, which is a better check than "
        "whether the orientation box was ticked correctly.",
    ),
    (
        "Rest, peak, and the activation ratio",
        "activation ratio  =  mean(A over the peak window)\n"
        "                     ────────────────────────────\n"
        "                      median(A over the rest windows)",
        "Rest is where the performed path sits within a few percent of its own span above "
        "its own baseline - a fraction of the trial's peak force rather than of an MVC, so "
        "it needs no calibration file. The peak window is the 250 ms of highest global "
        "amplitude outside rest. Both are drawn on the plot and can be dragged; everything "
        "downstream is measured inside them. With no reference channel the first and last "
        "seconds are used instead, and the JSON records that as the window source.",
    ),
    (
        "How a channel is graded",
        None,
        "Seven checks, each a measured number stored raw in the JSON. The grade is the "
        "<b>worst</b> state among them, never an average, so one fatal defect cannot be "
        "averaged away by six healthy ones. CQI is a weighted mean used only to rank the "
        "list - it never decides a grade.<br><br>"
        "Amplitude and spectrum are scored against the channel's own grid with a "
        "median/MAD robust z rather than mean and SD, because the outliers being looked "
        "for are <i>in</i> the sample: with two bad channels a classical z-score is "
        "inflated by exactly those two and hides the second one.<br><br>"
        "Neighbour correlation is measured inside the peak window only. Over a whole "
        "tracking trial - which is mostly rest - neighbouring monopolar channels share "
        "little but uncorrelated noise, so it collapses toward zero for good channels too.",
    ),
    (
        "What this tool does not decide",
        None,
        "Nothing here returns a verdict on its own. Where a threshold sits depends on the "
        "muscle, the electrode, the task and the population, not on the measurement - so "
        "the numbers and the thresholds that produced a grade are both written to the "
        "selection JSON, and either can be re-derived without the other. Deselection is "
        "always confirmed by hand.",
    ),
]

_REFERENCES = [
    ("Merletti R, Cerone GL. <i>Techniques for information extraction from the surface "
     "EMG signal</i>, eq. 5.1–5.2. In: Merletti &amp; Farina (2016/2018).",
     "The definition of amplitude over a region - the source of the root-last ordering."),
    ("Del Vecchio A et al. <i>J Appl Physiol</i> (2025). "
     "doi:10.1152/japplphysiol.00810.2024",
     "Contraction-to-rest ratio as a recording quality criterion."),
    ("Merletti R, Muceli S. <i>Tutorial. Surface EMG detection in space and time: Best "
     "practices.</i> J Electromyogr Kinesiol 49:102363 (2019).",
     "Grid detection practice and what a usable recording looks like."),
    ("<i>Detection and Reconstruction of Poor-Quality Channels in High-Density EMG Array "
     "Measurements.</i> Sensors 23(10):4759 (2023).",
     "Neighbour-based outlier detection; documents the classical z-score failure mode."),
    ("Farina D, Merletti R. <i>J Neurosci Methods</i> 134:199–208 (2004).",
     "Propagation and innervation-zone estimation, shared with Fiber Trajectory Analysis."),
]


class GaQcMethodDialog(QDialog):
    """Read-only explanation of the QC method and its references."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About the Method - Global Amplitude QC")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self.resize(720, 760)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        content = QWidget()
        content.setStyleSheet(f"background-color: {Colors.BG_PRIMARY};")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 14, 16, 16)

        for title, formula, body in _SECTIONS:
            layout.addWidget(self._heading(title))
            if formula:
                layout.addWidget(self._formula(formula))
            layout.addWidget(self._body(body))

        layout.addWidget(self._heading("References"))
        for citation, note in _REFERENCES:
            layout.addWidget(self._reference(citation, note))
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Colors.BORDER_DEFAULT}; "
            f"border-radius: 8px; background-color: {Colors.BG_PRIMARY}; }}"
        )
        root.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        source = QLabel(
            "Implemented in hdsemg-shared - global_parameters.global_amplitude, quality")
        source.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        footer.addWidget(source)
        footer.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: {Fonts.SIZE_BASE}; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        return label

    @staticmethod
    def _formula(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.PlainText)
        label.setStyleSheet(
            f"font-family: {Fonts.FAMILY_MONO}; font-size: {Fonts.SIZE_SM}; "
            f"color: {Colors.TEXT_PRIMARY}; background-color: {Colors.BG_SECONDARY}; "
            f"border: 1px solid {Colors.BORDER_MUTED}; border-radius: 6px; padding: 8px 10px;"
        )
        return label

    @staticmethod
    def _body(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setStyleSheet(
            f"font-size: {Fonts.SIZE_SM}; color: {Colors.TEXT_SECONDARY};")
        return label

    @staticmethod
    def _reference(citation: str, note: str) -> QWidget:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setSpacing(1)
        layout.setContentsMargins(0, 4, 0, 4)
        title = QLabel(citation)
        title.setWordWrap(True)
        title.setTextFormat(Qt.RichText)
        title.setStyleSheet(f"font-size: {Fonts.SIZE_SM}; color: {Colors.TEXT_PRIMARY};")
        detail = QLabel(note)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"font-size: {Fonts.SIZE_XS}; color: {Colors.TEXT_MUTED};")
        layout.addWidget(title)
        layout.addWidget(detail)
        return holder
