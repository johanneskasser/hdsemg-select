import numpy as np

from hdsemg_select._log.log_config import logger


class SNRCalculator:

    @staticmethod
    def compute_plateau_mask(
        data: np.ndarray,
        emg_indices: list,
        fs: float,
        window_ms: float = 250.0,
        threshold_fraction: float = 0.25,
    ) -> np.ndarray:
        """Return a boolean mask of active (plateau) samples.

        Averages the absolute-value envelope across all EMG channels, smooths it
        with a moving-average window, then thresholds at threshold_fraction * global_peak.
        """
        n_samples = data.shape[0]
        valid = [i for i in emg_indices if i is not None and 0 <= i < data.shape[1]]
        if not valid:
            return np.zeros(n_samples, dtype=bool)

        envelope = np.mean(np.abs(data[:, valid]), axis=1)
        window = max(1, int(window_ms * fs / 1000))
        kernel = np.ones(window) / window
        envelope = np.convolve(envelope, kernel, mode="same")

        peak = np.max(envelope)
        if peak < 1e-12:
            return np.zeros(n_samples, dtype=bool)

        return envelope > (threshold_fraction * peak)

    @staticmethod
    def compute_channel_snr(
        channel_data: np.ndarray,
        plateau_mask: np.ndarray,
        min_samples: int = 50,
    ) -> float | None:
        """SNR in dB = 20 · log10(RMS_active / RMS_rest). Returns None if data are insufficient."""
        active = channel_data[plateau_mask]
        rest = channel_data[~plateau_mask]

        if len(active) < min_samples or len(rest) < min_samples:
            return None

        rms_active = np.sqrt(np.mean(active ** 2))
        rms_rest = np.sqrt(np.mean(rest ** 2))

        if rms_rest < 1e-12 or rms_active < 1e-12:
            return None

        return float(round(20.0 * np.log10(rms_active / rms_rest), 1))

    @staticmethod
    def compute_all_snr(
        data: np.ndarray,
        emg_indices: list,
        plateau_mask: np.ndarray,
    ) -> dict:
        """Return {channel_idx: snr_db} for every EMG channel."""
        result = {}
        for idx in emg_indices:
            if idx is None or idx >= data.shape[1]:
                continue
            snr = SNRCalculator.compute_channel_snr(data[:, idx], plateau_mask)
            if snr is not None:
                result[idx] = snr
        return result

    @staticmethod
    def detect_rest_spikes(
        data: np.ndarray,
        emg_indices: list,
        plateau_mask: np.ndarray,
        threshold_factor: float = 5.0,
    ) -> list:
        """Flag channels whose rest-period peak exceeds threshold_factor × global noise floor.

        The global noise floor is the median RMS across all EMG channels during rest.
        Channels like a spike-artifact channel (e.g. one large transient during rest)
        will be detected here.
        """
        rest_mask = ~plateau_mask
        if rest_mask.sum() < 50:
            return []

        valid = [i for i in emg_indices if i is not None and 0 <= i < data.shape[1]]
        if not valid:
            return []

        rest_rms_per_channel = [
            np.sqrt(np.mean(data[rest_mask, idx] ** 2)) for idx in valid
        ]
        global_noise_floor = np.median(rest_rms_per_channel)
        if global_noise_floor < 1e-12:
            return []

        flagged = []
        for idx in valid:
            rest_peak = np.max(np.abs(data[rest_mask, idx]))
            if rest_peak > threshold_factor * global_noise_floor:
                flagged.append(idx)
                logger.debug(
                    "Ch %d: rest-spike ratio=%.1f (peak=%.2e, floor=%.2e)",
                    idx,
                    rest_peak / global_noise_floor,
                    rest_peak,
                    global_noise_floor,
                )

        return flagged

    @staticmethod
    def detect_amplitude_spikes(
        data: np.ndarray,
        emg_indices: list,
        threshold_factor: float = 5.0,
    ) -> list:
        """Flag channels whose overall peak amplitude >> median peak across all channels.

        No plateau detection required — robust for recordings without a clear rest period.
        """
        valid = [i for i in emg_indices if i is not None and 0 <= i < data.shape[1]]
        if not valid:
            return []

        peaks = np.array([np.max(np.abs(data[:, idx])) for idx in valid])
        median_peak = np.median(peaks)
        if median_peak < 1e-12:
            return []

        flagged = []
        for idx, peak in zip(valid, peaks):
            if peak > threshold_factor * median_peak:
                flagged.append(idx)
                logger.debug(
                    "Ch %d: amplitude-spike ratio=%.1f (peak=%.2e, median=%.2e)",
                    idx,
                    peak / median_peak,
                    peak,
                    median_peak,
                )

        return flagged
