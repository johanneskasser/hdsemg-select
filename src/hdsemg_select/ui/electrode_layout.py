"""
Physical electrode grid layouts for recognized OTB electrode models.

Layouts use orientation 180° (connector toward researcher/ground), which is the
most common setup. Each layout is stored as a list of columns where
base0[col][row] = 0-based local electrode index within the grid.
np.nan marks physically empty positions.
"""

import numpy as np
from typing import Optional

# Each entry: list of columns, each column is a list of row values (top→bottom).
# base0[col][row] = 0-based local electrode index.
_LAYOUTS_BASE0: dict[str, list] = {
    # GR08MM1305 and GR04MM1305 — 13 rows × 5 cols, orientation 180°
    # NaN at top-left (connector side)
    "GR08MM1305": [
        [np.nan,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11],
        [24,     23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12],
        [25,     26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37],
        [50,     49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38],
        [51,     52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63],
    ],
    # GR10MM0808 and HD10MM0808 — 8 rows × 8 cols, orientation 180°
    "GR10MM0808": [
        [ 7,  6,  5,  4,  3,  2,  1,  0],
        [15, 14, 13, 12, 11, 10,  9,  8],
        [23, 22, 21, 20, 19, 18, 17, 16],
        [31, 30, 29, 28, 27, 26, 25, 24],
        [39, 38, 37, 36, 35, 34, 33, 32],
        [47, 46, 45, 44, 43, 42, 41, 40],
        [55, 54, 53, 52, 51, 50, 49, 48],
        [63, 62, 61, 60, 59, 58, 57, 56],
    ],
    # HD04MM1305 and HD08MM1305 — 13 rows × 5 cols, orientation 180°
    # NaN at bottom-right (connector side)
    "HD04MM1305": [
        [    51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63],
        [    38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50],
        [    25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37],
        [    12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
        [np.nan,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11],
    ],
    # HD10MM0804, HD05MM0804, GR10MM0804 — 8 rows × 4 cols, orientation 180°
    "HD10MM0804": [
        [ 0,  1,  2,  3,  4,  5,  6,  7],
        [ 8,  9, 10, 11, 12, 13, 14, 15],
        [16, 17, 18, 19, 20, 21, 22, 23],
        [24, 25, 26, 27, 28, 29, 30, 31],
    ],
}

# Aliases pointing to the same layout
_ALIASES: dict[str, str] = {
    "GR04MM1305":  "GR08MM1305",
    "HD08MM1305":  "HD04MM1305",
    "HD10MM0808":  "GR10MM0808",
    "HD05MM0804":  "HD10MM0804",
    "GR10MM0804":  "HD10MM0804",
}


def _resolve_name(electrode_name: str) -> Optional[str]:
    """Return the canonical layout key for *electrode_name*, or None if unknown.

    Handles direct aliases and also the OTBiolab naming quirk where the two
    2-digit numbers after 'MM' are sometimes written in reversed order
    (e.g. HD08MM0513 == HD08MM1305, HD04MM0513 == HD04MM1305).
    """
    import re
    # Direct lookup / alias
    canonical = _ALIASES.get(electrode_name, electrode_name)
    if canonical in _LAYOUTS_BASE0:
        return canonical

    # Try swapping the two 2-digit suffix groups after MM: AABB → BBAA
    m = re.match(r'^([A-Z]{2}\d+MM)(\d{2})(\d{2})$', electrode_name)
    if m:
        swapped = m.group(1) + m.group(3) + m.group(2)
        canonical2 = _ALIASES.get(swapped, swapped)
        if canonical2 in _LAYOUTS_BASE0:
            return canonical2

    return None


def get_display_grid(electrode_name: str, rows: int, cols: int) -> Optional[np.ndarray]:
    """
    Return a (rows, cols) float array representing the physical electrode layout.

    arr[r, c] = 0-based local electrode index (within the grid).
    np.nan marks physically empty positions.

    Returns None if the electrode name is unrecognised or if the expected
    dimensions do not match the stored layout.

    Falls back to user-defined custom layouts persisted in config when the
    built-in layout lookup fails.
    """
    canonical = _resolve_name(electrode_name)
    if canonical is not None:
        base0 = _LAYOUTS_BASE0.get(canonical)
        if base0 is not None:
            # base0 is cols × rows (outer = col, inner = row)
            expected_cols = len(base0)
            expected_rows = len(base0[0])

            arr = np.array(base0, dtype=float)  # shape (expected_cols, expected_rows)

            if expected_rows == rows and expected_cols == cols:
                # Normal orientation: transpose to (rows, cols)
                return arr.T
            elif expected_rows == cols and expected_cols == rows:
                # File stores the grid with rows/cols swapped relative to the physical layout.
                # arr already has shape (expected_cols=rows, expected_rows=cols) = (rows, cols).
                return arr
            else:
                return None

    # Fall back to user-defined custom layouts stored in config
    try:
        from hdsemg_select.config.config_manager import config
        from hdsemg_select.config.config_enums import Settings
        custom = config.get(Settings.CUSTOM_ELECTRODE_LAYOUTS, {}) or {}
        entry = custom.get(electrode_name)
        if entry and entry.get("rows") == rows and entry.get("cols") == cols:
            raw = entry["grid"]  # list of rows, each a list of int|None
            arr = np.array(
                [[np.nan if v is None else float(v) for v in row] for row in raw],
                dtype=float,
            )
            if arr.shape == (rows, cols):
                return arr
    except Exception:
        pass

    return None
