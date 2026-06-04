"""Launch the WoolShed web app.

Usage
-----
    python -m woolshed              # Use port 5000.
    python -m woolshed --port 8080  # Use a custom port.
    python -m woolshed --browser    # Open the app in a browser.
"""

from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

from woolshed.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="WoolShed – Wool Value-Chain Optimiser")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port number (default 5000)")
    parser.add_argument("--browser", action="store_true", help="Open browser automatically")
    parser.add_argument("--debug", action="store_true", help="Flask debug mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    app = create_app()
    url = f"http://{args.host}:{args.port}"

    if args.browser:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    print(f"\n  🐑  WoolShed is running at {url}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
