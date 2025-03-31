<div align="center">
<br>
  <img src="src/resources/icon.png" alt="App Icon" width="100" height="100"><br>
    <h2 align="center">🧼 hdsemg-pipe 🧼</h2>
    <h3 align="center">HDsEMG data cleaning tool</h3>
</div>

---

A graphical user interface (GUI) application for selecting and analyzing HDsEMG channels from `.mat` files. This tool
helps identify and exclude faulty channels (e.g., due to electrode misplacement or corrosion) from HDsEMG recordings,
enabling more accurate and efficient analysis.

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [File Format](#file-format)
- [Requirements](#requirements)
- [Contributing](#contributing)

---

## Features

- ✅ Load `.mat` files and visualize multi-channel HDsEMG signals.
- 🧠 Automatic detection of grid size via inter-electrode distance.
- ✏️ Manual grid configuration when automatic detection fails.
- 🔄 Switch between grid orientations (parallel/perpendicular to muscle fibers).
- 🖼 Grid and signal visualization:
    - Electrode Widget with numbered and selectable channels.
    - Overview with page navigation and signal thumbnails.
    - Detailed viewer with time-domain and frequency spectrum plots.
- ✅ Manual and automatic channel selection.
    - 📈 Amplitude-based selection with configurable thresholds.
    - 📊 Frequency-based analysis (planned).
- 💾 Save selections in structured `.json` files and automatically generate cleaned `.mat` files.
- 🖥 Dashboard with file metadata: filename, number of channels, sampling rate, size, selection count.
- ⏱ Efficient loading with warnings and abort option for large data.

---

## Screenshots

| Dashboard                                 | Electrode Widget                                        |
|-------------------------------------------|---------------------------------------------------------|
| ![Dashboard](doc/resources/dashboard.png) | ![Electrode Widget](doc/resources/electrode_widget.png) |

| Detail Viewer                                           | Frequency Spectrum                                               | Raw Data Viewer                                                     |
|---------------------------------------------------------|------------------------------------------------------------------|---------------------------------------------------------------------|
| ![Detail Viewer](doc/resources/channel_detail_view.png) | ![Frequency Spectrum](doc/resources/frequency_spectrum_plot.png) | ![Raw Data Viewer](doc/resources/manual_grid_raw_channels_view.png) |

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/johanneskasser/hdsemg-select.git
   cd hdsemg-select

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python src/main.py
   ```

---

## Usage

### Load a File

- Click **"Load File"** and select a `.mat` file.
- The app attempts to auto-detect the grid based on inter-electrode distance.
- Alternatively, configure the grid manually.

### Navigate and Visualize

- Channels are shown in pages for performance.
- Use **Next/Previous** buttons to navigate pages.
- Click the **eye icon** for a detailed channel view (amplitude + frequency).

### Select Channels

- Mark individual channels as "good" using checkboxes.
- Use **Select All** to toggle all channels.
- Automatic selection available (Amplitude-based).

### Save Selection

- Click **"Save Selection"** to export selection to `.json`.

---

## File Format

A saved `.json` file includes:

```json
{
  "filename": "example.mat",
  "grids": [
    {
      "columns": 4,
      "rows": 4,
      "inter_electrode_distance_mm": 10,
      "channels": [
        {
          "channel": 1,
          "selected": true
        },
        {
          "channel": 2,
          "selected": false
        },
        ...
      ]
    }
  ]
}
```

---

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`
- Tested on: Linux and Windows 11

---

## 🔗 Related Tools

- [hdsemg-pipe App 🧼](https://github.com/johanneskasser/hdsemg-pipe.git)
- [openhdemg 🧬](https://github.com/GiacomoValliPhD/openhdemg)

---

## Contributing

Pull requests are welcome! If you find a bug or want to suggest a feature, feel free
to [open an issue](https://github.com/haripen/Neuromechanics_FHCW/issues).

---
