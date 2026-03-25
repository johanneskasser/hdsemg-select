import numpy as np

from hdsemg_select._log.log_config import logger

_SILENT_GRID_THRESHOLD = 1e-12  # median RMS below this → entire grid is silent, skip detection


class ZeroLineDetector:
    """
    Detects zero-line (dead) channels using a sliding-window relative RMS approach.

    A channel is flagged as bad if:
      - The fraction of dead windows exceeds ``min_dead_fraction``, OR
      - The longest consecutive run of dead windows exceeds ``min_dead_run_fraction``

    A window is "dead" when its RMS is below ``relative_threshold × median_rms_of_grid``.
    This makes the method self-calibrating — no absolute amplitude threshold is required.
    """

    def detect(
        self,
        data: np.ndarray,
        fs: float,
        grid_indices: list,
        settings: dict,
    ) -> dict:
        """
        Analyse each channel and return its quality.

        Parameters
        ----------
        data : ndarray, shape (n_samples, n_channels)
            Scaled EMG data.
        fs : float
            Sampling frequency in Hz.
        grid_indices : list[int]
            Channel indices to analyse (0-based).
        settings : dict
            Keys (all optional, defaults applied):
                window_size_ms      – window duration in ms        (default 200)
                relative_threshold  – fraction of grid median RMS  (default 0.05)
                min_dead_fraction   – max allowed dead-window frac  (default 0.05)
                min_dead_run_fraction – max allowed consecutive run  (default 0.10)

        Returns
        -------
        dict[int, bool]
            ``True`` → channel is good, ``False`` → channel is a zero-line.
        """
        window_ms = float(settings.get("window_size_ms", 200))
        rel_thr = float(settings.get("relative_threshold", 0.05))
        min_dead_frac = float(settings.get("min_dead_fraction", 0.05))
        min_dead_run_frac = float(settings.get("min_dead_run_fraction", 0.10))

        # Drop None sentinels (empty electrode positions in physical layouts)
        grid_indices = [ch for ch in grid_indices if ch is not None]

        window_samples = max(1, int(fs * window_ms / 1000))
        n_samples = data.shape[0]
        n_windows = n_samples // window_samples

        if n_windows == 0:
            logger.warning("ZeroLineDetector: signal too short for even one window — skipping.")
            return {ch: True for ch in grid_indices}

        # --- per-channel window RMS ---
        channel_window_rms: dict = {}
        for ch in grid_indices:
            segment = data[: n_windows * window_samples, ch]
            windows = segment.reshape(n_windows, window_samples)
            rms = np.sqrt(np.mean(windows ** 2, axis=1))
            channel_window_rms[ch] = rms

        # --- self-calibrating reference: median of per-channel mean RMS ---
        mean_rms_per_ch = np.array([rms.mean() for rms in channel_window_rms.values()])
        median_rms = float(np.median(mean_rms_per_ch))

        if median_rms < _SILENT_GRID_THRESHOLD:
            logger.warning(
                "ZeroLineDetector: entire grid appears silent (median RMS ≈ 0). "
                "Skipping detection to avoid false positives."
            )
            return {ch: True for ch in grid_indices}

        dead_threshold = rel_thr * median_rms

        # --- classify channels ---
        results: dict = {}
        for ch in grid_indices:
            rms = channel_window_rms[ch]
            is_dead = rms < dead_threshold

            dead_fraction = float(is_dead.mean())
            max_run = _longest_run(is_dead)
            dead_run_fraction = max_run / n_windows

            is_bad = dead_fraction > min_dead_frac or dead_run_fraction > min_dead_run_frac

            logger.debug(
                f"Ch {ch + 1}: dead_frac={dead_fraction:.2%}, "
                f"dead_run_frac={dead_run_fraction:.2%} → {'BAD' if is_bad else 'OK'}"
            )
            results[ch] = not is_bad

        n_bad = sum(1 for v in results.values() if not v)
        logger.info(
            f"ZeroLineDetector: {n_bad}/{len(grid_indices)} channels flagged "
            f"(window={window_ms}ms, rel_thr={rel_thr:.0%}, "
            f"dead_frac>{min_dead_frac:.0%}, run>{min_dead_run_frac:.0%})"
        )
        return results


def _longest_run(mask: np.ndarray) -> int:
    """Return the length of the longest consecutive True run in a boolean array."""
    max_run = 0
    current = 0
    for v in mask:
        if v:
            current += 1
            if current > max_run:
                max_run = current
        else:
            current = 0
    return max_run
