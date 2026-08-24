from enum import Enum


class Settings(Enum):
    LOG_LEVEL = "LOG_LEVEL"

    # Auto-Flagger Settings
    AUTO_FLAGGER_NOISE_FREQ_THRESHOLD = "auto_flagger_noise_freq_threshold"
    AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD = "auto_flagger_artifact_variance_threshold"
    AUTO_FLAGGER_CHECK_50HZ = "auto_flagger_check_50hz"
    AUTO_FLAGGER_CHECK_60HZ = "auto_flagger_check_60hz"
    AUTO_FLAGGER_NOISE_FREQ_BAND_HZ = "auto_flagger_noise_freq_band_hz"

    # Explicit values rather than auto(): auto() cannot follow string members,
    # which raises at import time on Python 3.12+. Only .name is ever stored.
    CUSTOM_FLAGS = "custom_flags"
    CUSTOM_FLAG_NAMES = "custom_flag_names"
    CUSTOM_FLAG_LAST_ID = "custom_flag_last_id"  # running ID generator

    DENSITY_ARV_WINDOW_MS = "density_arv_window_ms"
    DENSITY_SCALE_MAX_MV = "density_scale_max_mv"
    DENSITY_PLAYBACK_FPS = "density_playback_fps"
    DENSITY_DEFAULT_SPEED = "density_default_speed"
    CUSTOM_ELECTRODE_LAYOUTS = "custom_electrode_layouts"

    # Global Amplitude QC - the definition
    GA_QC_DERIVATION = "ga_qc_derivation"
    GA_QC_METHOD = "ga_qc_method"
    GA_QC_DIFF_DIRECTION = "ga_qc_diff_direction"
    GA_QC_BPF_LOW_HZ = "ga_qc_bpf_low_hz"
    GA_QC_BPF_HIGH_HZ = "ga_qc_bpf_high_hz"
    GA_QC_SMOOTH_HZ = "ga_qc_smooth_hz"
    GA_QC_LINE_FREQ_HZ = "ga_qc_line_freq_hz"

    # Global Amplitude QC - windowing
    GA_QC_REST_BELOW_PCT = "ga_qc_rest_below_pct"
    GA_QC_MIN_REST_S = "ga_qc_min_rest_s"
    GA_QC_PEAK_WINDOW_MS = "ga_qc_peak_window_ms"
    GA_QC_FALLBACK_S = "ga_qc_fallback_s"

    # Global Amplitude QC - grid verdict
    GA_QC_GRID_PASS = "ga_qc_grid_pass"
    GA_QC_GRID_BORDERLINE = "ga_qc_grid_borderline"
    GA_QC_MIN_CHANNEL_FRACTION = "ga_qc_min_channel_fraction"

    # Global Amplitude QC - channel checks (bounds, weights, on/off)
    GA_QC_CHANNEL_BOUNDS = "ga_qc_channel_bounds"
    GA_QC_CHANNEL_WEIGHTS = "ga_qc_channel_weights"
    GA_QC_CHANNEL_ENABLED = "ga_qc_channel_enabled"
