"""Render SAGE methodology diagrams as SVG and PNG assets."""

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
    bg: str = "#f7f9fc"
    ink: str = "#172033"
    muted: str = "#536178"
    line: str = "#9aa8bd"
    sage: str = "#1f7a6d"
    sage_light: str = "#dff3ef"
    blue: str = "#245f9f"
    blue_light: str = "#e5f0fb"
    gold: str = "#9a6a05"
    gold_light: str = "#fff3d8"
    red: str = "#a13a3a"
    red_light: str = "#fdeaea"
    gray_light: str = "#eef2f7"
    white: str = "#ffffff"


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
        width: int = 1800,
        height: int = 1100,
        *,
        paper: bool = False,
    ) -> None:
        self.name = name
        self.title = title
        self.width = width
        self.height = height
        self.paper = paper
        self.svg: list[str] = []
        self.image = Image.new("RGB", (width, height), PAL.white if paper else PAL.bg)
        self.draw = ImageDraw.Draw(self.image)
        self.svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        )
        self.svg.append("<defs>")
        self.svg.append(
            '<marker id="arrow" markerWidth="14" markerHeight="14" refX="12" refY="7" orient="auto" markerUnits="strokeWidth">'
            '<path d="M 0 0 L 14 7 L 0 14 z" fill="#536178"/></marker>'
        )
        self.svg.append("</defs>")
        self.rect(
            0, 0, width, height, PAL.white if paper else PAL.bg, stroke="none", radius=0
        )
        self.text(60, 48, title, 34, PAL.ink, bold=True, max_width=width - 120)

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
        radius: int = 24,
        width: int = 2,
    ) -> None:
        self.svg.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )
        self.draw.rounded_rectangle(
            (x, y, x + w, y + h),
            radius=radius,
            fill=fill,
            outline=None if stroke == "none" else stroke,
            width=width,
        )

    def line(
        self, x1: int, y1: int, x2: int, y2: int, color: str = PAL.line, width: int = 3
    ) -> None:
        self.svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'
        )
        self.draw.line((x1, y1, x2, y2), fill=color, width=width)

    def arrow(
        self, x1: int, y1: int, x2: int, y2: int, color: str = PAL.muted, width: int = 4
    ) -> None:
        self.svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"/>'
        )
        self.draw.line((x1, y1, x2, y2), fill=color, width=width)
        angle = math.atan2(y2 - y1, x2 - x1)
        head = 16
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
        size: int = 24,
        color: str = PAL.ink,
        *,
        bold: bool = False,
        max_width: int = 320,
        line_height: int | None = None,
    ) -> int:
        line_height = line_height or int(size * 1.25)
        chars = max(8, int(max_width / (size * 0.54)))
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

    def card(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        body: str,
        *,
        fill: str = PAL.white,
        stroke: str = PAL.line,
        title_color: str = PAL.ink,
        body_color: str = PAL.muted,
        title_size: int = 23,
        body_size: int = 19,
    ) -> None:
        self.rect(x, y, w, h, fill, stroke=stroke, radius=18)
        self.text(
            x + 24, y + 20, title, title_size, title_color, bold=True, max_width=w - 48
        )
        self.text(x + 24, y + 62, body, body_size, body_color, max_width=w - 48)

    def pill(
        self, x: int, y: int, text: str, fill: str, stroke: str, color: str = PAL.ink
    ) -> None:
        w = max(130, 16 * len(text) + 34)
        self.rect(x, y, w, 46, fill, stroke=stroke, radius=23)
        self.text(
            x + 18, y + 9, text, 18, color, bold=True, max_width=w - 28, line_height=20
        )


