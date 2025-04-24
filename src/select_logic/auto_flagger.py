# select_logic/auto_flagger.py
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks # find_peaks is useful but requires scipy 1.1.0+
import sys # To check scipy version if needed
from _log.log_config import logger

class AutoFlagger:
    def __init__(self):
        pass

    def suggest_flags(self, data: np.ndarray | None, sampling_frequency: float | None, settings: dict) -> dict:
        """
        Analyzes channel data to suggest artifact flags (Noise, Artifact).

        :param data: The raw or scaled EMG data (channels in columns).
        :param sampling_frequency: The data sampling frequency.
        :param settings: Dictionary of auto-flagger settings from settings_dialog.
                         Expected keys: 'noise_freq_threshold', 'artifact_variance_threshold',
                         'check_50hz', 'check_60hz', 'noise_freq_band_hz'
        :return: A dictionary {channel_idx: list_of_suggested_labels}
        """
        suggested_labels = {}

        if data is None or sampling_frequency is None or sampling_frequency <= 0:
            logger.warning("Auto-flagger skipped: Data or sampling frequency not available/valid.")
            return suggested_labels

        num_channels = data.shape[1]
        num_samples = data.shape[0]

        # Get settings with default fallbacks
        noise_freq_threshold = settings.get('noise_freq_threshold', 0.5) # Threshold for peak prominence/ratio
        artifact_variance_threshold = settings.get('artifact_variance_threshold', 1e-9) # Threshold for variance
        check_50hz = settings.get('check_50hz', True)
        check_60hz = settings.get('check_60hz', False) # Default to 50Hz standard
        noise_freq_band_hz = settings.get('noise_freq_band_hz', 2.0) # +/- band around target frequency

        target_frequencies = []
        if check_50hz:
            target_frequencies.append(50.0)
        if check_60hz:
            target_frequencies.append(60.0)

        if not target_frequencies and artifact_variance_threshold <= 0:
            logger.info("Auto-flagger skipped: No frequency checks enabled and artifact threshold is zero or less.")
            return suggested_labels

        logger.info("Running auto-flagger...")
        logger.debug(f"Settings: Noise Freq Threshold={noise_freq_threshold}, Artifact Var Threshold={artifact_variance_threshold}, Check 50Hz={check_50hz}, Check 60Hz={check_60hz}, Freq Band={noise_freq_band_hz}Hz")


        for i in range(num_channels):
            channel_data = data[:, i]
            channel_flags = []

            # --- Frequency Domain Analysis (Noise) ---
            # Only perform FFT if frequency checks are enabled
            if target_frequencies:
                try:
                    # Compute FFT
                    fft_vals = rfft(channel_data)
                    fft_freqs = rfftfreq(num_samples, 1.0/sampling_frequency)
                    power_spectrum = np.abs(fft_vals)**2 # Power Spectrum

                    # Find average power in a relevant band (e.g., up to Nyquist or a high frequency limit)
                    # Exclude the DC component (freq=0)
                    valid_freq_mask = fft_freqs > 0
                    if np.any(valid_freq_mask):
                        avg_power = np.mean(power_spectrum[valid_freq_mask])
                    else:
                         avg_power = 0 # Avoid division by zero if no valid frequencies

                    # Check for peaks at target frequencies
                    for target_freq in target_frequencies:
                        # Find index closest to the target frequency
                        freq_idx = np.argmin(np.abs(fft_freqs - target_freq))
                        if freq_idx > 0: # Ensure not DC component
                             peak_power = power_spectrum[freq_idx]

                             # Calculate ratio of peak power to average power
                             # Use a small epsilon to avoid division by zero if avg_power is exactly 0
                             power_ratio = peak_power / (avg_power + sys.float_info.epsilon)

                             # Alternative: Check prominence around the peak using scipy.signal.find_peaks
                             # This is often more robust than simple ratio, but requires scipy >= 1.1.0
                             # Check scipy version
                             scipy_version_ok = False
                             try:
                                 from scipy import __version__ as scipy_version
                                 major, minor, _ = map(int, scipy_version.split('.'))
                                 if major > 1 or (major == 1 and minor >= 1):
                                     scipy_version_ok = True
                             except Exception:
                                 pass # scipy not installed or version check failed

                             if scipy_version_ok:
                                 # Find peaks in the power spectrum
                                 # Limit search to a band around the target frequency for efficiency
                                 band_mask = (fft_freqs >= target_freq - noise_freq_band_hz) & (fft_freqs <= target_freq + noise_freq_band_hz)
                                 if np.any(band_mask):
                                      peaks, properties = find_peaks(power_spectrum[band_mask], prominence=None, height=None) # Can add thresholds here
                                      # Find the peak closest to the target frequency within the band
                                      band_freqs = fft_freqs[band_mask]
                                      band_power = power_spectrum[band_mask]

                                      if len(peaks) > 0:
                                          closest_peak_idx_in_band = peaks[np.argmin(np.abs(band_freqs[peaks] - target_freq))]
                                          # Calculate prominence of the peak at the target frequency
                                          # Need to recalculate properties for a single peak or use height/threshold directly
                                          # Simple check: Is there a peak *at* or *very near* the target freq above a height/prominence threshold?
                                          # Or check if the power ratio is high enough AND it's a local maximum.
                                          # Let's stick to the power ratio check combined with being a local max for simplicity if find_peaks logic is complex.

                                          # Check if the target freq bin is a local maximum (compared to immediate neighbors)
                                          is_local_max = True
                                          if freq_idx > 0 and power_spectrum[freq_idx] < power_spectrum[freq_idx - 1]:
                                              is_local_max = False
                                          if freq_idx < len(power_spectrum) - 1 and power_spectrum[freq_idx] < power_spectrum[freq_idx + 1]:
                                               is_local_max = False

                                          # Flag as noise if power ratio is high and it's a local max
                                          if is_local_max and power_ratio > noise_freq_threshold:
                                              if target_freq == 50.0:
                                                  channel_flags.append("Noise 50 Hz")
                                              elif target_freq == 60.0:
                                                  channel_flags.append("Noise 60 Hz")
                                              logger.debug(f"Ch {i+1}: Flagged Noise {target_freq}Hz (Ratio: {power_ratio:.2f}, Local Max: {is_local_max})")
                                          else:
                                              logger.debug(f"Ch {i+1}: Did not flag Noise {target_freq}Hz (Ratio: {power_ratio:.2f}, Local Max: {is_local_max})")

                                      else:
                                          logger.debug(f"Ch {i+1}: No peaks found near {target_freq}Hz band.")
                                 else:
                                      logger.debug(f"Ch {i+1}: No frequencies in {target_freq}Hz band.")

                             else: # Fallback if scipy find_peaks is not available
                                  is_local_max = True
                                  if freq_idx > 0 and power_spectrum[freq_idx] < power_spectrum[freq_idx - 1]:
                                      is_local_max = False
                                  if freq_idx < len(power_spectrum) - 1 and power_spectrum[freq_idx] < power_spectrum[freq_idx + 1]:
                                       is_local_max = False

                                  if is_local_max and power_ratio > noise_freq_threshold:
                                      if target_freq == 50.0:
                                          channel_flags.append("Noise 50 Hz")
                                      elif target_freq == 60.0:
                                          channel_flags.append("Noise 60 Hz")
                                      logger.debug(f"Ch {i+1}: Flagged Noise {target_freq}Hz (Fallback) (Ratio: {power_ratio:.2f}, Local Max: {is_local_max})")
                                  else:
                                      logger.debug(f"Ch {i+1}: Did not flag Noise {target_freq}Hz (Fallback) (Ratio: {power_ratio:.2f}, Local Max: {is_local_max})")


                except Exception as e:
                    logger.error(f"Error during frequency analysis for channel {i+1}: {e}", exc_info=True)


            # --- Time Domain Analysis (General Artifact/Amplitude) ---
            # Only perform variance check if threshold is positive
            if artifact_variance_threshold > 0:
                 try:
                    variance = np.var(channel_data)
                    if variance > artifact_variance_threshold:
                        # Avoid adding "Artifact" if a specific noise flag is already added?
                        # Or allow multiple flags? Let's allow multiple for now.
                        if "Artifact" not in channel_flags:
                            channel_flags.append("Artifact")
                            logger.debug(f"Ch {i+1}: Flagged Artifact (Variance: {variance:.2e})")
                        else:
                            logger.debug(f"Ch {i+1}: Variance above threshold ({variance:.2e}), but Artifact already flagged.")
                    else:
                        logger.debug(f"Ch {i+1}: Variance below threshold ({variance:.2e})")

                 except Exception as e:
                    logger.error(f"Error during variance analysis for channel {i+1}: {e}", exc_info=True)


            # Store flags for this channel if any were added
            if channel_flags:
                suggested_labels[i] = channel_flags

        logger.info(f"Auto-flagger finished. Suggested flags for {len(suggested_labels)} channels.")
        return suggested_labels