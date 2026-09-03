#!/usr/bin/env python3
"""Render Chapter 3 SAGE methodology figures as publication-style SVG/PNG.

The figures are intentionally flat and schematic. Captions in the dissertation
carry the full prose, while the figures show mechanisms, boundaries, and
evidence paths with minimal visual noise.
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/sage_protocol/figures"
WIDTH = 1800
HEIGHT = 1050

NODE = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
)
NODE_MODULES = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
)

COLORS = {
    "ink": "#172033",
    "muted": "#596579",
    "line": "#9aa7b7",
    "light_line": "#d8e0ea",
    "blue": "#2563eb",
    "blue_soft": "#edf5ff",
    "green": "#059669",
    "green_soft": "#ecfdf5",
    "amber": "#d97706",
    "amber_soft": "#fff7e6",
    "red": "#dc2626",
    "red_soft": "#fff1f1",
    "violet": "#7c3aed",
    "violet_soft": "#f5f1ff",
    "slate": "#64748b",
    "slate_soft": "#f4f7fb",
}


CSS = """
text {
  font-family: Arial, Helvetica, sans-serif;
  fill: #172033;
}
.caption { font-size: 18px; fill: #596579; }
.panelLetter { font-size: 19px; font-weight: 700; fill: #ffffff; }
.panelTitle { font-size: 24px; font-weight: 700; }
.moduleTitle { font-size: 22px; font-weight: 700; }
.moduleText { font-size: 17px; fill: #596579; }
.small { font-size: 15px; fill: #596579; }
.tiny { font-size: 13px; fill: #596579; }
.axis { font-size: 14px; fill: #596579; }
.metric { font-size: 18px; font-weight: 700; }
.num { font-size: 15px; font-weight: 700; fill: #ffffff; }
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
    cls: str = "moduleText",
    chars: int = 28,
    line_h: int = 22,
) -> str:
    lines = wrap(value, chars)
    tspans = []
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else line_h
        tspans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return f'<text class="{cls}" x="{x}" y="{y}">{"".join(tspans)}</text>'


def rect(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    fill: str = "#ffffff",
    stroke: str | None = None,
    rx: int = 10,
    width: float = 1.5,
) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{stroke_attr}/>'


def line(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    color: str = "line",
    width: float = 2.2,
    dash: str = "",
    arrow: bool = True,
) -> str:
    marker = f' marker-end="url(#{color}-arrow)"' if arrow else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{COLORS[color]}" stroke-width="{width}" stroke-linecap="round"{dash_attr}{marker}/>'


def path(
    d: str,
    *,
    color: str = "line",
    width: float = 2.2,
    dash: str = "",
    arrow: bool = True,
) -> str:
    marker = f' marker-end="url(#{color}-arrow)"' if arrow else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{COLORS[color]}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker}/>'


def circle(
    cx: int,
    cy: int,
    r: int,
    *,
    fill: str,
    stroke: str | None = None,
    width: float = 1.5,
) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{stroke_attr}/>'


def panel_label(x: int, y: int, letter: str, title: str, color: str = "blue") -> str:
    return (
        circle(x, y - 8, 17, fill=COLORS[color])
        + f'<text class="panelLetter" x="{x}" y="{y - 2}" text-anchor="middle">{letter}</text>'
        + f'<text class="panelTitle" x="{x + 30}" y="{y}">{esc(title)}</text>'
    )


def module(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    body: str = "",
    *,
    color: str = "blue",
    fill: str | None = None,
    title_chars: int = 24,
    body_chars: int = 30,
) -> str:
    fill = fill or COLORS[f"{color}_soft"]
    parts = [
        rect(x, y, w, h, fill=fill, stroke=COLORS[color], rx=8, width=1.6),
        f'<rect x="{x}" y="{y}" width="7" height="{h}" rx="3.5" fill="{COLORS[color]}"/>',
    ]
    title_lines = wrap(title, title_chars)
    ty = y + 31
    for idx, line_text in enumerate(title_lines):
        parts.append(
            f'<text class="moduleTitle" x="{x + 20}" y="{ty + idx * 26}">{esc(line_text)}</text>'
        )
    if body:
        parts.append(text_block(x + 20, y + 74, body, chars=body_chars, line_h=21))
    return "".join(parts)


def step(x: int, y: int, n: int, label: str, *, color: str = "blue") -> str:
    return (
        circle(x, y, 22, fill=COLORS[color])
        + f'<text class="num" x="{x}" y="{y + 5}" text-anchor="middle">{n}</text>'
        + f'<text class="moduleTitle" x="{x + 36}" y="{y + 7}">{esc(label)}</text>'
    )


def check_row(x: int, y: int, title: str, detail: str, *, color: str = "green") -> str:
    return (
        circle(x, y, 12, fill=COLORS[color])
        + f'<path d="M{x - 6} {y} L{x - 1} {y + 5} L{x + 8} {y - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        + f'<text class="moduleTitle" x="{x + 24}" y="{y + 7}">{esc(title)}</text>'
        + text_block(x + 24, y + 34, detail, chars=44, line_h=20)
    )


def defs() -> str:
    markers = []
    for key in ["line", "blue", "green", "amber", "red", "violet", "slate"]:
        markers.append(
            f'<marker id="{key}-arrow" markerWidth="10" markerHeight="10" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L9,4.5 L0,9 Z" fill="{COLORS[key]}"/></marker>'
        )
    return "<defs>" + "".join(markers) + "</defs>"


def svg(name: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
{defs()}
<style>{CSS}</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>
<rect x="0" y="0" width="{WIDTH}" height="8" fill="{COLORS["blue"]}"/>
<text class="caption" x="92" y="48">{esc(name.replace("_", " "))}</text>
{body}
</svg>
"""


def html_wrap(svg_text: str) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden;background:white}}</style>
</head>
<body>{svg_text}</body>
</html>
"""


def fig_overview() -> tuple[str, str]:
    body = []
    body.append(panel_label(95, 100, "A", "What Changes", "blue"))
    body.append(
        module(
            95,
            135,
            300,
            130,
            "Frozen LLM actor",
            "Model weights remain unchanged.",
            color="slate",
            fill=COLORS["slate_soft"],
        )
    )
    body.append(
        module(
            95,
            305,
            300,
            130,
            "Tool portfolio",
            "Generated tools are added, retained, routed, and reused.",
            color="green",
        )
    )
    body.append(line(245, 265, 245, 305, color="green"))

    body.append(panel_label(500, 100, "B", "Online Build Loop", "violet"))
    loop = [
        module(
            500,
            150,
            210,
            105,
            "Task attempt",
            "Actor uses original and routed tools.",
            color="blue",
            body_chars=24,
        ),
        module(
            790,
            150,
            210,
            105,
            "Gap evidence",
            "Reusable deterministic operation.",
            color="amber",
            body_chars=24,
        ),
        module(
            1080,
            150,
            210,
            105,
            "Generate tool",
            "Typed code and schema.",
            color="violet",
            body_chars=24,
        ),
        module(
            1370,
            150,
            230,
            105,
            "Validate",
            "Compile, call, safety.",
            color="red",
            body_chars=24,
        ),
        module(
            1080,
            390,
            245,
            105,
            "Registry entry",
            "Hash, metadata, status.",
            color="green",
            body_chars=24,
        ),
        module(
            790,
            390,
            210,
            105,
            "Route later",
            "Small relevant bundle.",
            color="green",
            body_chars=24,
        ),
        module(
            500,
            390,
            210,
            105,
            "Reuse",
            "Natural actor calls.",
            color="blue",
            body_chars=24,
        ),
    ]
    body.extend(loop)
    body.extend(
        [
            line(710, 202, 790, 202),
            line(1000, 202, 1080, 202),
            line(1290, 202, 1370, 202),
            path("M1485 255 L1485 338 L1220 338 L1220 390", color="green"),
            line(1080, 442, 1000, 442, color="green"),
            line(790, 442, 710, 442, color="green"),
            path("M500 442 L455 442 L455 202 L500 202", color="blue", dash="7 7"),
            path("M1485 255 L1485 292 L1190 292 L1190 255", color="red", dash="6 7"),
            f'<text class="small" x="1210" y="286" fill="{COLORS["red"]}">repair when validation fails</text>',
        ]
    )

    body.append(panel_label(95, 650, "C", "Boundary and Evidence", "green"))
    body.append(
        rect(95, 690, 1510, 250, fill="#fbfdff", stroke=COLORS["light_line"], rx=8)
    )
    body.append(
        check_row(
            130,
            745,
            "Original environment tools execute state changes",
            "Generated tools prepare, select, normalize, plan, or abstain.",
            color="green",
        )
    )
    body.append(
        check_row(
            810,
            745,
            "Evidence is task-level and paired",
            "Visibility, natural calls, gains, regressions, failures, and side effects are logged.",
            color="blue",
        )
    )
    body.append(
        check_row(
            130,
            850,
            "No answer leakage or synthetic completion",
            "Tools must not encode hidden labels, expected answers, scenario IDs, or code-side task completions.",
            color="red",
        )
    )
    return "SAGE_Overview", svg("SAGE Overview", "".join(body))


def fig_architecture() -> tuple[str, str]:
    body = []
    y0 = 110
    lanes = [
        (y0, "Evaluation protocol", COLORS["blue_soft"], "blue"),
        (310, "Acting layer", COLORS["slate_soft"], "slate"),
        (520, "Tool-evolution layer", COLORS["green_soft"], "green"),
        (745, "Evidence layer", COLORS["violet_soft"], "violet"),
    ]
    for y, label_text, fill, color in lanes:
        body.append(
            rect(
                90,
                y,
                1520,
                160 if y != 520 else 185,
                fill=fill,
                stroke=COLORS["light_line"],
                rx=8,
            )
        )
        body.append(
            f'<text class="moduleTitle" x="115" y="{y + 36}" fill="{COLORS[color]}">{esc(label_text)}</text>'
        )

    body.append(
        module(
            310,
            150,
            250,
            92,
            "Sealed manifest",
            "task order + hash",
            color="blue",
            body_chars=24,
        )
    )
    body.append(
        module(
            725,
            150,
            250,
            92,
            "Baseline arm",
            "original tools only",
            color="slate",
            fill="#ffffff",
            body_chars=24,
        )
    )
    body.append(
        module(
            1140,
            150,
            280,
            92,
            "SAGE arm",
            "original + generated tools",
            color="green",
            body_chars=26,
        )
    )
    body.append(line(560, 196, 725, 196, color="blue"))
    body.append(
        path("M560 222 L660 222 L660 258 L1095 258 L1095 196 L1140 196", color="blue")
    )

    body.append(
        module(
            245, 355, 255, 92, "Actor", "chooses actions", color="slate", fill="#ffffff"
        )
    )
    body.append(
        module(
            620,
            355,
            320,
            92,
            "Original environment tools",
            "state-changing interface",
            color="slate",
            fill="#ffffff",
        )
    )
    body.append(
        module(
            1065,
            355,
            305,
            92,
            "Generated tools",
            "deterministic support",
            color="green",
            body_chars=26,
        )
    )
    body.append(line(500, 401, 620, 401, color="slate"))
    body.append(line(940, 401, 1065, 401, color="green"))
    body.append(
        f'<text class="small" x="620" y="475" fill="{COLORS["red"]}">side-effect boundary: only original tools mutate state</text>'
    )
    body.append(line(615, 460, 1370, 460, color="red", dash="7 7", arrow=False))

    modules = [
        (215, "Router", "bounded bundle", "green"),
        (430, "Registry", "accepted tools", "blue"),
        (645, "Gap detector", "reusable gaps", "amber"),
        (860, "Tool generator", "candidate code", "violet"),
        (1075, "Validator", "safety gates", "red"),
        (1290, "Repair / park", "decision", "slate"),
    ]
    for x, title, sub, color in modules:
        body.append(
            module(
                x,
                575,
                175,
                88,
                title,
                sub,
                color=color,
                fill="#ffffff",
                title_chars=14,
                body_chars=16,
            )
        )
    for x1, x2 in [(390, 430), (605, 645), (820, 860), (1035, 1075), (1250, 1290)]:
        body.append(line(x1, 619, x2, 619, color="slate"))
    body.append(
        path("M1380 575 L1380 540 L520 540 L520 575", color="green", dash="7 7")
    )
    body.append(path("M305 575 L305 500 L1215 500 L1215 447", color="green"))

    body.append(
        module(
            250,
            790,
            310,
            95,
            "Task Compare dashboard",
            "progress, score, outcome",
            color="violet",
            fill="#ffffff",
        )
    )
    body.append(
        module(
            700,
            790,
            270,
            95,
            "Run artifacts",
            "manifest, traces, registry",
            color="blue",
            fill="#ffffff",
        )
    )
    body.append(
        module(
            1110,
            790,
            330,
            95,
            "Contribution audit",
            "visibility, calls, gains",
            color="green",
            fill="#ffffff",
        )
    )
    body.append(path("M850 447 L850 750 L405 750 L405 790", color="slate"))
    body.append(path("M1215 447 L1215 750 L1275 750 L1275 790", color="slate"))
    return "SAGE_Architecture", svg("SAGE Architecture", "".join(body))


def fig_lifecycle() -> tuple[str, str]:
    body = []
    body.append(panel_label(100, 95, "A", "Generated-Tool State Machine", "violet"))
    center_x, center_y = 860, 500
    stages = [
        (290, 210, 1, "Observe evidence", "visible task data", "blue"),
        (625, 135, 2, "Specify gap", "operation + abstain cases", "amber"),
        (1010, 135, 3, "Generate", "typed code + schema", "violet"),
        (1345, 210, 4, "Validate", "compile, call, safety", "red"),
        (1345, 620, 5, "Register", "hash + metadata", "green"),
        (1010, 730, 6, "Route", "bounded visibility", "green"),
        (625, 730, 7, "Measure", "calls + outcomes", "blue"),
        (290, 620, 8, "Decide", "retain, refine, park", "slate"),
    ]
    for x, y, n, title, sub, color in stages:
        body.append(
            rect(
                x,
                y,
                245,
                118,
                fill=COLORS[f"{color}_soft"]
                if f"{color}_soft" in COLORS
                else "#ffffff",
                stroke=COLORS[color],
                rx=8,
            )
        )
        body.append(circle(x + 32, y + 36, 21, fill=COLORS[color]))
        body.append(
            f'<text class="num" x="{x + 32}" y="{y + 41}" text-anchor="middle">{n}</text>'
        )
        body.append(
            f'<text class="moduleTitle" x="{x + 62}" y="{y + 38}">{esc(title)}</text>'
        )
        body.append(
            f'<text class="moduleText" x="{x + 62}" y="{y + 67}">{esc(sub)}</text>'
        )
    body.append(line(535, 260, 625, 195, color="line"))
    body.append(line(870, 194, 1010, 194, color="line"))
    body.append(line(1255, 195, 1345, 260, color="line"))
    body.append(line(1468, 328, 1468, 620, color="line"))
    body.append(line(1345, 680, 1255, 760, color="line"))
    body.append(line(1010, 790, 870, 790, color="line"))
    body.append(line(625, 790, 535, 680, color="line"))
    body.append(path("M290 680 L245 680 L245 328 L290 268", color="green", dash="7 7"))
    body.append(
        rect(
            center_x - 210,
            center_y - 72,
            420,
            144,
            fill="#ffffff",
            stroke=COLORS["light_line"],
            rx=12,
        )
    )
    body.append(
        f'<text class="panelTitle" x="{center_x}" y="{center_y - 18}" text-anchor="middle">Accepted generated tool</text>'
    )
    body.append(
        f'<text class="moduleText" x="{center_x}" y="{center_y + 16}" text-anchor="middle">side-effect-free, callable, structured, auditable</text>'
    )
    body.append(path("M1170 252 L1170 390 L860 390 L860 452", color="red", dash="7 7"))
    body.append(
        f'<text class="small" x="900" y="382" fill="{COLORS["red"]}">repair loop before acceptance</text>'
    )
    return "SAGE_Tool_Lifecycle", svg("SAGE Tool Lifecycle", "".join(body))


def fig_evidence_boundary() -> tuple[str, str]:
    body = []
    body.append(panel_label(105, 100, "A", "Claim Ladder", "blue"))
    stages = [
        (130, "Diagnostics", "repair/setup only", "slate"),
        (430, "20 / 60", "mechanism check", "amber"),
        (730, "250 / 500", "paired validation", "blue"),
        (1030, "Frozen reuse", "generation off", "green"),
        (1330, "Protected claim", "locked protocol", "violet"),
    ]
    for i, (x, title, sub, color) in enumerate(stages, start=1):
        body.append(
            rect(
                x,
                185,
                235,
                118,
                fill=COLORS[f"{color}_soft"]
                if f"{color}_soft" in COLORS
                else "#ffffff",
                stroke=COLORS[color],
                rx=8,
            )
        )
        body.append(circle(x + 35, 226, 20, fill=COLORS[color]))
        body.append(
            f'<text class="num" x="{x + 35}" y="231" text-anchor="middle">{i}</text>'
        )
        body.append(
            f'<text class="moduleTitle" x="{x + 65}" y="225">{esc(title)}</text>'
        )
        body.append(f'<text class="moduleText" x="{x + 65}" y="255">{esc(sub)}</text>')
        if i < len(stages):
            body.append(line(x + 235, 244, x + 300, 244, color="line"))

    body.append(panel_label(105, 440, "B", "Evidence Controls", "green"))
    body.append(
        rect(120, 485, 1450, 310, fill="#fbfdff", stroke=COLORS["light_line"], rx=10)
    )
    rows = [
        (
            160,
            540,
            "No hidden answers",
            "Generated tools cannot encode expected answers, hidden labels, or scenario IDs.",
            "red",
        ),
        (
            160,
            625,
            "No synthetic task completion",
            "Evidence excludes code-side completions and route-around shortcuts.",
            "red",
        ),
        (
            160,
            710,
            "Fresh SAGE arm",
            "SAGE task cache and whole-response replay are off; provider-prefix "
            "reuse is distinct and recorded in strict runs.",
            "blue",
        ),
        (
            860,
            540,
            "Control provenance recorded",
            "Baseline cache source and cached/fresh counts remain visible.",
            "amber",
        ),
        (
            860,
            625,
            "Natural tool calls only",
            "Forced generated-tool calls are diagnostic and excluded from adoption claims.",
            "green",
        ),
        (
            860,
            710,
            "Safety reported",
            "Runtime exceptions, tool failures, and side-effect incidents are logged.",
            "green",
        ),
    ]
    for x, y, title, detail, color in rows:
        body.append(check_row(x, y, title, detail, color=color))
    body.append(panel_label(105, 885, "C", "Protected Interpretation", "violet"))
    body.append(
        '<text class="moduleText" x="155" y="930">A result supports Chapter 3 only when accuracy, natural generated-tool use, cache provenance, and safety evidence are all visible.</text>'
    )
    return "SAGE_Evidence_Boundary", svg("SAGE Evidence Boundary", "".join(body))


def fig_contribution_flow() -> tuple[str, str]:
    body = []
    body.append(panel_label(100, 100, "A", "Attribution Funnel", "green"))
    funnel = [
        (170, 200, 340, 92, "Candidate tools", "born from gaps", "violet"),
        (260, 335, 300, 92, "Validated", "accepted or repaired", "green"),
        (360, 470, 260, 92, "Visible", "routed to actor", "blue"),
        (470, 605, 225, 92, "Called", "natural use only", "green"),
        (585, 740, 260, 92, "Outcome gain", "paired task improvement", "green"),
    ]
    for x, y, w, h, title, sub, color in funnel:
        body.append(
            rect(x, y, w, h, fill=COLORS[f"{color}_soft"], stroke=COLORS[color], rx=8)
        )
        body.append(
            f'<text class="moduleTitle" x="{x + 24}" y="{y + 38}">{esc(title)}</text>'
        )
        body.append(
            f'<text class="moduleText" x="{x + 24}" y="{y + 67}">{esc(sub)}</text>'
        )
    body.extend(
        [
            path("M340 292 L410 335", color="green"),
            path("M410 427 L490 470", color="blue"),
            path("M490 562 L585 605", color="green"),
            path("M585 697 L700 740", color="green"),
        ]
    )
    body.append(path("M510 245 L650 245 L650 350", color="red"))
    body.append(
        module(
            650,
            305,
            280,
            100,
            "Rejected / parked",
            "not evidence-bearing",
            color="red",
            body_chars=24,
        )
    )
    body.append(path("M620 515 L900 515", color="amber"))
    body.append(
        f'<text class="small" x="705" y="498" fill="{COLORS["amber"]}">diagnostic branch</text>'
    )
    body.append(path("M695 650 L900 720", color="red", dash="7 7"))
    body.append(
        f'<text class="small" x="730" y="678" fill="{COLORS["red"]}">reported branch</text>'
    )

    body.append(panel_label(1030, 100, "B", "Evidence Status Matrix", "blue"))
    body.append(
        rect(990, 150, 610, 500, fill="#fbfdff", stroke=COLORS["light_line"], rx=10)
    )
    body.append('<text class="small" x="1030" y="195">Status</text>')
    body.append('<text class="small" x="1230" y="195">Claim role</text>')
    body.append('<text class="small" x="1395" y="195">Interpretation</text>')
    body.append(line(1020, 212, 1560, 212, color="light_line", arrow=False, width=1.2))
    rows = [
        ("Called + gain", "Primary", "tool-attributed success", "green"),
        ("Visible not called", "Diagnostic", "routing/adoption issue", "amber"),
        ("Called regression", "Reported", "not hidden by lift", "red"),
        ("Forced or synthetic", "Excluded", "not adoption evidence", "red"),
    ]
    y = 260
    for status, role, interp, color in rows:
        body.append(circle(1025, y - 7, 10, fill=COLORS[color]))
        body.append(f'<text class="moduleText" x="1050" y="{y}">{esc(status)}</text>')
        body.append(f'<text class="moduleText" x="1230" y="{y}">{esc(role)}</text>')
        body.append(f'<text class="moduleText" x="1395" y="{y}">{esc(interp)}</text>')
        body.append(
            line(1020, y + 20, 1560, y + 20, color="light_line", arrow=False, width=1.0)
        )
        y += 86
    body.append(panel_label(1030, 740, "C", "Audit Fields", "violet"))
    body.append(
        rect(
            990,
            785,
            610,
            100,
            fill=COLORS["violet_soft"],
            stroke=COLORS["violet"],
            rx=10,
        )
    )
    body.append(
        text_block(
            1025,
            825,
            "tools born, accepted, repaired, visible, called, gains, regressions, failures, side-effect incidents, run configuration",
            chars=58,
            line_h=22,
        )
    )
    return "SAGE_Contribution_Flow", svg("SAGE Contribution Flow", "".join(body))


def xscale(
    value: float, domain_min: float, domain_max: float, left: int, right: int
) -> float:
    return left + (value - domain_min) / (domain_max - domain_min) * (right - left)


def dot_plot(
    x: int,
    y: int,
    title: str,
    values: list[tuple[str, float, str]],
    *,
    domain: tuple[float, float],
    unit: str = "",
) -> str:
    left, right = x + 180, x + 610
    body = [f'<text class="panelTitle" x="{x}" y="{y}">{esc(title)}</text>']
    body.append(
        line(left, y + 52, right, y + 52, color="light_line", arrow=False, width=1.5)
    )
    for tick in [domain[0], (domain[0] + domain[1]) / 2, domain[1]]:
        tx = xscale(tick, domain[0], domain[1], left, right)
        body.append(
            line(
                int(tx),
                y + 47,
                int(tx),
                y + 57,
                color="light_line",
                arrow=False,
                width=1.2,
            )
        )
        label = f"{tick:.1f}" if domain[1] <= 1 else f"{tick:.0f}"
        body.append(
            f'<text class="axis" x="{tx}" y="{y + 78}" text-anchor="middle">{label}</text>'
        )
    rows = [("Baseline", "slate"), ("Online build", "blue"), ("Frozen reuse", "green")]
    for idx, (label_text, color) in enumerate(rows):
        yy = y + 120 + idx * 55
        body.append(
            f'<text class="moduleText" x="{x}" y="{yy + 6}">{esc(label_text)}</text>'
        )
        val = next(v for label, v, c in values if c == color)
        px = xscale(val, domain[0], domain[1], left, right)
        body.append(
            line(left, yy, right, yy, color="light_line", arrow=False, width=1.0)
        )
        body.append(circle(int(px), yy, 11, fill=COLORS[color]))
        display = f"{val:.3f}" if domain[1] <= 1 else f"{val:.0f}{unit}"
        if unit == "K":
            display = f"{val:.1f}K"
        body.append(
            f'<text class="metric" x="{right + 36}" y="{yy + 6}" fill="{COLORS[color]}">{display}</text>'
        )
    return "".join(body)


def lift_bar(
    x: int,
    y: int,
    label_text: str,
    baseline: float,
    sage: float,
    lift: str,
    *,
    color: str = "green",
) -> str:
    left = x + 265
    right = x + 760
    b_x = xscale(baseline, 0.0, 1.0, left, right)
    s_x = xscale(sage, 0.0, 1.0, left, right)
    parts = [
        f'<text class="moduleTitle" x="{x}" y="{y + 6}">{esc(label_text)}</text>',
        line(left, y, right, y, color="light_line", arrow=False, width=2.0),
        line(int(b_x), y, int(s_x), y, color=color, width=4.0, arrow=False),
        circle(int(b_x), y, 10, fill=COLORS["slate"]),
        circle(int(s_x), y, 12, fill=COLORS[color]),
        f'<text class="axis" x="{int(b_x)}" y="{y + 34}" text-anchor="middle">baseline {baseline:.3f}</text>',
        f'<text class="axis" x="{int(s_x)}" y="{y - 22}" text-anchor="middle">SAGE {sage:.3f}</text>',
        rect(
            right + 34,
            y - 29,
            128,
            48,
            fill=COLORS[f"{color}_soft"],
            stroke=COLORS[color],
            rx=24,
        ),
        f'<text class="metric" x="{right + 98}" y="{y + 1}" text-anchor="middle" fill="{COLORS[color]}">{esc(lift)}</text>',
    ]
    return "".join(parts)


def fig_lift_evidence() -> tuple[str, str]:
    body = []
    body.append(panel_label(95, 95, "A", "Broad 500-Task Outcome Evidence", "green"))
    body.append(
        rect(120, 145, 1510, 330, fill="#fbfdff", stroke=COLORS["light_line"], rx=10)
    )
    body.append(
        lift_bar(
            170,
            305,
            "Outcome score",
            0.494746,
            0.880845,
            "+78.04%",
            color="green",
        )
    )
    body.append('<text class="moduleTitle" x="1140" y="220">v71 broad500</text>')
    body.append(
        text_block(
            1140,
            255,
            "Empty generated-tool registry; 16 accepted live-born tools; generated tools naturally called in 297 scenarios.",
            chars=50,
            line_h=22,
        )
    )
    body.append(
        text_block(
            1140,
            325,
            "Reported 0 generated-tool failures and 0 runtime exceptions.",
            chars=50,
            line_h=22,
        )
    )

    body.append(panel_label(95, 555, "B", "Safety Reference and Reuse Check", "blue"))
    body.append(
        rect(120, 605, 700, 260, fill=COLORS["blue_soft"], stroke=COLORS["blue"], rx=10)
    )
    body.append(
        '<text class="moduleTitle" x="155" y="655">v70 broad500 safety reference</text>'
    )
    body.append('<text class="moduleText" x="155" y="695">Outcome lift: +76.41%</text>')
    body.append(
        '<text class="moduleText" x="155" y="730">Natural generated-tool calls: 295 scenarios</text>'
    )
    body.append(
        '<text class="moduleText" x="155" y="765">Runtime/tool incidents: 0 / 0</text>'
    )
    body.append(
        '<text class="moduleText" x="155" y="800">Clean safety reference for the outcome comparison.</text>'
    )

    body.append(
        rect(
            900, 605, 700, 260, fill=COLORS["green_soft"], stroke=COLORS["green"], rx=10
        )
    )
    body.append(
        '<text class="moduleTitle" x="935" y="655">40-task frozen-registry reuse</text>'
    )
    body.append(
        '<text class="moduleText" x="935" y="695">Online build outcome lift: +124.11%</text>'
    )
    body.append(
        '<text class="moduleText" x="935" y="730">Frozen reuse outcome lift: +119.76%</text>'
    )
    body.append(
        '<text class="moduleText" x="935" y="765">Generated-tool calls: 57 in 29 scenarios</text>'
    )
    body.append(
        '<text class="moduleText" x="935" y="800">Generation and repair disabled</text>'
    )
    body.append(
        rect(
            1040, 890, 480, 58, fill=COLORS["green_soft"], stroke=COLORS["green"], rx=29
        )
    )
    body.append(
        f'<text class="metric" x="1280" y="926" text-anchor="middle" fill="{COLORS["green"]}">outcome lift preserved after generation was disabled</text>'
    )
    return "SAGE_Lift_Evidence", svg("SAGE Lift Evidence", "".join(body))


def figures() -> list[tuple[str, str]]:
    return [
        fig_overview(),
        fig_architecture(),
        fig_lifecycle(),
        fig_evidence_boundary(),
        fig_contribution_flow(),
        fig_lift_evidence(),
    ]


def render_pngs(jobs: list[dict[str, str]]) -> None:
    node = NODE if NODE.exists() else Path("node")
    env = os.environ.copy()
    if NODE_MODULES.exists():
        env["NODE_PATH"] = str(NODE_MODULES)
    js = r"""
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const jobs = JSON.parse(process.argv[1]);

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const job of jobs) {
    const page = await browser.newPage({ viewport: { width: 1800, height: 1050 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(job.html).href, { waitUntil: 'networkidle' });
    await page.screenshot({ path: job.png, omitBackground: false });
    await page.close();
  }
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    subprocess.run([str(node), "-e", js, json.dumps(jobs)], check=True, env=env)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name, svg_text in figures():
        svg_path = OUT / f"{name}.svg"
        html_path = OUT / f"{name}.html"
        png_path = OUT / f"{name}.png"
        svg_path.write_text(svg_text, encoding="utf-8")
        html_path.write_text(html_wrap(svg_text), encoding="utf-8")
        jobs.append({"html": str(html_path), "png": str(png_path)})
    render_pngs(jobs)
    for job in jobs:
        print(job["png"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
