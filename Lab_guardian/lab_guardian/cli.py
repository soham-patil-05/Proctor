"""cli.py — Command-line entry point for the Lab Guardian agent (offline-first)."""

import argparse
import asyncio
import logging
import sys
import threading
import time

from . import __version__, config
from .local_db import LocalDatabase
from .agent_ui import AgentMainWindow
from .dispatcher import run_with_ui

from PyQt5.QtWidgets import QApplication

log = logging.getLogger("lab_guardian")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="lab_guardian",
        description="Lab Guardian student monitoring agent (offline-first)",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")

    start = sub.add_parser("start", help="Start exam monitoring agent (offline-first)")
    start.add_argument("--api-url", default=None, help="Override API base URL for sync")
    start.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")

    return p.parse_args(argv)


def _setup_logging(verbosity: int):
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )




def main(argv=None):
    args = _parse_args(argv)

    if args.command is None:
        print("Usage: lab_guardian start [options]\nRun 'lab_guardian start -h' for help.")
        sys.exit(1)

    if args.command == "start":
        _setup_logging(args.verbose)

        if args.api_url:
            config.API_BASE_URL = args.api_url

        # Initialize local database
        local_db = LocalDatabase()

        # Start dispatcher in a separate thread, UI in main thread (Qt requirement)
        ui_window = [None]
        dispatcher_started = threading.Event()

        def run_dispatcher_thread():
            """Run dispatcher monitors in separate thread."""
            # Wait for UI to be ready
            timeout = 10
            while ui_window[0] is None and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
            
            if ui_window[0] is None:
                log.error("UI failed to start, cannot run dispatcher")
                return
            
            log.info("Starting dispatcher from background thread...")
            dispatcher_started.set()
            
            try:
                asyncio.run(run_with_ui(local_db, ui_window[0], config.API_BASE_URL))
            except Exception as e:
                log.error(f"Dispatcher error: {e}")

        # Start dispatcher thread
        dispatcher_thread = threading.Thread(target=run_dispatcher_thread, daemon=True)
        dispatcher_thread.start()

        # Run UI in main thread (Qt requirement)
        log.info("Starting UI in main thread...")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = AgentMainWindow(local_db)
        ui_window[0] = window
        window.show()
        
        # Run the Qt event loop
        try:
            sys.exit(app.exec_())
        except KeyboardInterrupt:
            log.info("Interrupted by user")
        finally:
            log.info("Agent stopped")


if __name__ == "__main__":
    main()
