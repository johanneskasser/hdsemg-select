from enum import Enum
from hdsemg_select.ui.theme import Colors

class BaseChannelLabel(Enum):
    ECG = {"id": 1, "name": "ECG", "color": Colors.RED_500}
    NOISE_50 = {"id": 2, "name": "Noise 50 Hz", "color": Colors.YELLOW_500}
    NOISE_60 = {"id": 3, "name": "Noise 60 Hz", "color": Colors.YELLOW_500}
    ARTIFACT = {"id": 4, "name": "Artifact", "color": Colors.YELLOW_600}
    BAD_CHANNEL = {"id": 5, "name": "Bad Channel", "color": Colors.RED_600}
    ZERO_LINE = {"id": 10, "name": "Zero Line", "color": Colors.RED_600}
    REFERENCE_SIGNAL = {"id": 6, "name": "Reference Signal", "color": Colors.GREEN_500}
    RMS_EXCELLENT = {"id": 7, "name": "RMS: Excellent", "color": Colors.GREEN_600}
    RMS_GOOD = {"id": 8, "name": "RMS: Good", "color": Colors.GREEN_500}
    RMS_OK = {"id": 9, "name": "RMS: OK", "color": Colors.YELLOW_500}

    @classmethod
    def get_by_name(cls, name: str):
        """Gibt das Dict zur Bezeichnung zurück oder None, falls nicht gefunden."""
        for label in cls:
            if label.value["name"] == name:
                return label.value
        return None

    @classmethod
    def all_labels(cls):
        """Gibt eine Liste aller Label-Dicts zurück."""
        return [label.value for label in cls]