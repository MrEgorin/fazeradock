"""
FazeraDock Entry Point
======================

Launches the FazeraDock application.
"""

import os
import sys

# Ensure project root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from PyQt5.QtWidgets import QApplication
from fazeradock.gui.main_window import MainWindow
from fazeradock.gui.styles import MAIN_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FazeraDock")
    app.setOrganizationName("FAZENA")
    app.setStyleSheet(MAIN_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
