"""main.py — PyInstaller entry point for Lab Guardian.

PyInstaller needs a top-level script; this delegates immediately to the
existing gui.main() so NO application code is duplicated or modified.
"""

import sys
import os

# When frozen by PyInstaller the package lives inside sys._MEIPASS.
# Nothing else needs to change — relative imports inside lab_guardian/
# work normally because PyInstaller adds the bundle root to sys.path.

from lab_guardian.gui import main

if __name__ == "__main__":
    main()
