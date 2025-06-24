import sys

import numpy as np
from scipy.fft import rfft, rfftfreq

from hdsemg_select._log.log_config import logger
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel


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
            # 1) FFT
            num_samples = channel_data.size
            fft_vals = rfft(channel_data)
            fft_freqs = rfftfreq(num_samples, 1.0 / sampling_frequency)
            power_spec = np.abs(fft_vals) ** 2

            # 2) check each target
            for freq in target_freqs:
                flag = self._check_frequency_peak(
                    fft_freqs, power_spec, freq, noise_settings
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
            noise_settings: dict
    ) -> str | None:

        # Build ±band mask
        band = noise_settings.get('band_hz', 2.0)
        # Background: all bins outside ±band (and above DC)
        mask_bg = (freqs > 0) & (np.abs(freqs - target_freq) > band)
        bg_vals = power_spec[mask_bg]
        med_bkgd = np.median(bg_vals) if bg_vals.size else 0.0

        # Local window: ±band around target
        mask_local = np.abs(freqs - target_freq) <= band
        local_vals = power_spec[mask_local]
        local_freqs = freqs[mask_local]

        if local_vals.size == 0:
            return None

        # Find the single largest peak in that window
        local_peak_idx = np.argmax(local_vals)
        peak_val = local_vals[local_peak_idx]
        peak_freq = local_freqs[local_peak_idx]

        # Ratio test against median background
        ratio = peak_val / (med_bkgd + sys.float_info.epsilon)

        if ratio > noise_settings.get('threshold', 1.0):
            label = (
                BaseChannelLabel.NOISE_50.value
                if target_freq == 50.0
                else BaseChannelLabel.NOISE_60.value
            )
            logger.debug(
                f"Flagged Noise {target_freq}Hz (actual at {peak_freq:.2f}Hz): "
                f"Peak={peak_val:.1f}, MedianBkgd={med_bkgd:.1f}, Ratio={ratio:.1f}"
            )
            return label

        logger.debug(
            f"No Noise {target_freq}Hz: BestLocalFreq={peak_freq:.2f}Hz, "
            f"Peak={peak_val:.1f}, MedianBkgd={med_bkgd:.1f}, Ratio={ratio:.1f}"
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
        for grid in global_state.get_emg_file().grids:
            for ref in grid.ref_indices:
                if isinstance(ref, int):
                    refs.append(ref)
        return refs
