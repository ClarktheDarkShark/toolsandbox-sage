#!/usr/bin/env python3
"""Render a publication-style SAGE self-evolution loop figure."""

from __future__ import annotations

import html
import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/sage_protocol/figures"
WIDTH = 2400
HEIGHT = 1500

NODE = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
)
NODE_MODULES = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
)

COLORS = {
    "ink": "#111827",
    "muted": "#5b6678",
    "paper": "#ffffff",
    "bg": "#f5f8fb",
    "panel": "#fbfdff",
    "line": "#9aa7b7",
    "light_line": "#d9e2ec",
    "blue": "#2563eb",
    "blue_soft": "#eaf3ff",
    "green": "#059669",
    "green_soft": "#e8f8f1",
    "amber": "#d97706",
    "amber_soft": "#fff4de",
    "violet": "#7c3aed",
    "violet_soft": "#f2edff",
    "red": "#dc2626",
    "red_soft": "#fff1f1",
    "slate": "#64748b",
    "slate_soft": "#f1f5f9",
}


CSS = """
text {
  font-family: Arial, Helvetica, sans-serif;
  letter-spacing: 0;
  fill: #111827;
}
.title { font-size: 42px; font-weight: 800; }
.subtitle { font-size: 21px; fill: #5b6678; }
.eyebrow { font-size: 15px; font-weight: 800; letter-spacing: 1.1px; }
.nodeTitle { font-size: 23px; font-weight: 800; }
.nodeBody { font-size: 17px; fill: #5b6678; }
.hubTitle { font-size: 30px; font-weight: 800; }
.hubBody { font-size: 18px; fill: #5b6678; }
.num { font-size: 22px; font-weight: 800; fill: #ffffff; }
.small { font-size: 15px; fill: #5b6678; }
.badge { font-size: 15px; font-weight: 800; }
.footerStrong { font-size: 16px; font-weight: 800; fill: #ffffff; }
.footerText { font-size: 16px; fill: #dbe7f1; }
"""


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def wrap(value: str, chars: int) -> list[str]:
    return textwrap.wrap(value, width=chars, break_long_words=False)


def text_block(
    x: int,
    y: int,
    value: str,
    *,
    cls: str = "nodeBody",
    chars: int = 34,
    line_h: int = 22,
    anchor: str | None = None,
) -> str:
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    lines = wrap(value, chars)
    spans = []
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else line_h
        spans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return f'<text class="{cls}" x="{x}" y="{y}"{anchor_attr}>{"".join(spans)}</text>'


def rect(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    fill: str,
    stroke: str | None = None,
    rx: int = 16,
    width: float = 1.5,
    dash: str | None = None,
    filter_id: str | None = None,
) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    filter_attr = f' filter="url(#{filter_id})"' if filter_id else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}"{stroke_attr}{dash_attr}{filter_attr}/>'
    )


def circle(cx: int, cy: int, r: int, *, fill: str, stroke: str | None = None) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{stroke_attr}/>'


def defs() -> str:
    markers = []
    for key in ["blue", "green", "amber", "violet", "red", "slate"]:
        markers.append(
            f'<marker id="{key}-arrow" markerWidth="18" markerHeight="18" refX="15" refY="9" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L18,9 L0,18 Z" fill="{COLORS[key]}"/></marker>'
        )
    return f"""
<defs>
  <filter id="softShadow" x="-12%" y="-18%" width="124%" height="140%">
    <feDropShadow dx="0" dy="12" stdDeviation="10" flood-color="#334155" flood-opacity="0.12"/>
  </filter>
  <filter id="hubGlow" x="-18%" y="-24%" width="136%" height="150%">
    <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#059669" flood-opacity="0.18"/>
  </filter>
  {"".join(markers)}
</defs>
"""


def path(
    d: str,
    *,
    color: str,
    width: float = 4,
    dash: str | None = None,
    arrow: bool = True,
    opacity: float = 1.0,
) -> str:
    marker = f' marker-end="url(#{color}-arrow)"' if arrow else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<path d="{d}" fill="none" stroke="{COLORS[color]}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"{dash_attr}{marker}/>'
    )


