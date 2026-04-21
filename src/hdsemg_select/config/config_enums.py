from enum import Enum, auto


class Settings(Enum):
    LOG_LEVEL = "LOG_LEVEL"

    # Auto-Flagger Settings
    AUTO_FLAGGER_NOISE_FREQ_THRESHOLD = "auto_flagger_noise_freq_threshold"
    AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD = "auto_flagger_artifact_variance_threshold"
    AUTO_FLAGGER_CHECK_50HZ = "auto_flagger_check_50hz"
    AUTO_FLAGGER_CHECK_60HZ = "auto_flagger_check_60hz"
    AUTO_FLAGGER_NOISE_FREQ_BAND_HZ = "auto_flagger_noise_freq_band_hz"

    CUSTOM_FLAGS = auto()
    CUSTOM_FLAG_NAMES = auto()
    CUSTOM_FLAG_LAST_ID = auto() #running ID generator

    DENSITY_ARV_WINDOW_MS = "density_arv_window_ms"
    DENSITY_SCALE_MAX_MV = "density_scale_max_mv"
    DENSITY_PLAYBACK_FPS = "density_playback_fps"
    DENSITY_DEFAULT_SPEED = "density_default_speed"
    CUSTOM_ELECTRODE_LAYOUTS = "custom_electrode_layouts"