def render_overview() -> None:
    d = Diagram(
        "sage_toolsandbox_system_overview",
        "1. SAGE + ToolSandbox End-to-End System",
        1900,
        1160,
    )
    d.card(
        60,
        130,
        390,
        230,
        "Sealed Task Cohort",
        "Manifest-defined scenario order, split protocol, family diversity checks, and no label peeking before unseen runs.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
    )
    d.card(
        60,
        410,
        390,
        210,
        "Control Baseline",
        "Base ToolSandbox tools. Eligible controls may use task-level baseline cache with fresh/cached counts and hash recorded.",
        fill=PAL.gray_light,
    )
    d.card(
        60,
        680,
        390,
        230,
        "SAGE Candidate",
        "Fresh candidate arm. Generation on for discovery, off for frozen validation. Candidate task cache remains off.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
    )

    d.card(
        560,
        210,
        360,
        230,
        "ToolSandbox Environment",
        "Stateful tools, user simulator, execution context, phone/contact/reminder/message/device state, and scenario scorer.",
        fill=PAL.white,
    )
    d.card(
        560,
        560,
        360,
        230,
        "Original Tool Calls",
        "SAGE helpers never replace required side-effect tools. They prepare deterministic values, selections, or next-call arguments.",
        fill=PAL.gold_light,
        stroke=PAL.gold,
    )

    d.card(
        1030,
        120,
        390,
        210,
        "SAGE Runtime",
        "Gap observer, live tool generation, validation, registry, bounded router, actor bridge policy, and lifecycle reflection.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
    )
    d.card(
        1030,
        410,
        390,
        220,
        "Matched Scoring",
        "Paired scenario-level canonical/reference score, primary outcome score, exact success, gains, regressions, and preserved counts.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
    )
    d.card(
        1030,
        710,
        390,
        220,
        "Contribution Evidence",
        "Visible/called/VNC, called-subset deltas, generated-tool births, helper failures, side-effect preservation, and route mismatch.",
        fill=PAL.white,
    )

    d.card(
        1510,
        260,
        320,
        220,
        "Dashboards",
        "Task Compare, Task Focus, run progress, task details, full transaction traces, generated tool events, and outcome lift.",
        fill=PAL.white,
    )
    d.card(
        1510,
        590,
        320,
        220,
        "Reports + Artifacts",
        "Run ledger, current state, registry manifests, hashes, summaries, statistics, and methodology assets.",
        fill=PAL.white,
    )

    for start_y in (245, 515, 795):
        d.arrow(450, start_y, 560, start_y)
    d.arrow(920, 325, 1030, 225)
    d.arrow(920, 675, 1030, 520)
    d.arrow(1420, 520, 1510, 370)
    d.arrow(1420, 820, 1510, 700)
    d.arrow(1225, 710, 1225, 630)
    d.arrow(1225, 330, 1225, 410)

    d.rect(60, 980, 1770, 110, PAL.red_light, stroke=PAL.red, radius=18)
    d.text(90, 1005, "Research Guardrails", 23, PAL.red, bold=True)
    d.text(
        90,
        1042,
        "No hidden labels, no expected-answer leakage, no scenario-specific hard-coding, no force-call promotion evidence, no candidate task cache, and zero helper side-effect incidents for claim candidates.",
        20,
        PAL.ink,
        max_width=1690,
    )
    d.finish()


