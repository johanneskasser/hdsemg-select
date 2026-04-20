import unittest
from hdsemg_select.ui.main_window import build_grid_label


class TestBuildGridLabel(unittest.TestCase):

    def test_with_muscle(self):
        result = build_grid_label(8, 8, "COLUMNS", "PARALLEL", "Biceps Brachii")
        self.assertEqual(result, "Biceps Brachii\n(8x8)  Columns Parallel to fibers")

    def test_without_muscle(self):
        result = build_grid_label(4, 16, "ROWS", "PARALLEL", None)
        self.assertEqual(result, "(4x16)  Rows Parallel to fibers")

    def test_empty_string_muscle_treated_as_absent(self):
        muscle = "" or None  # mirrors the None-coalescing in apply_grid_selection
        result = build_grid_label(8, 4, "COLUMNS", "PARALLEL", muscle)
        self.assertEqual(result, "(8x4)  Columns Parallel to fibers")

    def test_muscle_name_is_first_line(self):
        result = build_grid_label(13, 5, "ROWS", "PARALLEL", "Vastus Lateralis")
        lines = result.split("\n")
        self.assertEqual(lines[0], "Vastus Lateralis")
        self.assertIn("13x5", lines[1])
