"""cli.py — Command-line entry point for the Lab Guardian agent."""

import argparse
import asyncio
import getpass
import logging
import signal
import sys

from . import __version__, config
from .local_db import LocalDatabase
from .agent_ui import run_agent_ui
from .dispatcher import run_with_ui

log = logging.getLogger("lab_guardian")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="lab_guardian",
        description="Lab Guardian student monitoring agent",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")

    join = sub.add_parser("start", help="Start exam monitoring agent (offline-first)")
    join.add_argument("--api-url", default=None, help="Override API base URL")
    join.add_argument("--ws-url", default=None, help="Override WS base URL")
    join.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    
    # Legacy command
    join_legacy = sub.add_parser("join", help="Join a live lab session (legacy, deprecated)")
    join_legacy.add_argument("-r", "--roll-no", required=False, help="Student roll number")
    join_legacy.add_argument("-s", "--session-id", required=False, help="Session UUID")
    join_legacy.add_argument("-p", "--password", required=False, help="Session password (if set)")
    join_legacy.add_argument("--api-url", default=None, help="Override API base URL")
    join_legacy.add_argument("--ws-url", default=None, help="Override WS base URL")
    join_legacy.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")

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


def _prompt_missing(args):
    """Interactively ask for required values if not supplied as flags."""
    if not args.roll_no:
        args.roll_no = input("Roll number: ").strip()
    if not args.session_id:
        args.session_id = input("Session ID: ").strip()
    if args.password is None:
        pw = getpass.getpass("Session password (leave blank if none): ")
        args.password = pw.strip() or None


def main(argv=None):
    args = _parse_args(argv)

    if args.command is None:
        print("Usage: lab_guardian start [options]\nRun 'lab_guardian start -h' for help.")
        sys.exit(1)

    if args.command == "start":
        _setup_logging(args.verbose)

        if args.api_url:
            config.API_BASE_URL = args.api_url
        if args.ws_url:
            config.WS_BASE_URL = args.ws_url

        # Initialize local database
        local_db = LocalDatabase()

        # Start UI application (blocks until closed)
        run_agent_ui(local_db)

    elif args.command == "join":
        # Legacy command - kept for backward compatibility
        print("Warning: 'join' command is deprecated. Use 'start' instead.")
        _setup_logging(args.verbose)

        if args.api_url:
            config.API_BASE_URL = args.api_url
        if args.ws_url:
            config.WS_BASE_URL = args.ws_url

        _prompt_missing(args)

        # ---- HTTP join ----
        print(f"Joining session {args.session_id} as {args.roll_no} …")
        try:
            from .api import join_session
            resp = join_session(args.roll_no, args.session_id, args.password)
        except Exception as exc:
            print(f"Failed to join session: {exc}", file=sys.stderr)
            sys.exit(1)

        token = resp["token"]
        student_id = resp["studentId"]
        session_id = resp["sessionId"]
        print(f"Joined! studentId={student_id}")

        # ---- WS + monitors ----
        loop = asyncio.new_event_loop()

        def _shutdown():
            print("\nShutting down …")
            loop.call_soon_threadsafe(loop.stop)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _shutdown)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                signal.signal(sig, lambda *_: _shutdown())

        try:
            from .dispatcher import run as run_dispatcher
            loop.run_until_complete(run_dispatcher(session_id, student_id, token))
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
            print("Agent stopped.")


if __name__ == "__main__":
    main()
