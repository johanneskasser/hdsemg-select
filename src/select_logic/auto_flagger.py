import sys

import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks  # requires scipy >=1.1.0

from _log.log_config import logger
from state.state import global_state
from ui.labels.base_labels import BaseChannelLabel


class AutoFlagger:
    def __init__(self):
        pass

    def suggest_flags(
        self,
        data: np.ndarray | None,
        sampling_frequency: float | None,
        settings: dict
    ) -> tuple[dict[int, list[str]], int, int]:
        """
        Analyzes channel data to suggest artifact flags (Noise, Artifact),
        and labels any reference channels as REFERENCE_SIGNAL.

        :param data: The raw or scaled EMG data (channels in columns).
        :param sampling_frequency: The data sampling frequency.
        :param settings: Dictionary of auto-flagger settings from settings_dialog.
                         Expected keys: 'noise_freq_threshold', 'artifact_variance_threshold',
                         'check_50hz', 'check_60hz', 'noise_freq_band_hz'.
        :return: A tuple: (suggested_labels dict, num_emg_flagged, num_ref_flagged)
        """
        suggested_labels: dict[int, list[str]] = {}
        reference_indices = self._get_all_reference_indices()

        if not self._is_valid_input(data, sampling_frequency):
            return suggested_labels, 0, len(reference_indices)

        # load settings
        noise_settings = {
            'threshold': settings.get('noise_freq_threshold', 0.5),
            'check_50hz': settings.get('check_50hz', True),
            'check_60hz': settings.get('check_60hz', False),
            'band_hz': settings.get('noise_freq_band_hz', 2.0)
        }
        artifact_threshold = settings.get('artifact_variance_threshold', 1e-9)

        target_freqs = self._get_target_frequencies(noise_settings)
        if not target_freqs and artifact_threshold <= 0 and not reference_indices:
            logger.info("Auto-flagger skipped: No checks enabled.")
            return suggested_labels, 0, len(reference_indices)

        logger.info("Running auto-flagger...")
        logger.debug(
            f"Settings: {noise_settings}, Artifact Var Threshold={artifact_threshold}, References={reference_indices}"
        )

        num_channels = data.shape[1]
        for ch_idx in range(num_channels):
            channel_data = data[:, ch_idx]
            flags: list[str] = []

            # Frequency-based noise flags
            if target_freqs:
                noise_flags = self._detect_noise(
                    channel_data,
                    sampling_frequency,
                    target_freqs,
                    noise_settings
                )
                flags.extend(noise_flags)

            # Time-domain artifact flags
            artifact_flag = self._detect_artifact(channel_data, artifact_threshold)
            if artifact_flag:
                flags.append(artifact_flag)

            # Reference signal flag
            if ch_idx in reference_indices:
                flags.append(BaseChannelLabel.REFERENCE_SIGNAL.value)
                logger.debug(f"Ch {ch_idx}: Labeled Reference Signal")

            # Remove duplicates while preserving order
            if flags:
                unique_flags: list[str] = []
                for flag in flags:
                    if flag not in unique_flags:
                        unique_flags.append(flag)
                suggested_labels[ch_idx] = unique_flags

        num_flagged = len(suggested_labels)
        num_ref_flagged = sum(
            1 for idx in suggested_labels if BaseChannelLabel.REFERENCE_SIGNAL.value in suggested_labels[idx]
        )
        num_emg_flagged = num_flagged - num_ref_flagged

        logger.info(
            f"Auto-flagger finished. Flags on {num_emg_flagged} EMG channels and {num_ref_flagged} reference channels."
        )
        return suggested_labels, num_emg_flagged, num_ref_flagged

    @staticmethod
    def _is_valid_input(data, sampling_frequency) -> bool:
        if data is None or sampling_frequency is None or sampling_frequency <= 0:
            logger.warning("Auto-flagger skipped: Data or sampling frequency invalid.")
            return False
        return True

    @staticmethod
    def _get_target_frequencies(noise_settings: dict) -> list[float]:
        freqs: list[float] = []
        if noise_settings.get('check_50hz', False):
            freqs.append(50.0)
        if noise_settings.get('check_60hz', False):
            freqs.append(60.0)
        return freqs

    def _detect_noise(
        self,
        channel_data: np.ndarray,
        sampling_frequency: float,
        target_freqs: list[float],
        noise_settings: dict
    ) -> list[str]:
        flags: list[str] = []
        try:
            num_samples = channel_data.size
            fft_vals = rfft(channel_data)
            fft_freqs = rfftfreq(num_samples, 1.0 / sampling_frequency)
            power_spec = np.abs(fft_vals) ** 2

            # compute global average power excluding DC
            valid_mask = fft_freqs > 0
            avg_power = np.mean(power_spec[valid_mask]) if np.any(valid_mask) else 0

            for freq in target_freqs:
                flag = self._check_frequency_peak(
                    fft_freqs,
                    power_spec,
                    freq,
                    avg_power,
                    noise_settings
                )
                if flag:
                    flags.append(flag)
        except Exception as exc:
            logger.error(f"Error in frequency analysis: {exc}", exc_info=True)
        return flags

    def _check_frequency_peak(
        self,
        freqs: np.ndarray,
        power_spec: np.ndarray,
        target_freq: float,
        avg_power: float,
        noise_settings: dict
    ) -> str | None:
        idx = np.argmin(np.abs(freqs - target_freq))
        if idx == 0:
            return None
        peak = power_spec[idx]
        ratio = peak / (avg_power + sys.float_info.epsilon)
        is_local_max = (peak >= power_spec[idx - 1]) and (peak >= power_spec[idx + 1])

        use_find_peaks = False
        try:
            from scipy import __version__ as v
            major, minor, *_ = map(int, v.split('.'))
            use_find_peaks = (major > 1 or (major == 1 and minor >= 1))
        except Exception:
            pass

        if use_find_peaks:
            band = noise_settings.get('band_hz', 0)
            mask = (freqs >= target_freq - band) & (freqs <= target_freq + band)
            if np.any(mask):
                local = power_spec[mask]
                peaks, _ = find_peaks(local)
                if peaks.size:
                    is_local_max = (peak >= power_spec[idx - 1]) and (peak >= power_spec[idx + 1])

        if is_local_max and ratio > noise_settings.get('threshold', 0):
            label = (
                BaseChannelLabel.NOISE_50.value
                if target_freq == 50.0
                else BaseChannelLabel.NOISE_60.value
            )
            logger.debug(
                f"Flagged Noise {target_freq}Hz: Ratio={ratio:.2f}, LocalMax={is_local_max}"
            )
            return label
        logger.debug(
            f"No Noise {target_freq}Hz: Ratio={ratio:.2f}, LocalMax={is_local_max}"
        )
        return None

    @staticmethod
    def _detect_artifact(
        channel_data: np.ndarray,
        threshold: float
    ) -> str | None:
        try:
            var = np.var(channel_data)
            if var > threshold:
                logger.debug(f"Flagged Artifact: Variance={var:.2e}")
                return BaseChannelLabel.ARTIFACT.value
            logger.debug(f"Variance below threshold: {var:.2e}")
        except Exception as exc:
            logger.error(f"Error in artifact detection: {exc}", exc_info=True)
        return None

    @staticmethod
    def _get_all_reference_indices() -> list[int]:
        """
        Retrieves all reference-signal indices from global grid info.
        """
        refs: list[int] = []
        grid_info = global_state.get_grid_info() or {}
        for grid in grid_info.values():
            for ref in grid.get('reference_signals', []):
                idx = ref.get('index')
                if isinstance(idx, int):
                    refs.append(idx)
        return refs
