"""
RMS Quality Data Loader

Loads and parses companion _rms.json files containing channel quality metrics.
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional

from hdsemg_select._log.log_config import logger
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel


class RMSData:
    """Container for RMS quality data for a single channel."""

    def __init__(self, channel_number: int, rms_label: str, rms_quality: str):
        self.channel_number = channel_number  # 0-indexed from JSON
        self.rms_label = rms_label  # "excellent", "good", "ok"
        self.rms_quality = rms_quality  # e.g., "10.23 µV"

    def get_base_label(self) -> Optional[dict]:
        """Convert rms_label string to BaseChannelLabel value dict."""
        label_map = {
            "excellent": BaseChannelLabel.RMS_EXCELLENT.value,
            "good": BaseChannelLabel.RMS_GOOD.value,
            "ok": BaseChannelLabel.RMS_OK.value,
        }
        return label_map.get(self.rms_label.lower())


class RMSLoader:
    """Loads RMS quality data from companion _rms.json files."""

    @staticmethod
    def get_rms_file_path(data_file_path: str) -> str:
        """
        Derives the companion RMS file path from the data file path.

        Example: /path/to/data.mat -> /path/to/data_rms.json
        """
        path = Path(data_file_path)
        stem = path.stem  # filename without extension
        rms_filename = f"{stem}_rms.json"
        rms_path = path.parent / rms_filename
        return str(rms_path)

    @staticmethod
    def load_rms_file(data_file_path: str) -> Optional[Dict[str, Dict[int, RMSData]]]:
        """
        Loads the companion RMS file if it exists.

        Returns:
            Dict mapping grid_key -> {channel_number: RMSData} or None if file not found
        """
        rms_path = RMSLoader.get_rms_file_path(data_file_path)

        if not os.path.isfile(rms_path):
            logger.debug(f"No RMS file found at {rms_path}")
            return None

        try:
            with open(rms_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return RMSLoader._parse_rms_data(data)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in RMS file {rms_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading RMS file {rms_path}: {e}")
            return None

    @staticmethod
    def _parse_rms_data(data: dict) -> Dict[str, Dict[int, RMSData]]:
        """
        Parses the RMS JSON structure into RMSData objects.

        Expected structure:
        {
            "grids": {
                "8mm_5x13": {
                    "0": {"rms_label": "excellent", "rms_quality": "0.00 µV"},
                    "1": {"rms_label": "good", "rms_quality": "6.30 µV"},
                    ...
                }
            }
        }
        """
        result = {}

        grids = data.get("grids", {})
        for grid_key, channels in grids.items():
            result[grid_key] = {}
            for channel_str, channel_data in channels.items():
                try:
                    channel_num = int(channel_str)
                    rms_data = RMSData(
                        channel_number=channel_num,
                        rms_label=channel_data.get("rms_label", ""),
                        rms_quality=channel_data.get("rms_quality", ""),
                    )
                    result[grid_key][channel_num] = rms_data
                except (ValueError, KeyError) as e:
                    logger.warning(
                        f"Invalid channel data for grid {grid_key}, channel {channel_str}: {e}"
                    )

        return result

    @staticmethod
    def match_grid_key(rms_grid_key: str, emg_grid_key: str) -> bool:
        """
        Determines if an RMS grid key matches an EMG file grid key.

        This handles potential naming variations between systems.
        Simple exact match for now, can be extended for fuzzy matching.
        """
        # Normalize: lowercase and strip whitespace
        rms_normalized = rms_grid_key.lower().strip()
        emg_normalized = emg_grid_key.lower().strip()

        return rms_normalized == emg_normalized

    @staticmethod
    def find_matching_grid(
        rms_data: Dict[str, Dict[int, RMSData]], emg_grid_key: str
    ) -> Optional[Dict[int, RMSData]]:
        """
        Finds RMS data that matches the selected EMG grid.

        Returns the RMS channel data dict for the matching grid, or None.
        """
        for rms_grid_key, channel_data in rms_data.items():
            if RMSLoader.match_grid_key(rms_grid_key, emg_grid_key):
                return channel_data

        logger.debug(f"No RMS grid match found for EMG grid '{emg_grid_key}'")
        return None