def node(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    n: str,
    eyebrow: str,
    title: str,
    body: str,
    color: str,
    chars: int = 35,
) -> str:
    accent = COLORS[color]
    soft = COLORS[f"{color}_soft"]
    return "".join(
        [
            rect(
                x,
                y,
                w,
                h,
                fill=COLORS["paper"],
                stroke=accent,
                rx=18,
                width=2,
                filter_id="softShadow",
            ),
            rect(x, y, w, 54, fill=soft, rx=18),
            rect(x, y, 8, h, fill=accent, rx=4),
            circle(x + 44, y + 42, 28, fill=accent),
            f'<text class="num" x="{x + 44}" y="{y + 50}" text-anchor="middle">{esc(n)}</text>',
            f'<text class="eyebrow" x="{x + 86}" y="{y + 30}" fill="{accent}">{esc(eyebrow)}</text>',
            text_block(x + 86, y + 58, title, cls="nodeTitle", chars=18, line_h=25),
            text_block(x + 32, y + 104, body, cls="nodeBody", chars=chars, line_h=22),
        ]
    )


def pill(x: int, y: int, text: str, *, color: str, w: int) -> str:
    return (
        rect(
            x,
            y,
            w,
            38,
            fill=COLORS[f"{color}_soft"],
            stroke=COLORS[color],
            rx=19,
            width=1.3,
        )
        + f'<text class="badge" x="{x + w / 2}" y="{y + 25}" text-anchor="middle" fill="{COLORS[color]}">{esc(text)}</text>'
    )


def hub() -> str:
    x, y, w, h = 805, 560, 610, 210
    return "".join(
        [
            rect(
                x,
                y,
                w,
                h,
                fill=COLORS["paper"],
                stroke=COLORS["green"],
                rx=26,
                width=2.3,
                filter_id="hubGlow",
            ),
            rect(
                x + 28,
                y + 28,
                w - 56,
                h - 56,
                fill=COLORS["green_soft"],
                stroke=COLORS["green"],
                rx=20,
                width=1.2,
            ),
            circle(x + 98, y + 104, 48, fill=COLORS["green"]),
            '<text class="num" x="903" y="672" text-anchor="middle">+</text>',
            '<text class="hubTitle" x="985" y="635">Validated tool inventory</text>',
            text_block(
                985,
                672,
                "Accepted tools persist with proof, code hash, triggers, and lifecycle state.",
                cls="hubBody",
                chars=50,
                line_h=24,
            ),
            pill(985, 718, "current proof required", color="green", w=230),
        ]
    )


def governance() -> str:
    body: list[str] = []
    body.append(
        rect(
            104,
            1040,
            2192,
            280,
            fill=COLORS["slate_soft"],
            stroke=COLORS["light_line"],
            rx=24,
            width=1.5,
        )
    )
    body.append(
        '<text class="eyebrow" x="140" y="1082" fill="#64748b">LIFECYCLE GOVERNANCE</text>'
    )

    body.append(
        rect(
            150,
            1132,
            360,
            108,
            fill=COLORS["paper"],
            stroke=COLORS["red"],
            rx=14,
            width=1.7,
        )
    )
    body.append(rect(150, 1132, 8, 108, fill=COLORS["red"], rx=4))
    body.append('<text class="nodeTitle" x="184" y="1170">Reflection</text>')
    body.append(
        text_block(
            184,
            1200,
            "Review reuse, regressions, utility, and side effects.",
            chars=36,
            line_h=21,
        )
    )

    body.append(pill(610, 1095, "retain", color="green", w=150))
    body.append(pill(610, 1165, "repair", color="amber", w=150))
    body.append(pill(610, 1235, "retire", color="red", w=150))

    body.append(
        rect(
            900,
            1088,
            400,
            94,
            fill=COLORS["paper"],
            stroke=COLORS["green"],
            rx=16,
            width=1.5,
        )
    )
    body.append('<text class="nodeTitle" x="934" y="1128">Maintain</text>')
    body.append(
        text_block(
            934,
            1156,
            "Eligible tools stay available for future routing.",
            chars=42,
            line_h=21,
        )
    )

    body.append(
        rect(
            900,
            1210,
            400,
            78,
            fill=COLORS["amber_soft"],
            stroke=COLORS["amber"],
            rx=16,
            width=1.5,
        )
    )
    body.append('<text class="nodeTitle" x="934" y="1244">Repair loop</text>')
    body.append(
        '<text class="small" x="1084" y="1244">Update candidate, triggers, or tests.</text>'
    )

    body.append(
        rect(
            1535,
            1150,
            410,
            96,
            fill=COLORS["red_soft"],
            stroke=COLORS["red"],
            rx=16,
            width=1.5,
        )
    )
    body.append('<text class="nodeTitle" x="1570" y="1190">Suppress</text>')
    body.append(
        text_block(
            1570,
            1218,
            "Unsafe or low-value tools are hidden, parked, or retired.",
            chars=43,
            line_h=21,
        )
    )

    body.append(path("M510 1186 L610 1114", color="slate", width=2.5, arrow=True))
    body.append(path("M510 1186 L610 1184", color="slate", width=2.5, arrow=True))
    body.append(path("M510 1186 L610 1254", color="slate", width=2.5, arrow=True))
    body.append(path("M760 1114 L900 1135", color="green", width=3))
    body.append(path("M760 1184 L900 1248", color="amber", width=3, dash="9 8"))
    body.append(path("M760 1254 H1535 V1198", color="red", width=3, dash="9 8"))
    return "".join(body)


