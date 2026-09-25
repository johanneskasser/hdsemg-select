## Fiber Trajectory Analysis

The **Fiber Trajectory Analysis** estimates, for one grid, the direction in which motor unit action potentials travel across the electrodes. From that direction it reports the fiber angle relative to the grid, the conduction velocity and, if one lies under the grid, the position of the innervation zone. Use it to check whether a grid was placed along the fibers, or to find out why a grid yields few motor units.

![Fiber Trajectory Analysis with a detected innervation zone](../img/fiber_trajectory/fiber_trajectory_iz.png)

---

## Opening the Dialog

Go to **Signal → Fiber Trajectory Analysis...**

> The menu item is only enabled after a file has been loaded and a grid has been configured.

---

## Controls

| Control | Description |
|---------|-------------|
| **Grid** | The grid to analyse. |
| **Window** | Shows which part of the signal is used: the full signal, or the crop range if one is set (see [Crop Signal](crop_signal.md)). |
| **Run Analysis** | Runs the angle search and fills the result cards and plots. |
| **Auto Detect** | Runs the analysis and suggests a grid orientation: within ±20° the fibers run along the columns, beyond ±70° along the rows. In between the fibers run obliquely and no orientation change is suggested. |
| **Export JSON** | Saves the results, the full angle search and the pairwise delays to a JSON file. |

## Results

| Card | Meaning |
|------|---------|
| **Fiber angle** | Angle of the fiber direction, measured from the column axis (0° = parallel to the columns, ±90° = parallel to the rows). |
| **Conduction velocity** | Propagation speed along the fiber direction, in m/s. |
| **IZ position** | Position of the innervation zone along the fiber direction, in mm. `n/d` if no innervation zone lies under the grid, which is normal when the grid covers only one side of it. |
| **Alignment (R²)** | How well the delays fit a single propagation direction. Values of 0.80 and above are good, 0.60 to 0.80 moderate, below 0.60 unreliable. |

The left plot shows the electrode grid with the estimated fiber trajectory. If an innervation zone is detected, it is drawn as a dashed line and the electrodes closest to it are highlighted. The right plot shows R² over all search angles; the selected angle is marked.

## Reading the Result

A clear result has one distinct peak in the angle search and a high R²:

![Clear fiber direction](../img/fiber_trajectory/fiber_trajectory_aligned.png)

A low R² with several competing peaks means the direction is not well defined. Typical causes are poor signal quality on part of the grid, a grid placed across the fibers, or a window that contains more rest than contraction. Cropping to a clean contraction burst often helps.

![Poorly defined fiber direction](../img/fiber_trajectory/fiber_trajectory_poor_fit.png)

---

## Method

Pairwise cross-correlation between electrodes and delay plane fitting, following Farina & Merletti, *J Neurosci Methods* 134:199–208, 2004. The innervation zone is detected as a sign reversal of the delays between adjacent positions along the fiber direction.
