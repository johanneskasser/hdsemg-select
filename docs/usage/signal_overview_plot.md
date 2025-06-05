## Signal Overview Plot

The **Signal Overview Plot** is a powerful tool that allows you to visualize the full grid of HD-sEMG signals at once. This view is especially useful for identifying action potential propagation patterns and determining the correct orientation of the electrode grid (i.e., whether rows or columns are aligned with the muscle fibers).

![Signal Overview Plot](../img/signal_overview_plot/signal_overview_plot.png)

---

## Purpose

The Signal Overview Plot serves two key purposes:

- **Visual Inspection of Action Potentials (APs):**  
  You can easily identify propagation patterns and noisy channels by reviewing the full recording in a compressed yet informative layout.

- **Orientation Decision:**  
  You can decide whether the **rows** or **columns** of the grid are parallel to the muscle fibers. This orientation is crucial for accurate physiological interpretation and propagation analysis.

---

## View Settings

### Parallel Orientation Control

At the top of the window, you will find a button labeled with the current orientation 🔄 (e.g., `8 Columns are parallel to muscle fibers`).  
- **Click this button to rotate the view**, i.e., to switch between visualizing columns or rows as aligned with the fibers.
- If you close the overview window, the **current view setting will be saved and applied**, updating the active grid orientation used throughout the application.

---

## Signal Type Options

You can choose the representation type for your signals using the dropdown labeled **Signal Type**:

| Signal Type | Description |
|-------------|-------------|
| **Monopolar (MP)** | Raw signals from each electrode. Useful for checking overall signal integrity. |
| **Single Differential (SD)** | Differences between adjacent electrodes along the fiber axis. Helps highlight local signal structure. |
| **Double Differential (DD)** | Enhanced spatial derivative emphasizing AP propagation. Often used for detecting MUAP propagation along muscle fibers. |

Switching between these modes allows you to evaluate your signals from different perspectives and better detect propagation trends or noise.

The views are calculated using the methods from the [hdsemg-shared](https://github.com/johanneskasser/hdsemg-shared) library.

---

## Navigation and Tools

The toolbar in the top-left corner of the plot provides additional tools:
-  Reset View
-  Zoom & Pan
-  Rotate View (toggle orientation)
-  Show/Hide Grid or Axes
-  Save Image

These tools allow for flexible interaction with the signal data and quick export of your current view.

---

## Recommended Use

- Use **Monopolar view** to identify noisy or flat channels and evaluate baseline stability.
- Switch to **Double Differential view** to observe motor unit action potential propagation across the grid.
- Rotate the view to match your expected muscle fiber orientation and confirm that APs propagate consistently along the intended axis.
- Once confident, **close the dialog** to lock in your orientation setting (rows or columns parallel to muscle fibers).

> This step is critical before performing spatial analyses or using automatic decomposition tools.

---

## Summary

| Feature                  | Description                                      |
|--------------------------|--------------------------------------------------|
| Signal Types             | Monopolar, Single Differential, Double Differential |
| View Orientation Toggle  | Align view to muscle fiber direction (rows or columns) |
| Signal Propagation Check| Helps visually confirm direction of MUAPs        |
| Configuration Persistence| Selection is applied when closing the dialog     |
