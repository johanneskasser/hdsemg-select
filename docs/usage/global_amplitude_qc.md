## Global Amplitude QC

**Global Amplitude QC** answers the question a channel browser cannot: *did this grid actually record physiological signal during the contraction?*

A grid can look plausible channel by channel and still be worthless — lifted off the skin, poorly gelled, placed over tendon rather than muscle belly, or recording a subject who never really contracted. QC measures the grid's global amplitude during the contraction against its own amplitude at rest, and grades every channel that contributed.

Nothing is deselected without your confirmation, and every measured number is written to the selection JSON next to the verdict it produced.

---

## Opening the Dialog

Go to **Signal → Global Amplitude QC…**

> The menu item is only enabled after a file has been loaded and a grid has been configured.
>
> The step needs `hdsemg-shared >= 0.14.1`. With an older version installed the dialog says so instead of opening.

---

## The Grid tab

### The plot

The global amplitude of the selected grid is drawn over the **performed path**, which sits behind it on a second y-axis scaled so the two align. What you are looking for is whether the amplitude rises *where the force does*.

| Overlay | Meaning |
|---------|---------|
| **Blue trace** | Global amplitude of the grid, in µV |
| **Amber fill** | The performed path (reference channel) on its own axis |
| **Light blue bands** | Rest windows — where the resting floor is measured |
| **Grey band** | Peak window — the 250 ms of highest amplitude inside the contraction |
| **Solid red line** | Resting floor: the median amplitude over the rest windows |
| **Dashed red line** | Pass mark: the floor times the required activation ratio |
| **Green bar** | Mean amplitude over the peak window |

### The verdict

```
activation ratio  =  mean(amplitude over the peak window)
                     ───────────────────────────────────
                      median(amplitude over the rest windows)
```

| Verdict | Meaning |
|---------|---------|
| **pass** | The peak reaches the required multiple of the resting floor (default 1.50 ×) |
| **borderline** | Between the borderline and pass marks (default 1.30 – 1.50 ×) |
| **fail** | The contraction never leaves the noise floor |
| **no verdict** | Measuring the selection, and fewer than half the grid's channels are in it — a verdict on a selection is not a verdict on a grid. The ratio is still measured and still stored |

### Amplitude units

