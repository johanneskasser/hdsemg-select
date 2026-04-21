import math
import numpy as np
import unittest

from hdsemg_select.logic.density.arv import compute_arv_window, channels_to_grid, ms_to_samples


class TestMsToSamples(unittest.TestCase):
    def test_basic_conversion(self):
        assert ms_to_samples(250.0, 2048.0) == 512

    def test_zero_ms_returns_one(self):
        assert ms_to_samples(0.0, 2048.0) == 1

    def test_sub_sample_rounds_to_one(self):
        assert ms_to_samples(0.1, 2048.0) == 1

    def test_exact_multiple(self):
        assert ms_to_samples(1000.0, 1000.0) == 1000


class TestComputeArvWindow(unittest.TestCase):
    def _make_data(self, n_samples=100, n_channels=4, value=0.0):
        return np.full((n_samples, n_channels), value, dtype=float)

    def test_zero_vector(self):
        data = self._make_data(value=0.0)
        result = compute_arv_window(data, center_sample=50, window_samples=20)
        np.testing.assert_array_equal(result, np.zeros(4))

    def test_dc_rectification(self):
        data = self._make_data(value=-1.0)
        result = compute_arv_window(data, center_sample=50, window_samples=20)
        np.testing.assert_allclose(result, np.ones(4))

    def test_returns_correct_length(self):
        data = self._make_data(n_channels=8)
        result = compute_arv_window(data, center_sample=50, window_samples=10)
        assert result.shape == (8,)

    def test_clamp_at_start(self):
        data = self._make_data(value=2.0)
        result = compute_arv_window(data, center_sample=0, window_samples=20)
        np.testing.assert_allclose(result, np.full(4, 2.0))

    def test_clamp_at_end(self):
        data = self._make_data(n_samples=50, value=3.0)
        result = compute_arv_window(data, center_sample=49, window_samples=20)
        np.testing.assert_allclose(result, np.full(4, 3.0))

    def test_mixed_sign_signal(self):
        data = np.array([[1.0, -2.0], [-3.0, 4.0]])
        result = compute_arv_window(data, center_sample=0, window_samples=10)
        np.testing.assert_allclose(result, [2.0, 3.0])


class TestChannelsToGrid(unittest.TestCase):
    def _simple_grid(self):
        return np.array([[0.0, 1.0], [2.0, np.nan]])

    def test_basic_mapping(self):
        arv = np.array([10.0, 20.0, 30.0])
        emg_indices = [0, 1, 2]
        grid = self._simple_grid()
        result = channels_to_grid(arv, grid, emg_indices)
        assert result[0, 0] == 10.0
        assert result[0, 1] == 20.0
        assert result[1, 0] == 30.0
        assert math.isnan(result[1, 1])

    def test_nan_cells_preserved(self):
        arv = np.zeros(3)
        grid = np.array([[np.nan, 0.0], [1.0, np.nan]])
        result = channels_to_grid(arv, grid, [0, 1])
        assert math.isnan(result[0, 0])
        assert math.isnan(result[1, 1])

    def test_uses_emg_indices_mapping(self):
        # local index 0 maps to data column 5, local 1 maps to data column 3
        arv = np.zeros(10)
        arv[5] = 99.0
        arv[3] = 42.0
        grid = np.array([[0.0, 1.0]])
        result = channels_to_grid(arv, grid, emg_indices=[5, 3])
        assert result[0, 0] == 99.0
        assert result[0, 1] == 42.0

    def test_result_shape_matches_grid(self):
        arv = np.ones(64)
        grid = np.arange(64, dtype=float).reshape(8, 8)
        result = channels_to_grid(arv, grid, emg_indices=list(range(64)))
        assert result.shape == (8, 8)


if __name__ == "__main__":
    unittest.main()
