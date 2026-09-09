#!/usr/bin/env python3
"""Render Chapter 4 evidence tables as dissertation-ready PNG images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

MINIMUM_SCHEMA_VERSION = 2

SYSTEM_FONT_CANDIDATES = {
    False: (
        Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
    ),
    True: (
        Path("/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf"),
    ),
}

COLORS = {
    "page": "#ffffff",
    "rule": "#111111",
    "thin_rule": "#b8b8b8",
    "text": "#111111",
    "muted": "#444444",
}


def _font(
    size: int,
    *,
    bold: bool = False,
    preferred: Path | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if preferred is not None:
        if not preferred.is_file():
            raise FileNotFoundError(f"Font file does not exist: {preferred}")
        return ImageFont.truetype(str(preferred), size)
    for path in SYSTEM_FONT_CANDIDATES[bold]:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    try:
        return ImageFont.truetype(
            "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf",
            size,
        )
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def configure_fonts(
    regular_font: Path | None = None,
    bold_font: Path | None = None,
) -> None:
    global FONTS, COMPACT_FONTS
    FONTS = {
        "title": _font(34, bold=True, preferred=bold_font),
        "subtitle": _font(22, preferred=regular_font),
        "caption": _font(20, preferred=regular_font),
        "header": _font(31, bold=True, preferred=bold_font),
        "cell": _font(32, preferred=regular_font),
        "cell_bold": _font(32, bold=True, preferred=bold_font),
        "small": _font(22, preferred=regular_font),
    }
    COMPACT_FONTS = {
        "header": _font(25, bold=True, preferred=bold_font),
        "cell": _font(26, preferred=regular_font),
        "cell_bold": _font(26, bold=True, preferred=bold_font),
    }


FONTS: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]
COMPACT_FONTS: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]
configure_fonts()


def text_width(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), value, font=face)
    return box[2] - box[0]


def line_height(draw: ImageDraw.ImageDraw, face: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), "Ag", font=face)
    return box[3] - box[1] + 7


def wrap_text(
    draw: ImageDraw.ImageDraw, value: object, face: ImageFont.ImageFont, max_width: int
) -> list[str]:
    text = str(value)
    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_width(draw, candidate, face) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            if text_width(draw, word, face) <= max_width:
                current = word
                continue
            chunk = ""
            for char in word:
                candidate = chunk + char
                if text_width(draw, candidate, face) <= max_width:
                    chunk = candidate
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = char
            current = chunk
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    value: object,
    xy: tuple[int, int],
    face: ImageFont.ImageFont,
    max_width: int,
    fill: str,
    spacing: int = 3,
) -> int:
    x, y = xy
    lines = wrap_text(draw, value, face, max_width)
    lh = line_height(draw, face)
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += lh + spacing
    return y


def color_for_value(value: object) -> str:
    return COLORS["text"]


def render_table(
    path: Path,
    title: str,
    subtitle: str,
    columns: list[str],
    rows: list[list[object]],
    widths: list[float],
    caption: str | None = None,
    compact: bool = False,
) -> None:
    del title, subtitle, caption
    width = 1500
    margin = 36 if compact else 42
    table_width = width - 2 * margin
    col_widths = [int(table_width * w / sum(widths)) for w in widths]
    col_widths[-1] += table_width - sum(col_widths)
    faces = COMPACT_FONTS if compact else FONTS
    header_face = faces["header"]
    cell_face = faces["cell"]
    cell_bold_face = faces["cell_bold"]
    cell_x_pad = 7 if compact else 8
    cell_y_pad = 10 if compact else 18
    header_y_pad = 8 if compact else 12
    header_h = 54 if compact else 82
    min_row_h = 44 if compact else 76
    row_extra = 18 if compact else 34
    line_spacing = 1 if compact else 4

    probe = Image.new("RGB", (width, 200), COLORS["page"])
    draw = ImageDraw.Draw(probe)
    row_heights: list[int] = []
    for row in rows:
        heights = []
        for value, col_width in zip(row, col_widths, strict=True):
            face = cell_bold_face if str(value).startswith("+") else cell_face
            lines = wrap_text(draw, value, face, col_width - 24)
            heights.append(
                len(lines) * (line_height(draw, face) + line_spacing) + row_extra
            )
        row_heights.append(max(min_row_h, max(heights)))
    height = header_h + sum(row_heights) + 56

    image = Image.new("RGB", (width, height), COLORS["page"])
    draw = ImageDraw.Draw(image)

    y = 24

    x = margin
    draw.line((margin, y, width - margin, y), fill=COLORS["rule"], width=4)
    y += 11
    for label, col_width in zip(columns, col_widths, strict=True):
        draw_wrapped(
            draw,
            label,
            (x + cell_x_pad, y + header_y_pad),
            header_face,
            col_width - 16,
            COLORS["text"],
            spacing=line_spacing,
        )
        x += col_width
    y += header_h - 11
    draw.line((margin, y, width - margin, y), fill=COLORS["rule"], width=2)

    for idx, (row, row_h) in enumerate(zip(rows, row_heights, strict=True)):
        x = margin
        for value, col_width in zip(row, col_widths, strict=True):
            value_text = str(value)
            face = (
                cell_bold_face
                if value_text.startswith("+") or value_text.startswith("[+")
                else cell_face
            )
            draw_wrapped(
                draw,
                value_text,
                (x + cell_x_pad, y + cell_y_pad),
                face,
                col_width - 16,
                color_for_value(value_text),
                spacing=line_spacing,
            )
            x += col_width
        if idx < len(rows) - 1:
            draw.line(
                (margin, y + row_h, width - margin, y + row_h),
                fill=COLORS["thin_rule"],
                width=1,
            )
        y += row_h
    draw.line((margin, y, width - margin, y), fill=COLORS["rule"], width=4)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def metric_value(metrics: Iterable[dict], label: str) -> str:
    for metric in metrics:
        if metric["label"] == label:
            return metric["value_label"]
    raise KeyError(label)


def _number(value: object, *, digits: int = 4) -> str:
    return "-" if value is None else f"{float(value):.{digits}f}"


def _percent(value: object, *, signed: bool = False) -> str:
    if value is None:
        return "-"
    number = float(value)
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.1f}%"


def _percent_interval(interval: dict[str, object]) -> str:
    low = interval.get("lower")
    high = interval.get("upper")
    if low is None or high is None:
        return "-"
    return f"[{float(low):+.1f}%, {float(high):+.1f}%]"


def _threshold(value: object, *, signed: bool = False) -> str:
    prefix = "+" if signed else ""
    return f">= {prefix}{float(value):g}%"


def _claim_safeguards(campaign: dict) -> str:
    safeguards = campaign.get("claim_safeguards") or {}
    labels = []
    if safeguards.get("synthetic_bridge_completions_disabled"):
        labels.append("bridge off")
    if safeguards.get("scenario_name_birth_disabled") and safeguards.get(
        "scenario_name_routing_disabled"
    ):
        labels.append("metadata routing off")
    if safeguards.get("diagnostic_force_calls_disabled"):
        labels.append("diagnostic overrides off")
    summary = "; ".join(labels) or "see campaign evidence manifest"
    return summary[0].upper() + summary[1:]


FAILURE_TOOL_COPY = {
    "apply_single_device_state_action": (
        "Device setting action tool",
        "Usually called when the setting action was not needed or could not be applied, such as turning a service off when already off.",
        "Kept because it was useful overall; marked for better routing.",
    ),
    "plan_device_status_lookup": (
        "Device status lookup tool",
        "Occasional failed status checks for device services.",
        "Kept because successful uses strongly outweighed failures.",
    ),
    "extract_distance_result": (
        "Distance extraction tool",
        "Occasional failure while extracting distance from visible results.",
        "Kept and marked for route repair where needed.",
    ),
    "prepare_broad_location_search_args": (
        "Broad location search argument tool",
        "Occasional failed call for the available location-search context.",
        "Kept and marked for better routing.",
    ),
    "plan_contact_lookup_query": (
        "Contact lookup query tool",
        "A failed contact-search attempt was observed.",
        "Kept because it was useful across many other tasks.",
    ),
    "prepare_safe_action_or_abstain": (
        "Safe action or abstain tool",
        "A failed decision about whether to act or abstain was observed.",
        "Kept but marked for route repair due to mixed usefulness.",
    ),
}


def _failure_rows(summary: dict) -> list[list[object]]:
    rows: list[list[object]] = []
    order = {name: index for index, name in enumerate(FAILURE_TOOL_COPY)}
    failure_tools = sorted(
        summary.get("tools") or [],
        key=lambda item: (order.get(str(item["name"]), len(order)), str(item["name"])),
    )
    for item in failure_tools:
        name = str(item["name"])
        label, explanation, action = FAILURE_TOOL_COPY.get(
            name,
            (
                name.replace("_", " ").title(),
                "A generated-tool call failed during a matched task.",
                "Review routing and runtime evidence before the next release.",
            ),
        )
        rows.append(
            [
                label,
                f"{int(item['failed_scenarios']):,}",
                explanation,
                action,
            ]
        )
    total = int(summary["failed_scenarios"])
    rows.append(
        [
            "Total",
            f"{total:,}",
            (
                "Task scenarios with at least one failed generated-tool call, "
                f"not {total:,} separate failed tools."
            ),
            "No tool was retired solely because of these failures.",
        ]
    )
    return rows


def build_tables(data: dict) -> list[dict]:
    schema_version = int(data.get("schema_version") or 0)
    if schema_version < MINIMUM_SCHEMA_VERSION:
        raise ValueError(
            "Chapter 4 evidence data schema is too old for paper rendering: "
            f"expected >= {MINIMUM_SCHEMA_VERSION}, got {schema_version}. "
            "Regenerate it with write_evidence_dashboard()."
        )
    campaign = data["campaign"]
    performance = data["performance"]
    hypotheses = {item["id"]: item for item in data["hypotheses"]}
    statistics = data["statistics"]
    integrity = data["integrity"]["counts"]
    metrics = data["tool_metrics"]
    failure_summary = data["tool_failure_summary"]

    h1 = hypotheses["Hypothesis 1"]
    h2 = hypotheses["Hypothesis 2"]
    h3 = hypotheses["Hypothesis 3"]
    h1_threshold = _threshold(h1["threshold_percent"])
    h2_threshold = _threshold(h2["threshold_percent"], signed=True)
    h3_threshold = _threshold(h3["threshold_percent"], signed=True)
    benchmark_name = str(campaign["benchmark_label"]).split(maxsplit=1)[0]
    rounded_frozen_values = [
        round(float(run["frozen_sage_outcome"]), 3)
        for run in data["runs"]
        if run["frozen_sage_outcome"] is not None
    ]
    displayed_frozen_mean = (
        sum(rounded_frozen_values) / len(rounded_frozen_values)
        if rounded_frozen_values
        else None
    )

    return [
        {
            "filename": "table_4_1_evidence_campaign.png",
            "title": "Table 4.1 - Evidence Campaign Configuration",
            "subtitle": "Claim-grade Chapter 4 evidence run settings used for the final SAGE analysis.",
            "columns": ["Configuration item", "Final setting", "Purpose"],
            "widths": [0.24, 0.31, 0.45],
            "rows": [
                [
                    "Benchmark",
                    f"{benchmark_name}, {campaign['tasks_per_run']:,} tasks",
                    "Matched baseline and SAGE task environment.",
                ],
                [
                    "Model",
                    campaign["model"],
                    "Same model family for actor, user, and generation.",
                ],
                [
                    "Evidence set",
                    f"{campaign['completed_runs']} runs; {campaign['paired_observations']:,} paired observations",
                    "Replicated full-benchmark evidence.",
                ],
                [
                    "Baseline cache",
                    campaign["baseline_cache_policy"],
                    "Fixed matched baseline values.",
                ],
                [
                    "SAGE safeguards",
                    _claim_safeguards(campaign),
                    "Prevents shortcut completions and routing.",
                ],
                [
                    "Performance endpoint",
                    "Outcome / task completion",
                    "Sole performance criterion: requested final result achieved.",
                ],
                [
                    "Descriptive audit",
                    "Canonical/reference similarity",
                    "Route-compatibility audit only; not an acceptance or performance criterion.",
                ],
            ],
            "caption": f"Benchmark manifest hash: {campaign['benchmark_sha256']}.",
            "compact": True,
        },
        {
            "filename": "table_4_2_replication_results.png",
            "title": "Table 4.2 - Replication-Level Online-Build And Frozen-Registry Results",
            "subtitle": (
                f"Each row is a complete {campaign['tasks_per_run']:,}-task "
                "replication with paired online-build and frozen-registry evidence."
            ),
            "columns": [
                "Run",
                "Baseline",
                "Online SAGE",
                "Online lift",
                "Frozen SAGE",
                "Retained",
            ],
            "widths": [0.10, 0.17, 0.21, 0.17, 0.20, 0.15],
            "rows": [
                [
                    run["short_label"],
                    _number(run["baseline_outcome"], digits=3),
                    _number(run["online_sage_outcome"], digits=3),
                    _percent(run["online_outcome_lift_percent"], signed=True),
                    _number(run["frozen_sage_outcome"], digits=3),
                    _percent(run["frozen_gain_retention_percent"]),
                ]
                for run in data["runs"]
            ]
            + [
                [
                    "Mean",
                    _number(performance["baseline"]),
                    _number(performance["sage"]),
                    _percent(h2["estimate_percent"], signed=True),
                    _number(displayed_frozen_mean),
                    _percent(h1["estimate_percent"]),
                ]
            ],
            "caption": "Frozen-registry runs reused the registry from their paired online-build run with generation and repair disabled.",
            "compact": True,
        },
        {
            "filename": "table_4_3_h1_frozen_registry_retention.png",
            "title": "Table 4.3 - Hypothesis 1 Evidence",
            "subtitle": "Reusable generated tools preserve online-build gains after tool creation stops.",
            "columns": [
                "Claim component",
                "Observed evidence",
                "Decision rule",
                "Interpretation",
            ],
            "widths": [0.25, 0.25, 0.20, 0.30],
            "rows": [
                [
                    "Gain retention",
                    _percent(h1["estimate_percent"]),
                    h1_threshold,
                    (
                        f"{h1['decision_label']}: frozen-registry reuse retained "
                        f"at least {h1['threshold_percent']:g} percent of the "
                        "online-build gain."
                    ),
                ],
                [
                    "Confidence interval",
                    _percent_interval(h1["confidence_interval"]),
                    f"Lower bound above {h1['threshold_percent']:g}%",
                    "The uncertainty range remains above the required retention threshold.",
                ],
                [
                    "Replication design",
                    f"{h1['sample_size']:,} paired online/frozen runs",
                    "Complete pairs only",
                    "Each frozen run reused tools born in the matched online-build run.",
                ],
                [
                    "Generation during reuse",
                    "Disabled",
                    "No new tool creation",
                    "Frozen-registry performance reflects reuse rather than additional online learning.",
                ],
            ],
            "caption": "Hypothesis 1 is a persistence claim: SAGE-generated tools remain useful after the build phase.",
        },
        {
            "filename": "table_4_4_h2_overall_task_completion.png",
            "title": "Table 4.4 - Hypothesis 2 Evidence",
            "subtitle": "SAGE improves overall task-completion accuracy over a non-learning baseline on matched benchmark tasks.",
            "columns": [
                "Measure",
                "Baseline",
                "SAGE",
                "Observed lift",
                "Hypothesis threshold",
            ],
            "widths": [0.24, 0.17, 0.17, 0.20, 0.22],
            "rows": [
                [
                    "Outcome / task completion",
                    _number(h2["baseline_mean"]),
                    _number(h2["sage_mean"]),
                    _percent(h2["estimate_percent"], signed=True),
                    h2_threshold,
                ],
                [
                    "Absolute paired difference",
                    "",
                    "",
                    statistics["mean_delta_label"],
                    "Positive paired gain",
                ],
                [
                    "95% paired bootstrap CI",
                    "",
                    "",
                    statistics["ci_label"],
                    "CI above zero",
                ],
                [
                    "Permutation test",
                    "",
                    "",
                    statistics["p_label"],
                    f"p < {statistics['significance_alpha']:.2f}".replace("0.", "."),
                ],
                [
                    "Full-outcome successes B / S",
                    "",
                    "",
                    statistics["successes_label"],
                    "SAGE count exceeds baseline",
                ],
            ],
            "caption": "Outcome/task completion is the sole performance endpoint because it evaluates whether the requested final result was achieved; canonical/reference similarity is descriptive only.",
        },
        {
            "filename": "table_4_5_h3_generated_tool_attribution.png",
            "title": "Table 4.5 - Hypothesis 3 Evidence",
            "subtitle": "Generated-tool-called tasks isolate whether autonomous tools account for the observed accuracy gain.",
            "columns": [
                "Attribution measure",
                "Observed value",
                "Decision rule",
                "Why it supports the claim",
            ],
            "widths": [0.27, 0.20, 0.20, 0.33],
            "rows": [
                [
                    "Called-task subset",
                    f"{h3['sample_size']:,} observations",
                    "Generated tool selected by SAGE policy",
                    "Uses tasks where the declared production actor policy selected a generated tool; diagnostic overrides remain disabled.",
                ],
                [
                    "Baseline outcome on subset",
                    _number(h3["baseline_mean"]),
                    "Matched baseline rows",
                    "Defines how the same tasks performed without generated tools.",
                ],
                [
                    "SAGE outcome on subset",
                    _number(h3["sage_mean"]),
                    "Matched SAGE rows",
                    "Shows substantially higher completion after generated-tool use.",
                ],
                [
                    "Relative outcome lift",
                    _percent(h3["estimate_percent"], signed=True),
                    h3_threshold,
                    "The called-tool subset exceeds the attribution threshold by a wide margin.",
                ],
                [
                    "95% paired bootstrap CI",
                    _percent_interval(h3["confidence_interval"]),
                    f"Lower bound above +{h3['threshold_percent']:g}%",
                    "The effect remains large after paired uncertainty estimation.",
                ],
            ],
            "caption": "Hypothesis 3 describes the generated-tool pathway under the production actor policy; it is not evidence of natural base-model tool selection.",
        },
        {
            "filename": "table_4_6_generated_tool_lifecycle.png",
            "title": "Table 4.6 - Generated-Tool Lifecycle And Contribution Evidence",
            "subtitle": "Lifecycle metrics show that tools were created, retained, selected, and reused across later tasks.",
            "columns": ["Lifecycle metric", "Observed value", "What it means"],
            "widths": [0.32, 0.20, 0.48],
            "rows": [
                [
                    "Accepted tools",
                    metric_value(metrics, "Accepted tools"),
                    "Generated tools that passed validation and entered the registry.",
                ],
                [
                    "Reused on later tasks",
                    metric_value(metrics, "Reused on later tasks"),
                    "Accepted tools with at least one later registry reuse event.",
                ],
                [
                    "Tool reuse rate",
                    metric_value(metrics, "Tool reuse rate"),
                    "Share of accepted tools that were reused after birth.",
                ],
                [
                    "Policy-directed tool calls",
                    metric_value(metrics, "Policy-directed tool calls"),
                    "Scenarios where the production SAGE actor policy selected and called a generated tool, without diagnostic overrides.",
                ],
                [
                    "Attributed gains",
                    metric_value(metrics, "Attributed gains"),
                    "Generated-tool-called scenarios with positive matched outcome difference.",
                ],
                [
                    "Preserved outcomes",
                    metric_value(metrics, "Preserved outcomes"),
                    "Generated-tool-called scenarios with no matched outcome loss.",
                ],
                [
                    "Attributed regressions",
                    metric_value(metrics, "Attributed regressions"),
                    "Generated-tool-called scenarios with negative matched outcome difference.",
                ],
                [
                    "Tool-call failure scenarios",
                    metric_value(metrics, "Tool-call failure scenarios"),
                    "Scenarios containing at least one failed generated-tool call.",
                ],
            ],
            "caption": "These metrics describe the autonomous tool lifecycle rather than only the final task score.",
        },
        {
            "filename": "table_4_8_hypothesis_decision_summary.png",
            "title": "Table 4.8 - Summary of Hypothesis Decisions",
            "subtitle": "Summary of Chapter 4 hypothesis decisions and observed results.",
            "columns": [
                "Hypothesis",
                "Claim tested",
                "Threshold",
                "Observed result",
                "Decision",
            ],
            "widths": [0.12, 0.34, 0.21, 0.23, 0.10],
            "rows": [
                [
                    "H1",
                    "Generated tools remain useful when reused from a frozen registry.",
                    f"{h1_threshold} of online-build gain retained",
                    (
                        f"{_percent(h1['estimate_percent'])} retained; 95% CI "
                        f"{_percent_interval(h1['confidence_interval']).replace('+', '')}"
                    ),
                    h1["decision_label"],
                ],
                [
                    "H2",
                    "SAGE improves task-completion accuracy over the baseline.",
                    f"{_threshold(h2['threshold_percent'])} outcome lift",
                    (
                        f"{_percent(h2['estimate_percent'])} lift; baseline "
                        f"{_number(h2['baseline_mean'])}, SAGE {_number(h2['sage_mean'])}"
                    ),
                    h2["decision_label"],
                ],
                [
                    "H3",
                    "The policy-directed generated-tool pathway is associated with the strongest accuracy gains.",
                    (
                        f"{_threshold(h3['threshold_percent'])} called-tool lift; "
                        "no shortcut violations"
                    ),
                    (
                        f"{_percent(h3['estimate_percent'])} called-tool lift; "
                        f"{integrity['shortcut_violations']:,} shortcut violations"
                    ),
                    h3["decision_label"],
                ],
            ],
            "caption": "The decision table summarizes the threshold, observed result, and support decision for each hypothesis.",
            "compact": True,
        },
        {
            "filename": "table_4_7_validity_checks.png",
            "title": "Table 4.7 - Evidence Validity Checks",
            "subtitle": "Claim safeguards used to rule out shortcut explanations for the observed gain.",
            "columns": ["Validity check", "Observed count", "Interpretation"],
            "widths": [0.38, 0.18, 0.44],
            "rows": [
                [
                    "Same SAGE settings across runs",
                    f"{integrity['configuration_mismatches']:,} mismatches",
                    "All completed claim runs used the same claim-grade SAGE configuration.",
                ],
                [
                    "Benchmark-metadata shortcut checks",
                    f"{integrity['metadata_shortcut_violations']:,} violations",
                    "No scenario-name birth or scenario-name routing was used for claim evidence.",
                ],
                [
                    "Code-based answer shortcut checks",
                    f"{integrity['bridge_shortcut_violations']:,} violations",
                    "Synthetic bridge completions were disabled and did not solve tasks for SAGE.",
                ],
                [
                    "Diagnostic tool-call override checks",
                    f"{integrity['forced_call_violations']:,} violations",
                    "No ad hoc diagnostic override was used; named choices from the declared production actor policy are part of the intervention.",
                ],
                [
                    "Tool side-effect audit flags",
                    f"{integrity['side_effect_flags']:,} flags",
                    "Audit flags remained visible for review; they were not hidden from the validity record.",
                ],
            ],
            "caption": "This table supports the integrity claim that the Chapter 4 effect is not produced by hidden answers or synthetic task completions.",
        },
        {
            "filename": "table_4_9_generated_tool_failure_summary.png",
            "title": "Table 4.9 - Generated-Tool Failure Summary",
            "subtitle": (
                "Tool-call failures observed across the "
                f"{failure_summary['completed_online_runs']:,} complete Chapter 4 runs."
            ),
            "columns": [
                "Tool failure area",
                "Failed scenarios",
                "What happened",
                "Lifecycle action",
            ],
            "widths": [0.27, 0.15, 0.33, 0.25],
            "rows": _failure_rows(failure_summary),
            "caption": "Failure counts describe generated-tool call failures, not distinct failed tools.",
            "compact": True,
        },
    ]


def write_gallery(image_paths: list[Path], output_dir: Path) -> None:
    html = [
        "<!doctype html>",
        '<meta charset="utf-8">',
        "<title>Chapter 4 Evidence Table Images</title>",
        "<style>",
        "body{margin:0;background:#fff;color:#111;font:16px Arial,sans-serif;padding:32px;}",
        "h1{margin:0 0 24px;font-size:28px;}",
        ".grid{display:grid;gap:28px;}",
        "figure{margin:0;padding:0;background:#fff;border:1px solid #ddd;overflow:hidden;}",
        "img{display:block;width:100%;height:auto;}",
        "figcaption{padding:12px 16px;color:#444;}",
        "</style>",
        "<h1>Chapter 4 Evidence Table Images</h1>",
        '<div class="grid">',
    ]
    for path in image_paths:
        html.append(
            f'<figure><img src="{path.name}" alt="{path.stem}"><figcaption>{path.name}</figcaption></figure>'
        )
    html.append("</div>")
    (output_dir / "index.html").write_text(
        "\n".join(html) + "\n",
        encoding="utf-8",
    )


def write_contact_sheet(image_paths: list[Path], output_dir: Path) -> None:
    thumbs = []
    for path in image_paths:
        img = Image.open(path)
        img.thumbnail((760, 420))
        thumb = Image.new("RGB", (800, 470), COLORS["page"])
        thumb.paste(img, ((800 - img.width) // 2, 20))
        d = ImageDraw.Draw(thumb)
        d.text((24, 435), path.name, font=FONTS["small"], fill=COLORS["muted"])
        thumbs.append(thumb)

    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 820, rows * 500), COLORS["page"])
    for idx, thumb in enumerate(thumbs):
        x = (idx % cols) * 820
        y = (idx // cols) * 500
        sheet.paste(thumb, (x, y))
    sheet.save(output_dir / "chapter4_evidence_tables_contact_sheet.png")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render dissertation-ready Chapter 4 evidence table images."
    )
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="Versioned chapter4_evidence_data.json input.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for table PNGs, gallery, and contact sheet.",
    )
    parser.add_argument(
        "--regular-font",
        type=Path,
        help="Optional regular TrueType/OpenType font; portable system fallback otherwise.",
    )
    parser.add_argument(
        "--bold-font",
        type=Path,
        help="Optional bold TrueType/OpenType font; portable system fallback otherwise.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    configure_fonts(args.regular_font, args.bold_font)
    data = json.loads(args.data.read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    for spec in build_tables(data):
        path = output_dir / spec.pop("filename")
        render_table(path=path, **spec)
        image_paths.append(path)
        print(path)
    write_gallery(image_paths, output_dir)
    write_contact_sheet(image_paths, output_dir)
    print(output_dir / "index.html")
    print(output_dir / "chapter4_evidence_tables_contact_sheet.png")


if __name__ == "__main__":
    main()
