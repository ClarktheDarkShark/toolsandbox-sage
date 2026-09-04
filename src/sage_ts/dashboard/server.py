"""Local static-file server for generated SAGE dashboards."""

from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DASHBOARD_SERVER_IDENTITY_PATH = "/__sage_dashboard_server_identity__"
DASHBOARD_SERVER_PROTOCOL = "sage_ts_dashboard_server_v1"


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Static dashboard handler with a root-bound identity endpoint."""

    def __init__(
        self,
        *args: object,
        dashboard_root: str,
        **kwargs: object,
    ) -> None:
        self.dashboard_root = str(Path(dashboard_root).resolve())
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - inherited HTTP handler API.
        if urlsplit(self.path).path == DASHBOARD_SERVER_IDENTITY_PATH:
            body = json.dumps(
                {
                    "protocol": DASHBOARD_SERVER_PROTOCOL,
                    "root": self.dashboard_root,
                },
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5520, type=int)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    handler = partial(
        DashboardRequestHandler,
        directory=str(root),
        dashboard_root=str(root),
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"Serving SAGE dashboards on http://{args.host}:{args.port}/",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
