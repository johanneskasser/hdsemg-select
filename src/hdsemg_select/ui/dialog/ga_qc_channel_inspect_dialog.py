"""Look at one channel's own signal, then keep or discard it.

A grade is a number. Deciding whether a borderline channel belongs in the
analysis means looking at the signal behind it, which is what this shows:
the exact trace that channel contributes to the global amplitude, with the
rest and peak windows the grade was measured inside.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
)

from hdsemg_select.select_logic.global_amplitude_qc import (
    BORDERLINE, CHECK_LABELS, FAIL, NOT_AVAILABLE, PASS,
)
from hdsemg_select.ui.theme import BorderRadius, Colors, Fonts, Spacing

_GRADE_STYLE = {
    PASS: (Colors.GREEN_50, Colors.GREEN_600, Colors.GREEN_800),
    BORDERLINE: (Colors.YELLOW_50, Colors.YELLOW_600, Colors.YELLOW_600),
    FAIL: (Colors.RED_50, Colors.RED_600, Colors.RED_700),
    NOT_AVAILABLE: (Colors.BG_TERTIARY, Colors.BORDER_DEFAULT, Colors.TEXT_SECONDARY),
}

#: What the dialog was closed with.
KEEP = "keep"
DISCARD = "discard"


class GaQcChannelInspectDialog(QDialog):
    """One channel's derived trace, plus a keep/discard decision."""

    def __init__(self, channel, trace, trace_label, time, windows, fs,
                 is_selected, parent=None):
        super().__init__(parent)
        self._channel = channel
        self._trace = np.asarray(trace, dtype=np.float64)
        self._trace_label = trace_label
        self._time = np.asarray(time, dtype=np.float64)
        self._windows = windows
        self._fs = fs
        self._is_selected = is_selected
        self.decision = None

        self.setWindowTitle(f"Channel {channel.channel_index + 1} - signal")
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_SECONDARY}; }}")
        self.setMinimumSize(720, 480)
        self.resize(960, 620)
        self._build_ui()
        self._draw()

    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        root.addWidget(self._header())

        figure = Figure(figsize=(8, 4), facecolor=Colors.BG_PRIMARY)
        self._ax = figure.add_subplot(111)
        self._canvas = FigureCanvas(figure)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar = NavigationToolbar(self._canvas, self)
        toolbar.setStyleSheet(
            f"QToolBar {{ background-color: {Colors.BG_SECONDARY}; "
            f"border: 1px solid {Colors.BORDER_DEFAULT}; "
            f"border-radius: {BorderRadius.SM}; padding: {Spacing.XS}px; }}"
            f"QToolButton {{ background-color: transparent; border: 1px solid transparent; "
            f"border-radius: {BorderRadius.SM}; padding: {Spacing.XS}px; }}"
            f"QToolButton:hover {{ background-color: {Colors.GRAY_100}; "
            f"border-color: {Colors.BORDER_DEFAULT}; }}"
        )
        root.addWidget(toolbar)
        root.addWidget(self._canvas, stretch=1)

        root.addWidget(self._evidence_line())
        root.addLayout(self._footer())

    def _header(self) -> QLabel:
        background, border, text = _GRADE_STYLE[self._channel.grade]
        driver = (CHECK_LABELS.get(self._channel.worst_check, "")
                  if self._channel.worst_check else "")
        detail = f" - worst check: <b>{driver}</b>" if driver else ""
        label = QLabel(
            f"<b>Channel {self._channel.channel_index + 1}</b> · grade "
            f"<b>{self._channel.grade}</b> · CQI <b>{self._channel.cqi}</b>{detail}"
            f"<br>Showing {self._trace_label}."
        )
        label.setWordWrap(True)
        label.setStyleSheet(
            f"background-color: {background}; border: 1px solid {border}; "
            f"border-radius: 6px; padding: 8px 12px; color: {text}; "
            f"font-size: {Fonts.SIZE_SM};"
        )
        return label

    def _evidence_line(self) -> QLabel:
        parts = []
        for check, state in self._channel.states.items():
            value = self._channel.values.get(check)
            if check == "flat":
                shown = "yes" if value else "no"
            elif value is None:
                shown = "-"
            else:
                shown = f"{value:.3f}" if check == "clipping" else f"{value:.2f}"
            parts.append(f"{CHECK_LABELS[check]} {shown} ({state})")
        label = QLabel(" · ".join(parts))
        label.setWordWrap(True)
        label.setStyleSheet(f"font-size: {Fonts.SIZE_XS}; color: {Colors.TEXT_MUTED};")
        return label

    def _footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setSpacing(8)

        state = QLabel(
            "Currently <b>selected</b>" if self._is_selected
            else "Currently <b>not selected</b>")
        state.setStyleSheet(f"font-size: {Fonts.SIZE_SM}; color: {Colors.TEXT_SECONDARY};")
        footer.addWidget(state)
        footer.addStretch()

        close = QPushButton("Close")
        close.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.BG_SECONDARY}; "
            f"color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 8px 16px; }}"
        )
        close.clicked.connect(self.reject)

        discard = QPushButton("Discard channel")
        discard.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.RED_600}; color: white; "
            f"border-radius: 6px; padding: 8px 16px; font-weight: 500; }}"
            f"QPushButton:hover {{ background-color: {Colors.RED_700}; }}"
        )
        discard.clicked.connect(lambda: self._decide(DISCARD))

        keep = QPushButton("Keep channel")
        keep.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.GREEN_600}; color: white; "
            f"border-radius: 6px; padding: 8px 16px; font-weight: 500; }}"
            f"QPushButton:hover {{ background-color: {Colors.GREEN_700}; }}"
        )
        keep.clicked.connect(lambda: self._decide(KEEP))

        footer.addWidget(close)
        footer.addWidget(discard)
        footer.addWidget(keep)
        return footer

    def _decide(self, decision: str):
        self.decision = decision
        self.accept()

    # ------------------------------------------------------------------

    def _draw(self):
        axes = self._ax
        axes.clear()

        samples = min(self._trace.size, self._time.size)
        time, trace = self._time[:samples], self._trace[:samples]

        for start, stop in self._windows.rest:
            if start < samples:
                axes.axvspan(time[start], time[min(stop, samples - 1)],
                             color=Colors.BLUE_100, alpha=0.5, zorder=0,
                             label="_rest")
        peak_start, peak_stop = self._windows.peak
        if peak_start < samples:
            axes.axvspan(time[peak_start], time[min(peak_stop, samples - 1)],
                         color=Colors.GRAY_400, alpha=0.5, zorder=1,
                         label="_peak")

        axes.plot(time, trace, linewidth=0.6, color=Colors.BLUE_600, zorder=2)
        axes.set_xlabel("time [s]", fontsize=9)
        axes.set_ylabel("amplitude [µV]", fontsize=9)
        axes.tick_params(labelsize=8)
        axes.margins(x=0)

        axes.text(
            0.01, 0.98,
            "blue band: rest   ·   grey band: peak window",
            transform=axes.transAxes, fontsize=8, va="top",
            color=Colors.TEXT_MUTED,
        )
        axes.figure.tight_layout()
        self._canvas.draw_idle()
