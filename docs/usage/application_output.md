## Application Output

The Application Output section provides an overview of how the **hdsemg-select** application handles data export and what information is included in the output files.

### Export Data

Once you are finished reviewing and cleaning your HD-sEMG data, you can export the processed data for further analysis via the Menu "File" -> "Save Selection". 
This will open a file dialog where you can choose the export location. Once you select the location, the application will create two files:

- A **JSON** file containing metadata and channel flags.
- A **MAT** file that contains a cleaned version of the original data file.

### Export Formats
The application supports exporting data in the following formats:
- **JSON**: A structured format that includes metadata and channel flags.
- **MAT**: A cleaned version of the original data file, which can be used for further analysis in MATLAB or similar environments.

### JSON Export
When you export data to JSON, the following information is included:
- **File Metadata**: Information about the original file, such as filename, sampling rate, and grid configuration.
- **Channel Metadata**: Details about each channel, including:
  - Channel number
  - Selection status (selected or not)
  - Flags (e.g., artifact, bad channel, ECG contamination)
  - Custom labels
- **Grid Configuration**: Information about the electrode grid, including orientation (rows or columns) and reference channels.
- **Global Amplitude QC** (only when [QC](global_amplitude_qc.md) has been run): a `global_amplitude` block per grid holding the amplitude definition, the analysis windows, the measured floor and peak and the verdict, plus a `qc` block per channel holding its seven measured values, the state each produced, the grade and the CQI.

```json
{
  "filename": "example.mat",
  "layout": {
        "layout_mapping": {
            "parallel": "cols",
            "perpendicular": "rows"
        },
        "set_by_user": "False" // indicates if the grid was set by the user or auto-detected
    },
  "total_channels_summary": [
    {
      "channel_index": 0,
      "channel_number": 1,
      "selected": true,
      "description": "Grid1_1x1",
      "labels": []
    },
     {
      "channel_index": 1,
      "channel_number": 2,
      "selected": false,
      "description": "Grid1_1x2",
      "labels": ["ECG", "Artifact"]
    },
    {
      "channel_index": 15,
      "channel_number": 16,
      "selected": true,
      "description": "Grid1_4x4",
      "labels": ["Noise_60Hz"]
    }
    ...
  ],
  "grids": [
    {
      "grid_key": "Grid1",
      "rows": 4,
      "columns": 4,
      "inter_electrode_distance_mm": 10,
      "channels": [
        {
          "channel_index": 0,
          "channel_number": 1,
          "selected": true,
          "description": "Grid1_1x1",
          "labels": []
        },
        {
          "channel_index": 1,
          "channel_number": 2,
          "selected": false,
          "description": "Grid1_1x2",
          "labels": ["ECG", "Artifact"]
        },
        ...
      ]
    }
    ...
  ]
}
```

#### Quality control block

Running [Global Amplitude QC](global_amplitude_qc.md) adds two things to the JSON. Per grid:

```json
"global_amplitude": {
    "derivation": "DD", "method": "RMS", "diff_direction": "cols",
    "channel_scope": "selected",
    "amplitude_unit": "mV", "amplitude_unit_source": "assumed",
    "amplitude_unit_warning": null,
    "rest_windows_s": [[0.0, 7.4], [24.6, 31.0]],
    "peak_window_s": [13.86, 14.11],
    "window_source": "force",
    "reference_signal": "Performed Path",
    "resting_floor_raw": 0.00858, "resting_floor_uv": 8.58,
    "peak_mean_raw": 0.01147, "peak_mean_uv": 11.47,
    "activation_ratio": 1.34, "verdict": "fail",
    "thresholds": { "pass": 1.5, "borderline": 1.3, "min_channel_fraction": 0.5 },
    "n_channels_contributing": 48, "n_channels_selected": 58, "n_channels_total": 64
}
```

And per channel, inside its entry in the grid's `channels` list:

```json
"qc": {
    "values": { "activation_ratio": 1.21, "neighbor_correlation": 0.27, "flat": false },
    "states": { "activation_ratio": "borderline", "neighbor_correlation": "borderline" },
    "grade": "borderline", "cqi": 61, "worst_check": "activation_ratio"
}
```

The measured values and the thresholds that turned them into a verdict are both stored, so a reviewer can re-derive either one without the other — including after the thresholds are changed.

### MAT Export
When exporting to MAT format, the application creates a cleaned version of the original data file. This file includes everything the original file had, but removes the deselected channels from the data and the descriptions array. Therefore, the size of the length of the data and descriptions array will be equal to the number of selected channels. The MAT file can be used for further analysis in MATLAB or similar environments.

