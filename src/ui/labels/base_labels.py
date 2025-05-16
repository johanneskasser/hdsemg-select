from enum import Enum

class BaseChannelLabel(Enum):
    ECG = {"id": 1, "name": "ECG", "color": "#FA8072"}
    NOISE_50 = {"id": 2, "name": "Noise 50 Hz", "color": "#FFD700"}
    NOISE_60 = {"id": 3, "name": "Noise 60 Hz", "color": "#FFD700"}
    ARTIFACT = {"id": 4, "name": "Artifact", "color": "#FFA500"}
    BAD_CHANNEL = {"id": 5, "name": "Bad Channel", "color": "#FF0000"}
    REFERENCE_SIGNAL = {"id": 6, "name": "Reference Signal", "color": "#00FF00"}

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