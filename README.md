# HDsEMG Channel Selector

A graphical user interface (GUI) application for selecting and analyzing HDsEMG channels from `.mat` files. The application allows for visualizing channel data, selecting channels as "good," toggling all channels, and saving the results in a `.json` format.

---

## Features

- Load `.mat` files and visualize channel data.
- Pagination for improved performance with large datasets.
- Detailed view for individual channels with interactive plots.
- Select or deselect all channels using a "Select All" checkbox.
- Save the selected channel information in a `.json` file, including:
  - File name
  - Grid layout
  - Selection status for each channel.

---

## Installation

1. Clone the repository or download the script.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

---

## Usage

### Loading a File
- Click the **Load File** button and select a `.mat` file to visualize the data.

### Visualizing Channels
- Channels are displayed as small plots in a grid format.
- Use the **Previous** and **Next** buttons to navigate through pages.

### Selecting Channels
- Each channel has a **checkbox** labeled "Good" to mark it as selected.
- Use the **Select All** checkbox to toggle all channels at once.

### Detailed View
- Click the **extend icon** next to a channel to open a detailed, interactive plot for that channel.

### Saving Selections
- Click the **Save Selection** button to save selected channel information in a `.json` file.

### Future Implementation
- Automatic Selection based on Frequency and Amplitude Analysis

---

## File Information
- The app displays:
  - File name and size.
  - Total number of channels in the file.
  - Number of currently selected channels.

---

## Requirements

- Python 3.8+
- Packages listed in `requirements.txt`.

---

## Example Output File

A saved `.json` file might look like this:

```json
{
    "filename": "example.mat",
    "grid": {
        "columns": 4,
        "rows": 4
    },
    "channels": [
        {"channel": 1, "selected": true},
        {"channel": 2, "selected": false}
    ]
}
```
### Notes:
- Replace `channelSelectionApp.py` in the commands with your script name if it's different.
- Ensure that the `"resources/extend.png"` eye icon file exists in the specified path or replace it with another valid icon.