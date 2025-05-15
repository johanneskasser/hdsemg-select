from enum import Enum, auto

class LayoutMode(Enum):
    ROWS = auto()
    COLS = auto()

    @classmethod
    def list_modes(cls):
        return list(cls)

class FiberMode(Enum):
    PARALLEL = auto()
    PERPENDICULAR = auto()

    @classmethod
    def list_modes(cls):
        return list(cls)