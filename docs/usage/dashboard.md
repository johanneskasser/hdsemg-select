## Dashboard

The dashboard is the central interface of the **hdsemg-select** application, providing access to all major features. It gives an overview of the loaded data, the current grid position, and tools for reviewing and cleaning HD-sEMG recordings.

![Dashboard](../img/dashboard.png)

### Overview of Dashboard Components

Once you've loaded HD-sEMG data (see the [Getting Started Guide](getting_started.md) if needed), the dashboard displays several interactive components:

* **Grid Navigation**
  Navigate through electrode rows and columns using the on-screen controls or keyboard arrow keys.

* **Signal Plot**
  View the time-domain signal from individual channels.

  * Channels can be toggled on/off using the checkboxes below the plot.
  * Use the **"View Time Series"** button (expand icon) to open a larger, interactive plot.
  * Use the **"View Frequency Spectrum"** button (frequency icon) to inspect the frequency content of a channel.

* **Electrode Grid Visualization**
  Displays the electrode layout with the currently selected row or column highlighted.
  Use the **"Rotate View"** button to switch between row-wise and column-wise views.

* **Metadata Panel**
  Shows metadata about the loaded file, including:

  * File name, size, total number of channels (including reference channels) and sampling frequency
  * Number of selected channels

* **Currently Selected Grid and Orientation**
  Displays the currently active grid and fiber orientation (rows or columns).
  * By clicking on the panel, the **Grid and Orientation Selection** dialog can be reopened to change the grid or orientation.
  <br>
  ![Grid and Orientation Selection Dialog](../img/grid_orientation_dialog.png)
* **Selection Controls**

  * **Select All**: Activates all channels in the current grid view.
  * **Deselect All**: Deactivates all channels in the current grid view.

* **Label Management**
  Assign or edit labels for individual channels (see [Channel Flagging](channel_flagging.md) for details).

  * **Label Dropdown**: Assign a label to the currently selected channel.
  * **Displayed Labels**: All applied labels are shown below each corresponding channel.

* **Reference Signal Display**
  Toggle the visibility of the reference signal for the current grid.

  * You can choose which reference to display via the dropdown next to the checkbox.

* **Signal Overview Plot**
  Opens a detailed plot of all selected channels to help identify artifacts or abnormal patterns.
  For more information, see [Signal Overview Plot](signal_overview_plot.md).

* Application Menu
  Access additional features and settings via the menu bar at the top of the window.
  * **File Menu**: Open and Save Data and Open Application Settings (see [Application Settings](application_settings.md)).
  * **Grid**: Change the grid and fiber orientation. Opens the **Grid and Orientation Selection** dialog.
  * **Automatic Selection**: 
    * Amplitude-based selection: Automatically selects channels based on amplitude thresholds (see [Automatic Channel Selection](automatic_selection.md)).
    * Automatic Channel Flagging: Automatically assigns flags to channels based on predefined criteria (see [Automatic Labeling](channel_flagging.md)).
---

### Reference Signal Behavior

By default, **all reference signals are automatically selected and included** in the exported data. You do not need to select them manually.

