import math
import unittest
from unittest.mock import patch, MagicMock

import numpy as np


def _make_mock_config(layouts: dict):
    """Return a mock ConfigManager whose .get() returns *layouts* for CUSTOM_ELECTRODE_LAYOUTS."""
    from hdsemg_select.config.config_enums import Settings
    mock_cfg = MagicMock()

    def side_effect(key, default=None):
        if key == Settings.CUSTOM_ELECTRODE_LAYOUTS:
            return layouts
        return default

    mock_cfg.get.side_effect = side_effect
    return mock_cfg


class TestCustomLayoutPersistence(unittest.TestCase):
    """Test that get_display_grid falls back to user-defined custom layouts."""

    def test_known_custom_layout_returned(self):
        layouts = {
            "FOO": {"rows": 2, "cols": 2, "grid": [[0, 1], [2, 3]]},
        }
        with patch("hdsemg_select.config.config_manager.config", _make_mock_config(layouts)):
            from hdsemg_select.ui.electrode_layout import get_display_grid
            result = get_display_grid("FOO", 2, 2)

        assert result is not None
        assert result.shape == (2, 2)
        np.testing.assert_array_equal(result, np.array([[0.0, 1.0], [2.0, 3.0]]))

    def test_none_entries_become_nan(self):
        layouts = {
            "BAR": {"rows": 1, "cols": 3, "grid": [[0, None, 2]]},
        }
        with patch("hdsemg_select.config.config_manager.config", _make_mock_config(layouts)):
            from hdsemg_select.ui.electrode_layout import get_display_grid
            result = get_display_grid("BAR", 1, 3)

        assert result is not None
        assert result[0, 0] == 0.0
        assert math.isnan(result[0, 1])
        assert result[0, 2] == 2.0

    def test_mismatched_dimensions_returns_none(self):
        layouts = {
            "BAZ": {
                "rows": 4,
                "cols": 4,
                "grid": [[i * 4 + j for j in range(4)] for i in range(4)],
            }
        }
        with patch("hdsemg_select.config.config_manager.config", _make_mock_config(layouts)):
            from hdsemg_select.ui.electrode_layout import get_display_grid
            # Ask for 2×2 but stored as 4×4
            result = get_display_grid("BAZ", 2, 2)

        assert result is None

    def test_unknown_name_still_returns_none(self):
        with patch("hdsemg_select.config.config_manager.config", _make_mock_config({})):
            from hdsemg_select.ui.electrode_layout import get_display_grid
            result = get_display_grid("COMPLETELY_UNKNOWN", 4, 4)

        assert result is None


if __name__ == "__main__":
    unittest.main()
