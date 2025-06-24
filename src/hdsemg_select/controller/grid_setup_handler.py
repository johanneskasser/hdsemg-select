# grid_setup_handler.py
import numpy as np
from PyQt5.QtWidgets import QMessageBox
from hdsemg_select._log.log_config import logger
from hdsemg_select.state.enum.layout_mode_enums import FiberMode, LayoutMode
from hdsemg_select.state.state import global_state # Import global state

class GridSetupHandler:
    def __init__(self):
        # Local variables derived from grid info and selection
        self.current_grid_indices = []
        self.grid_channel_map = {}
        self.fiber_orientation: FiberMode = None
        self.rows = 0
        self.cols = 0
        self.items_per_page = 16 # Default, will be updated based on grid/orientation
        self.total_pages = 0
        self.selected_grid = None

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
        grid_layout = global_state.get_layout_for_fiber(self.fiber_orientation) # get the layout for the selected fiber orientation, can be defined by user

        self.rows = grid.rows
        self.cols = grid.cols
        indices = grid.emg_indices


        # Validate the grid shape
        expected_electrodes = grid.electrodes
        if len(indices) != expected_electrodes:
             logger.error(f"Grid shape mismatch for '{selected_grid}': Expected {expected_electrodes} indices, got {len(indices)}.")
             QMessageBox.critical(
                 parent_window, "Grid Error",
                 f"Grid shape mismatch: Configuration error for '{selected_grid}'. Expected {expected_electrodes} channels, but file description indicates {len(indices)}."
             )
             return False

        full_grid_array = self.reshape_grid(indices, self.rows, self.cols, pad_value=None)
        if full_grid_array is None:
            # Either too many indices or reshape blew up
            logger.error(f"Failed to reshape grid indices for '{selected_grid}'.")
            QMessageBox.critical(
                parent_window, "Grid Error",
                f"Failed to reshape grid indices for '{selected_grid}'. "
                "Check grid dimensions and indices."
            )
            return False


        if grid_layout == LayoutMode.ROWS:
            self.current_grid_indices = full_grid_array.flatten(order='C').tolist() # row-major order
            self.items_per_page = self.cols # Items per page depends on display orientation
            full_flattened_indices = full_grid_array.flatten(order='C').tolist()
        else: # 'parallel' or default
            self.current_grid_indices = full_grid_array.flatten(order='F').tolist() # column-major order
            self.items_per_page = self.rows # Items per page depends on display orientation
            full_flattened_indices = full_grid_array.flatten(order='F').tolist()

        self.current_grid_indices = [ch for ch in self.current_grid_indices if ch is not None]

        self.grid_channel_map = {ch_idx: i for i, ch_idx in enumerate(full_flattened_indices) if ch_idx is not None}
        self.current_grid_indices = [ch for ch in full_flattened_indices if ch is not None]


        self.total_pages = int(np.ceil(len(self.current_grid_indices) / self.items_per_page))
        self.current_page = 0 # Reset page on grid change

        logger.debug(f"Applied grid '{selected_grid}' ({self.rows}x{self.cols}, {self.fiber_orientation})")
        logger.debug(f"Items per page: {self.items_per_page}")
        logger.debug(f"Total pages: {self.total_pages}")
        logger.debug(f"Current grid indices (first 20): {self.current_grid_indices[:20]}")
        # logger.debug(f"Grid channel map (first 20): {list(self.grid_channel_map.items())[:20]}") # Can be large

        return True # Indicate success

    def reshape_grid(self, indices, n_rows, n_cols, pad_value=None):
        """
            Pad a flat list `indices` up to length (n_rows * n_cols) using `pad_value`,
            then reshape into a NumPy array of shape (n_rows, n_cols). If len(indices)
            > n_rows*n_cols, or if reshape fails, logs an error and returns None.

            Parameters
            ----------
            indices : Sequence
                The flat list of channel indices (or whatever) you want to lay out in a grid.
            n_rows : int
                Number of rows for the final 2D array.
            n_cols : int
                Number of columns for the final 2D array.
            pad_value : any, optional
                The value to insert for “empty” spots if len(indices) < n_rows*n_cols.
                Often `None` if you want missing cells to be represented as None.

            Returns
            -------
            np.ndarray or None
                If successful, a (n_rows × n_cols) array. If indices are too long,
                or reshape still fails, returns None (and logs an error).
            """

        expected = n_rows * n_cols

        # 1) If there are too few indices, pad with pad_value
        if len(indices) < expected:
            padded = list(indices) + [pad_value] * (expected - len(indices))
        # 2) If there are too many indices, bail out
        elif len(indices) > expected:
            logger.error(
                f"safe_reshape_indices: {len(indices)} elements cannot fit into "
                f"{n_rows}×{n_cols} = {expected} slots. "
                "Dropping into error."
            )
            return None
        else:
            padded = indices

        # 3) Try to reshape
        try:
            arr = np.array(padded).reshape(n_rows, n_cols)
        except ValueError as e:
            logger.error(
                f"safe_reshape_indices: reshape failed for shape ({n_rows},{n_cols}): {e}"
            )
            return None

        return arr



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