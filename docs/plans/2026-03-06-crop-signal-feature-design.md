# Crop Signal Feature – Design Document
Date: 2026-03-06

## Summary

Add a "Crop Signal" feature to hdsemg-select that lets users interactively select a time-range ROI to crop all signals across all grids. The crop is reversible until the file is saved; saving writes the cropped data permanently.

## Requirements

- Open a crop editor dialog from a menu item
- Dialog plots selectable signals (all channels from `emg_file.description`, grouped by grid in GroupBoxes)
- User selects crop region via SpanSelector (drag) or two-click
- Crop is stored as `(start_idx, end_idx)` in `global_state` — reversible in-session
- All in-app plots (main channel view, signal overview) respect the crop
- On Save: crop range is applied to `emg_file.data` and `emg_file.time` before writing .mat

## Architecture

### New file: `src/hdsemg_select/ui/dialog/crop_signal.py`

`CropSignalDialog(QDialog)`:
- Reads data from `global_state.get_emg_file()` — no file loading
- Right sidebar: channels grouped by grid (QGroupBox per grid), all channels from `emg_file.description` as QCheckBoxes
- Pre-selects reference signal channels by default
- Matplotlib plot with SpanSelector + two-click mode + NavigationToolbar
- ROI info bar: start / end / duration labels
- Reset button → full range
- "Apply & Close" → stores result
- `get_crop_range() -> tuple[int, int]`

### Modified: `src/hdsemg_select/state/state.py`

Add:
```python
self._crop_range: tuple[int, int] | None = None  # (start, end) sample indices
```

Methods:
- `set_crop_range(range: tuple[int,int] | None)`
- `get_crop_range() -> tuple[int,int] | None`
- `get_effective_data() -> np.ndarray` — returns `scaled_data[start:end+1]` if crop set, else full `scaled_data`
- `get_effective_time() -> np.ndarray` — returns `emg_file.time[start:end+1]` if crop set, else full `time`

Reset `_crop_range = None` in `reset()`.

### Modified: `src/hdsemg_select/controller/menu_manager.py`

Add new top-level "Signal" menu with:
- `self.crop_signal_action = QAction("Crop Signal...", parent_window)`
- Shortcut: `Ctrl+R`
- Disabled until data loaded
- Triggers `parent_window.open_crop_dialog()`
- Store reference: `self.crop_signal_action`
- Add getter `get_crop_signal_action()`

### Modified: `src/hdsemg_select/ui/main_window.py`

- After file load: `self.crop_signal_action.setEnabled(True)`
- In `reset_to_start_state()`: `self.crop_signal_action.setEnabled(False)`; `global_state.set_crop_range(None)`
- New method `open_crop_dialog()`:
  ```python
  def open_crop_dialog(self):
      dlg = CropSignalDialog(parent=self)
      if dlg.exec_() == QDialog.Accepted:
          global_state.set_crop_range(dlg.get_crop_range())
          self.display_page(True)
  ```
- In `display_page()`: replace `global_state.get_scaled_data()` → `global_state.get_effective_data()`, replace `global_state.get_emg_file().time` → `global_state.get_effective_time()`
- In `ref_sig_signal_changed()`: same replacement for ref signal display

### Modified: `src/hdsemg_select/ui/plot/signal_overview_plot.py`

- In `_draw_plot()` (or equivalent): replace `global_state.get_emg_file().data` with `global_state.get_effective_data()` and `emg_file.time` with `global_state.get_effective_time()`

### Modified: `src/hdsemg_select/controller/file_management.py`

In `save_selection()`, before calling `emg_file.save()`:
- If `global_state.get_crop_range()` is set:
  - Apply crop to `emg_file.data` and `emg_file.time` in-place (or copy then save)
  - After saving, restore originals (or make the save permanent — user's choice is permanent on save)
  - Since save = permanent crop, modify `emg_file.data` and `emg_file.time` permanently and clear `global_state._crop_range`

## Data Flow

```
User opens "Crop Signal..."
  → CropSignalDialog (reads global_state emg_file)
  → User selects channels to display (all from description, grouped by grid)
  → User drags/clicks to select ROI
  → "Apply & Close"
  → global_state.set_crop_range((start, end))
  → display_page() refreshes with cropped view

User saves file
  → save_selection() reads crop_range
  → applies crop to emg_file.data[start:end+1] and emg_file.time[start:end+1]
  → emg_file.save() writes cropped .mat
  → crop_range cleared from state (data is now permanently cropped in memory)
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `ui/dialog/crop_signal.py` | CREATE |
| `state/state.py` | MODIFY |
| `controller/menu_manager.py` | MODIFY |
| `ui/main_window.py` | MODIFY |
| `ui/plot/signal_overview_plot.py` | MODIFY |
| `controller/file_management.py` | MODIFY |