`EMGFile` does not yet declare what unit its data is in ([hdsemg-shared#53](https://github.com/johanneskasser/hdsemg-shared/issues/53)), and OTB loaders return **millivolts**. QC therefore assumes millivolts and converts to microvolts for display and for the `*_uv` keys in the JSON, recording both the raw value and the unit it assumed.

If the resulting resting floor is not physiologically plausible — outside roughly 0.5 – 500 µV, which catches a factor of 1000 rather than a factor of two — the dialog shows a **Check the amplitude unit** warning naming the unit that *would* make it plausible, and the same warning is written to the JSON.

> The activation ratio is a ratio, so it is unaffected by the unit either way. Only the absolute amplitudes can be wrong.

Once `EMGFile` gains a `unit` attribute, QC reads it and stops assuming; the JSON records `"amplitude_unit_source": "file"` rather than `"assumed"`.

### Saving the plot

Both the global amplitude plot and the CQI heatmap carry the standard matplotlib toolbar — **Save** writes a PNG, PDF or SVG, alongside zoom, pan and reset, exactly as in Crop Signal and the Density Map.

While pan or zoom is active the toolbar owns the drag, so dragging then adjusts the view rather than the analysis windows. Switch the mode off to go back to setting windows.

### Adjusting the windows

Windows are detected from the performed path: rest is where the path sits within a few percent of its own force span above its own baseline, for at least two seconds; the peak window is placed at the highest global amplitude outside rest.

To correct a badly segmented trial, pick **peak window** or **rest window** in the drop-down under the plot and drag across the plot. The analysis re-runs on the new window. **Re-detect windows** discards your drag and segments from the performed path again.

If the grid has no reference signal, the first and last three seconds are used as rest instead, and the JSON records `"window_source": "fallback"` so a pooled analysis can filter those trials out.

### Which channels are measured

A file straight off disk has **every EMG channel deselected** — only reference signals start selected. QC is the step that *informs* a selection, so requiring one first would be backwards.

**Measure** in the top bar therefore offers:

| Setting | Meaning |
|---------|---------|
| **all channels** | Every channel of the grid enters the global amplitude, whatever the selection says. Defaults to this when the grid has no selection yet |
| **selected channels** | Only the selected channels. Defaults to this as soon as the grid has a selection |

The choice is recorded as `"channel_scope"` in the JSON — a ratio over the whole grid and one over a selection are not the same measurement, so it has to stay readable afterwards.

When the grid has no selection yet, **Suggest deselection** becomes **Suggested Selection**: it selects the channels that passed and leaves the failing ones out, making the first selection rather than deselecting from an empty one.

### The definition

**Derivation** (MP / SD / DD), **Method** (RMS / ARV) and **Difference along** (columns / rows) are chosen in the top bar and apply to the whole grid. They are written to the grid's `global_amplitude` block in the selection JSON when you save.

Point the difference axis along the muscle fibres. **Signal → Fiber Trajectory Analysis** measures which way they actually run, which is a better check than whether the orientation box was ticked correctly.

---

## The Channels tab

### The heatmap

Each electrode is coloured by its **Channel Quality Index (CQI)** and sits where it physically sits on the grid, so a bad patch reads as a patch rather than as a scattered list of channel numbers. Click a cell to see that channel's evidence.

| Colour | Grade |
|--------|-------|
| Green | pass |
| Amber | borderline |
| Red | fail |

### The seven checks

| Check | Question it answers |
|-------|---------------------|
| **Activation ratio** | Did this channel rise above its own rest? |
| **Amplitude robust z** | Is it unlike the rest of *this* grid? |
| **Spectrum robust z (MNF)** | Is its power in the wrong place? |
| **Line-noise ratio** | Does it pick up the mains? |
| **Clipping fraction** | Does it sit at the amplifier rail? |
| **Neighbour correlation** | Does it share anything with the electrodes next to it? |
| **Flat** | Is it dead? |

Each check has a **pass bound** and a **fail bound**. Between them the check is *borderline* and its sub-score ramps linearly.

> **The grade is the worst check, never an average.** One fatal defect must not be averaged away by six healthy ones. The **CQI** (0 – 100) is a weighted mean of the sub-scores and exists only to rank the list — it never decides a grade.

Amplitude and spectrum are scored against the channel's own grid with a **median/MAD robust z** rather than mean and standard deviation, because the outliers being looked for are *in* the sample: with two bad channels a classical z-score is inflated by exactly those two and hides the second one.

Neighbour correlation is measured **inside the peak window only**. Over a whole tracking trial — which is mostly rest — neighbouring monopolar channels share little but uncorrelated noise, so it collapses toward zero for good channels too. Calibrate its threshold on data you know to be good before rejecting anything with it.

### Looking at a borderline channel

A grade is a number; deciding whether to keep a borderline channel means looking at the signal behind it.

Select a channel — in the table, or by clicking its cell on the heatmap — and press **Show this channel's signal** (or double-click the row). The dialog plots the exact trace that channel contributes to the global amplitude, in the chosen derivation, with the rest and peak windows shaded so you can see what the grade was measured inside. Its own toolbar saves the plot.

**Keep channel** and **Discard channel** apply the decision to that one channel straight away.

> SD and DD are differences between neighbouring electrodes, so the electrodes at the edge of the difference axis have none — the last two rows of each column for DD. For those the dialog shows the monopolar trace and says so, rather than silently plotting something else.

---

## Deselecting failing channels

**Suggest deselection** lists the failing channels with the reason each was flagged, all pre-ticked. Untick anything you disagree with and confirm; nothing changes until you do.

Deselected channels keep their data in the `.mat` file — the JSON records the selection. Re-running QC afterwards recomputes the global amplitude over the channels that remain.

---

## What lands in the JSON

Per grid, alongside the existing `channels` and `reference_signals`:

```json
"global_amplitude": {
    "derivation": "DD",
    "method": "RMS",
    "diff_direction": "cols",
    "channel_scope": "selected",
    "amplitude_unit": "mV",
    "amplitude_unit_source": "assumed",
    "amplitude_unit_warning": null,
    "resting_floor_raw": 0.00858,
    "rest_windows_s": [[0.0, 7.4], [24.6, 31.0]],
    "peak_window_s": [13.86, 14.11],
    "window_source": "force",
    "reference_signal": "Performed Path",
    "resting_floor_uv": 8.58,
    "peak_mean_uv": 11.47,
    "activation_ratio": 1.34,
    "verdict": "fail",
    "thresholds": { "pass": 1.5, "borderline": 1.3, "min_channel_fraction": 0.5 },
    "n_channels_contributing": 48,
    "n_channels_selected": 58,
    "n_channels_total": 64
}
```

And per channel, a `qc` block holding the seven raw values, the state each produced, the grade and the CQI:

```json
"qc": {
    "values": { "activation_ratio": 1.21, "neighbor_correlation": 0.27, "flat": false, "...": 0 },
    "states": { "activation_ratio": "borderline", "neighbor_correlation": "borderline", "...": "pass" },
    "grade": "borderline",
    "cqi": 61,
    "worst_check": "activation_ratio"
}
```

**Export JSON** in the dialog writes the same report as a standalone file without saving the selection.

---

## Settings

**File → Settings → Global Amplitude QC** holds the defaults: the amplitude definition, the band-pass and smoothing, the windowing parameters, the grid verdict bounds, and the per-check bounds, weights and on/off switches.

> Nothing here returns a verdict on its own. Where a threshold sits depends on the muscle, the electrode, the task and the population — not on the measurement. That is why the numbers and the thresholds that produced a grade are both written to the JSON: either can be re-derived without the other.

---

## Method and references

**ⓘ About the method** in the dialog explains why the root is taken last, how the windows are found, and how a channel is graded, with the literature it rests on:

- Merletti R, Cerone GL. *Techniques for information extraction from the surface EMG signal*, eq. 5.1–5.2. In: Merletti & Farina (2016/2018)
- Del Vecchio A et al. *J Appl Physiol* (2025). doi:10.1152/japplphysiol.00810.2024
- Merletti R, Muceli S. *Tutorial. Surface EMG detection in space and time: Best practices.* J Electromyogr Kinesiol 49:102363 (2019)
- *Detection and Reconstruction of Poor-Quality Channels in High-Density EMG Array Measurements.* Sensors 23(10):4759 (2023)