def render_sage_zoom() -> None:
    d = Diagram(
        "sage_internal_components_zoom", "2. SAGE Internal Components", 1900, 1160
    )
    d.card(
        70,
        150,
        310,
        170,
        "Task + Trace Input",
        "Current task text, visible state, prior tool calls, errors, and run feedback.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
    )
    d.card(
        465,
        150,
        310,
        170,
        "Gap Observer",
        "Classifies missing deterministic step without truth labels.",
        fill=PAL.white,
    )
    d.card(
        860,
        150,
        310,
        170,
        "Tool Generator",
        "Creates typed scalar/list helper specs and code.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
    )
    d.card(
        1255,
        150,
        310,
        170,
        "Validation Gates",
        "AST safety, schema, callability, minefields, side-effect preservation.",
        fill=PAL.gold_light,
        stroke=PAL.gold,
    )

    d.card(
        70,
        460,
        310,
        170,
        "Accepted Registry",
        "Persistent helper code, metadata, validation evidence, known risks, reuse counts, hashes.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
    )
    d.card(
        465,
        460,
        310,
        170,
        "Router / Composer",
        "Small relevant helper bundle selected by task features and lifecycle evidence.",
        fill=PAL.white,
    )
    d.card(
        860,
        460,
        310,
        170,
        "Actor Bridge Policy",
        "Natural helper adoption while preserving original ToolSandbox side-effect calls.",
        fill=PAL.white,
    )
    d.card(
        1255,
        460,
        310,
        170,
        "ToolSandbox Run",
        "Agent acts in stateful benchmark with original tools plus routed helpers.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
    )

    d.card(
        465,
        780,
        310,
        170,
        "Lifecycle Reflection",
        "Retain, route-repair, adoption-repair, schema-repair, park, or scale.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
    )
    d.card(
        860,
        780,
        310,
        170,
        "Evidence Export",
        "Dashboards, contribution summary, residual gaps, run ledger, methodology reports.",
        fill=PAL.white,
    )

    d.arrow(380, 235, 465, 235)
    d.arrow(775, 235, 860, 235)
    d.arrow(1170, 235, 1255, 235)
    d.arrow(1410, 320, 1410, 460)
    d.arrow(1255, 545, 1170, 545)
    d.arrow(860, 545, 775, 545)
    d.arrow(465, 545, 380, 545)
    d.arrow(225, 460, 225, 320)
    d.arrow(1410, 630, 775, 780)
    d.arrow(775, 865, 860, 865)
    d.arrow(620, 780, 620, 630)
    d.arrow(620, 780, 1015, 320)

    d.card(
        1610,
        150,
        230,
        260,
        "Safety",
        "Side-effect-free helpers. Explicit original action follow-up. Runtime and helper incidents must remain zero.",
        fill=PAL.red_light,
        stroke=PAL.red,
        title_color=PAL.red,
    )
    d.card(
        1610,
        480,
        230,
        230,
        "Cache Policy",
        "Controls can be cached task-by-task. SAGE/candidate task evidence is fresh.",
        fill=PAL.gray_light,
    )
    d.card(
        1610,
        770,
        230,
        210,
        "Metrics",
        "Outcome primary. Canonical secondary. Exact success and contribution are explanatory.",
        fill=PAL.gray_light,
    )
    d.finish()


def render_tool_loop() -> None:
    d = Diagram(
        "sage_tool_generation_validation_repair_loop",
        "3. Tool Generation, Validation, And Repair Loop",
        1900,
        1250,
    )
    card_h = 205
    body_size = 17
    d.card(
        80,
        160,
        310,
        card_h,
        "Gap Packet",
        "Missing deterministic step, no helper fit, VNC, bad args, or called-negative evidence.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
        body_size=body_size,
    )
    d.card(
        475,
        160,
        310,
        card_h,
        "Candidate Designs",
        "Typed helper specs with final-ready outputs, abstain behavior, and negative triggers.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
        body_size=body_size,
    )
    d.card(
        870,
        160,
        310,
        card_h,
        "Static + Schema Gate",
        "No unsafe imports or side effects. Scalar/list contracts and valid metadata.",
        fill=PAL.white,
        body_size=body_size,
    )
    d.card(
        1265,
        160,
        310,
        card_h,
        "Minefield Tests",
        "Ambiguity, duplicates, missing fields, wrong units, empty results, and irrelevant families.",
        fill=PAL.gold_light,
        stroke=PAL.gold,
        body_size=body_size,
    )

    d.card(
        1265,
        520,
        310,
        card_h,
        "Live Smoke",
        "Small safe examples confirm callability and side-effect preservation mechanics.",
        fill=PAL.white,
        body_size=body_size,
    )
    d.card(
        870,
        520,
        310,
        card_h,
        "Natural Adoption Gate",
        "Visibility, calls, VNC, called-subset outcome, failures, and route mismatch.",
        fill=PAL.blue_light,
        stroke=PAL.blue,
        body_size=body_size,
    )
    d.card(
        475,
        520,
        310,
        card_h,
        "Decision",
        "Retain, refine, route repair, adoption repair, schema repair, final-output repair, or park.",
        fill=PAL.sage_light,
        stroke=PAL.sage,
        body_size=body_size,
    )
    d.card(
        80,
        520,
        310,
        card_h,
        "Registry Update",
        "Accepted helpers are versioned, hashed, bounded by routing, and tracked over time.",
        fill=PAL.white,
        body_size=body_size,
    )

    d.card(
        475,
        875,
        310,
        card_h,
        "Repair Prompt",
        "Failed-call evidence and lifecycle stats drive the smallest contract or routing repair.",
        fill=PAL.red_light,
        stroke=PAL.red,
        title_color=PAL.red,
        body_size=body_size,
    )
    d.card(
        870,
        875,
        310,
        card_h,
        "Scale If Promising",
        "Move from 20/60 to 100/250/500 only when outcome, calls, safety, and cache policy pass.",
        fill=PAL.white,
        body_size=body_size,
    )

    d.arrow(390, 245, 475, 245)
    d.arrow(785, 245, 870, 245)
    d.arrow(1180, 245, 1265, 245)
    d.arrow(1420, 365, 1420, 520)
    d.arrow(1265, 622, 1180, 622)
    d.arrow(870, 622, 785, 622)
    d.arrow(475, 622, 390, 622)
    d.arrow(800, 625, 800, 875, PAL.red)
    d.arrow(800, 875, 800, 365, PAL.red)
    d.arrow(1025, 725, 1025, 875, PAL.sage)

    d.rect(80, 1140, 1495, 70, PAL.gray_light, stroke=PAL.line, radius=18)
    d.text(
        110,
        1159,
        "Diagnostic force-call can expose latent value or schema defects, but it is never counted as promotion evidence. Final comparisons must walk back to natural routing and natural calls.",
        19,
        PAL.ink,
        max_width=1440,
    )
    d.finish()


