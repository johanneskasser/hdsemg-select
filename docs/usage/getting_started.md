## Getting Started with hdsemg-shared

This guide walks you through the first steps of using the **hdsemg-shared** application to inspect and clean your high-density surface EMG (HD-sEMG) data.

---

### 1. Launching the Application

After completing the installation, start the application with the following command:

```bash
python main.py
```

This will open the application window and display the dashboard interface.

![Dashboard Empty](../img/dashboard_empty.png)

---

### 2. Loading Data

To load HD-sEMG data into the application:

1. Open the file explorer:
   Go to **File → Open…** or press `Ctrl + O`.

2. Choose a supported file:
   The application supports the following formats:

   * `.mat`
   * `.otb+`
   * `.otb4`
   * `.otb`

3. The application will attempt to **auto-detect the grid configuration**.
   If this fails, you’ll be prompted to configure the layout manually.

4. Once the file is recognized, a **Grid and Orientation Selection** dialog will appear:

   * Select the appropriate grid (if multiple are detected).
   * Choose the fiber orientation (whether rows or columns are aligned with the muscle fibers).
     If you're unsure, you can evaluate the orientation later by observing propagation patterns in the [Signal Overview Plot](signal_overview_plot.md) and adjust it if needed.

![Grid Orientation Dialog](../img/grid_orientation_dialog.png)

5. After confirming grid and orientation, the main dashboard will be displayed.

![Dashboard](../img/dashboard.png)

You can now navigate the grid using the bottom navigation buttons or your keyboard’s left/right arrow keys.

> For a detailed overview of the dashboard features, see the [Dashboard Guide](dashboard.md).