def svg() -> str:
    body: list[str] = []
    body.append(rect(0, 0, WIDTH, HEIGHT, fill=COLORS["bg"], rx=0))
    body.append(
        rect(
            60,
            44,
            2280,
            1400,
            fill=COLORS["paper"],
            stroke=COLORS["light_line"],
            rx=26,
            width=1.5,
        )
    )
    body.append(
        '<text class="title" x="110" y="105">SAGE Generated-Tool Self-Evolution Loop</text>'
    )
    body.append(
        text_block(
            110,
            142,
            "A governed flywheel: visible task context reveals an inadequacy, SAGE births and validates a generated tool, routes accepted tools for natural actor use, and updates lifecycle state from reuse evidence.",
            cls="subtitle",
            chars=132,
            line_h=26,
        )
    )

    body.append(
        rect(
            100,
            205,
            2200,
            770,
            fill=COLORS["panel"],
            stroke=COLORS["line"],
            rx=24,
            width=1.3,
            dash="10 10",
        )
    )
    body.append(
        rect(
            130,
            188,
            330,
            38,
            fill=COLORS["paper"],
            stroke=COLORS["line"],
            rx=19,
            width=1,
        )
    )
    body.append(
        '<text class="eyebrow" x="158" y="214" fill="#64748b">CLAIM-COUNTED RUNTIME</text>'
    )

    # A quiet ring makes the closed loop obvious without fighting the nodes.
    body.append(
        '<ellipse cx="1110" cy="620" rx="760" ry="405" fill="none" stroke="#dbe7f1" stroke-width="20" opacity="0.85"/>'
    )

    body.append(
        node(
            170,
            520,
            360,
            155,
            n="1",
            eyebrow="OBSERVE",
            title="Visible gap",
            body="Task text, state, traces, and native tool affordances reveal an inadequacy.",
            color="blue",
            chars=33,
        )
    )
    body.append(
        node(
            575,
            290,
            360,
            155,
            n="2",
            eyebrow="BIRTH",
            title="Candidate tool",
            body="SAGE decides whether to generate tool code, schema, triggers, and abstention logic.",
            color="green",
            chars=33,
        )
    )
    body.append(
        node(
            1285,
            290,
            380,
            155,
            n="3",
            eyebrow="VALIDATE",
            title="Gate before use",
            body="Contract, static safety, callability, negative cases, and smoke traces must pass.",
            color="amber",
            chars=35,
        )
    )
    body.append(
        node(
            1680,
            520,
            380,
            155,
            n="4",
            eyebrow="REGISTER + ROUTE",
            title="Bounded bundle",
            body="Accepted tools enter inventory and only relevant tools are routed at runtime.",
            color="violet",
            chars=34,
        )
    )
    body.append(
        node(
            895,
            820,
            430,
            155,
            n="5",
            eyebrow="USE + LEARN",
            title="Natural actor use",
            body="The actor may call routed tools; SAGE logs calls, failures, outcomes, and side effects.",
            color="red",
            chars=39,
        )
    )

    body.append(hub())

    # Main flywheel arrows.
    body.append(path("M520 538 C550 420 585 365 610 350", color="green", width=5))
    body.append(path("M935 365 C1080 285 1190 285 1285 350", color="green", width=5))
    body.append(path("M1665 365 C1755 405 1815 465 1855 520", color="violet", width=5))
    body.append(path("M1880 675 C1745 850 1505 940 1325 900", color="red", width=5))
    body.append(path("M895 895 C640 965 310 835 260 675", color="blue", width=5))

    # Inventory interactions.
    body.append(path("M1475 430 C1450 510 1410 555 1350 585", color="green", width=3))
    body.append(path("M1415 665 C1515 650 1600 620 1680 598", color="violet", width=3))
    body.append(path("M990 820 C980 790 978 770 985 745", color="red", width=3))

    # Validation failure and repair path.
    body.append(pill(1124, 486, "repair or reject", color="amber", w=190))
    body.append(
        path(
            "M1395 445 C1320 495 1250 505 1218 505",
            color="amber",
            width=2.8,
            dash="8 8",
        )
    )
    body.append(
        path("M1124 505 C960 520 820 455 760 445", color="amber", width=2.8, dash="8 8")
    )

    # Invariant pills.
    body.append(pill(208, 705, "visible evidence only", color="blue", w=230))
    body.append(pill(635, 205, "birth is conditional", color="green", w=230))
    body.append(pill(1390, 205, "proof before routing", color="amber", w=230))
    body.append(pill(1756, 705, "bounded routing", color="violet", w=210))
    body.append(pill(1000, 1000, "side effects audited", color="red", w=230))

    # Governance feedback.
    body.append(path("M1110 975 V1040", color="red", width=3))
    body.append(governance())
    body.append(pill(910, 1324, "retain: future routing", color="green", w=220))
    body.append(pill(1160, 1324, "repair: return to gates", color="amber", w=235))

    body.append(rect(100, 1370, 2200, 44, fill=COLORS["ink"], rx=12))
    body.append('<text class="footerStrong" x="134" y="1399">Paper boundary:</text>')
    body.append(
        '<text class="footerText" x="270" y="1399">generated tools use visible context, pass validation before routing, preserve native side-effect tools, and remain subject to lifecycle repair or retirement.</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">SAGE generated-tool self-evolution loop</title>
<desc id="desc">A clockwise flywheel diagram shows five SAGE phases around a central validated tool inventory: observe visible gap, birth candidate tool, validate before use, register and route a bounded bundle, and use and learn from actor evidence. A lower governance band branches lifecycle reflection into retain, repair, or suppress decisions.</desc>
{defs()}
<style>{CSS}</style>
{"".join(body)}
</svg>
"""


def html_wrap(svg_text: str) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>
html, body {{
  margin: 0;
  width: {WIDTH}px;
  height: {HEIGHT}px;
  background: white;
  overflow: hidden;
}}
</style>
</head>
<body>{svg_text}</body>
</html>
"""


def render_png(html_path: Path, png_path: Path) -> None:
    node_bin = NODE if NODE.exists() else Path("node")
    env = os.environ.copy()
    if NODE_MODULES.exists():
        env["NODE_PATH"] = str(NODE_MODULES)
    js = r"""
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const htmlPath = process.argv[1];
const pngPath = process.argv[2];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 2400, height: 1500 }, deviceScaleFactor: 2 });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle' });
  await page.screenshot({ path: pngPath, omitBackground: false });
  await page.close();
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    subprocess.run(
        [str(node_bin), "-e", js, str(html_path), str(png_path)], check=True, env=env
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    name = "sage_self_evolution_loop_publication"
    svg_text = svg()
    svg_path = OUT / f"{name}.svg"
    html_path = OUT / f"{name}.html"
    png_path = OUT / f"{name}.png"
    svg_path.write_text(svg_text, encoding="utf-8")
    html_path.write_text(html_wrap(svg_text), encoding="utf-8")
    render_png(html_path, png_path)
    print(svg_path)
    print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
