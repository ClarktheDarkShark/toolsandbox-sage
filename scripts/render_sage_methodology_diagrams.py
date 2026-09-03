"""Render architecture-grade SAGE methodology diagrams as synchronized assets.

Run this script directly whenever any methodology figure changes. The full render
keeps SVG, PNG, and HTML companions in sync so one figure artifact does not drift
from another.
"""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path("docs/sage_protocol/figures")


@dataclass(frozen=True)
class Palette:
    bg: str = "#f5f7fb"
    paper: str = "#ffffff"
    ink: str = "#142033"
    muted: str = "#526278"
    faint: str = "#e7ecf4"
    line: str = "#74829a"
    dark_line: str = "#263246"
    sage: str = "#0b7a70"
    sage_fill: str = "#dff4f1"
    control: str = "#1f5d99"
    control_fill: str = "#e3f0fb"
    sandbox: str = "#6545a4"
    sandbox_fill: str = "#eee8fb"
    evidence: str = "#8a5b05"
    evidence_fill: str = "#fff1d0"
    danger: str = "#a13737"
    danger_fill: str = "#fde8e8"
    neutral_fill: str = "#ffffff"
    store_fill: str = "#f8fafc"


PAL = Palette()


def _font(
    size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Diagram:
    def __init__(
        self,
        name: str,
        title: str,
        width: int = 2200,
        height: int = 1450,
        *,
        paper: bool = False,
    ) -> None:
        self.name = name
        self.title = title
        self.width = width
        self.height = height
        self.paper = paper
        self.svg: list[str] = []
        bg = PAL.paper if paper else PAL.bg
        self.image = Image.new("RGB", (width, height), bg)
        self.draw = ImageDraw.Draw(self.image)
        self.svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        )
        self.svg.append("<defs>")
        self.svg.append(
            '<marker id="arrow" markerWidth="16" markerHeight="16" refX="13" refY="8" orient="auto" markerUnits="strokeWidth">'
            '<path d="M 0 0 L 16 8 L 0 16 z" fill="#526278"/></marker>'
        )
        self.svg.append(
            '<marker id="dark_arrow" markerWidth="16" markerHeight="16" refX="13" refY="8" orient="auto" markerUnits="strokeWidth">'
            '<path d="M 0 0 L 16 8 L 0 16 z" fill="#263246"/></marker>'
        )
        self.svg.append("</defs>")
        self.rect(0, 0, width, height, bg, stroke="none", radius=0)
        self.text(70, 48, title, 36, PAL.ink, bold=True, max_width=width - 140)

    def finish(self) -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.svg.append("</svg>")
        (OUT_DIR / f"{self.name}.svg").write_text(
            "\n".join(self.svg) + "\n", encoding="utf-8"
        )
        self.image.save(OUT_DIR / f"{self.name}.png")

    def rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        fill: str,
        *,
        stroke: str = PAL.line,
        radius: int = 18,
        width: int = 2,
        dash: str | None = None,
    ) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
        )
        self.draw.rounded_rectangle(
            (x, y, x + w, y + h),
            radius=radius,
            fill=None if fill == "none" else fill,
            outline=None if stroke == "none" else stroke,
            width=width,
        )
        if dash and stroke != "none":
            self._dashed_rect(x, y, w, h, stroke)

    def _dashed_rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        for x0 in range(x, x + w, 26):
            self.draw.line((x0, y, min(x0 + 14, x + w), y), fill=color, width=2)
            self.draw.line((x0, y + h, min(x0 + 14, x + w), y + h), fill=color, width=2)
        for y0 in range(y, y + h, 26):
            self.draw.line((x, y0, x, min(y0 + 14, y + h)), fill=color, width=2)
            self.draw.line((x + w, y0, x + w, min(y0 + 14, y + h)), fill=color, width=2)

    def line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: str = PAL.line,
        width: int = 3,
        *,
        dash: str | None = None,
    ) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash_attr}/>'
        )
        if dash:
            self._dashed_line((x1, y1), (x2, y2), color, width)
        else:
            self.draw.line((x1, y1, x2, y2), fill=color, width=width)

    def _dashed_line(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        color: str,
        width: int,
        dash_len: int = 14,
        gap: int = 10,
    ) -> None:
        x1, y1 = start
        x2, y2 = end
        total = math.hypot(x2 - x1, y2 - y1)
        if total == 0:
            return
        dx = (x2 - x1) / total
        dy = (y2 - y1) / total
        pos = 0.0
        while pos < total:
            end_pos = min(pos + dash_len, total)
            self.draw.line(
                (
                    x1 + dx * pos,
                    y1 + dy * pos,
                    x1 + dx * end_pos,
                    y1 + dy * end_pos,
                ),
                fill=color,
                width=width,
            )
            pos += dash_len + gap

    def polyline(
        self,
        points: list[tuple[int, int]],
        *,
        color: str = PAL.line,
        width: int = 4,
        arrow: bool = True,
        label: str | None = None,
        label_at: tuple[int, int] | None = None,
        dash: str | None = None,
    ) -> None:
        pts = " ".join(f"{x},{y}" for x, y in points)
        marker = (
            ' marker-end="url(#dark_arrow)"' if arrow and color == PAL.dark_line else ""
        )
        marker = (
            ' marker-end="url(#arrow)"' if arrow and color != PAL.dark_line else marker
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash_attr}{marker}/>'
        )
        for first, second in zip(points, points[1:]):
            if dash:
                self._dashed_line(first, second, color, width)
            else:
                self.draw.line((*first, *second), fill=color, width=width)
        if arrow and len(points) >= 2:
            self._arrow_head(points[-2], points[-1], color)
        if label:
            lx, ly = label_at or points[len(points) // 2]
            self.badge(lx, ly, label, fill=PAL.paper if self.paper else PAL.bg)

    def _arrow_head(
        self, start: tuple[int, int], end: tuple[int, int], color: str
    ) -> None:
        x1, y1 = start
        x2, y2 = end
        angle = math.atan2(y2 - y1, x2 - x1)
        head = 18
        points = [
            (x2, y2),
            (
                x2 - head * math.cos(angle - math.pi / 6),
                y2 - head * math.sin(angle - math.pi / 6),
            ),
            (
                x2 - head * math.cos(angle + math.pi / 6),
                y2 - head * math.sin(angle + math.pi / 6),
            ),
        ]
        self.draw.polygon(points, fill=color)

    def text(
        self,
        x: int,
        y: int,
        text: str,
        size: int = 22,
        color: str = PAL.ink,
        *,
        bold: bool = False,
        max_width: int = 320,
        line_height: int | None = None,
    ) -> int:
        line_height = line_height or int(size * 1.25)
        chars = max(8, int(max_width / (size * 0.52)))
        lines: list[str] = []
        for paragraph in text.split("\n"):
            lines.extend(textwrap.wrap(paragraph, chars) or [""])
        font = _font(size, bold)
        for i, line in enumerate(lines):
            yy = y + i * line_height
            self.svg.append(
                f'<text x="{x}" y="{yy + size}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
                f'font-weight="{"700" if bold else "400"}" fill="{color}">{escape(line)}</text>'
            )
            self.draw.text((x, yy), line, fill=color, font=font)
        return y + len(lines) * line_height

    def badge(
        self,
        x: int,
        y: int,
        text: str,
        *,
        fill: str = PAL.bg,
        stroke: str = PAL.line,
        color: str = PAL.ink,
    ) -> None:
        w = max(90, 10 * len(text) + 32)
        self.rect(x - w // 2, y - 20, w, 40, fill, stroke=stroke, radius=20, width=1)
        self.text(x - w // 2 + 16, y - 11, text, 15, color, bold=True, max_width=w - 24)

    def component(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        bullets: list[str],
        *,
        fill: str = PAL.neutral_fill,
        stroke: str = PAL.line,
        accent: str = PAL.line,
        title_color: str = PAL.ink,
        body_color: str = PAL.muted,
        title_size: int = 23,
        body_size: int = 16,
    ) -> None:
        self.rect(x, y, w, h, fill, stroke=stroke, radius=18)
        self.rect(x, y, 12, h, accent, stroke="none", radius=18)
        self.text(
            x + 30, y + 20, title, title_size, title_color, bold=True, max_width=w - 60
        )
        yy = y + 64
        for bullet in bullets:
            self.circle(x + 38, yy + 10, 5, accent, stroke="none")
            yy = self.text(
                x + 54,
                yy,
                bullet,
                body_size,
                body_color,
                max_width=w - 78,
                line_height=int(body_size * 1.22),
            )
            yy += 9

    def data_store(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        body: str,
        *,
        stroke: str = PAL.line,
        fill: str = PAL.store_fill,
    ) -> None:
        ellipse_h = 32
        self.svg.append(
            f'<rect x="{x}" y="{y + ellipse_h // 2}" width="{w}" height="{h - ellipse_h}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        self.svg.append(
            f'<ellipse cx="{x + w / 2}" cy="{y + ellipse_h / 2}" rx="{w / 2}" ry="{ellipse_h / 2}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        self.svg.append(
            f'<ellipse cx="{x + w / 2}" cy="{y + h - ellipse_h / 2}" rx="{w / 2}" ry="{ellipse_h / 2}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        self.draw.rectangle(
            (x, y + ellipse_h // 2, x + w, y + h - ellipse_h // 2),
            fill=fill,
            outline=stroke,
            width=2,
        )
        self.draw.ellipse(
            (x, y, x + w, y + ellipse_h), fill=fill, outline=stroke, width=2
        )
        self.draw.ellipse(
            (x, y + h - ellipse_h, x + w, y + h), fill=fill, outline=stroke, width=2
        )
        self.text(x + 22, y + 28, title, 21, PAL.ink, bold=True, max_width=w - 44)
        self.text(x + 22, y + 70, body, 16, PAL.muted, max_width=w - 44, line_height=20)

    def circle(
        self,
        cx: int,
        cy: int,
        r: int,
        fill: str,
        *,
        stroke: str = PAL.line,
        width: int = 2,
    ) -> None:
        self.svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )
        self.draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill=fill,
            outline=None if stroke == "none" else stroke,
            width=width,
        )

    def boundary(
        self, x: int, y: int, w: int, h: int, label: str, *, color: str = PAL.line
    ) -> None:
        self.rect(x, y, w, h, "none", stroke=color, radius=24, width=2, dash="12 10")
        self.rect(
            x + 24,
            y - 18,
            max(220, len(label) * 13),
            40,
            PAL.bg if not self.paper else PAL.paper,
            stroke=color,
            radius=20,
            width=1,
        )
        self.text(
            x + 44,
            y - 8,
            label,
            16,
            color,
            bold=True,
            max_width=max(200, len(label) * 12),
        )

    def lane(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        label: str,
        *,
        fill: str,
        stroke: str,
    ) -> None:
        self.rect(x, y, w, h, fill, stroke=stroke, radius=22, width=2)
        self.rect(x, y, w, 48, stroke, stroke="none", radius=22)
        self.text(x + 22, y + 12, label, 17, PAL.paper, bold=True, max_width=w - 44)

    def legend(self, items: list[tuple[str, str]], x: int, y: int) -> None:
        self.rect(
            x,
            y,
            430,
            54 + len(items) * 34,
            PAL.paper if self.paper else PAL.bg,
            stroke=PAL.line,
            radius=16,
            width=1,
        )
        self.text(x + 20, y + 16, "Legend", 16, PAL.ink, bold=True, max_width=120)
        yy = y + 54
        for color, label in items:
            self.rect(x + 22, yy + 4, 28, 16, color, stroke="none", radius=4)
            self.text(x + 62, yy, label, 15, PAL.muted, max_width=330, line_height=19)
            yy += 34


def render_overview() -> None:
    d = Diagram(
        "sage_toolsandbox_system_overview",
        "1. SAGE + ToolSandbox System Architecture",
        2200,
        1450,
    )
    d.text(
        70,
        95,
        "End-to-end execution architecture showing trust boundaries, data stores, runtime arms, ToolSandbox integration, scoring, and research guardrails.",
        20,
        PAL.muted,
        max_width=1900,
    )
    d.boundary(40, 140, 2120, 1190, "Research protocol boundary", color=PAL.dark_line)

    d.lane(
        80,
        190,
        430,
        1010,
        "Protocol inputs and preflight",
        fill="#eef3f8",
        stroke=PAL.line,
    )
    d.lane(
        560, 190, 430, 1010, "Matched execution arms", fill="#eef7f6", stroke=PAL.sage
    )
    d.lane(
        1040,
        190,
        460,
        1010,
        "ToolSandbox benchmark system",
        fill="#f3eefb",
        stroke=PAL.sandbox,
    )
    d.lane(
        1550,
        190,
        560,
        1010,
        "Evidence, review, and claim boundary",
        fill="#fff7e5",
        stroke=PAL.evidence,
    )

    d.data_store(
        120,
        270,
        340,
        145,
        "Sealed manifest store",
        "Scenario order, split labels, family diversity, manifest hash.",
        stroke=PAL.dark_line,
    )
    d.component(
        120,
        460,
        340,
        160,
        "Final-run preflight",
        [
            "Clean git and registry hashes",
            "Generation/cache/routing policy checked",
            "Diagnostic force paths absent",
        ],
        accent=PAL.dark_line,
    )
    d.component(
        120,
        670,
        340,
        190,
        "Leakage controls",
        [
            "No hidden labels or expected answers",
            "No scenario-specific hard-coding",
            "No prior SAGE trace reuse",
        ],
        fill=PAL.danger_fill,
        stroke=PAL.danger,
        accent=PAL.danger,
    )
    d.data_store(
        120,
        915,
        340,
        150,
        "Control cache policy",
        "Task-level baseline cache allowed only with eligibility counts and hash.",
        stroke=PAL.control,
    )

    d.component(
        600,
        265,
        350,
        170,
        "Baseline control arm",
        [
            "Base ToolSandbox tools only",
            "Task-level cached controls when eligible",
            "Same model policy and manifest order",
        ],
        fill=PAL.control_fill,
        stroke=PAL.control,
        accent=PAL.control,
    )
    d.component(
        600,
        500,
        350,
        210,
        "SAGE candidate arm",
        [
            "Fresh candidate execution",
            "Generation on for discovery",
            "Generation off for frozen validation",
            "Candidate task cache off",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
    )
    d.data_store(
        600,
        770,
        350,
        155,
        "Generated registry",
        "Helper code, metadata, validation evidence, lifecycle state, digest.",
        stroke=PAL.sage,
    )
    d.component(
        600,
        980,
        350,
        150,
        "Router and bridge policy",
        [
            "Small bounded helper bundle",
            "Original side-effect tools preserved",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
    )

    d.component(
        1090,
        270,
        360,
        190,
        "ToolSandbox execution core",
        [
            "Stateful phone/contact/reminder/message state",
            "Original benchmark tools",
            "Conversation and tool-call traces",
        ],
        fill=PAL.sandbox_fill,
        stroke=PAL.sandbox,
        accent=PAL.sandbox,
    )
    d.component(
        1090,
        530,
        360,
        180,
        "User simulator and agent loop",
        [
            "On-policy turns",
            "Tool results returned to actor",
            "Final response recorded",
        ],
        fill=PAL.sandbox_fill,
        stroke=PAL.sandbox,
        accent=PAL.sandbox,
    )
    d.component(
        1090,
        790,
        360,
        190,
        "Scenario scorer",
        [
            "Canonical/reference milestones",
            "Performance outcome checks",
            "Exact success and state deltas",
        ],
        fill=PAL.sandbox_fill,
        stroke=PAL.sandbox,
        accent=PAL.sandbox,
    )

    d.component(
        1600,
        270,
        450,
        165,
        "Paired score table",
        [
            "Baseline vs SAGE per scenario",
            "Outcome performance, canonical descriptive",
            "Gains, regressions, preserved counts",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
    )
    d.component(
        1600,
        495,
        450,
        175,
        "Contribution export",
        [
            "Visible/called/VNC",
            "Called-subset deltas",
            "Route mismatch and no-helper-fit metrics",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
    )
    d.component(
        1600,
        735,
        450,
        170,
        "Safety and cache audit",
        [
            "Runtime exceptions and helper incidents",
            "Control cache counts and hashes",
            "External-service fixture policy",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
    )
    d.data_store(
        1600,
        965,
        450,
        160,
        "Run artifact store",
        "Dashboards, feedback packets, registries, summaries, statistics, reports.",
        stroke=PAL.evidence,
    )

    d.polyline([(460, 342), (600, 342)], label="same manifest", label_at=(530, 310))
    d.polyline(
        [(460, 342), (530, 342), (530, 605), (600, 605)],
        label="same manifest",
        label_at=(530, 465),
    )
    d.polyline([(460, 990), (600, 350)], color=PAL.control, label="cached controls")
    d.polyline([(775, 435), (775, 500)], color=PAL.sage, label="matched arm")
    d.polyline([(950, 350), (1090, 350)], color=PAL.control, label="base tools")
    d.polyline(
        [(950, 605), (1040, 605), (1040, 625), (1090, 625)],
        color=PAL.sage,
        label="helpers + original tools",
    )
    d.polyline([(950, 1050), (1010, 1050), (1010, 625), (1090, 625)], color=PAL.sage)
    d.polyline([(1270, 460), (1270, 530)], color=PAL.sandbox)
    d.polyline([(1270, 710), (1270, 790)], color=PAL.sandbox)
    d.polyline([(1450, 885), (1600, 350)], color=PAL.evidence, label="paired metrics")
    d.polyline([(1450, 625), (1600, 582)], color=PAL.evidence, label="trace evidence")
    d.polyline([(1450, 885), (1600, 820)], color=PAL.evidence, label="safety")
    d.polyline([(1825, 965), (1825, 670)], color=PAL.evidence)
    d.polyline([(1825, 495), (1825, 435)], color=PAL.evidence)
    d.polyline(
        [(1600, 1045), (1440, 1045), (1440, 1190), (775, 1190), (775, 1130)],
        color=PAL.sage,
        dash="10 8",
        label="discovery feedback",
        label_at=(1120, 1190),
    )

    d.rect(80, 1240, 2030, 82, PAL.danger_fill, stroke=PAL.danger, radius=18)
    d.text(110, 1260, "Claim-run invariants", 20, PAL.danger, bold=True)
    d.text(
        350,
        1260,
        "No force-call promotion evidence; no candidate task cache; no label or expected-answer leakage; zero helper side-effect incidents for protected candidates.",
        19,
        PAL.ink,
        max_width=1700,
    )
    d.finish()


def render_sage_zoom() -> None:
    d = Diagram(
        "sage_internal_components_zoom",
        "2. SAGE Runtime Component Architecture",
        2200,
        1500,
    )
    d.text(
        70,
        95,
        "Zoom-in on SAGE as a self-evolving subsystem: event ingestion, gap reasoning, generation, validation, registry lifecycle, runtime routing, and feedback control.",
        20,
        PAL.muted,
        max_width=1900,
    )
    d.boundary(55, 155, 2088, 1180, "SAGE runtime boundary", color=PAL.sage)

    d.component(
        100,
        235,
        330,
        215,
        "Event ingress",
        [
            "Task text and visible state",
            "Tool-call trace and final response",
            "Scores, failures, VNC, route mismatch",
        ],
        fill=PAL.control_fill,
        stroke=PAL.control,
        accent=PAL.control,
        body_size=15,
    )
    d.component(
        505,
        235,
        330,
        215,
        "Gap observer",
        [
            "Classifies missing deterministic step",
            "Separates insufficient information",
            "Builds oracle-free gap packet",
        ],
        fill=PAL.neutral_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
        body_size=15,
    )
    d.component(
        910,
        235,
        330,
        215,
        "Opportunity ranker",
        [
            "Buckets repeated unsupported work",
            "Scores lift potential and risk",
            "Selects next generation target",
        ],
        fill=PAL.neutral_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
        body_size=15,
    )
    d.component(
        1315,
        235,
        330,
        215,
        "Tool generator",
        [
            "Creates scalar/list helper specs",
            "Emits code, metadata, triggers",
            "Includes abstain and negative cases",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
        body_size=15,
    )
    d.component(
        1720,
        235,
        330,
        215,
        "Candidate builder",
        [
            "Normalizes type annotations",
            "Packages tool metadata",
            "Assigns lifecycle identifiers",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
        body_size=15,
    )

    d.component(
        1720,
        530,
        330,
        215,
        "Validation gates",
        [
            "AST and import safety",
            "Schema/callability checks",
            "Synthetic minefields",
            "Live smoke and side-effect preservation",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
    )
    d.data_store(
        1315,
        560,
        330,
        170,
        "Accepted registry",
        "Helper code, metadata, validation evidence, lifecycle state, hash.",
        stroke=PAL.sage,
    )
    d.component(
        910,
        540,
        330,
        205,
        "Router / composer",
        [
            "System selects bounded helper bundle",
            "Uses triggers and lifecycle evidence",
            "Can compose helper chains",
        ],
        fill=PAL.neutral_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
    )
    d.component(
        505,
        540,
        330,
        205,
        "Actor bridge policy",
        [
            "Natural adoption guidance",
            "Final-answer retention",
            "Original side-effect calls preserved",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
    )
    d.component(
        100,
        540,
        330,
        205,
        "ToolSandbox adapter",
        [
            "Injects routed helpers",
            "Preserves original tools",
            "Records traces and tool attempts",
        ],
        fill=PAL.sandbox_fill,
        stroke=PAL.sandbox,
        accent=PAL.sandbox,
    )

    d.component(
        100,
        870,
        330,
        190,
        "Contribution export",
        [
            "Visible/called/VNC",
            "Called-subset outcome",
            "Helper incidents and route mismatch",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
    )
    d.data_store(
        505,
        885,
        330,
        165,
        "Feedback packets",
        "Per-task machine-readable gap, trace, metric, safety, and routing evidence.",
        stroke=PAL.evidence,
    )
    d.component(
        910,
        870,
        330,
        190,
        "Lifecycle reflection",
        [
            "Retain, refine, recombine, scale",
            "Park unsafe or negative tools",
            "Schedule next gap bucket",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
    )
    d.data_store(
        1315,
        885,
        330,
        165,
        "Lifecycle ledger",
        "Use counts, failure classes, repair history, adoption evidence, hashes.",
        stroke=PAL.sage,
    )
    d.component(
        1720,
        870,
        330,
        190,
        "Repair planner",
        [
            "Schema/input bridge repair",
            "Output-shape and final-action repair",
            "Routing and affordance repair",
        ],
        fill=PAL.danger_fill,
        stroke=PAL.danger,
        accent=PAL.danger,
    )

    d.component(
        100,
        1150,
        390,
        160,
        "Execution flags",
        [
            "Discovery: generation on",
            "Frozen validation: generation off",
            "Candidate task cache off",
        ],
        fill=PAL.neutral_fill,
        stroke=PAL.line,
        accent=PAL.dark_line,
        body_size=15,
    )
    d.component(
        560,
        1150,
        390,
        160,
        "Research contracts",
        [
            "No labels for unseen design",
            "No force-call promotion",
            "No task-specific facts in tools",
        ],
        fill=PAL.danger_fill,
        stroke=PAL.danger,
        accent=PAL.danger,
        body_size=15,
    )
    d.component(
        1020,
        1150,
        390,
        160,
        "Promotion contracts",
        [
            "Natural calls and positive called subset",
            "Runtime/helper incidents zero",
            "Scale only after gates pass",
        ],
        fill=PAL.evidence_fill,
        stroke=PAL.evidence,
        accent=PAL.evidence,
        body_size=15,
    )
    d.component(
        1480,
        1150,
        570,
        160,
        "System-owned routing",
        [
            "SAGE selects bundles from policy, registry metadata, and lifecycle evidence.",
            "The user does not pick helpers to expose.",
        ],
        fill=PAL.sage_fill,
        stroke=PAL.sage,
        accent=PAL.sage,
        body_size=15,
    )

    for start_x, end_x in [(430, 505), (835, 910), (1240, 1315), (1645, 1720)]:
        d.polyline([(start_x, 330), (end_x, 330)], color=PAL.sage)
    d.polyline([(1885, 425), (1885, 530)], color=PAL.evidence)
    d.polyline([(1720, 640), (1645, 640)], color=PAL.evidence, label="accept")
    d.polyline([(1315, 640), (1240, 640)], color=PAL.sage)
    d.polyline([(910, 640), (835, 640)], color=PAL.sage)
    d.polyline([(505, 640), (430, 640)], color=PAL.sage)
    d.polyline([(265, 745), (265, 870)], color=PAL.evidence)
    d.polyline([(430, 965), (505, 965)], color=PAL.evidence)
    d.polyline([(835, 965), (910, 965)], color=PAL.sage)
    d.polyline([(1240, 965), (1315, 965)], color=PAL.sage)
    d.polyline([(1645, 965), (1720, 965)], color=PAL.danger)
    d.polyline(
        [(1885, 870), (2075, 870), (2075, 425), (1885, 425)],
        color=PAL.danger,
        dash="10 8",
        label="repair",
        label_at=(2075, 640),
    )
    d.polyline([(1080, 870), (1080, 745)], color=PAL.sage, label="route evidence")
    d.polyline(
        [(670, 885), (670, 790), (1460, 790), (1460, 730)],
        color=PAL.evidence,
        dash="10 8",
        label="feedback",
    )
    d.finish()


def render_tool_loop() -> None:
    d = Diagram(
        "sage_tool_generation_validation_repair_loop",
        "3. Tool Generation, Validation, And Repair State Machine",
        2200,
        1500,
    )
    d.text(
        70,
        95,
        "Detailed tool birth contract: only system-generated, validated, naturally adopted, safety-clean helpers can move toward scale. Diagnostics repair the system; they do not count as promotion evidence.",
        20,
        PAL.muted,
        max_width=1940,
    )

    steps = [
        (
            "1",
            "Gap packet",
            "Oracle-free shortfall from task text, visible state, trace, VNC, or failed-call evidence.",
        ),
        (
            "2",
            "Design candidates",
            "Multiple scalar/list helper specs with final-ready output and explicit abstain behavior.",
        ),
        (
            "3",
            "Contract gate",
            "Typed inputs, no opaque records unless justified, metadata triggers, negative triggers.",
        ),
        (
            "4",
            "Static gate",
            "AST/import safety, no writes, no network, no hidden benchmark strings.",
        ),
        (
            "5",
            "Minefield gate",
            "Ambiguity, duplicates, missing fields, wrong units, empty results, irrelevant tasks.",
        ),
        (
            "6",
            "Live smoke",
            "Callability and side-effect preservation mechanics on small safe diagnostics.",
        ),
        (
            "7",
            "Natural adoption",
            "System-routed bundle, visible/called/VNC measured without forced promotion.",
        ),
        (
            "8",
            "Scale gate",
            "Outcome, called subset, safety, cache, leakage, and route metrics decide scale.",
        ),
    ]
    x0 = 95
    y0 = 235
    w = 235
    h = 185
    gap = 32
    positions: list[tuple[int, int]] = []
    for i, (num, title, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        positions.append((x, y0))
        d.rect(x, y0, w, h, PAL.neutral_fill, stroke=PAL.sage, radius=22, width=2)
        d.circle(x + 34, y0 + 38, 25, PAL.sage, stroke=PAL.sage, width=2)
        d.text(x + 25, y0 + 22, num, 22, PAL.paper, bold=True, max_width=40)
        d.text(x + 72, y0 + 24, title, 20, PAL.ink, bold=True, max_width=w - 90)
        d.text(x + 24, y0 + 78, body, 15, PAL.muted, max_width=w - 48, line_height=19)
        if i:
            prev_x = positions[i - 1][0] + w
            d.polyline([(prev_x, y0 + h // 2), (x, y0 + h // 2)], color=PAL.sage)

    d.rect(90, 520, 2020, 410, PAL.faint, stroke=PAL.line, radius=26)
    d.text(
        120,
        545,
        "Failure classification and self-healing routes",
        24,
        PAL.ink,
        bold=True,
    )
    repairs = [
        (
            "Schema repair",
            "Bad types, optional annotations, missing defaults, opaque payloads.",
        ),
        (
            "Input bridge repair",
            "Actor lacks scalar values; add extraction or preparatory helper.",
        ),
        (
            "Output-shape repair",
            "Intermediate value not final-answer-ready or final-action-ready.",
        ),
        (
            "Routing repair",
            "Hidden helper, weak triggers, overbroad negative trigger, context budget issue.",
        ),
        (
            "Adoption repair",
            "Visible but not called; metadata, examples, ordering, or bridge wording issue.",
        ),
        (
            "Safety redesign",
            "Side-effect risk, over-answering, ambiguity handling, insufficient-info failure.",
        ),
    ]
    for i, (title, body) in enumerate(repairs):
        x = 125 + (i % 3) * 650
        y = 610 + (i // 3) * 150
        d.component(
            x,
            y,
            560,
            110,
            title,
            [body],
            fill=PAL.paper,
            stroke=PAL.danger if i == 5 else PAL.line,
            accent=PAL.danger if i == 5 else PAL.line,
            body_size=15,
        )

    d.rect(90, 1000, 2020, 255, PAL.paper, stroke=PAL.dark_line, radius=26)
    d.text(120, 1025, "Promotion evidence boundary", 24, PAL.ink, bold=True)
    evidence_cols = [
        (
            "Diagnostics only",
            "Force exposure and force calls can test latent value, schema defects, and preservation mechanics. They cannot promote a helper.",
        ),
        (
            "Natural comparison",
            "Actual evidence requires natural routing and natural calls on unseen tasks with no code or registry changes between matched arms.",
        ),
        (
            "Scale decision",
            "Move to 100/250/500 only when outcome lift, called-subset contribution, safety, leakage, and cache policy all pass.",
        ),
    ]
    for i, (title, body) in enumerate(evidence_cols):
        d.component(
            125 + i * 650,
            1090,
            560,
            120,
            title,
            [body],
            fill=PAL.control_fill
            if i == 0
            else PAL.sage_fill
            if i == 1
            else PAL.evidence_fill,
            stroke=PAL.control if i == 0 else PAL.sage if i == 1 else PAL.evidence,
            accent=PAL.control if i == 0 else PAL.sage if i == 1 else PAL.evidence,
            body_size=15,
        )

    for i, (x, _) in enumerate(positions):
        if i in {2, 3, 4, 5, 6}:
            d.polyline(
                [(x + w // 2, y0 + h), (x + w // 2, 520)],
                color=PAL.danger,
                dash="10 8",
                label="fail -> repair",
                label_at=(x + w // 2, 470),
            )
    d.polyline([(395, 930), (395, 1000)], color=PAL.control, label="diagnose")
    d.polyline([(1045, 930), (1045, 1000)], color=PAL.sage, label="walk back")
    d.polyline([(1695, 930), (1695, 1000)], color=PAL.evidence, label="scale if safe")
    d.rect(90, 1305, 2020, 95, PAL.danger_fill, stroke=PAL.danger, radius=20)
    d.text(120, 1328, "Hard stop conditions", 22, PAL.danger, bold=True)
    d.text(
        390,
        1328,
        "Label leakage, expected-answer hard-coding, scenario-specific strings, unresolved side-effect incidents, or candidate task-cache reuse block promotion immediately.",
        19,
        PAL.ink,
        max_width=1650,
    )
    d.finish()


def render_paper_diagram() -> None:
    d = Diagram(
        "sage_peer_review_methodology_figure",
        "4. Paper Figure: Matched Validation And Self-Evolving Tool Lifecycle",
        2200,
        1500,
        paper=True,
    )
    d.text(
        70,
        95,
        "Single-figure methodology view for peer review: experimental contract, self-evolution mechanism, safety/leakage controls, and evidence roles.",
        20,
        PAL.muted,
        max_width=1940,
    )

    d.rect(70, 165, 990, 570, PAL.paper, stroke=PAL.dark_line, radius=18)
    d.text(
        95, 190, "A. Matched ToolSandbox validation contract", 24, PAL.ink, bold=True
    )
    d.data_store(
        120,
        270,
        250,
        145,
        "Sealed manifest",
        "Scenario order, task splits, hash.",
        stroke=PAL.dark_line,
        fill=PAL.paper,
    )
    d.component(
        460,
        230,
        250,
        180,
        "Baseline",
        ["Base tools", "Fresh same-run controls", "Same model policy"],
        fill=PAL.paper,
        stroke=PAL.dark_line,
        accent=PAL.control,
        body_size=13,
    )
    d.component(
        460,
        500,
        250,
        180,
        "SAGE",
        ["Fresh candidate arm", "Registry or live generation", "Candidate cache off"],
        fill=PAL.paper,
        stroke=PAL.dark_line,
        accent=PAL.sage,
        body_size=13,
    )
    d.component(
        810,
        360,
        210,
        190,
        "ToolSandbox + scorer",
        ["Stateful tools", "User simulator", "Outcome and canonical scoring"],
        fill=PAL.paper,
        stroke=PAL.dark_line,
        accent=PAL.sandbox,
        body_size=13,
    )
    d.polyline([(370, 327), (460, 305)], color=PAL.dark_line)
    d.polyline([(370, 327), (430, 327), (430, 575), (460, 575)], color=PAL.dark_line)
    d.polyline([(710, 305), (810, 425)], color=PAL.dark_line)
    d.polyline([(710, 575), (810, 455)], color=PAL.dark_line)
    d.polyline([(1020, 440), (1090, 440)], color=PAL.dark_line)

    d.rect(1090, 165, 1040, 570, PAL.paper, stroke=PAL.dark_line, radius=18)
    d.text(
        1115, 190, "B. Statistical and reproducibility outputs", 24, PAL.ink, bold=True
    )
    outputs = [
        ("Performance endpoint", "Outcome/task completion delta, paired by scenario."),
        ("Descriptive audit", "Canonical/reference route compatibility."),
        ("Uncertainty", "Paired bootstrap CI and paired randomization test."),
        (
            "Trace evidence",
            "Visible/called/VNC, route mismatch, called-subset contribution.",
        ),
        ("Safety", "Runtime exceptions, helper failures, side-effect incidents."),
        (
            "Reproducibility",
            "Registry hashes, cache manifests, run ledger, dashboards.",
        ),
    ]
    for i, (title, body) in enumerate(outputs):
        d.component(
            1130 + (i % 2) * 480,
            270 + (i // 2) * 130,
            420,
            100,
            title,
            [body],
            fill=PAL.paper,
            stroke=PAL.dark_line,
            accent=PAL.evidence if i < 4 else PAL.danger if i == 4 else PAL.line,
            body_size=13,
        )

    d.rect(70, 805, 1250, 530, PAL.paper, stroke=PAL.dark_line, radius=18)
    d.text(95, 830, "C. Self-evolving SAGE mechanism", 24, PAL.ink, bold=True)
    loop = [
        ("Observe", "Gap packets from traces"),
        ("Generate", "Typed helper candidates"),
        ("Validate", "Static, schema, minefield, live smoke"),
        ("Retain", "Registry with lifecycle state"),
        ("Route", "System-selected bounded bundle"),
        ("Reflect", "Scale, repair, recombine, park"),
    ]
    centers: list[tuple[int, int]] = []
    for i, (title, body) in enumerate(loop):
        cx = 190 + i * 205
        cy = 1070
        centers.append((cx, cy))
        d.circle(cx, cy, 78, PAL.paper, stroke=PAL.sage, width=3)
        d.text(cx - 58, cy - 40, title, 17, PAL.ink, bold=True, max_width=116)
        d.text(cx - 62, cy - 10, body, 12, PAL.muted, max_width=124, line_height=15)
    for first, second in zip(centers, centers[1:]):
        d.polyline(
            [(first[0] + 78, first[1]), (second[0] - 78, second[1])], color=PAL.sage
        )
    d.polyline(
        [
            (centers[-1][0], centers[-1][1] + 78),
            (centers[-1][0], 1238),
            (centers[0][0], 1238),
            (centers[0][0], centers[0][1] + 78),
        ],
        color=PAL.sage,
        dash="10 8",
    )

    d.rect(1380, 805, 750, 530, PAL.paper, stroke=PAL.dark_line, radius=18)
    d.text(1405, 830, "D. Research integrity guardrails", 24, PAL.ink, bold=True)
    guardrails = [
        (
            "Leakage",
            "No hidden labels, expected answers, scenario-specific tool logic, or prior SAGE trace reuse.",
        ),
        (
            "Cache",
            "No task/result or stored-response replay; provider prefix reuse is recorded separately.",
        ),
        (
            "Side effects",
            "Helpers prepare values or action specs; original ToolSandbox side-effect tools still execute.",
        ),
        (
            "Promotion",
            "Force-call diagnostics repair the system but never count as evidence.",
        ),
        (
            "Claim boundary",
            "Experimental candidates become protected claims only after locked matched review.",
        ),
    ]
    for i, (title, body) in enumerate(guardrails):
        y = 890 + i * 86
        accent = PAL.danger if i in {0, 2, 3} else PAL.evidence
        d.rect(1420, y, 660, 76, PAL.paper, stroke=PAL.dark_line, radius=14, width=2)
        d.rect(1420, y, 12, 76, accent, stroke="none", radius=14)
        d.text(1450, y + 14, title, 16, PAL.ink, bold=True, max_width=180)
        d.text(1475, y + 42, body, 12, PAL.muted, max_width=560, line_height=15)

    d.text(
        80,
        1390,
        "Caption draft: SAGE is evaluated as a matched ToolSandbox treatment with a sealed manifest, fresh same-run control and SAGE arms, bounded generated-tool routing, safety/leakage gates, and paired statistical analysis. Outcome/task completion is the sole performance endpoint; canonical/reference similarity is descriptive only.",
        18,
        PAL.ink,
        max_width=2040,
    )
    d.finish()


def write_sage_one_page_infographic_html() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    example_registry = Path(
        "artifacts/self_evolving_sage/current_formal500_live_generation_v71_clean_repro/formal500_registry/registry_manifest.json"
    )
    example_specs = [
        (
            "prepare_side_effect_args_from_selected_record",
            "Action-spec helper",
            "Turns a selected contact or reminder record into safe downstream ToolSandbox arguments without mutating state.",
        ),
        (
            "prepare_reminder_creation_args",
            "Reminder helper",
            "Builds add_reminder arguments from resolved time and optional location fields while preserving abstain cases.",
        ),
        (
            "next_weekday_time_to_timestamp",
            "Time normalizer",
            "Converts a visible current timestamp plus weekday/time fields into a deterministic reminder timestamp.",
        ),
    ]
    tool_example_cards: list[str] = []
    if example_registry.exists():
        import json

        registry_data = json.loads(example_registry.read_text(encoding="utf-8"))
        generated_tools = registry_data.get("tools", {})
        for tool_name, label, description in example_specs:
            entry = generated_tools.get(tool_name, {})
            code = (entry.get("tool") or {}).get("code") or ""
            snippet = "\n".join(code.strip().splitlines()[:42])
            if not snippet:
                continue
            tool_example_cards.append(
                f"""
              <article class="example-card" data-section="example-{escape(tool_name)}">
                <h3>{escape(tool_name)}</h3>
                <p><strong>{escape(label)}.</strong> {escape(description)}</p>
                <pre><code>{escape(snippet)}</code></pre>
              </article>"""
            )
    tool_examples_html = "\n".join(tool_example_cards)
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SAGE One-Page Infographic</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111f;
      --panel: #0f1c2d;
      --ink: #eef6ff;
      --muted: #9fb2c7;
      --cyan: #37c5ff;
      --green: #43e08f;
      --yellow: #ffd45a;
      --purple: #a78bfa;
      --red: #ff6b7a;
      --line: #28405d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 15% 10%, rgba(55, 197, 255, 0.14), transparent 30%),
        radial-gradient(circle at 86% 12%, rgba(167, 139, 250, 0.16), transparent 28%),
        var(--bg);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
    }
    main {
      width: min(100%, 1180px);
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 4vw, 52px);
      letter-spacing: 0;
    }
    p {
      margin: 8px 0 0;
      max-width: 760px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.45;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }
    a {
      color: var(--ink);
      text-decoration: none;
    }
    .button {
      border: 1px solid var(--cyan);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(55, 197, 255, 0.1);
      color: var(--ink);
      font-weight: 700;
      font-size: 14px;
      white-space: nowrap;
    }
    .figure-shell {
      border: 1px solid var(--line);
      border-radius: 28px;
      background: rgba(15, 28, 45, 0.72);
      box-shadow: 0 26px 80px rgba(0, 0, 0, 0.34);
      padding: 18px;
      overflow-x: auto;
    }
    img {
      display: block;
      width: 100%;
      height: auto;
      border-radius: 18px;
      background: #07111f;
    }
    .infographic {
      min-width: 1040px;
      display: grid;
      gap: 28px;
      border-radius: 20px;
      background:
        radial-gradient(circle at 18% 6%, rgba(55, 197, 255, 0.11), transparent 30%),
        radial-gradient(circle at 85% 8%, rgba(167, 139, 250, 0.12), transparent 28%),
        #07111f;
      padding: 26px;
    }
    section,
    article,
    .endpoint-card,
    .tool-row,
    .metric-row,
    .ladder-step {
      scroll-margin: 24px;
    }
    .top-band {
      display: grid;
      grid-template-columns: 1fr 280px;
      gap: 26px;
      align-items: stretch;
    }
    .intro-card,
    .endpoint-card,
    .flywheel-panel,
    .panel,
    .evidence-ladder {
      border: 1px solid var(--line);
      background: #0f1c2d;
      border-radius: 26px;
    }
    .intro-card {
      padding: 28px;
    }
    .intro-card h2 {
      margin: 0;
      font-size: 72px;
      line-height: 0.95;
    }
    .intro-card h3 {
      margin: 16px 0 0;
      font-size: 30px;
      line-height: 1.15;
    }
    .endpoint-stack {
      display: grid;
      gap: 16px;
    }
    .endpoint-card {
      padding: 22px 24px;
      border-color: var(--cyan);
      background: #102b3f;
    }
    .endpoint-card.secondary {
      border-color: var(--purple);
      background: #2c2035;
    }
    .eyebrow {
      display: block;
      color: var(--muted);
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .endpoint-value {
      display: block;
      color: var(--green);
      font-size: 28px;
      font-weight: 800;
      line-height: 1.05;
    }
    .secondary .endpoint-value {
      color: var(--purple);
    }
    .flywheel-panel {
      background: #0a1728;
      padding: 30px;
    }
    .flywheel-panel h2,
    .panel h2,
    .evidence-ladder h2 {
      margin: 0;
      font-size: 30px;
      line-height: 1.1;
    }
    .flywheel-panel > p {
      max-width: 660px;
      font-size: 19px;
      line-height: 1.4;
      margin-bottom: 24px;
    }
    .flywheel-grid {
      position: relative;
      height: 800px;
      margin-top: 16px;
    }
    .flywheel-grid::before {
      content: "";
      position: absolute;
      left: 50%;
      top: 50%;
      width: 570px;
      height: 570px;
      transform: translate(-50%, -56%);
      border: 4px solid rgba(55, 197, 255, 0.22);
      border-radius: 50%;
      box-shadow:
        0 0 0 22px rgba(55, 197, 255, 0.035),
        inset 0 0 0 1px rgba(55, 197, 255, 0.2);
    }
    .flywheel-grid::after {
      content: "continuous evidence loop";
      position: absolute;
      left: 50%;
      bottom: 132px;
      transform: translateX(-50%);
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 999px;
      padding: 8px 14px;
      font-size: 15px;
      font-weight: 700;
      background: #0a1728;
    }
    .step-card,
    .registry-core,
    .loop-note {
      position: absolute;
      min-height: 166px;
      border-radius: 22px;
      background: var(--panel);
      border: 2px solid var(--accent);
      padding: 20px 22px;
    }
    .step-card {
      display: grid;
      grid-template-columns: 48px 1fr;
      column-gap: 14px;
      align-content: start;
      width: 270px;
      z-index: 2;
    }
    .step-number {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: #07111f;
      background: var(--accent);
      font-size: 24px;
      font-weight: 800;
    }
    .step-card h3 {
      margin: 4px 0 0;
      font-size: 21px;
      line-height: 1.12;
    }
    .step-card p {
      grid-column: 1 / -1;
      margin-top: 12px;
      font-size: 16px;
      line-height: 1.35;
    }
    .cyan { --accent: var(--cyan); }
    .green { --accent: var(--green); }
    .yellow { --accent: var(--yellow); }
    .purple { --accent: var(--purple); }
    .red { --accent: var(--red); }
    .registry-core {
      --accent: var(--cyan);
      left: 50%;
      top: 50%;
      width: 276px;
      height: 276px;
      transform: translate(-50%, -50%);
      display: grid;
      align-content: center;
      justify-items: center;
      text-align: center;
      background: #102235;
      border-radius: 50%;
      box-shadow:
        inset 0 0 0 8px rgba(55, 197, 255, 0.08),
        0 0 38px rgba(55, 197, 255, 0.18);
      z-index: 1;
    }
    .registry-core h3 {
      margin: 0 0 8px;
      color: var(--yellow);
      font-size: 30px;
      line-height: 1;
    }
    .registry-core strong {
      display: block;
      font-size: 22px;
      line-height: 1.15;
    }
    .registry-core p,
    .loop-note p {
      font-size: 16px;
      line-height: 1.35;
    }
    .loop-note {
      --accent: var(--line);
      left: 50%;
      bottom: 0;
      width: min(680px, calc(100% - 120px));
      min-height: 86px;
      transform: translateX(-50%);
      border-style: dashed;
      color: var(--muted);
      text-align: center;
      z-index: 2;
    }
    .loop-note strong {
      display: block;
      color: var(--ink);
      font-size: 20px;
      margin-bottom: 8px;
    }
    .step-card[data-section="step-run-sealed-task"] { left: calc(50% - 135px); top: 0; }
    .step-card[data-section="step-detect-gap"] { right: 48px; top: 86px; }
    .step-card[data-section="step-generate-helper"] { right: 48px; top: 336px; }
    .step-card[data-section="step-validate-repair"] { right: 176px; top: 560px; }
    .step-card[data-section="step-store-registry"] { left: 176px; top: 560px; }
    .step-card[data-section="step-route-bundle"] { left: 48px; top: 336px; }
    .step-card[data-section="step-measure-reflect"] { left: 48px; top: 86px; }
    .info-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 28px;
    }
    .panel {
      padding: 28px;
      min-height: 350px;
      border-color: var(--accent);
    }
    .tools { --accent: var(--green); }
    .guardrails { --accent: var(--yellow); }
    .metrics { --accent: var(--purple); }
    .tool-list,
    .metric-list,
    .guardrails ul {
      display: grid;
      gap: 16px;
      margin-top: 26px;
    }
    .tool-row {
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 18px;
      align-items: center;
    }
    .tool-pill {
      border: 1px solid var(--green);
      border-radius: 999px;
      color: var(--green);
      padding: 8px 12px;
      font-size: 15px;
      font-weight: 800;
      text-align: center;
      background: #102b3f;
      cursor: pointer;
      font-family: inherit;
      display: inline-block;
    }
    button.tool-pill {
      width: 100%;
    }
    .tool-pill:hover,
    .tool-pill:focus {
      outline: none;
      border-color: var(--cyan);
      box-shadow: 0 0 0 3px rgba(55, 197, 255, 0.22);
    }
    .tool-row span:last-child,
    .metric-row span:last-child,
    .guardrails li {
      color: var(--muted);
      font-size: 18px;
      line-height: 1.3;
    }
    .guardrails ul {
      padding: 0;
      list-style: none;
    }
    .guardrails li {
      position: relative;
      padding-left: 28px;
    }
    .guardrails li::before {
      content: "";
      position: absolute;
      left: 0;
      top: 8px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--yellow);
    }
    .metric-row {
      display: grid;
      grid-template-columns: 104px 1fr;
      gap: 18px;
    }
    .metric-row strong {
      color: var(--purple);
      font-size: 18px;
    }
    .evidence-ladder {
      padding: 28px;
      background: #101f32;
    }
    .tool-example-drawer {
      display: none;
      border: 1px solid var(--green);
      border-radius: 28px;
      background: #0f1c2d;
      padding: 28px;
    }
    .tool-example-drawer.open {
      display: block;
    }
    .tool-example-drawer h2 {
      margin: 0;
      font-size: 30px;
    }
    .tool-example-drawer > p {
      font-size: 18px;
      max-width: 860px;
    }
    .example-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      margin-top: 22px;
    }
    .example-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #0a1728;
      padding: 18px;
    }
    .example-card h3 {
      margin: 0 0 10px;
      font-size: 18px;
      color: var(--green);
    }
    .example-card p {
      font-size: 15px;
      line-height: 1.35;
    }
    pre {
      margin: 14px 0 0;
      max-height: 360px;
      overflow: auto;
      border-radius: 14px;
      padding: 14px;
      background: #06101d;
      border: 1px solid #203854;
      color: #d7e7f7;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre;
    }
    .ladder-track {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 18px;
      margin-top: 28px;
    }
    .ladder-step {
      position: relative;
      min-height: 164px;
      padding: 88px 12px 12px;
      text-align: center;
      border-radius: 20px;
      background: rgba(15, 28, 45, 0.76);
      border: 1px solid var(--line);
    }
    .ladder-step::before {
      content: attr(data-step);
      position: absolute;
      left: 50%;
      top: 16px;
      width: 60px;
      height: 60px;
      transform: translateX(-50%);
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: #07111f;
      background: var(--accent);
      font-size: 26px;
      font-weight: 800;
    }
    .ladder-step strong {
      display: block;
      font-size: 20px;
      margin-bottom: 6px;
    }
    .ladder-step span {
      color: var(--muted);
      font-size: 16px;
      line-height: 1.25;
    }
    .note {
      border-left: 4px solid var(--green);
      margin-top: 18px;
      padding: 10px 14px;
      color: var(--muted);
      background: rgba(67, 224, 143, 0.08);
      border-radius: 10px;
      font-size: 15px;
      line-height: 1.45;
    }
    @media (max-width: 760px) {
      header {
        align-items: flex-start;
        flex-direction: column;
      }
      .actions {
        justify-content: flex-start;
      }
      main {
        padding-inline: 12px;
      }
      .figure-shell {
        padding: 10px;
        border-radius: 18px;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>SAGE One-Page Infographic</h1>
        <p>Shareable visual summary of the self-evolving SAGE loop: observe gaps, generate helpers, validate and repair, store safe tools, route a bounded helper bundle, and measure matched ToolSandbox lift.</p>
      </div>
      <nav class="actions" aria-label="Asset links">
        <a class="button" href="sage_one_page_infographic.svg">Open SVG</a>
        <a class="button" href="sage_one_page_infographic.png">Open PNG</a>
      </nav>
    </header>
    <section class="figure-shell" aria-label="SAGE infographic with selectable sections">
      <div class="infographic">
        <section class="top-band" data-section="infographic-summary" aria-label="SAGE summary">
          <article class="intro-card" data-section="hero">
            <h2>SAGE</h2>
            <h3>A self-evolving tool system for ToolSandbox tasks</h3>
            <p>Observe capability gaps, generate safe helper tools, validate them, remember what works, and reuse them on future tasks.</p>
          </article>
          <aside class="endpoint-stack" data-section="endpoint-summary" aria-label="Endpoint summary">
            <div class="endpoint-card" data-section="performance-endpoint">
              <span class="eyebrow">Performance endpoint</span>
              <span class="endpoint-value">task outcome</span>
            </div>
            <div class="endpoint-card secondary" data-section="descriptive-audit">
              <span class="eyebrow">Descriptive audit</span>
              <span class="endpoint-value">route match</span>
            </div>
          </aside>
        </section>

        <section class="flywheel-panel" data-section="sage-flywheel" aria-label="SAGE flywheel">
          <h2>The SAGE flywheel</h2>
          <p>Each task either uses the current registry or teaches SAGE what reusable deterministic help is missing.</p>
          <div class="flywheel-grid">
            <article class="step-card yellow" data-section="step-measure-reflect">
              <span class="step-number">7</span>
              <h3>Measure and reflect</h3>
              <p>SAGE records gains, regressions, visible-not-called cases, safety, and lifecycle decisions.</p>
            </article>
            <article class="step-card cyan" data-section="step-run-sealed-task">
              <span class="step-number">1</span>
              <h3>Run a sealed task</h3>
              <p>The task comes from a fixed manifest. Baseline and SAGE see the same task order.</p>
            </article>
            <article class="step-card yellow" data-section="step-detect-gap">
              <span class="step-number">2</span>
              <h3>Detect a gap</h3>
              <p>Finds missing deterministic steps: selection, time, preconditions, action args, or abstention.</p>
            </article>
            <article class="step-card green" data-section="step-route-bundle">
              <span class="step-number">6</span>
              <h3>Route a small bundle</h3>
              <p>The system selects relevant helpers. The actor naturally decides whether to call them.</p>
            </article>
            <article class="registry-core" data-section="registry-core">
              <h3>registry</h3>
              <strong>validated helper memory</strong>
              <p>Accepted tools become reusable memory after safety and usefulness checks.</p>
            </article>
            <article class="step-card green" data-section="step-generate-helper">
              <span class="step-number">3</span>
              <h3>Generate a helper</h3>
              <p>A small typed Python tool is proposed. It should solve a reusable subproblem, not memorize an answer.</p>
            </article>
            <article class="step-card cyan" data-section="step-store-registry">
              <span class="step-number">5</span>
              <h3>Store what passes</h3>
              <p>Accepted helpers enter the registry with metadata, hashes, evidence, risks, and lifecycle status.</p>
            </article>
            <article class="step-card purple" data-section="step-validate-repair">
              <span class="step-number">4</span>
              <h3>Validate and repair</h3>
              <p>Static, schema, minefield, smoke, and side-effect checks run before acceptance.</p>
            </article>
            <article class="loop-note" data-section="flywheel-loop-note">
              <strong>Closed loop</strong>
              <p>New evidence updates routing, repair, retention, and scale decisions for later tasks.</p>
            </article>
          </div>
        </section>

        <section class="info-grid" data-section="infographic-detail-panels" aria-label="Infographic detail panels">
          <article class="panel tools" data-section="what-sage-generates">
            <h2>What SAGE generates</h2>
            <div class="tool-list">
              <div class="tool-row" data-section="generated-helper-tools"><button class="tool-pill" type="button" data-open-examples>helper tools</button><span>small Python functions</span></div>
              <div class="tool-row" data-section="generated-action-specs"><button class="tool-pill" type="button" data-open-examples>action specs</button><span>safe next-tool arguments</span></div>
              <div class="tool-row" data-section="generated-selectors"><button class="tool-pill" type="button" data-open-examples>selectors</button><span>choose the right record</span></div>
              <div class="tool-row" data-section="generated-normalizers"><button class="tool-pill" type="button" data-open-examples>normalizers</button><span>dates, units, formats</span></div>
              <div class="tool-row" data-section="generated-abstainers"><button class="tool-pill" type="button" data-open-examples>abstainers</button><span>say when info is missing</span></div>
            </div>
          </article>
          <article class="panel guardrails" data-section="scientific-guardrails">
            <h2>Scientific guardrails</h2>
            <ul>
              <li data-section="guardrail-no-labels">No hidden labels or expected answers.</li>
              <li data-section="guardrail-no-hardcoding">No scenario-specific hard-coding.</li>
              <li data-section="guardrail-no-helper-side-effects">Helpers do not mutate ToolSandbox state.</li>
              <li data-section="guardrail-force-call-boundary">Force-calls diagnose; they are not evidence.</li>
              <li data-section="guardrail-fresh-sage-arms">SAGE arms stay fresh in claim runs.</li>
            </ul>
          </article>
          <article class="panel metrics" data-section="what-gets-measured">
            <h2>What gets measured</h2>
            <div class="metric-list">
              <div class="metric-row" data-section="metric-outcome"><strong>Outcome</strong><span>Did the task get completed?</span></div>
              <div class="metric-row" data-section="metric-canonical"><strong>Canonical</strong><span>Did the route match the benchmark?</span></div>
              <div class="metric-row" data-section="metric-adoption"><strong>Adoption</strong><span>Was the helper visible and called?</span></div>
              <div class="metric-row" data-section="metric-safety"><strong>Safety</strong><span>Any exceptions or side-effect incidents?</span></div>
              <div class="metric-row" data-section="metric-lift"><strong>Lift</strong><span>Did SAGE beat the matched baseline?</span></div>
            </div>
          </article>
        </section>

        <section class="tool-example-drawer" id="generated-tool-examples" data-section="generated-tool-examples" aria-label="Generated Python tool examples">
          <h2>Generated Python tool examples</h2>
          <p>These snippets come from the self-evolving v71 generated-tool registry and show the kind of side-effect-free helper code SAGE can create, validate, retain, and reuse.</p>
          <div class="example-grid">
__TOOL_EXAMPLES__
          </div>
        </section>

        <section class="evidence-ladder" data-section="evidence-ladder" aria-label="Evidence ladder">
          <h2>Evidence ladder</h2>
          <div class="ladder-track">
            <article class="ladder-step cyan" data-step="1" data-section="evidence-discovery"><strong>Discovery</strong><span>generation on</span></article>
            <article class="ladder-step green" data-step="2" data-section="evidence-candidate"><strong>Candidate</strong><span>retain and recombine</span></article>
            <article class="ladder-step yellow" data-step="3" data-section="evidence-freeze"><strong>Freeze</strong><span>generation off</span></article>
            <article class="ladder-step purple" data-step="4" data-section="evidence-validation"><strong>Validation</strong><span>matched statistical review</span></article>
            <article class="ladder-step red" data-step="5" data-section="evidence-claim"><strong>Claim</strong><span>only if safe and reproducible</span></article>
          </div>
        </section>

        <section class="note" data-section="plain-language-summary">
          Plain-language summary: SAGE learns reusable, side-effect-free helpers from observed gaps, validates them before use, stores the safe ones, and tests whether natural reuse improves matched ToolSandbox outcomes.
        </section>
      </div>
    </section>
    <div class="note">
      Generated by <code>scripts/render_sage_methodology_diagrams.py</code>. Regenerate the full figure set with <code>python3 scripts/render_sage_methodology_diagrams.py</code> whenever any figure is changed, so SVG, PNG, and HTML companions remain synchronized.
    </div>
  </main>
  <script>
    const exampleDrawer = document.getElementById("generated-tool-examples");
    document.querySelectorAll("[data-open-examples]").forEach((button) => {
      button.addEventListener("click", () => {
        exampleDrawer.classList.add("open");
        exampleDrawer.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  </script>
</body>
</html>
"""
    html = html.replace("__TOOL_EXAMPLES__", tool_examples_html)
    (OUT_DIR / "sage_one_page_infographic.html").write_text(html, encoding="utf-8")


def render_sage_one_page_infographic() -> None:
    d = Diagram(
        "sage_one_page_infographic",
        "",
        1600,
        2250,
    )
    bg = "#07111f"
    panel = "#0f1c2d"
    ink = "#eef6ff"
    muted = "#9fb2c7"
    cyan = "#37c5ff"
    green = "#43e08f"
    yellow = "#ffd45a"
    purple = "#a78bfa"
    red = "#ff6b7a"
    line = "#28405d"

    d.rect(0, 0, 1600, 2250, bg, stroke="none", radius=0)
    for x in range(80, 1520, 160):
        for y in range(110, 2220, 160):
            d.circle(x, y, 3, "#13243a", stroke="none")

    d.text(90, 78, "SAGE", 92, ink, bold=True, max_width=360, line_height=96)
    d.text(
        92,
        190,
        "A self-evolving tool system for ToolSandbox tasks",
        34,
        "#c8dbef",
        bold=True,
        max_width=1040,
    )
    d.text(
        95,
        246,
        "Observe capability gaps, generate safe helper tools, validate them, remember what works, and reuse them on future tasks.",
        24,
        muted,
        max_width=1100,
        line_height=32,
    )
    d.rect(1190, 88, 300, 96, "#102b3f", stroke=cyan, radius=28, width=2)
    d.text(1230, 108, "Performance endpoint", 19, muted, bold=True, max_width=230)
    d.text(1230, 144, "task outcome", 30, green, bold=True, max_width=230)
    d.rect(1190, 205, 300, 96, "#2c2035", stroke=purple, radius=28, width=2)
    d.text(1230, 225, "Descriptive audit", 19, muted, bold=True, max_width=230)
    d.text(1230, 261, "route match", 30, purple, bold=True, max_width=230)

    d.rect(70, 360, 1460, 1015, "#0a1728", stroke=line, radius=36, width=2)
    d.text(110, 398, "The SAGE flywheel", 34, ink, bold=True, max_width=520)
    d.text(
        110,
        448,
        "Each task either uses the current registry or teaches SAGE what reusable deterministic help is missing.",
        22,
        muted,
        max_width=900,
        line_height=30,
    )

    nodes = [
        (
            656,
            525,
            "1",
            "Run a sealed task",
            "The task comes from a fixed manifest. Baseline and SAGE see the same task order.",
            cyan,
        ),
        (
            1080,
            625,
            "2",
            "Detect a gap",
            "Finds missing deterministic steps: selection, time, preconditions, action args, or abstention.",
            yellow,
        ),
        (
            1080,
            910,
            "3",
            "Generate a helper",
            "A small typed Python tool is proposed. It should solve a reusable subproblem, not memorize an answer.",
            green,
        ),
        (
            832,
            1140,
            "4",
            "Validate and repair",
            "Static, schema, minefield, smoke, and side-effect checks run before acceptance.",
            purple,
        ),
        (
            480,
            1140,
            "5",
            "Store what passes",
            "Accepted helpers enter the registry with metadata, hashes, evidence, risks, and lifecycle status.",
            cyan,
        ),
        (
            232,
            910,
            "6",
            "Route a small bundle",
            "The system selects relevant helpers. The actor naturally decides whether to call them.",
            green,
        ),
        (
            232,
            625,
            "7",
            "Measure and reflect",
            "SAGE records gains, regressions, visible-not-called cases, safety, and lifecycle decisions.",
            yellow,
        ),
    ]
    node_w = 310
    node_h = 176
    centers = [(x + node_w // 2, y + node_h // 2) for x, y, *_ in nodes]
    for a, b in zip(centers, centers[1:] + centers[:1]):
        d.polyline([a, b], color="#2c6f91", width=5)

    d.circle(800, 875, 178, "#12283c", stroke="#295170", width=4)
    d.circle(800, 875, 126, "#102235", stroke=cyan, width=2)
    d.text(700, 795, "registry", 32, yellow, bold=True, max_width=220)
    d.text(660, 850, "validated helper memory", 24, ink, bold=True, max_width=292)
    d.text(
        668,
        920,
        "Accepted tools become reusable memory after safety and usefulness checks.",
        18,
        muted,
        max_width=265,
        line_height=23,
    )

    for x, y, num, title, body, accent in nodes:
        d.rect(x, y, node_w, node_h, panel, stroke=accent, radius=24, width=2)
        d.circle(x + 40, y + 40, 28, accent, stroke=accent, width=2)
        d.text(x + 31, y + 21, num, 27, bg, bold=True, max_width=42)
        d.text(x + 82, y + 25, title, 22, ink, bold=True, max_width=200)
        d.text(x + 30, y + 84, body, 16, muted, max_width=250, line_height=20)

    d.rect(100, 1430, 440, 405, panel, stroke=green, radius=28, width=2)
    d.text(135, 1460, "What SAGE generates", 30, ink, bold=True, max_width=360)
    generated = [
        ("helper tools", "small Python functions"),
        ("action specs", "safe next-tool arguments"),
        ("selectors", "choose the right record"),
        ("normalizers", "dates, units, formats"),
        ("abstainers", "say when info is missing"),
    ]
    yy = 1532
    for label, body in generated:
        d.rect(135, yy, 170, 38, "#102b3f", stroke=green, radius=19, width=1)
        d.text(154, yy + 6, label, 16, green, bold=True, max_width=142)
        d.text(326, yy + 1, body, 19, muted, max_width=170, line_height=24)
        yy += 56

    d.rect(580, 1430, 440, 405, panel, stroke=yellow, radius=28, width=2)
    d.text(615, 1460, "Scientific guardrails", 30, ink, bold=True, max_width=360)
    guardrails = [
        "No hidden labels or expected answers.",
        "No scenario-specific hard-coding.",
        "Helpers do not mutate ToolSandbox state.",
        "Force-calls diagnose; they are not evidence.",
        "SAGE arms stay fresh in claim runs.",
    ]
    yy = 1532
    for item in guardrails:
        d.circle(628, yy + 13, 8, yellow, stroke="none")
        d.text(653, yy, item, 19, muted, max_width=320, line_height=24)
        yy += 58

    d.rect(1060, 1430, 440, 405, panel, stroke=purple, radius=28, width=2)
    d.text(1095, 1460, "What gets measured", 30, ink, bold=True, max_width=360)
    measures = [
        ("Outcome", "Did the task get completed?"),
        ("Canonical", "Did the route match the benchmark?"),
        ("Adoption", "Was the helper visible and called?"),
        ("Safety", "Any exceptions or side-effect incidents?"),
        ("Lift", "Did SAGE beat the matched baseline?"),
    ]
    yy = 1532
    for label, body in measures:
        d.text(1095, yy, label, 19, purple, bold=True, max_width=118)
        d.text(1220, yy, body, 19, muted, max_width=245, line_height=24)
        yy += 58

    d.rect(100, 1890, 1400, 225, "#101f32", stroke=line, radius=30, width=2)
    d.text(140, 1920, "Evidence ladder", 30, ink, bold=True, max_width=280)
    ladder = [
        ("Discovery", "generation on", cyan),
        ("Candidate", "retain and recombine", green),
        ("Freeze", "generation off", yellow),
        ("Validation", "matched statistical review", purple),
        ("Claim", "only if safe and reproducible", red),
    ]
    start_x = 380
    for i, (title, sub, color) in enumerate(ladder):
        x = start_x + i * 215
        d.circle(x, 1978, 48, color, stroke=color, width=2)
        d.text(x - 20, 1957, str(i + 1), 32, bg, bold=True, max_width=40)
        d.text(x - 82, 2038, title, 20, ink, bold=True, max_width=164)
        d.text(x - 84, 2072, sub, 16, muted, max_width=168, line_height=20)
        if i < len(ladder) - 1:
            d.polyline([(x + 52, 1978), (x + 162, 1978)], color=line, width=4)

    d.text(
        105,
        2165,
        "Plain-language summary: SAGE learns reusable, side-effect-free helpers from observed gaps, validates them before use, stores the safe ones, and tests whether natural reuse improves matched ToolSandbox outcomes.",
        20,
        "#b8cce0",
        max_width=1390,
        line_height=26,
    )
    d.finish()
    write_sage_one_page_infographic_html()


def main() -> None:
    render_overview()
    render_sage_zoom()
    render_tool_loop()
    render_paper_diagram()
    render_sage_one_page_infographic()


if __name__ == "__main__":
    main()
