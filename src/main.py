import argparse
import logging
import sys

from _log.exception_hook import exception_hook
from _log.log_config import setup_logging

from PyQt5.QtWidgets import (
    QApplication
)

from ui.main_window import ChannelSelector

if __name__ == "__main__":
    setup_logging()
    sys.excepthook = exception_hook
    logger = logging.getLogger("hdsemg")

    # Parse command-line arguments for inputFile and outputFile.
    parser = argparse.ArgumentParser(description="hdsemg-select")
    parser.add_argument("--inputFile", type=str, help="File to be opened upon startup")
    parser.add_argument("--outputFile", type=str, help="Destination .mat file for saving the selection")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = ChannelSelector(input_file=args.inputFile, output_file=args.outputFile)
    window.showMaximized()

    # If an input file was specified, load it automatically.
    if args.inputFile:
        window.load_file_path(args.inputFile)

    sys.exit(app.exec_())
