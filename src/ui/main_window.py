# main_window.py

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QScrollArea, QGridLayout, \
    QPushButton, QStyle, QCheckBox, QFileDialog, QDialog, QComboBox, QMessageBox

from _log.log_config import logger
from config.config_enums import Settings
from controller.file_management import FileManager
from controller.grid_setup_handler import GridSetupHandler
from controller.menu_manager import MenuManager
from select_logic.auto_flagger import AutoFlagger
from select_logic.channel_management import select_all_channels, update_channel_status_single, count_selected_channels
from settings.settings_dialog import SettingsDialog
from settings.tabs.auto_flagger_settings_tab import validate_auto_flagger_settings
from state.enum.layout_mode_enums import FiberMode
from state.state import global_state
from ui.channel_details import ChannelDetailWindow
from ui.channel_spectrum import ChannelSpectrum
from ui.plot.channel_widget import ChannelWidget
from ui.electrode_widget import ElectrodeWidget
from ui.selection.amplitude_based import AutomaticAmplitudeSelection
from config.config_manager import config
# noinspection PyUnresolvedReferences
import resources_rc


class ChannelSelector(QMainWindow):
    def __init__(self, input_file=None, output_file=None):
        super().__init__()
        self.setWindowTitle("hdsemg-select")
        self.setWindowIcon(QIcon(":/resources/icon.png"))
        self.setGeometry(100, 100, 1200, 800)
        self.setFocusPolicy(Qt.StrongFocus)

        self.app_settings_dialog = SettingsDialog()

        # Save startup parameters (if any)
        global_state.set_input_file(input_file)
        global_state.set_output_file(output_file)

        # Instantiate handlers
        self.menu_manager = MenuManager()
        self.file_handler = FileManager()
        self.grid_setup_handler = GridSetupHandler()
        self.checkboxes = []
        self.channels_per_row = 4
        self.auto_flagger = AutoFlagger()

        self.upper_quartile = None
        self.global_min = None
        self.global_max = None
        self.ylim = None
        self.channel_widgets = []

        # Create the main layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        self.outer_layout = QHBoxLayout(self.main_widget)
        self.electrode_widget = ElectrodeWidget(self)
        self.electrode_widget.signal_overview_plot_applied.connect(self.display_page)
        self.outer_layout.addWidget(self.electrode_widget)
        self.electrode_widget.setHidden(True)

        # Add a vertical line separator
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        self.outer_layout.addWidget(line)

        # Right side vertical layout
        self.layout = QVBoxLayout()
        self.outer_layout.addLayout(self.layout)

        # Header layout
        self.header_layout = QHBoxLayout()
        self.layout.addLayout(self.header_layout)

        # File info label
        self.info_label = QLabel("No file loaded. Use File -> Open... to load a .mat file.")
        self.header_layout.addWidget(self.info_label)

        # Scroll area for channel plots
        self.scroll_area = QScrollArea(self)
        self.scroll_widget = QWidget()
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.layout.addLayout(self.pagination_layout)

        self.prev_button = QPushButton()
        self.prev_button.setToolTip("Previous (Left Arrow)")
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.prev_button.clicked.connect(self.prev_page)
        self.pagination_layout.addWidget(self.prev_button)

        self.page_label = QLabel("Page 1/1")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.pagination_layout.addWidget(self.page_label)

        self.next_button = QPushButton()
        self.next_button.setToolTip("Next (Right Arrow)")
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.next_button.clicked.connect(self.next_page)
        self.pagination_layout.addWidget(self.next_button)

        # Create the menu bar using the MenuManager
        self.automatic_selection = AutomaticAmplitudeSelection(self)  # Keep AutomaticSelection here
        self.create_menus()  # This method now delegates to MenuManager

        self.grid_label = QLabel("")
        self.grid_label.setAlignment(Qt.AlignCenter)
        self.grid_label.setHidden(True)
        font = QFont()
        font.setPointSize(10)
        self.grid_label.setFont(font)
        self.header_layout.addWidget(self.grid_label)

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        self.select_all_checkbox.setEnabled(False)
        self.header_layout.addWidget(self.select_all_checkbox)

    def create_menus(self):
        """Delegates menu creation to the MenuManager."""
        menubar = self.menuBar()
        self.menu_manager.create_menus(menubar, self)

        # Get references to actions/menus created by the manager to control their enabled state
        self.save_action = self.menu_manager.get_save_action()
        self.change_grid_action = self.menu_manager.get_change_grid_action()
        self.amplidude_menu = self.menu_manager.get_amplitude_menu()
        self.suggest_flags_action = self.menu_manager.get_suggest_flags_action()

    def load_file(self):
        """Opens a file dialog and triggers file loading."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "MAT Files (*.mat)", options=options)
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path):
        """
        Loads a file from the provided path using the FileManager.
        """
        # Delegate file processing to the FileManager
        success = self.file_handler.process_file(file_path, self)  # Pass self for parent window context

        if success:
            # Update UI elements enabled/disabled state based on successful load and processing
            self.change_grid_action.setEnabled(True)
            self.amplidude_menu.setEnabled(True)

            # Update UI elements enabled/disabled state based on successful load and processing
            if hasattr(self, 'change_grid_action') and self.change_grid_action: self.change_grid_action.setEnabled(True)
            if hasattr(self, 'amplidude_menu') and self.amplidude_menu: self.amplidude_menu.setEnabled(True)
            if hasattr(self, 'save_action') and self.save_action: self.save_action.setEnabled(True)
            if hasattr(self, 'suggest_flags_action') and self.suggest_flags_action: self.suggest_flags_action.setEnabled(True)

            # Trigger grid selection after successful file processing
            self.select_grid_and_orientation()

            self.electrode_widget.setHidden(False)
            self.setWindowTitle(f"hdsemg-select - Amplitude over Time - {global_state.get_file_name()}")  # Use getter
        else:
            self.reset_to_start_state()

    def select_grid_and_orientation(self):
        """Opens dialog to select grid and orientation."""
        # Access grid info from state to populate the dialog
        grid_info = global_state.get_grid_info()
        if not grid_info:
            return  # Should not happen if load_file_path succeeded, but safety check

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Grid and Orientation")
        layout = QVBoxLayout()

        grid_label = QLabel("Select a Grid:")
        layout.addWidget(grid_label)

        grid_combo = QComboBox()
        for grid_key in grid_info.keys():
            grid_combo.addItem(grid_key)
        layout.addWidget(grid_combo)

        orientation_label = QLabel("Select Orientation:")
        layout.addWidget(orientation_label)

        orientation_combo = QComboBox()
        orientation_combo.addItem("Parallel to fibers", FiberMode.PARALLEL)
        orientation_combo.addItem("Perpendicular to fibers", FiberMode.PERPENDICULAR)
        layout.addWidget(orientation_combo)

        ok_button = QPushButton("OK")

        def on_ok():
            selected_grid = grid_combo.currentText()
            orientation: FiberMode = orientation_combo.currentData()
            # Call method to apply selection logic
            self.apply_grid_selection(selected_grid, orientation, dialog)

        ok_button.clicked.connect(on_ok)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def apply_grid_selection(self, selected_grid, orientation, dialog):
        """Applies the selected grid and orientation using the GridSetupHandler."""

        # Delegate the calculation and logic to the handler
        success = self.grid_setup_handler.apply_selection(selected_grid, orientation,
                                                          self)
        if success:
            self.rows = self.grid_setup_handler.get_rows()
            self.cols = self.grid_setup_handler.get_cols()
            self.items_per_page = self.grid_setup_handler.get_items_per_page()
            self.total_pages = self.grid_setup_handler.get_total_pages()
            self.grid_setup_handler.set_current_page(0)  # Ensure page resets on grid change

            dialog.accept()

            # Update UI elements based on new grid setup
            self.electrode_widget.set_grid_shape((self.rows, self.cols))
            self.electrode_widget.label_electrodes()
            self.electrode_widget.set_orientation_highlight(self.grid_setup_handler.get_orientation(),
                                                            self.grid_setup_handler.get_current_page())

            self.display_page()  # Refresh the display

            # Enable relevant actions
            self.save_action.setEnabled(True)
            self.select_all_checkbox.setEnabled(True)
            # Update grid label using values from handler
            self.grid_label.setText(f"{self.rows}x{self.cols} grid - {self.grid_setup_handler.get_orientation().name.title()}")
            self.grid_label.setHidden(False)
        else:
            # Grid setup failed (message box already shown by handler)
            dialog.reject()
            pass

    def toggle_select_all(self):
        """Toggles selection status for all channels."""
        # Get channel status from state
        channel_status = global_state.get_channel_status()

        if self.select_all_checkbox.isChecked():
            # Update status in state
            global_state.set_channel_status(select_all_channels(channel_status, True))
            self.select_all_checkbox.setText("Deselect All")
        else:
            # Update status in state
            global_state.set_channel_status(select_all_channels(channel_status, False))
            self.select_all_checkbox.setText("Select All")

        self.display_page()  # Refresh display to show changes
        self.update_info_label()  # Update selected count label

    def clear_grid_display(self):
        """Clears all widgets from the channel grid layout."""
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def display_page(self):
        """Displays the channels for the current page."""
        selected_grid = self.grid_setup_handler.get_selected_grid()
        orientation = self.grid_setup_handler.get_orientation()
        success = self.grid_setup_handler.apply_selection(selected_grid, orientation, self) # Reapply selection to ensure state is consistent and grid layout changes are respected
        # Get display/paging parameters from GridSetupHandler
        current_page = self.grid_setup_handler.get_current_page()
        total_pages = self.grid_setup_handler.get_total_pages()
        items_per_page = self.grid_setup_handler.get_items_per_page()
        current_grid_indices = self.grid_setup_handler.get_current_grid_indices()
        rows = self.grid_setup_handler.get_rows()  # Needed for potential full grid calculations
        cols = self.grid_setup_handler.get_cols()  # Needed for potential full grid calculations
        selected_grid_key = self.grid_setup_handler.get_selected_grid()  # Needed for grid info lookup

        self.page_label.setText(f"Page {current_page + 1}/{total_pages}")
        self.prev_button.setEnabled(current_page > 0)
        self.next_button.setEnabled(current_page < total_pages - 1)

        self.clear_grid_display()
        self.checkboxes = []  # Clear list of checkboxes for the previous page

        start_idx = current_page * items_per_page
        end_idx = start_idx + items_per_page

        # Get state data
        grid_info = global_state.get_grid_info()  # Needed to find electrode count for grid
        scaled_data = global_state.get_scaled_data()
        time_data = global_state.get_time()
        channel_status = global_state.get_channel_status()
        channel_labels = global_state.get_channel_labels()

        if selected_grid_key and grid_info and selected_grid_key in grid_info:
            full_grid_indices_flat = [ch for ch in grid_info[selected_grid_key]["indices"] if ch is not None]

            if full_grid_indices_flat and scaled_data is not None:
                data_for_grid = scaled_data[:, full_grid_indices_flat]
                self.global_min = np.min(data_for_grid)
                self.global_max = np.max(data_for_grid)
            else:
                self.global_min = -1
                self.global_max = 1
                if scaled_data is None:
                    logger.warning("Scaled data is None when trying to calculate global min/max.")
                if not full_grid_indices_flat and selected_grid_key:
                    logger.warning(
                        f"No valid indices found for grid '{selected_grid_key}' to calculate global min/max.")

        else:
            # No grid selected or grid info missing
            self.global_min = -1
            self.global_max = 1
            logger.warning("Grid info or selected grid missing, using default ylim.")

        buffer = 0.1 * (abs(self.global_max) + abs(
            self.global_min)) if self.global_min is not None and self.global_max is not None else 0.2
        self.ylim = (self.global_min - buffer if self.global_min is not None else -1.1,
                     self.global_max + buffer if self.global_max is not None else 1.1)

        # Get the channels for the current page based on current_grid_indices
        page_channels = current_grid_indices[start_idx:end_idx]

        # Create and add a ChannelWidget for each channel on the page
        for page_pos, channel_idx in enumerate(page_channels):
            # channel_idx should not be None here because current_grid_indices is filtered

            # Ensure channel_idx is valid for scaled_data shape before creating widget
            if scaled_data is None or channel_idx < 0 or channel_idx >= scaled_data.shape[1]:
                logger.warning(
                    f"Skipping display for channel index {channel_idx}: Data not available or index out of bounds.")
                continue  # Skip this channel if data is missing or index invalid

            # Determine initial status and labels for this channel
            initial_status = channel_status[channel_idx] if channel_idx < len(channel_status) else False
            initial_labels = channel_labels.get(channel_idx, [])

            channel_widget = ChannelWidget(
                channel_idx=channel_idx,
                time_data=time_data,  # Pass data for plotting
                scaled_data_slice=scaled_data[:, channel_idx],  # Pass slice for plotting
                ylim=self.ylim,  # Pass calculated ylim
                initial_status=initial_status,  # Pass initial checkbox state
                initial_labels=initial_labels,  # Pass initial labels
                parent=self  # Set self as parent
            )

            # Connect signals from the ChannelWidget to ChannelSelector methods
            channel_widget.channel_status_changed.connect(self.handle_single_channel_update)
            channel_widget.view_detail_requested.connect(self.view_channel_in_detail)
            channel_widget.view_spectrum_requested.connect(self.view_channel_spectrum)

            # Calculate row and col for the QGridLayout
            ui_col = page_pos % self.channels_per_row
            # Each ChannelWidget now takes up 1 'logical' row in the grid layout
            ui_row = page_pos // self.channels_per_row

            # Add the ChannelWidget to the grid layout
            self.grid_layout.addWidget(channel_widget, ui_row, ui_col)

            # Store the widget instance
            self.channel_widgets.append(channel_widget)

        self.update_info_label()
        self.electrode_widget.update_all(channel_status, self.grid_setup_handler.get_current_grid_indices())
        self.electrode_widget.set_orientation_highlight(
            self.grid_setup_handler.get_orientation(),
            self.grid_setup_handler.get_current_page()  # Use handler's current page
        )

    def handle_single_channel_update(self, idx, state):
        """Handles state change for a single channel checkbox."""
        channel_status = global_state.get_channel_status()
        if idx < len(channel_status):  # Safety check
            update_channel_status_single(channel_status, idx, state)
        else:
            logger.warning(f"Attempted to update status for channel index {idx} which is out of bounds.")
            return  # Exit if index is invalid

        self.update_info_label()  # Update selected count label

        grid_channel_map = self.grid_setup_handler.get_grid_channel_map()
        if idx in grid_channel_map:
            grid_idx = grid_channel_map[idx]
            self.electrode_widget.set_orientation_highlight(
                self.grid_setup_handler.get_orientation(),
                self.grid_setup_handler.get_current_page()
            )
            self.electrode_widget.update_electrode(grid_idx, channel_status[idx])
        else:
            logger.debug(f"Channel index {idx} not found in current grid map.")

    def prev_page(self):
        """Navigates to the previous page."""
        if self.grid_setup_handler.get_current_page() > 0:
            self.grid_setup_handler.decrement_page()
            self.display_page()

    def next_page(self):
        """Navigates to the next page."""
        if self.grid_setup_handler.get_current_page() < self.grid_setup_handler.get_total_pages() - 1:
            self.grid_setup_handler.increment_page()
            self.display_page()  # Refresh display

    def view_channel_in_detail(self, channel_idx):
        """Opens a detailed time series view for a channel."""
        # Use data from state
        if global_state.get_data() is not None:
            self.detail_window = ChannelDetailWindow(self, global_state.get_data(), channel_idx)
            self.detail_window.show()
        else:
            logger.warning("Cannot view channel detail: No data loaded.")

    def update_info_label(self):
        """Updates the information label in the header."""
        selected_count = count_selected_channels(global_state.get_channel_status())
        file_size = global_state.get_file_size()
        file_size_kb = file_size / 1024 if file_size is not None else 0
        info_text = (
            f"File: {global_state.get_file_name() if global_state.get_file_name() else 'None'} ({file_size_kb:.2f} KB)\n"
            f"Total Channels: {global_state.get_channel_count()}\n"
            f"Sampling Frequency: {global_state.get_sampling_frequency() if global_state.get_sampling_frequency() is not None else 'N/A'}\n"
            f"Selected Channels: {selected_count}"
        )
        self.info_label.setText(info_text)

    def view_channel_spectrum(self, channel_idx):
        """Opens a frequency spectrum view for a channel."""
        if global_state.get_scaled_data() is not None and global_state.get_sampling_frequency() is not None:
            if not hasattr(self, 'channel_spectrum'):
                self.channel_spectrum = ChannelSpectrum(self)
            self.channel_spectrum.view_channel_spectrum(channel_idx)
        else:
            logger.warning("Cannot view spectrum: Data or sampling frequency not available.")

    def openAppSettings(self):
        """Opens the application settings dialog."""
        if self.app_settings_dialog.exec_():
            logger.debug("Settings Dialog closed and accepted")
        else:
            logger.debug("Settings Dialog closed")

    def run_auto_flagger(self):
        """Triggers the automatic suggestion of artifact flags."""
        scaled_data = global_state.get_scaled_data()
        sampling_frequency = global_state.get_sampling_frequency()

        if scaled_data is None or sampling_frequency is None:
            QMessageBox.warning(self, "Auto-Flagger",
                                "Cannot run auto-flagger: No data loaded or sampling frequency missing.")
            return

        # Get settings from the settings dialog
        try:
            settings = {
                Settings.AUTO_FLAGGER_NOISE_FREQ_THRESHOLD.name: config.get(Settings.AUTO_FLAGGER_NOISE_FREQ_THRESHOLD),
                Settings.AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD.name: config.get(Settings.AUTO_FLAGGER_ARTIFACT_VARIANCE_THRESHOLD),
                Settings.AUTO_FLAGGER_CHECK_50HZ.name: config.get(Settings.AUTO_FLAGGER_CHECK_50HZ),
                Settings.AUTO_FLAGGER_CHECK_60HZ.name: config.get(Settings.AUTO_FLAGGER_CHECK_60HZ),
                Settings.AUTO_FLAGGER_NOISE_FREQ_BAND_HZ.name: config.get(Settings.AUTO_FLAGGER_NOISE_FREQ_BAND_HZ),
            }
            # Basic validation that settings are available
            validate_auto_flagger_settings(settings)

        except Exception as e:
            logger.error(f"Failed to retrieve auto-flagger settings: {e}")
            QMessageBox.critical(self, "Auto-Flagger Error",
                                 f"Failed to retrieve settings. Please check application settings under File -> Settings -> Automatic Channel Flagging Settings.\nError: {e}")
            return

        # Run the auto-flagger
        suggested_labels = self.auto_flagger.suggest_flags(scaled_data, sampling_frequency, settings)

        # Apply suggested labels to the state (add to existing labels)
        current_labels = global_state.get_channel_labels()  # Get the current labels dict
        if current_labels is None:
            current_labels = {}  # Initialize if None

        updated_count = 0
        for channel_idx, suggestions in suggested_labels.items():
            if not isinstance(channel_idx, int) or channel_idx < 0 or channel_idx >= global_state.get_channel_count():
                logger.warning(f"Skipping suggested labels for invalid channel index: {channel_idx}")
                continue

            # Get current labels for this channel, add suggestions, ensure uniqueness and sorting
            existing_labels = current_labels.get(channel_idx, [])
            combined_labels = sorted({str(label): label for label in (existing_labels + suggestions)}.values(), key=lambda l: l["name"])

            # Only update state if labels actually changed
            if combined_labels != existing_labels:
                global_state.update_channel_labels(channel_idx, combined_labels)
                updated_count += 1

        if updated_count > 0:
            logger.info(f"Applied suggested flags to {updated_count} channels.")
            # Refresh the display page to show updated labels on the channel widgets
            self.display_page()
            QMessageBox.information(self, "Auto-Flagger", f"Suggested flags applied to {updated_count} channels.")
        else:
            logger.info("Auto-flagger suggested no new flags for any channel.")
            QMessageBox.information(self, "Auto-Flagger", "No new flags were suggested based on the current settings.")

    def reset_to_start_state(self):
        """Resets the application state and UI to the initial state."""
        # Reset the global state singleton
        global_state.reset()

        self.checkboxes = []
        self.upper_quartile = None
        self.global_min = None
        self.global_max = None
        self.ylim = None
        self.channel_widgets = []

        self.grid_setup_handler = GridSetupHandler()

        self.info_label.setText("No file loaded. Use File -> Open... to load a file.")
        self.grid_label.setHidden(True)
        self.select_all_checkbox.setEnabled(False)
        self.select_all_checkbox.setChecked(False)
        self.electrode_widget.setHidden(True)
        self.setWindowTitle("hdsemg-select")
        self.clear_grid_display()  # Clear the visual grid layout

        if self.amplidude_menu: self.amplidude_menu.setEnabled(False)
        if self.save_action: self.save_action.setEnabled(False)
        if self.change_grid_action: self.change_grid_action.setEnabled(False)
