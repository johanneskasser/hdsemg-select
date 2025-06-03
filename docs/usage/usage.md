# Usage Guide

This guide covers the main functionality of hdsemg-select and how to effectively use its features.

## File Management

### Supported File Formats
- `.mat` files
- `.otb+` files
- `.otb4` files

### Loading Data
1. Go to **"File" -> "Open..."**
2. Select your data file
3. The application will attempt to auto-detect the grid configuration

## Grid Configuration

### Automatic Grid Detection
The application automatically detects:
- Grid size
- Inter-electrode distance
- Channel arrangement

### Manual Configuration
If automatic detection fails:
1. Use the manual grid configuration dialog
2. Set rows and columns
3. Define inter-electrode distance
4. Specify orientation (parallel/perpendicular to muscle fibers)

## Channel Management

### Manual Selection
- Use checkboxes to mark channels as "good"
- Click individual channels in the Electrode Widget
- Toggle selection status in the detailed view

### Automatic Selection
Access via "Automatic Selection" menu:
- **Select All**: Toggle all channels
- **Amplitude Based**: Select channels based on configurable thresholds

## Artifact Detection

### Configuration
1. Navigate to **"File" -> "Settings"**
2. Select **"Automatic Channel Flagging Settings"** tab
3. Configure:
   - Frequency thresholds
   - Variance thresholds
   - Frequency bands
   - ECG detection parameters
   - Power line noise detection (50Hz/60Hz)

### Running Artifact Detection
1. Load your data file
2. Go to **"Automatic Selection" -> "Suggest Artifact Flags..."**
3. Review suggested flags in:
   - Channel widgets
   - Detailed view
4. Manually adjust flags if needed

## Visualization Tools

### Dashboard View
- File metadata
- Channel statistics
- Selection count
- Sampling rate information

### Electrode Widget
- Numbered channel display
- Selection status indicators
- Channel flag visualization
- Grid orientation controls

### Detail Viewer
- Time-domain signal plots
- Frequency spectrum analysis
- Channel-specific metrics
- Flag/label management

### Signal Overview
- Amplitude-normalized channel display
- Action potential propagation visualization
- Row/column bold line emphasis
- Signal view options:
  - Monopolar (MP)
  - Single Differential (SD)
  - Double Differential (DD)

## Data Export

### JSON Export
1. Select **"File" -> "Save Selection"**
2. Choose save location
3. Exported data includes:
   - Channel selection status
   - Artifact flags
   - Grid configuration
   - Channel metadata

### Cleaned Data Export
- Automatically generates cleaned `.mat` files
- Options to exclude:
  - Selected channels
  - Flagged channels
  - Custom labeled channels

## Performance Considerations

### Large File Handling
- Warning messages for large files
- Abort option during loading
- Pagination for better performance
- Memory usage optimization

### Efficient Navigation
- Use page navigation for large datasets
- Utilize thumbnails for quick overview
- Apply filters to manage large channel counts
