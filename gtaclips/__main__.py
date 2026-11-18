"""Entry point.

    python -m gtaclips                 # start the dashboard (http://127.0.0.1:8000)
    python -m gtaclips set-password    # set / reset the owner password from the terminal
"""
from __future__ import annotations

import argparse
import getpass
import logging
import sys


def main() -> None:
    from . import config

    parser = argparse.ArgumentParser(prog="gtaclips", description="GTA Clip Engine")
    sub = parser.add_subparsers(dest="cmd")
    srv = sub.add_parser("serve", help="run the dashboard (default)")
    srv.add_argument("--host", default=config.HOST)
    srv.add_argument("--port", type=int, default=config.PORT)
    sub.add_parser("set-password", help="set or reset the owner password")
    args = parser.parse_args()

    if args.cmd == "set-password":
        from . import auth, db

        db.init()
        pw = getpass.getpass("New password: ")
        if pw != getpass.getpass("Repeat: "):
            sys.exit("Passwords do not match")
        try:
            auth.set_password(pw)
        except ValueError as exc:
            sys.exit(str(exc))
        print("Password saved. All existing sessions were signed out.")
        return

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host = getattr(args, "host", config.HOST)
    port = getattr(args, "port", config.PORT)
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"⚠  Listening on {host} — put this behind HTTPS (Tailscale / Cloudflare Tunnel / reverse proxy).")
    uvicorn.run("gtaclips.server:app", host=host, port=port, proxy_headers=True, forwarded_allow_ips="127.0.0.1", log_level="info")


if __name__ == "__main__":
    main()
