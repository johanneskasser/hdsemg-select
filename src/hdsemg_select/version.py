# src/version.py
from importlib.metadata import version, PackageNotFoundError
from ._log.log_config import logger

try:
    __version__ = version("hdsemg-select")
except PackageNotFoundError:
    __version__ = "0.0.0"

logger.info("hdsemg_select version: %s", __version__)

