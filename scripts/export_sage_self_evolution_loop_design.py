#!/usr/bin/env python3
"""Export the HTML SAGE self-evolution loop design to PNG and PDF."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/sage_protocol/figures/sage_self_evolution_loop_design.html"
PNG = ROOT / "docs/sage_protocol/figures/sage_self_evolution_loop_design.png"
PDF = ROOT / "docs/sage_protocol/figures/sage_self_evolution_loop_design.pdf"
NODE = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
)
NODE_MODULES = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
)


def main() -> int:
    node = NODE if NODE.exists() else Path("node")
    env = os.environ.copy()
    if NODE_MODULES.exists():
        env["NODE_PATH"] = str(NODE_MODULES)

    payload = {
        "html": str(HTML),
        "png": str(PNG),
        "pdf": str(PDF),
    }
    js = r"""
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const job = JSON.parse(process.argv[1]);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 2400, height: 1500 },
    deviceScaleFactor: 2
  });
  const url = new URL(pathToFileURL(job.html).href);
  url.searchParams.set('export', '1');
  await page.goto(url.href, { waitUntil: 'networkidle' });
  await page.locator('.figure').screenshot({ path: job.png, omitBackground: false });
  await page.pdf({
    path: job.pdf,
    width: '24in',
    height: '15in',
    printBackground: true,
    margin: { top: '0in', right: '0in', bottom: '0in', left: '0in' }
  });
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    subprocess.run([str(node), "-e", js, json.dumps(payload)], check=True, env=env)
    print(HTML)
    print(PNG)
    print(PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
