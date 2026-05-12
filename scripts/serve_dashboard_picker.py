#!/usr/bin/env python3
"""Serve local SAGE dashboards with a mobile-friendly picker.

This is intended for LAN use from a phone or another device on the same WiFi.
It serves the repository as static files and adds a generated index page that
lists every `outputs/**/dashboard/task_compare.html` dashboard, newest first.
If Task Compare is missing for an older run, it falls back to Task Focus or the
standard dashboard.
By default it also discovers sibling worktrees named `toolsandbox-sage*`, so a
single port can browse dashboards produced on the experimental, repair, and
review branches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit


def _json_contains_running(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                isinstance(key, str)
                and key.lower() in {"status", "state", "phase_status"}
                and isinstance(child, str)
            ):
                if child.lower() in {"running", "in_progress", "active"}:
                    return True
            if _json_contains_running(child):
                return True
    if isinstance(value, list):
        return any(_json_contains_running(child) for child in value)
    return False


def _dashboard_activity(path: Path) -> tuple[float, bool]:
    run_root = path.parent.parent
    candidates = [
        path,
        path.parent / "task_focus_data.json",
        path.parent / "dashboard_data.json",
        run_root / "manifest.json",
        run_root / "status.json",
    ]
    latest_mtime = 0.0
    running = False
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        latest_mtime = max(latest_mtime, stat.st_mtime)
        if candidate.suffix == ".json":
            try:
                running = running or _json_contains_running(
                    json.loads(candidate.read_text())
                )
            except (OSError, json.JSONDecodeError):
                pass
    return latest_mtime, running


def _candidate_roots(root: Path) -> list[Path]:
    roots = [root.resolve()]
    for sibling in sorted(root.parent.glob("toolsandbox-sage*")):
        try:
            resolved = sibling.resolve()
        except OSError:
            continue
        if resolved == roots[0] or not (resolved / "outputs").exists():
            continue
        roots.append(resolved)
    return roots


def _preferred_dashboard(path: Path) -> Path:
    dashboard_dir = path.parent if path.parent.name == "dashboard" else path
    if not dashboard_dir.is_dir():
        dashboard_dir = path.parent
    for name in ("task_compare.html", "task_focus.html", "index.html"):
        candidate = dashboard_dir / name
        if candidate.exists():
            return candidate.resolve()
    return path.resolve()


def _process_cwd(pid: str) -> Path | None:
    try:
        output = subprocess.check_output(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        if line.startswith("n/"):
            return Path(line[1:]).resolve()
    return None


def _running_output_roots(root: Path) -> set[Path]:
    output_roots: set[Path] = set()
    try:
        output = subprocess.check_output(
            ["ps", "-axo", "pid=,command="], text=True, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return output_roots

    for line in output.splitlines():
        stripped = line.strip()
        if "run_sage_protocol.py" not in stripped:
            continue
        try:
            pid, command = stripped.split(None, 1)
            args = shlex.split(command)
        except ValueError:
            continue
        output_root = None
        for index, arg in enumerate(args):
            if arg == "--output-root" and index + 1 < len(args):
                output_root = args[index + 1]
                break
            if arg.startswith("--output-root="):
                output_root = arg.split("=", 1)[1]
                break
        if not output_root:
            continue
        cwd = _process_cwd(pid) or root
        path = Path(output_root)
        if not path.is_absolute():
            path = cwd / path
        output_roots.add(path.resolve())
    return output_roots


def _recent_dashboard_paths(root: Path, recent_minutes: int) -> set[Path]:
    outputs = root / "outputs"
    if not outputs.exists():
        return set()
    try:
        output = subprocess.check_output(
            [
                "find",
                str(outputs),
                "(",
                "-path",
                "*/dashboard/task_focus.html",
                "-o",
                "-path",
                "*/dashboard/task_focus_data.json",
                ")",
                "-mmin",
                f"-{recent_minutes}",
                "-print",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    dashboards = set()
    for line in output.splitlines():
        path = Path(line)
        if path.exists():
            dashboards.add(_preferred_dashboard(path))
    return dashboards


def _dashboard_paths(root: Path, recent_seconds: int) -> tuple[set[Path], set[Path]]:
    active: set[Path] = set()
    for candidate_root in _candidate_roots(root):
        running_roots = _running_output_roots(candidate_root)
        for output_root in running_roots:
            for path in output_root.glob("*/dashboard/task_focus.html"):
                active.add(_preferred_dashboard(path))
            direct = output_root / "dashboard" / "task_focus.html"
            if direct.exists():
                active.add(_preferred_dashboard(direct))
    dashboards: set[Path] = set()
    for candidate_root in _candidate_roots(root):
        outputs = candidate_root / "outputs"
        if outputs.exists():
            for dashboard_dir in outputs.rglob("dashboard"):
                if not dashboard_dir.is_dir():
                    continue
                for name in ("task_compare.html", "task_focus.html", "index.html"):
                    path = dashboard_dir / name
                    if path.exists():
                        dashboards.add(path.resolve())
                        break
        dashboards.update(
            _recent_dashboard_paths(candidate_root, max(1, recent_seconds // 60))
        )
    return active | dashboards, active


def _run_token(path: Path) -> str:
    return hashlib.sha1(str(path.parent.parent.resolve()).encode("utf-8")).hexdigest()[
        :12
    ]


def _external_run_map(root: Path, recent_seconds: int = 3600) -> dict[str, Path]:
    paths, _active = _dashboard_paths(root, recent_seconds)
    mapping: dict[str, Path] = {}
    for path in paths:
        try:
            path.relative_to(root)
            continue
        except ValueError:
            pass
        mapping[_run_token(path)] = path.parent.parent.resolve()
    return mapping


def _dashboard_entries(
    root: Path, recent_seconds: int = 3600
) -> list[dict[str, str | float]]:
    dashboards: list[dict[str, str | float]] = []
    paths, active_paths = _dashboard_paths(root, recent_seconds)
    for path in paths:
        latest_mtime, running = _dashboard_activity(path)
        running = running or path in active_paths
        try:
            rel = path.relative_to(root)
            parts = rel.parts
            label = " / ".join(parts[1:-2]) if len(parts) > 4 else str(rel)
            dashboard_path = "/" + quote(rel.as_posix())
        except ValueError:
            run_dir = path.parent.parent
            worktree = next(
                (
                    candidate_root.name
                    for candidate_root in _candidate_roots(root)
                    if candidate_root != root and path.is_relative_to(candidate_root)
                ),
                run_dir.parent.parent.parent.name,
            )
            label = (
                f"{worktree} / {run_dir.parent.parent.name} / "
                f"{run_dir.parent.name} / {run_dir.name}"
            )
            dashboard_path = f"/external/{_run_token(path)}/dashboard/{path.name}"
        if running:
            label = "RUNNING · " + label
        dashboards.append(
            {
                "label": label,
                "path": dashboard_path,
                "mtime": latest_mtime,
            }
        )
    dashboards.sort(key=lambda item: float(item["mtime"]), reverse=True)
    return dashboards


def _page() -> bytes:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SAGE Dashboard Picker</title>
  <style>
    :root { color-scheme: dark; --bg: #07101f; --panel: #101d33; --line: #294574; --text: #f3f7ff; --muted: #9fb3d9; --accent: #77c9ff; }
    * { box-sizing: border-box; }
    body { margin: 0; background: radial-gradient(circle at top left, #15345e, var(--bg) 34rem); color: var(--text); font: 16px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { position: sticky; top: 0; z-index: 2; padding: 14px; background: rgba(7,16,31,.94); border-bottom: 1px solid var(--line); backdrop-filter: blur(12px); }
    h1 { margin: 0 0 10px; font-size: 22px; letter-spacing: -.03em; }
    .row { display: grid; gap: 10px; grid-template-columns: 1fr; }
    select, button { width: 100%; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); color: var(--text); padding: 12px; font: inherit; }
    input { width: 100%; border: 1px solid var(--line); border-radius: 12px; background: #071427; color: var(--text); padding: 12px; font: inherit; margin-bottom: 10px; }
    button { background: #123b62; border-color: #3e88c7; font-weight: 700; }
    .meta { margin-top: 8px; color: var(--muted); font-size: 13px; }
    iframe { width: 100%; height: calc(100vh - 158px); border: 0; display: block; background: var(--bg); }
    a { color: var(--accent); }
    @media (min-width: 720px) {
      .row { grid-template-columns: 1fr 150px; }
      iframe { height: calc(100vh - 132px); }
    }
  </style>
</head>
<body>
  <header>
    <h1>SAGE dashboards</h1>
    <input id="filter" placeholder="Filter dashboard runs">
    <div class="row">
      <select id="dashboards"></select>
      <button id="open">Open selected</button>
    </div>
    <div class="meta"><span id="count">Loading...</span> · list refreshes automatically · <a id="direct" href="#">direct link</a></div>
  </header>
  <iframe id="viewer" title="Selected dashboard"></iframe>
  <script>
    const select = document.getElementById("dashboards");
    const viewer = document.getElementById("viewer");
    const direct = document.getElementById("direct");
    const count = document.getElementById("count");
    const openButton = document.getElementById("open");
    const filter = document.getElementById("filter");
    let allDashboards = [];

    function choose(path) {
      if (!path) return;
      viewer.src = path;
      direct.href = path;
      history.replaceState(null, "", "?dashboard=" + encodeURIComponent(path));
      localStorage.setItem("sageDashboardPath", path);
    }

    async function refreshList() {
      const selected = new URLSearchParams(location.search).get("dashboard") || localStorage.getItem("sageDashboardPath");
      const response = await fetch("/api/dashboards?ts=" + Date.now());
      const dashboards = await response.json();
      allDashboards = dashboards;
      renderOptions(selected);
    }

    function renderOptions(selected) {
      const query = filter.value.trim().toLowerCase();
      const dashboards = allDashboards.filter((dashboard) => !query || dashboard.label.toLowerCase().includes(query) || dashboard.path.toLowerCase().includes(query));
      select.innerHTML = "";
      for (const dashboard of dashboards) {
        const option = document.createElement("option");
        option.value = dashboard.path;
        option.textContent = dashboard.label;
        select.append(option);
      }
      const paths = dashboards.map((dashboard) => dashboard.path);
      const next = paths.includes(selected) ? selected : paths[0];
      if (next) {
        select.value = next;
        if (viewer.src !== new URL(next, location.href).href) choose(next);
      }
      count.textContent = dashboards.length + " dashboards shown / " + allDashboards.length + " total";
    }

    select.addEventListener("change", () => choose(select.value));
    filter.addEventListener("input", () => renderOptions(select.value));
    openButton.addEventListener("click", () => {
      if (select.value) location.href = select.value;
    });
    refreshList();
    setInterval(refreshList, 15000);
  </script>
</body>
</html>
""".encode("utf-8")


class DashboardPickerHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str | os.PathLike[str],
        **kwargs: Any,
    ) -> None:
        self.root = Path(directory).resolve()
        super().__init__(*args, directory=str(self.root), **kwargs)

    def do_GET(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/":
            self._send_bytes(_page(), "text/html; charset=utf-8")
            return
        if request_path == "/api/dashboards":
            payload = json.dumps(_dashboard_entries(self.root)).encode("utf-8")
            self._send_bytes(payload, "application/json; charset=utf-8")
            return
        if request_path.startswith("/external/"):
            if self._serve_external(request_path):
                return
        if request_path.startswith("/outputs/") and self._serve_sibling_output(
            request_path
        ):
            return
        super().do_GET()

    def _send_bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_external(self, request_path: str) -> bool:
        parts = request_path.split("/", 3)
        if len(parts) < 4:
            self.send_error(404, "File not found")
            return True
        token = parts[2]
        suffix = unquote(parts[3])
        run_dir = _external_run_map(self.root).get(token)
        if run_dir is None:
            self.send_error(404, "External dashboard not found")
            return True
        target = (run_dir / suffix).resolve()
        try:
            target.relative_to(run_dir)
        except ValueError:
            self.send_error(403, "Forbidden")
            return True
        if not target.is_file():
            self.send_error(404, "File not found")
            return True
        content_type = (
            "application/json; charset=utf-8"
            if target.suffix == ".json"
            else "text/html; charset=utf-8"
        )
        self._send_bytes(target.read_bytes(), content_type)
        return True

    def _serve_sibling_output(self, request_path: str) -> bool:
        suffix = unquote(request_path.lstrip("/"))
        for root in _candidate_roots(self.root):
            if root == self.root:
                continue
            target = (root / suffix).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
            if not target.is_file():
                continue
            self._send_bytes(target.read_bytes(), self.guess_type(str(target)))
            return True
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    def handler(*handler_args: Any, **handler_kwargs: Any) -> DashboardPickerHandler:
        return DashboardPickerHandler(*handler_args, directory=root, **handler_kwargs)

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"Serving SAGE dashboard picker from {root} on http://{args.host}:{args.port}/",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
