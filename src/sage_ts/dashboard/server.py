"""Local static-file server for generated SAGE dashboards."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5520, type=int)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"Serving SAGE dashboards on http://{args.host}:{args.port}/",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
