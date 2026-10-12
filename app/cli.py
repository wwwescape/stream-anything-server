"""`stream-anything-server [--config config.toml]` — loads the config, prints how to connect,
announces the server on the network, and serves until Ctrl+C."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

import uvicorn

from app import __version__
from app.config import ConfigError, load_config
from app.discovery import Announcer, lan_addresses
from app.main import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stream-anything-server",
        description="Share video folders with the Stream Anything app on your home network.",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="config file (default: config.toml)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    # Show the connection details immediately even when output is redirected to a file.
    sys.stdout.reconfigure(line_buffering=True)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    addresses = lan_addresses() or ["<this-computer's-Wi-Fi-IP>"]
    key = quote(config.access_key)
    # Plain ASCII in console output: Windows consoles and redirected logs don't all speak UTF-8.
    print(f"\nStream Anything Server {__version__} - {config.name}\n")
    print("Shared libraries:")
    for lib in config.libraries:
        print(f"  {lib.name:<16} {lib.root}")
    print("\nOpen on your phone's browser (same Wi-Fi) to browse and copy video links:")
    for address in addresses:
        print(f"  http://{address}:{config.port}/?key={key}")
    print(f"\nAccess key: {config.access_key}   (kept in {args.config.parent / 'access_key.txt'})")
    print("Delete that file and restart to issue a new key (old links stop working).\n")
    print("Press Ctrl+C to stop.\n")

    announcer = Announcer(config.name, config.port)
    try:
        uvicorn.run(create_app(config), host="0.0.0.0", port=config.port, log_level="warning")
    finally:
        announcer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
