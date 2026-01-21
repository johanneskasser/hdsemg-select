from enum import Enum


class Settings(Enum):
    LOG_LEVEL = "LOG_LEVEL"

    # Auto-Flagger Settings
    AUTO_FLAGGER_NOISE_FREQ_THRESHOLD = "auto_flagger_noise_freq_threshold"
    AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD = "auto_flagger_artifact_variance_threshold"
    AUTO_FLAGGER_CHECK_50HZ = "auto_flagger_check_50hz"
    AUTO_FLAGGER_CHECK_60HZ = "auto_flagger_check_60hz"
    AUTO_FLAGGER_NOISE_FREQ_BAND_HZ = "auto_flagger_noise_freq_band_hz"

    CUSTOM_FLAGS = "custom_flags"
    CUSTOM_FLAG_NAMES = "custom_flag_names"
    CUSTOM_FLAG_LAST_ID = "custom_flag_last_id"  # running ID generator


