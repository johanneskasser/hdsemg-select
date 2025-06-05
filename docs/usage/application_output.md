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

### MAT Export
When exporting to MAT format, the application creates a cleaned version of the original data file. This file includes everything the original file had, but removes the deselected channels from the data and the descriptions array. Therefore, the size of the length of the data and descriptions array will be equal to the number of selected channels. The MAT file can be used for further analysis in MATLAB or similar environments.

