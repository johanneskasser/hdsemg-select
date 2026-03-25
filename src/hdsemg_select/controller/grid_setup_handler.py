# grid_setup_handler.py
import numpy as np
from PyQt5.QtWidgets import QMessageBox
from hdsemg_select._log.log_config import logger
from hdsemg_select.state.enum.layout_mode_enums import FiberMode, LayoutMode
from hdsemg_select.state.state import global_state
from hdsemg_select.ui.electrode_layout import get_display_grid


class GridSetupHandler:
    def __init__(self):
        # Local variables derived from grid info and selection
        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.fiber_orientation: FiberMode = None
        self.rows = 0
        self.cols = 0
        self.items_per_page = 16  # Default, will be updated based on grid/orientation
        self.total_pages = 0
        self.selected_grid = None
        self._electrode_display_grid = None   # Optional[np.ndarray] shape (rows, cols)
        self._electrode_number_map = {}       # dict[data_idx, int] — 1-based electrode number

    def apply_selection(self, selected_grid, orientation, parent_window):
        """
        Applies the selected grid and orientation, calculates display parameters.
        Returns True on success, False on failure. Updates self attributes.
        """
        if not global_state.get_emg_file().grids:
            logger.warning("apply_selection called without grid_info in state.")
            return False

        grid = global_state.get_emg_file().get_grid(grid_key=selected_grid)
        if grid is None:
            logger.error(f"Selected grid '{selected_grid}' not found in grid_info.")
            QMessageBox.critical(parent_window, "Grid Error", f"Selected grid '{selected_grid}' not found.")
            return False

        self.selected_grid = selected_grid
        if not isinstance(orientation, FiberMode):
            raise TypeError(f"Expected FiberMode, got {type(orientation)}")
        self.fiber_orientation = orientation
        grid_layout = global_state.get_layout_for_fiber(self.fiber_orientation)

        self.rows = grid.rows
        self.cols = grid.cols
        indices = grid.emg_indices

        # Validate the grid shape
        expected_electrodes = grid.electrodes
        if len(indices) != expected_electrodes:
            logger.error(
                f"Grid shape mismatch for '{selected_grid}': "
                f"Expected {expected_electrodes} indices, got {len(indices)}."
            )
            QMessageBox.critical(
                parent_window, "Grid Error",
                f"Grid shape mismatch: Configuration error for '{selected_grid}'. "
                f"Expected {expected_electrodes} channels, but file description indicates {len(indices)}."
            )
            return False

        # --- Try to get physical electrode layout ---
        electrode_name = self._extract_electrode_name(indices)
        display_grid = None
        if electrode_name:
            display_grid = get_display_grid(electrode_name, self.rows, self.cols)
            if display_grid is None:
                logger.debug(
                    f"No physical layout for electrode '{electrode_name}' "
                    f"({self.rows}×{self.cols}). Using fallback ordering."
                )
            else:
                logger.info(f"Using physical layout for electrode '{electrode_name}'.")

        self._electrode_display_grid = display_grid

        if display_grid is not None:
            self._apply_with_layout(indices, display_grid, grid_layout)
        else:
            self._apply_fallback(indices, grid_layout)

        self.total_pages = int(np.ceil(len(self.current_grid_indices) / self.items_per_page))
        self.current_page = 0

        logger.debug(f"Applied grid '{selected_grid}' ({self.rows}x{self.cols}, {self.fiber_orientation})")
        logger.debug(f"Items per page: {self.items_per_page}, Total pages: {self.total_pages}")
        logger.debug(f"Current grid indices (first 20): {self.current_grid_indices[:20]}")
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_electrode_name(self, indices) -> str:
        """Extract electrode model code from the description array.

        Descriptions may contain full strings like
        'Novecento+ (147 - 210) HD08MM0513 ch1 [MUSCLE:...]' — we pull out
        the first token matching the OTBiolab model-code pattern (e.g. HD08MM0513).
        """
        import re
        try:
            desc = global_state.get_emg_file().description
            if desc is None or len(indices) == 0:
                return ""
            first_ch = indices[0]
            if desc.ndim == 2:
                raw = str(desc[first_ch, 0].item()).strip()
            else:
                raw = str(desc[first_ch]).strip()
            # Try to pull out the electrode model code: 2 letters + digits + MM + digits
            match = re.search(r'\b([A-Z]{2}\d+MM\d{4})\b', raw)
            if match:
                return match.group(1)
            return raw  # fallback: return the whole string as before
        except Exception as e:
            logger.debug(f"Could not extract electrode name: {e}")
            return ""

    def _apply_with_layout(self, indices, display_grid: np.ndarray, grid_layout: LayoutMode):
        """Build current_grid_indices and maps using the physical electrode layout."""
        rows, cols = self.rows, self.cols

        # current_grid_indices: physical order per orientation.
        # None is used as a sentinel for NaN (empty) electrode positions so that
        # page slicing always aligns with column/row boundaries even when a
        # column or row has fewer than items_per_page valid electrodes.
        if grid_layout == LayoutMode.COLUMNS:
            # Column-major: page = one physical column
            self.items_per_page = rows
            ordered = [
                None if np.isnan(display_grid[r, c]) else indices[int(display_grid[r, c])]
                for c in range(cols)
                for r in range(rows)
            ]
        else:  # ROWS
            # Row-major: page = one physical row
            self.items_per_page = cols
            ordered = [
                None if np.isnan(display_grid[r, c]) else indices[int(display_grid[r, c])]
                for r in range(rows)
                for c in range(cols)
            ]
        self.current_grid_indices = ordered

        # grid_channel_map: data_idx → row-major position in (rows, cols) grid
        # electrode_number_map: data_idx → 1-based local electrode number
        gcm = {}
        enm = {}
        for r in range(rows):
            for c in range(cols):
                local_idx = display_grid[r, c]
                if np.isnan(local_idx):
                    continue
                data_idx = indices[int(local_idx)]
                gcm[data_idx] = r * cols + c
                enm[data_idx] = int(local_idx) + 1
        self.grid_channel_map = gcm
        self._electrode_number_map = enm

    def _apply_fallback(self, indices, grid_layout: LayoutMode):
        """Fallback ordering when no physical layout is known."""
        rows, cols = self.rows, self.cols
        full_grid_array = self.reshape_grid(indices, rows, cols, pad_value=None)
        if full_grid_array is None:
            logger.error(f"reshape_grid failed for fallback ({rows}×{cols})")
            # Still provide empty results so we don't crash
            self.current_grid_indices = [ch for ch in indices if ch is not None]
            self.items_per_page = rows
            self.grid_channel_map = {ch: i for i, ch in enumerate(self.current_grid_indices)}
            self._electrode_number_map = {ch: i + 1 for i, ch in enumerate(self.current_grid_indices)}
            return

        if grid_layout == LayoutMode.ROWS:
            self.items_per_page = cols
            flat_order = full_grid_array.flatten(order='C').tolist()
        else:
            self.items_per_page = rows
            flat_order = full_grid_array.flatten(order='F').tolist()

        self.current_grid_indices = [ch for ch in flat_order if ch is not None]

        # grid_channel_map: data_idx → row-major position (consistent with label_electrodes)
        gcm = {}
        enm = {}
        for r in range(rows):
            for c in range(cols):
                ch = full_grid_array[r, c]
                if ch is None:
                    continue
                gcm[ch] = r * cols + c
                enm[ch] = r * cols + c + 1  # sequential electrode number
        self.grid_channel_map = gcm
        self._electrode_number_map = enm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reshape_grid(self, indices, n_rows, n_cols, pad_value=None):
        """
        Pad a flat list `indices` up to length (n_rows * n_cols) using `pad_value`,
        then reshape into a NumPy array of shape (n_rows, n_cols).
        Returns None on error.
        """
        expected = n_rows * n_cols

        if len(indices) < expected:
            padded = list(indices) + [pad_value] * (expected - len(indices))
        elif len(indices) > expected:
            logger.error(
                f"safe_reshape_indices: {len(indices)} elements cannot fit into "
                f"{n_rows}×{n_cols} = {expected} slots."
            )
            return None
        else:
            padded = indices

        try:
            arr = np.array(padded).reshape(n_rows, n_cols)
        except ValueError as e:
            logger.error(f"safe_reshape_indices: reshape failed for shape ({n_rows},{n_cols}): {e}")
            return None

        return arr

    def get_electrode_display_grid(self):
        """Return the (rows, cols) physical layout array, or None if unknown."""
        return self._electrode_display_grid

    def get_electrode_number(self, data_idx: int) -> int:
        """Return 1-based electrode number within the grid for the given data channel index."""
        return self._electrode_number_map.get(data_idx, data_idx + 1)

    def get_current_grid_indices(self):
        return self.current_grid_indices

    def get_grid_channel_map(self):
        return self.grid_channel_map

    def get_orientation(self):
        return self.fiber_orientation

    def get_rows(self):
        return self.rows

    def get_cols(self):
        return self.cols

    def get_items_per_page(self):
        return self.items_per_page

    def get_total_pages(self):
        return self.total_pages

    def get_selected_grid(self):
        return self.selected_grid

    def get_current_page(self):
        return self.current_page

    def set_current_page(self, page_num):
        self.current_page = page_num

    def increment_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1

    def decrement_page(self):
        if self.current_page > 0:
            self.current_page -= 1