def render_paper_diagram() -> None:
    d = Diagram(
        "sage_peer_review_methodology_figure",
        "4. SAGE Methodology For Matched ToolSandbox Validation",
        1900,
        1220,
        paper=True,
    )
    d.card(
        70,
        150,
        330,
        190,
        "Sealed Manifest",
        "Frozen scenario order\nNo label peeking\nDiversity/gap profile recorded",
        fill=PAL.white,
        stroke=PAL.ink,
        title_color=PAL.ink,
    )
    d.card(
        520,
        115,
        330,
        160,
        "Baseline Arm",
        "Base tools\nTask-level cached controls allowed\nFresh/cached counts hashed",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        520,
        330,
        330,
        160,
        "SAGE Arm",
        "Fresh candidate execution\nGenerated helpers or frozen registry\nCandidate task cache off",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        970,
        115,
        330,
        160,
        "ToolSandbox",
        "Stateful environment\nUser simulator\nOriginal tools\nExecution traces",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        970,
        330,
        330,
        160,
        "SAGE Runtime",
        "Gap observer -> generator -> validator -> registry -> router -> reflection",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        1420,
        150,
        330,
        190,
        "Paired Analysis",
        "Outcome primary\nCanonical secondary\nBootstrap CI\nPermutation test",
        fill=PAL.white,
        stroke=PAL.ink,
    )

    d.card(
        270,
        660,
        340,
        190,
        "Safety Gate",
        "Zero runtime exceptions\nZero helper side-effect incidents\nNo force-call promotion evidence",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        780,
        660,
        340,
        190,
        "Leakage Controls",
        "No hidden labels\nNo expected-answer strings\nNo scenario-specific hard-coding\nNo prior SAGE trace reuse",
        fill=PAL.white,
        stroke=PAL.ink,
    )
    d.card(
        1290,
        660,
        340,
        190,
        "Reproducibility",
        "Registry hashes\nCache manifests\nRun ledger\nDashboard/report exports",
        fill=PAL.white,
        stroke=PAL.ink,
    )

    d.arrow(400, 245, 520, 195, PAL.ink)
    d.arrow(400, 245, 520, 410, PAL.ink)
    d.arrow(850, 195, 970, 195, PAL.ink)
    d.arrow(850, 410, 970, 410, PAL.ink)
    d.arrow(1300, 195, 1420, 245, PAL.ink)
    d.arrow(1300, 410, 1420, 245, PAL.ink)
    d.arrow(1135, 330, 1135, 275, PAL.ink)

    d.line(160, 590, 1740, 590, PAL.ink, 3)
    d.text(80, 930, "Figure caption draft:", 24, PAL.ink, bold=True)
    d.text(
        80,
        970,
        "SAGE is evaluated as a matched ToolSandbox treatment. Baseline and SAGE arms share a sealed manifest and model policy. Controls may use transparent task-level cache; SAGE/candidate evidence is fresh. Tool generation, validation, routing, and reflection are bounded by safety and leakage controls before paired outcome and canonical analyses.",
        21,
        PAL.ink,
        max_width=1680,
    )
    d.finish()


def main() -> None:
    render_overview()
    render_sage_zoom()
    render_tool_loop()
    render_paper_diagram()


if __name__ == "__main__":
    main()
