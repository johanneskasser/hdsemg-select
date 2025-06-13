import json
import os
import enum
from threading import Lock
from hdsemg_select._log.log_config import logger
from hdsemg_select.config.config_enums import Settings
from hdsemg_select.ui.labels.base_labels import BaseChannelLabel

CONFIG_FILE = "config/config.json"

class ConfigManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Ensure a single instance (Singleton Pattern)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance.settings = {}
                cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                try:
                    self.settings = json.load(f)
                except json.JSONDecodeError:
                    self.settings = {}
                    logger.error("Failed to open config file.")
        else:
            logger.error("Config file does not exist yet.")
            self.settings = {}

    def save_config(self):
        """Save configuration to JSON file."""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

        with open(CONFIG_FILE, "w") as f:
            json.dump(self.settings, f, indent=4)

    def set(self, key, value):
        """Set a configuration value and save it."""
        if isinstance(key, enum.Enum):
            key = key.name  # Store enum as a string
        self.settings[key] = value
        self.save_config()

    def get(self, key, default=None):
        """Get a configuration value."""
        key = key.name
        return self.settings.get(key, default)

    def get_available_channel_labels(self):
        """Get available channel labels from the configuration."""
        base_labels = BaseChannelLabel.all_labels()
        custom_flags = self.get(Settings.CUSTOM_FLAGS, [])
        all_flags = base_labels + custom_flags
        return sorted(all_flags, key=lambda x: x["name"])

# Singleton instance
config = ConfigManager()
