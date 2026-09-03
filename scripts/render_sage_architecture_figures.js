#!/usr/bin/env node

/* Render the publication architecture figure set for SAGE. */

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "docs", "sage_protocol", "figures", "v061_architecture");
const VIS_OUT = "/Users/christopherclark/.codex/visualizations/2026/06/14/019ec623-9717-7811-ac2d-b27fb75d65c4";

const C = {
  background: "#F7F9FB",
  paper: "#FFFFFF",
  ink: "#17243A",
  muted: "#53657A",
  faint: "#7A8A9D",
  line: "#C9D4DF",
  lineDark: "#8191A5",
  navy: "#215985",
  navySoft: "#E8F1F8",
  teal: "#008C7A",
  tealSoft: "#E2F4F0",
  violet: "#6948B8",
  violetSoft: "#F0ECFA",
  amber: "#B96A00",
  amberSoft: "#FFF0D2",
  red: "#C43D50",
  redSoft: "#FBE8EC",
  gray: "#607185",
  graySoft: "#EDF1F5",
  green: "#2B7D59",
  greenSoft: "#E6F3EB",
};

// Lucide v0.468.0 icon paths, used under the ISC license.
const ICONS = {
  "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
  eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
  "scan-search": '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3"/><path d="m16 16-1.9-1.9"/>',
  "git-branch": '<line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
  "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  route: '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
  "list-checks": '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  "refresh-cw": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  "code-xml": '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
  workflow: '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/>',
  "clipboard-check": '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  network: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
  blocks: '<rect width="7" height="7" x="14" y="3" rx="1"/><path d="M10 21V8a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5a1 1 0 0 0-1-1H3"/>',
  "brain-circuit": '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M9 13a4.5 4.5 0 0 0 3-4"/><path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/><path d="M3.477 10.896a4 4 0 0 1 .585-.396"/><path d="M6 18a4 4 0 0 1-1.967-.516"/><path d="M12 13h4"/><path d="M12 18h6a2 2 0 0 1 2 2v1"/><path d="M12 8h8"/><path d="M16 8V5a2 2 0 0 1 2-2"/><circle cx="16" cy="13" r=".5"/><circle cx="18" cy="3" r=".5"/><circle cx="20" cy="21" r=".5"/><circle cx="20" cy="8" r=".5"/>',
  "package-check": '<path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/>',
  "archive-x": '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="m9.5 17 5-5"/><path d="m9.5 12 5 5"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  "settings-2": '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
  "memory-stick": '<path d="M6 19v-3"/><path d="M10 19v-3"/><path d="M14 19v-3"/><path d="M18 19v-3"/><path d="M8 11V9"/><path d="M16 11V9"/><path d="M12 11V9"/><path d="M2 15h20"/><path d="M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1.1a2 2 0 0 0 0 3.837V17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5.1a2 2 0 0 0 0-3.837Z"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  "arrow-right-left": '<path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/>',
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function textWidth(value, fontSize, weight = 400) {
  let units = 0;
  for (const ch of String(value)) {
    if (ch === " ") units += 0.31;
    else if ("ilI.,:;!'|".includes(ch)) units += 0.29;
    else if ("mwMW@%&".includes(ch)) units += 0.79;
    else if (/[A-Z0-9]/.test(ch)) units += 0.61;
    else if ("-_+/()[]".includes(ch)) units += 0.43;
    else units += 0.52;
  }
  return units * fontSize * (weight >= 600 ? 1.035 : 1);
}

function wrap(value, maxWidth, fontSize, weight = 400) {
  const lines = [];
  for (const paragraph of String(value).split("\n")) {
    if (!paragraph.trim()) {
      lines.push("");
      continue;
    }
    let line = "";
    for (const word of paragraph.trim().split(/\s+/)) {
      const candidate = line ? `${line} ${word}` : word;
      if (!line || textWidth(candidate, fontSize, weight) <= maxWidth) line = candidate;
      else {
        lines.push(line);
        line = word;
      }
    }
    if (line) lines.push(line);
  }
  return lines;
}

function points(values) {
  return values.map(([x, y]) => `${x},${y}`).join(" ");
}

function rect(x, y, w, h, fill, stroke = "none", rx = 0, strokeWidth = 1.5, extra = "") {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}" ${extra}/>`;
}

class Diagram {
  constructor(width, height, title, description) {
    this.width = width;
    this.height = height;
    this.titleText = title;
    this.description = description;
    this.back = [rect(0, 0, width, height, C.background)];
    this.paths = [];
    this.front = [];
    this.checks = [];
    this.nodeIds = new Set();
  }

  textLines(x, y, lines, className, lineHeight, anchor = "start", style = "") {
    const spans = lines.map((line, index) => `<tspan x="${x}" dy="${index ? lineHeight : 0}">${esc(line)}</tspan>`).join("");
    return `<text class="${className}" x="${x}" y="${y}" text-anchor="${anchor}"${style ? ` style="${style}"` : ""}>${spans}</text>`;
  }

  header(title, legend) {
    this.front.push(`<text class="figure-title" x="58" y="76">${esc(title)}</text>`);
    let x = this.width - 58;
    const items = [];
    for (let index = legend.length - 1; index >= 0; index -= 1) {
      const item = legend[index];
      const width = textWidth(item.label, 17, 600) + 56;
      x -= width;
      let mark;
      if (item.kind === "shape") {
        mark = this.shapeMarkup(item.shape || "hex", x + 16, 122, 24, 20, item.color, item.soft || C.paper, 1.5);
      } else {
        mark = `<line x1="${x + 2}" y1="122" x2="${x + 28}" y2="122" stroke="${item.color}" stroke-width="3" ${item.dashed ? 'stroke-dasharray="7 6"' : ""}/>`;
      }
      items.push(`${mark}<text class="legend" x="${x + 36}" y="128">${esc(item.label)}</text>`);
      x -= 16;
    }
    this.front.push(items.reverse().join(""));
    this.front.push(`<line x1="58" y1="151" x2="${this.width - 58}" y2="151" stroke="${C.line}" stroke-width="2"/>`);
  }

  boundary(x, y, w, h, label, accent, soft, options = {}) {
    const dash = options.dashed ? 'stroke-dasharray="10 8"' : "";
    this.back.push(rect(x, y, w, h, soft, accent, 12, options.strokeWidth || 1.6, `${dash} fill-opacity="${options.opacity || 0.38}"`));
    this.back.push(`<line x1="${x + 18}" y1="${y + 55}" x2="${x + w - 18}" y2="${y + 55}" stroke="${accent}" stroke-width="1.2" opacity="0.45"/>`);
    this.front.push(`<text class="boundary-label" x="${x + 21}" y="${y + 37}" fill="${accent}">${esc(label)}</text>`);
  }

  icon(name, cx, cy, size, color = C.ink, strokeWidth = 1.9) {
    const body = ICONS[name];
    if (!body) throw new Error(`unknown icon: ${name}`);
    const scale = size / 24;
    this.front.push(`<g transform="translate(${cx - size / 2} ${cy - size / 2}) scale(${scale})" fill="none" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round">${body}</g>`);
  }

  shapeMarkup(shape, cx, cy, w, h, accent, soft, strokeWidth = 2) {
    const x = cx - w / 2;
    const y = cy - h / 2;
    if (shape === "circle") return `<circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) / 2}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "hex") return `<polygon points="${points([[x + w * 0.18, y], [x + w * 0.82, y], [x + w, cy], [x + w * 0.82, y + h], [x + w * 0.18, y + h], [x, cy]])}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "octagon") return `<polygon points="${points([[x + w * 0.2, y], [x + w * 0.8, y], [x + w, y + h * 0.2], [x + w, y + h * 0.8], [x + w * 0.8, y + h], [x + w * 0.2, y + h], [x, y + h * 0.8], [x, y + h * 0.2]])}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "diamond") return `<polygon points="${points([[cx, y], [x + w, cy], [cx, y + h], [x, cy]])}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "document") {
      const fold = Math.min(22, w * 0.25);
      return `<path d="M${x},${y} H${x + w - fold} L${x + w},${y + fold} V${y + h} H${x} Z M${x + w - fold},${y} V${y + fold} H${x + w}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
    }
    if (shape === "database") {
      const ry = Math.min(15, h * 0.18);
      return `<path d="M${x},${y + ry} C${x},${y - 2} ${x + w},${y - 2} ${x + w},${y + ry} V${y + h - ry} C${x + w},${y + h + 2} ${x},${y + h + 2} ${x},${y + h - ry} Z" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/><ellipse cx="${cx}" cy="${y + ry}" rx="${w / 2}" ry="${ry}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/><path d="M${x},${cy} C${x},${cy + ry} ${x + w},${cy + ry} ${x + w},${cy}" fill="none" stroke="${accent}" stroke-width="${strokeWidth * 0.75}"/>`;
    }
    if (shape === "stack") return `${rect(x + 12, y - 10, w, h, soft, accent, 7, strokeWidth)}${rect(x + 6, y - 5, w, h, soft, accent, 7, strokeWidth)}${rect(x, y, w, h, soft, accent, 7, strokeWidth)}`;
    if (shape === "shield") return `<path d="M${cx},${y} C${cx + w * 0.17},${y + h * 0.12} ${x + w * 0.82},${y + h * 0.16} ${x + w},${y + h * 0.12} V${y + h * 0.48} C${x + w},${y + h * 0.76} ${cx + w * 0.18},${y + h * 0.92} ${cx},${y + h} C${cx - w * 0.18},${y + h * 0.92} ${x},${y + h * 0.76} ${x},${y + h * 0.48} V${y + h * 0.12} C${x + w * 0.18},${y + h * 0.16} ${cx - w * 0.17},${y + h * 0.12} ${cx},${y} Z" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "funnel") return `<polygon points="${points([[x, y], [x + w, y], [cx + w * 0.18, cy], [cx + w * 0.1, y + h], [cx - w * 0.1, y + h], [cx - w * 0.18, cy]])}" fill="${soft}" stroke="${accent}" stroke-width="${strokeWidth}"/>`;
    if (shape === "chip") {
      const pins = [0.25, 0.5, 0.75].map((p) => `<line x1="${x - 9}" y1="${y + h * p}" x2="${x}" y2="${y + h * p}"/><line x1="${x + w}" y1="${y + h * p}" x2="${x + w + 9}" y2="${y + h * p}"/><line x1="${x + w * p}" y1="${y - 9}" x2="${x + w * p}" y2="${y}"/><line x1="${x + w * p}" y1="${y + h}" x2="${x + w * p}" y2="${y + h + 9}"/>`).join("");
      return `<g fill="none" stroke="${accent}" stroke-width="${strokeWidth}">${rect(x, y, w, h, soft, accent, 9, strokeWidth)}${pins}</g>`;
    }
    if (shape === "component") return `${rect(x, y, w, h, soft, accent, 7, strokeWidth)}${rect(x + 10, y + h * 0.24, w * 0.24, h * 0.18, C.paper, accent, 3, strokeWidth * 0.8)}${rect(x + 10, y + h * 0.58, w * 0.24, h * 0.18, C.paper, accent, 3, strokeWidth * 0.8)}`;
    return rect(x, y, w, h, soft, accent, 8, strokeWidth);
  }

  node(options) {
    const {
      id, cx, cy, shape = "circle", icon, title, subtitle = "", accent = C.navy,
      soft = C.navySoft, w = 78, h = 78, iconSize = 34, labelWidth = 190,
      titleSize = 23, subtitleSize = 17, titleGap = 30, eyebrow = "",
    } = options;
    if (id) {
      if (this.nodeIds.has(id)) throw new Error(`duplicate node id: ${id}`);
      this.nodeIds.add(id);
    }
    this.back.push(this.shapeMarkup(shape, cx, cy, w, h, accent, soft));
    if (icon) this.icon(icon, cx, cy, iconSize, accent);
    if (eyebrow) this.front.push(`<text class="eyebrow" x="${cx}" y="${cy - h / 2 - 14}" text-anchor="middle" fill="${accent}">${esc(eyebrow)}</text>`);
    const titleLines = wrap(title, labelWidth, titleSize, 700);
    const titleY = cy + h / 2 + titleGap;
    this.front.push(this.textLines(cx, titleY, titleLines, "node-title", titleSize + 4, "middle", `font-size:${titleSize}px`));
    const subtitleLines = subtitle ? wrap(subtitle, labelWidth, subtitleSize, 400) : [];
    const subtitleY = titleY + titleLines.length * (titleSize + 4) + (subtitleLines.length ? 10 : 0);
    if (subtitleLines.length) this.front.push(this.textLines(cx, subtitleY, subtitleLines, "node-subtitle", subtitleSize + 5, "middle", `font-size:${subtitleSize}px`));
    const textBottom = subtitleLines.length
      ? subtitleY + (subtitleLines.length - 1) * (subtitleSize + 5) + subtitleSize * 0.4
      : titleY + (titleLines.length - 1) * (titleSize + 4) + titleSize * 0.4;
    const checkY = cy - h / 2;
    this.checks.push({ id: id || title, x: cx - labelWidth / 2, y: checkY, w: labelWidth, h: textBottom - checkY + 24, textBottom });
  }

  connector(d, color, options = {}) {
    const dash = options.dashed ? 'stroke-dasharray="10 8"' : "";
    const marker = options.noArrow ? "" : `marker-end="url(#arrow-${options.marker || "gray"})"`;
    this.paths.push(`<path d="${d}" fill="none" stroke="${color}" stroke-width="${options.width || 3}" stroke-linecap="round" stroke-linejoin="round" ${dash} ${marker}/>`);
    if (options.label) {
      const width = textWidth(options.label, 16, 600) + 22;
      const x = options.labelX;
      const y = options.labelY;
      this.back.push(rect(x - width / 2, y - 17, width, 26, C.background, "none", 4));
      this.front.push(`<text class="edge-label" x="${x}" y="${y + 2}" text-anchor="middle" fill="${color}">${esc(options.label)}</text>`);
    }
  }

  annotation(x, y, title, lines, accent = C.gray, options = {}) {
    const width = options.width || 250;
    this.front.push(`<text class="annotation-title" x="${x}" y="${y}" fill="${accent}">${esc(title)}</text>`);
    const wrapped = [];
    for (const line of lines) wrapped.push(...wrap(line, width, options.size || 16, 400));
    this.front.push(this.textLines(x, y + 27, wrapped, "annotation", (options.size || 16) + 5));
  }

  finalize() {
    const css = `
      text { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; letter-spacing: 0; fill: ${C.ink}; }
      .figure-title { font-size: 48px; font-weight: 700; }
      .legend { font-size: 17px; font-weight: 600; fill: ${C.muted}; }
      .boundary-label { font-size: 21px; font-weight: 700; letter-spacing: 0.6px; }
      .node-title { font-size: 23px; font-weight: 700; }
      .node-subtitle { font-size: 17px; font-weight: 400; fill: ${C.muted}; }
      .eyebrow { font-size: 15px; font-weight: 700; letter-spacing: 0.5px; }
      .edge-label { font-size: 16px; font-weight: 700; }
      .annotation-title { font-size: 18px; font-weight: 700; }
      .annotation { font-size: 16px; font-weight: 400; fill: ${C.muted}; }
      .router-stage { font-size: 17px; font-weight: 700; }
      .router-detail { font-size: 15px; font-weight: 400; fill: ${C.muted}; }
    `;
    const defs = `
      <defs>
        <filter id="shadow" x="-15%" y="-15%" width="130%" height="145%"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#24364F" flood-opacity="0.10"/></filter>
        <marker id="arrow-gray" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.lineDark}"/></marker>
        <marker id="arrow-navy" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.navy}"/></marker>
        <marker id="arrow-teal" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.teal}"/></marker>
        <marker id="arrow-violet" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.violet}"/></marker>
        <marker id="arrow-amber" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.amber}"/></marker>
        <marker id="arrow-red" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 Z" fill="${C.red}"/></marker>
      </defs>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${this.width}" height="${this.height}" viewBox="0 0 ${this.width} ${this.height}" role="img" aria-labelledby="svg-title svg-desc"><title id="svg-title">${esc(this.titleText)}</title><desc id="svg-desc">${esc(this.description)}</desc><style>${css}</style>${defs}${this.back.join("")}${this.paths.join("")}${this.front.join("")}</svg>`;
  }
}

function overviewFigure() {
  const f = new Diagram(
    1800,
    1350,
    "SAGE system architecture",
    "A system architecture view showing benchmark setup, the SAGE generated-tool layer, actor runtime, persistent registries, and the evidence-driven lifecycle feedback loop.",
  );
  f.header("SAGE System Architecture", [
    { kind: "shape", shape: "hex", label: "controller", color: C.teal, soft: C.tealSoft },
    { kind: "shape", shape: "document", label: "artifact", color: C.violet, soft: C.violetSoft },
    { kind: "shape", shape: "database", label: "persistent state", color: C.navy, soft: C.navySoft },
    { kind: "line", label: "current-task flow", color: C.lineDark },
    { kind: "line", label: "feedback / reuse", color: C.red, dashed: true },
  ]);

  f.boundary(34, 180, 280, 1115, "BENCHMARK SETUP", C.navy, C.navySoft, { dashed: true, opacity: 0.28 });
  f.boundary(350, 180, 1090, 1115, "SAGE GENERATED-TOOL LAYER", C.teal, C.tealSoft, { opacity: 0.25 });
  f.boundary(1475, 180, 290, 1115, "ACTOR + TASK RUNTIME", C.gray, C.graySoft, { dashed: true, opacity: 0.30 });

  f.connector("M218 330 H403", C.navy, { marker: "navy" });
  f.connector("M477 330 H613", C.teal, { marker: "teal" });
  f.connector("M687 330 H823", C.teal, { marker: "teal" });
  f.connector("M897 330 H1038", C.violet, { marker: "violet" });
  f.connector("M1122 330 H1275", C.amber, { marker: "amber" });
  f.connector("M1364 330 H1435 V535 H650 V661", C.teal, { marker: "teal", label: "accepted", labelX: 1185, labelY: 524 });
  f.connector("M693 700 H888", C.violet, { marker: "violet" });
  f.connector("M972 700 H1168", C.violet, { marker: "violet" });
  f.connector("M1252 700 H1455 V330 H1578", C.teal, { marker: "teal", label: "routed tools", labelX: 1370, labelY: 684 });
  f.connector("M440 371 H540 V565 H930 V658", C.navy, { marker: "navy", label: "task context", labelX: 720, labelY: 554 });
  f.connector("M216 700 H330 V605 H1210 V658", C.navy, { marker: "navy", label: "native tools", labelX: 470, labelY: 594 });
  f.connector("M1662 330 H1732 V700 H1662", C.lineDark, { marker: "gray" });
  f.connector("M1662 700 H1732 V1080 H1662", C.lineDark, { marker: "gray" });
  f.connector("M1578 1080 H1302", C.red, { marker: "red", label: "trajectory + score", labelX: 1370, labelY: 1064 });
  f.connector("M1218 1080 H1062", C.red, { marker: "red" });
  f.connector("M978 1080 H832", C.red, { marker: "red" });
  f.connector("M748 1080 H592", C.red, { marker: "red" });
  f.connector("M550 1038 V940 H410 V680 H607", C.red, { marker: "red", dashed: true, label: "lifecycle update", labelX: 475, labelY: 928 });
  f.connector("M550 1038 V980 H380 V620 H930 V658", C.violet, { marker: "violet", dashed: true, label: "future visibility", labelX: 470, labelY: 850 });
  f.connector("M1620 1121 V1130 H1490 V1260 H50 V330 H132", C.teal, { marker: "teal", dashed: true, label: "next ordered task", labelX: 430, labelY: 1248 });

  f.node({ id: "scenario", cx: 175, cy: 330, shape: "document", icon: "file-text", title: "Executable task scenario", subtitle: "Seeded state, user script, native visibility, and grading", accent: C.navy, soft: C.navySoft, w: 86, h: 86, labelWidth: 235, titleSize: 22 });
  f.node({ id: "native-tools", cx: 175, cy: 700, shape: "component", icon: "blocks", title: "Native tool inventory", subtitle: "Task allow list and scrambling", accent: C.navy, soft: C.navySoft, w: 88, h: 76, labelWidth: 230 });

  f.node({ id: "visible-context", cx: 440, cy: 330, shape: "circle", icon: "eye", title: "Visible task context", subtitle: "Request + native tool names", accent: C.navy, soft: C.navySoft, w: 74, h: 74, labelWidth: 185, titleSize: 21 });
  f.node({ id: "gap-analysis", cx: 650, cy: 330, shape: "circle", icon: "scan-search", title: "Inadequacy observation", subtitle: "Reusable gap + proof evidence", accent: C.teal, soft: C.tealSoft, w: 74, h: 74, labelWidth: 190, titleSize: 21 });
  f.node({ id: "birth-controller", cx: 860, cy: 330, shape: "hex", icon: "git-branch", title: "Online birth controller", subtitle: "Recurrence, rejection, coverage, and breadth", accent: C.teal, soft: C.tealSoft, w: 82, h: 72, labelWidth: 195, titleSize: 21 });
  f.node({ id: "candidate-generation", cx: 1080, cy: 330, shape: "octagon", icon: "sparkles", title: "Candidate generation", subtitle: "ToolSpec + one Python function", accent: C.violet, soft: C.violetSoft, w: 84, h: 76, labelWidth: 205, titleSize: 21 });
  f.node({ id: "validation", cx: 1320, cy: 330, shape: "shield", icon: "shield-check", title: "Gate, validate, and repair", subtitle: "Contract gate, sandbox proof, and repair", accent: C.amber, soft: C.amberSoft, w: 88, h: 88, labelWidth: 210, titleSize: 21 });

  f.node({ id: "registry", cx: 650, cy: 700, shape: "component", icon: "blocks", title: "Generated-tool registry", subtitle: "Spec, code, proof, hash, version, and lifecycle state", accent: C.violet, soft: C.violetSoft, w: 88, h: 76, labelWidth: 230, titleSize: 21 });
  f.node({ id: "runtime-router", cx: 930, cy: 700, shape: "hex", icon: "route", title: "Runtime router", subtitle: "Proof, relevance, dependencies, lifecycle, and redundancy", accent: C.violet, soft: C.violetSoft, w: 84, h: 74, labelWidth: 235, titleSize: 21 });
  f.node({ id: "tool-injection", cx: 1210, cy: 700, shape: "component", icon: "plug", title: "Generated-tool injection", subtitle: "Compile, merge, and recompute scrambling maps", accent: C.teal, soft: C.tealSoft, w: 88, h: 76, labelWidth: 230, titleSize: 21 });

  f.node({ id: "combined-inventory", cx: 1620, cy: 330, shape: "stack", icon: "blocks", title: "Actor-visible tool inventory", subtitle: "Native + routed generated tools", accent: C.teal, soft: C.tealSoft, w: 84, h: 70, labelWidth: 225, titleSize: 21 });
  f.node({ id: "actor", cx: 1620, cy: 700, shape: "chip", icon: "bot", title: "Actor execution", subtitle: "Natural tool selection", accent: C.red, soft: C.redSoft, w: 82, h: 72, labelWidth: 220, titleSize: 21 });
  f.node({ id: "task-score", cx: 1620, cy: 1080, shape: "database", icon: "gauge", title: "Task state + scoring", subtitle: "Native effects + benchmark score", accent: C.gray, soft: C.graySoft, w: 86, h: 78, labelWidth: 220, titleSize: 21 });

  f.node({ id: "execution-log", cx: 1260, cy: 1080, shape: "document", icon: "list-checks", title: "Reuse + execution log", subtitle: "Visibility, calls, traces, result, score/outcome", accent: C.red, soft: C.redSoft, w: 84, h: 84, labelWidth: 225, titleSize: 21 });
  f.node({ id: "side-effect-audit", cx: 1020, cy: 1080, shape: "shield", icon: "shield-check", title: "Side-effect audit", subtitle: "Required native follow-up", accent: C.red, soft: C.redSoft, w: 84, h: 84, labelWidth: 215, titleSize: 21 });
  f.node({ id: "reflection", cx: 790, cy: 1080, shape: "circle", icon: "refresh-cw", title: "Lifecycle reflection", subtitle: "Matched controls, utility, failures, incidents", accent: C.red, soft: C.redSoft, w: 76, h: 76, labelWidth: 220, titleSize: 21 });
  f.node({ id: "lifecycle", cx: 550, cy: 1080, shape: "database", icon: "history", title: "Lifecycle state + checkpoint", subtitle: "Retain, repair, audit, park, or retire", accent: C.violet, soft: C.violetSoft, w: 86, h: 78, labelWidth: 230, titleSize: 21 });
  return f;
}

function generationFigure() {
  const f = new Diagram(
    1800,
    1500,
    "SAGE tool birth, generation, validation, and repair architecture",
    "A detailed component architecture showing visible-context observation, online birth control, deterministic and model-based synthesis, metadata normalization, candidate gating, sandbox validation, repair, rejection memory, and registry admission.",
  );
  f.header("Tool Birth, Generation, Validation, and Repair", [
    { kind: "shape", shape: "document", label: "request / artifact", color: C.navy, soft: C.navySoft },
    { kind: "shape", shape: "hex", label: "policy / controller", color: C.teal, soft: C.tealSoft },
    { kind: "shape", shape: "shield", label: "proof gate", color: C.amber, soft: C.amberSoft },
    { kind: "line", label: "admission flow", color: C.lineDark },
    { kind: "line", label: "repair loop", color: C.amber, dashed: true },
  ]);

  f.boundary(34, 180, 480, 1260, "1  OBSERVE + DECIDE", C.navy, C.navySoft, { opacity: 0.27 });
  f.boundary(548, 180, 605, 1260, "2  SYNTHESIZE", C.teal, C.tealSoft, { opacity: 0.23 });
  f.boundary(1187, 180, 578, 1260, "3  NORMALIZE, PROVE + ADMIT", C.amber, C.amberSoft, { opacity: 0.25 });

  f.connector("M159 310 H205 V500 H235", C.navy, { marker: "navy" });
  f.connector("M305 310 H345 V500 H315", C.gray, { marker: "gray" });
  f.connector("M391 310 H360 V515 H315", C.navy, { marker: "navy" });
  f.connector("M315 500 H470 V800 H324", C.teal, { marker: "teal" });
  f.connector("M226 800 H130 V1086", C.red, { marker: "red", label: "suppress", labelX: 155, labelY: 784 });
  f.connector("M324 800 H530 V340 H636", C.teal, { marker: "teal", label: "birth", labelX: 494, labelY: 784 });
  f.connector("M714 340 H820 V508", C.teal, { marker: "teal" });
  f.connector("M798 530 H720 V655", C.teal, { marker: "teal" });
  f.connector("M842 530 H970 V654", C.violet, { marker: "violet" });
  f.connector("M761 690 H835 V835 H850 V857", C.teal, { marker: "teal" });
  f.connector("M1011 690 H1110 V835 H890 V857", C.violet, { marker: "violet" });
  f.connector("M913 900 H1140 V350 H1270", C.amber, { marker: "amber", label: "candidate", labelX: 1060, labelY: 884 });
  f.connector("M1350 350 H1539", C.amber, { marker: "amber" });
  f.connector("M1621 350 H1735 V550 H1475 V585", C.amber, { marker: "amber" });
  f.connector("M1475 815 V882", C.amber, { marker: "amber" });
  f.connector("M1427 930 H1280 V1095", C.amber, { marker: "amber", label: "repairable", labelX: 1345, labelY: 914 });
  f.connector("M1509 964 H1545 V1090 H1475 V1097", C.red, { marker: "red", label: "final fail", labelX: 1545, labelY: 1058 });
  f.connector("M1523 930 H1655 V1096", C.teal, { marker: "teal", label: "pass", labelX: 1600, labelY: 914 });
  f.connector("M1239 1130 H1169 V1370 H1157 V350 H1270", C.amber, { marker: "amber", dashed: true, label: "renormalize + revalidate", labelX: 1295, labelY: 1358 });

  f.node({ id: "gen-context", cx: 130, cy: 310, shape: "circle", icon: "eye", title: "Visible task context", subtitle: "Request + native names", accent: C.navy, soft: C.navySoft, w: 58, h: 58, iconSize: 27, labelWidth: 140, titleSize: 18, subtitleSize: 15, titleGap: 25 });
  f.node({ id: "gen-memory", cx: 275, cy: 310, shape: "database", icon: "memory-stick", title: "Coverage + failure memory", subtitle: "Proof, handled keys, rejections", accent: C.gray, soft: C.graySoft, w: 60, h: 54, iconSize: 25, labelWidth: 145, titleSize: 18, subtitleSize: 15, titleGap: 24 });
  f.node({ id: "gen-template", cx: 420, cy: 310, shape: "document", icon: "clipboard-check", title: "Observation template", subtitle: "Families, examples, evidence", accent: C.navy, soft: C.navySoft, w: 58, h: 62, iconSize: 27, labelWidth: 140, titleSize: 18, subtitleSize: 15, titleGap: 24 });
  f.node({ id: "capability-observation", cx: 275, cy: 500, shape: "circle", icon: "scan-search", title: "Visible-context capability observation", subtitle: "Reusable mechanism, gap key, candidate families, and validation evidence", accent: C.teal, soft: C.tealSoft, w: 80, h: 80, labelWidth: 280, titleSize: 21, subtitleSize: 16 });
  f.node({ id: "online-birth", cx: 275, cy: 800, shape: "diamond", icon: "git-branch", title: "Online birth controller", subtitle: "Recurrence, rejection limit, current proof, broader-helper coverage, and cluster breadth", accent: C.teal, soft: C.tealSoft, w: 98, h: 98, iconSize: 31, labelWidth: 285, titleSize: 21, subtitleSize: 16 });
  f.node({ id: "suppression-memory", cx: 130, cy: 1120, shape: "database", icon: "archive-x", title: "Suppressed / remembered", subtitle: "Handled or twice-rejected gap", accent: C.red, soft: C.redSoft, w: 68, h: 58, iconSize: 27, labelWidth: 190, titleSize: 19, subtitleSize: 15 });

  f.node({ id: "generation-request", cx: 675, cy: 340, shape: "document", icon: "file-text", title: "Structured generation request", subtitle: "Visible family, allowed families, examples, structured evidence, and failure memory", accent: C.teal, soft: C.tealSoft, w: 78, h: 84, labelWidth: 245, titleSize: 21, subtitleSize: 16 });
  f.node({ id: "synthesis-dispatch", cx: 820, cy: 530, shape: "circle", icon: "workflow", title: "Synthesis dispatch", accent: C.teal, soft: C.tealSoft, w: 44, h: 44, iconSize: 22, labelWidth: 170, titleSize: 17, titleGap: 22 });
  f.node({ id: "mapped-contract", cx: 720, cy: 690, shape: "hex", icon: "settings-2", title: "Mapped contract path", subtitle: "Engineered deterministic ToolSpec + code", accent: C.teal, soft: C.tealSoft, w: 82, h: 70, labelWidth: 220, titleSize: 20, subtitleSize: 16 });
  f.node({ id: "llm-synthesis", cx: 970, cy: 690, shape: "octagon", icon: "sparkles", title: "LLM synthesis fallback", subtitle: "GPT-4o-mini ToolSpec + one Python function", accent: C.violet, soft: C.violetSoft, w: 82, h: 72, labelWidth: 230, titleSize: 20, subtitleSize: 16 });
  f.node({ id: "candidate-artifact", cx: 870, cy: 900, shape: "document", icon: "code-xml", title: "Candidate artifact", subtitle: "ToolSpec + one self-contained deterministic Python function", accent: C.violet, soft: C.violetSoft, w: 86, h: 86, labelWidth: 255, titleSize: 21, subtitleSize: 16 });
  f.annotation(620, 1165, "Candidate contract", ["Assigned family + typed input/output schema", "Positive / negative triggers + abstention", "Native-call preservation", "Compression, cross-task reach, composite decomposition"], C.violet, { width: 260, size: 16 });
  f.annotation(900, 1165, "Generated implementation", ["One matching function", "Deterministic and self-contained", "JSON-safe output + safe fallback", "No shallow native-tool wrapper"], C.teal, { width: 235, size: 16 });

  f.node({ id: "metadata-normalization", cx: 1310, cy: 350, shape: "funnel", icon: "filter", title: "Candidate metadata normalization", subtitle: "Visible families and triggers; diagnostic-only when breadth is insufficient", accent: C.amber, soft: C.amberSoft, w: 80, h: 72, labelWidth: 240, titleSize: 19, subtitleSize: 15 });
  f.node({ id: "candidate-gate", cx: 1580, cy: 350, shape: "shield", icon: "shield-check", title: "Candidate and native-contract gate", subtitle: "Typed contract, applicability, abstention, reuse value, and native-call preservation", accent: C.amber, soft: C.amberSoft, w: 82, h: 82, labelWidth: 250, titleSize: 19, subtitleSize: 15 });

  f.back.push(f.shapeMarkup("octagon", 1475, 700, 290, 230, C.amber, C.paper, 2));
  f.icon("shield-check", 1475, 635, 38, C.amber);
  f.front.push(`<text class="node-title" x="1475" y="685" text-anchor="middle" style="font-size:21px">Sandbox validation stack</text>`);
  const validatorLines = [
    "Held-out + negative applicability",
    "AST safety restrictions",
    "Schema + restricted compilation",
    "Deterministic replay + JSON",
    "Isolated runtime smoke trace",
  ];
  f.front.push(f.textLines(1475, 708, validatorLines, "node-subtitle", 20, "middle", "font-size:16px"));
  f.checks.push({ id: "sandbox-validator", x: 1330, y: 585, w: 290, h: 230, textBottom: 794.4 });

  f.node({ id: "validation-decision", cx: 1475, cy: 930, shape: "diamond", icon: "package-check", title: "All active proofs pass?", accent: C.amber, soft: C.amberSoft, w: 96, h: 96, iconSize: 31, labelWidth: 210, titleSize: 20 });
  f.node({ id: "repair-loop", cx: 1280, cy: 1130, shape: "hex", icon: "wrench", title: "Repair loop", subtitle: "Deterministic or GPT-4o-mini; two attempts; full revalidation", accent: C.amber, soft: C.amberSoft, w: 82, h: 70, labelWidth: 180, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "rejection", cx: 1475, cy: 1130, shape: "database", icon: "archive-x", title: "Reject and remember", subtitle: "Errors, repair history, rejection count, birth suppression", accent: C.red, soft: C.redSoft, w: 74, h: 66, labelWidth: 180, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "registry-admission", cx: 1655, cy: 1130, shape: "component", icon: "blocks", title: "Registry admission", subtitle: "Spec, code, proof, hash, version, snapshot, events", accent: C.teal, soft: C.tealSoft, w: 76, h: 68, labelWidth: 170, titleSize: 18, subtitleSize: 14 });
  return f;
}

function runtimeFigure() {
  const f = new Diagram(
    1800,
    1450,
    "SAGE registry, routing, execution, and lifecycle architecture",
    "A component architecture showing persistent routing inputs, the four-stage runtime router, bounded generated-tool bundle, compilation and injection, natural actor use, execution telemetry, side-effect auditing, reflection, lifecycle decisions, and checkpoint reuse.",
  );
  f.header("Registry, Routing, Execution, and Lifecycle", [
    { kind: "shape", shape: "database", label: "state", color: C.navy, soft: C.navySoft },
    { kind: "shape", shape: "funnel", label: "routing filter", color: C.violet, soft: C.violetSoft },
    { kind: "shape", shape: "component", label: "runtime component", color: C.teal, soft: C.tealSoft },
    { kind: "line", label: "execution evidence", color: C.red },
    { kind: "line", label: "next-task update", color: C.teal, dashed: true },
  ]);

  f.boundary(34, 180, 1500, 1210, "SAGE RUNTIME + LIFECYCLE", C.violet, C.violetSoft, { opacity: 0.20 });
  f.boundary(1570, 180, 195, 1210, "BENCHMARK", C.gray, C.graySoft, { dashed: true, opacity: 0.28 });

  f.connector("M209 320 H350 V420 H394", C.navy, { marker: "navy" });
  f.connector("M208 570 H414", C.navy, { marker: "navy" });
  f.connector("M209 820 H350 V630 H448", C.gray, { marker: "gray" });
  f.connector("M755 500 H819", C.violet, { marker: "violet" });
  f.connector("M901 500 H999", C.violet, { marker: "violet" });
  f.connector("M1081 500 H1198", C.teal, { marker: "teal" });
  f.connector("M1282 500 H1398", C.teal, { marker: "teal" });
  f.connector("M1620 310 H1535 V430 H1440 V463", C.navy, { marker: "navy" });
  f.connector("M1482 500 H1617", C.teal, { marker: "teal", label: "one tool interface", labelX: 1545, labelY: 484 });
  f.connector("M1699 500 H1745 V1030 H1696", C.lineDark, { marker: "gray" });
  f.connector("M1620 1030 H1472", C.red, { marker: "red", label: "trajectory + score", labelX: 1548, labelY: 1014 });
  f.connector("M1388 1030 H1242", C.red, { marker: "red" });
  f.connector("M1158 1030 H1012", C.red, { marker: "red" });
  f.connector("M928 1030 H782", C.red, { marker: "red" });
  f.connector("M698 1030 H542", C.red, { marker: "red" });
  f.connector("M580 690 V760 H820", C.violet, { marker: "violet", label: "decision map", labelX: 700, labelY: 748 });
  f.connector("M740 994 V960 H380 V650 H475", C.violet, { marker: "violet", dashed: true, label: "future routing state", labelX: 555, labelY: 948 });
  f.connector("M458 1030 H320 V820 H209", C.teal, { marker: "teal", dashed: true });
  f.connector("M458 1030 H280 V1350 H60 V320 H131", C.teal, { marker: "teal", dashed: true, label: "checkpoint for later tasks", labelX: 170, labelY: 1338 });

  f.node({ id: "route-registry-input", cx: 170, cy: 320, shape: "component", icon: "blocks", title: "Registry entries", subtitle: "Spec, code, proof, hash, version, reuse, retirement", accent: C.navy, soft: C.navySoft, w: 78, h: 70, labelWidth: 230, titleSize: 20, subtitleSize: 15 });
  f.node({ id: "route-context-input", cx: 170, cy: 570, shape: "document", icon: "eye", title: "Visible routing context", subtitle: "Request, native names, signals, family, allow list", accent: C.navy, soft: C.navySoft, w: 76, h: 78, labelWidth: 230, titleSize: 20, subtitleSize: 15 });
  f.node({ id: "route-lifecycle-input", cx: 170, cy: 820, shape: "database", icon: "history", title: "Lifecycle routing state", subtitle: "Use, failures, family, side effects, prior decision", accent: C.gray, soft: C.graySoft, w: 78, h: 70, labelWidth: 230, titleSize: 20, subtitleSize: 15 });

  const routerX = 380;
  const routerY = 320;
  const routerW = 400;
  const routerH = 370;
  f.back.push(`<polygon points="${points([[380, 320], [780, 320], [740, 610], [630, 690], [530, 690], [420, 610]])}" fill="${C.violetSoft}" stroke="${C.violet}" stroke-width="2" filter="url(#shadow)"/>`);
  f.icon("filter", 580, 360, 34, C.violet);
  f.front.push(`<text class="node-title" x="580" y="410" text-anchor="middle" style="font-size:23px">Runtime router</text>`);
  const stages = [
    ["Current-proof eligibility", ["accepted + active; proof/hash current"]],
    ["Visible-context match", ["positive evidence; hard negatives first"]],
    ["Dependency + safety fit", ["native dependencies + lifecycle state"]],
    ["Portfolio shaping", ["remove redundancy; rank", "retain top four"]],
  ];
  stages.forEach(([title, details], index) => {
    const y = 458 + index * 52;
    f.front.push(`<text class="router-stage" x="580" y="${y}" text-anchor="middle">${esc(title)}</text>`);
    f.front.push(f.textLines(580, y + 20, details, "router-detail", 17, "middle"));
  });
  f.checks.push({ id: "runtime-router", x: routerX, y: routerY, w: routerW, h: routerH, textBottom: routerY + routerH - 24 });

  f.node({ id: "routing-decision", cx: 860, cy: 800, shape: "document", icon: "list-checks", title: "Per-tool routing decision", subtitle: "Status, reason, relevance, matched triggers, task families", accent: C.violet, soft: C.violetSoft, w: 80, h: 82, labelWidth: 245, titleSize: 20, subtitleSize: 15 });
  f.node({ id: "tool-bundle", cx: 860, cy: 500, shape: "stack", icon: "package-check", title: "Bounded generated-tool bundle", subtitle: "Eligible ordered set; maximum four", accent: C.violet, soft: C.violetSoft, w: 82, h: 68, labelWidth: 180, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "runtime-compile", cx: 1040, cy: 500, shape: "hex", icon: "code-xml", title: "Generated callable", subtitle: "Restricted compile, typed signature, schema, trace", accent: C.teal, soft: C.tealSoft, w: 82, h: 72, labelWidth: 180, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "runtime-handoff", cx: 1240, cy: 500, shape: "component", icon: "arrow-right-left", title: "Generated-tool injection", subtitle: "Merge callable and allow list; recompute name maps", accent: C.teal, soft: C.tealSoft, w: 84, h: 72, labelWidth: 180, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "combined-inventory-runtime", cx: 1440, cy: 500, shape: "stack", icon: "blocks", title: "Combined inventory", subtitle: "Native + generated; maps recomputed", accent: C.teal, soft: C.tealSoft, w: 84, h: 70, labelWidth: 180, titleSize: 18, subtitleSize: 14 });

  f.node({ id: "runtime-native-tools", cx: 1658, cy: 310, shape: "component", icon: "blocks", title: "Native tool inventory", subtitle: "Task allow list + scrambling", accent: C.navy, soft: C.navySoft, w: 76, h: 64, labelWidth: 165, titleSize: 17, subtitleSize: 13, titleGap: 22 });
  f.node({ id: "runtime-actor", cx: 1658, cy: 500, shape: "chip", icon: "bot", title: "Actor execution", subtitle: "Natural selection; native calls perform effects", accent: C.red, soft: C.redSoft, w: 82, h: 72, labelWidth: 170, titleSize: 19, subtitleSize: 14 });
  f.node({ id: "benchmark-state", cx: 1658, cy: 1030, shape: "database", icon: "gauge", title: "Benchmark state + score", subtitle: "Host-owned state, milestones, minefields", accent: C.gray, soft: C.graySoft, w: 76, h: 68, labelWidth: 170, titleSize: 18, subtitleSize: 14 });

  f.node({ id: "runtime-telemetry", cx: 1430, cy: 1030, shape: "document", icon: "list-checks", title: "Execution evidence", subtitle: "Visibility, calls, traces, result, score/outcome", accent: C.red, soft: C.redSoft, w: 84, h: 84, labelWidth: 200, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "side-effect-follow-up", cx: 1200, cy: 1030, shape: "shield", icon: "shield-check", title: "Native side-effect follow-up", subtitle: "Verify required native actions", accent: C.red, soft: C.redSoft, w: 84, h: 84, labelWidth: 205, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "runtime-reflection", cx: 970, cy: 1030, shape: "circle", icon: "brain-circuit", title: "Reflection controller", subtitle: "Control deltas, use/failure, incidents", accent: C.red, soft: C.redSoft, w: 80, h: 80, labelWidth: 200, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "future-visibility", cx: 740, cy: 1030, shape: "hex", icon: "refresh-cw", title: "Future visibility state", subtitle: "Retain, route repair, audit, repair, park, retire", accent: C.violet, soft: C.violetSoft, w: 84, h: 72, labelWidth: 200, titleSize: 18, subtitleSize: 14 });
  f.node({ id: "checkpoint", cx: 500, cy: 1030, shape: "component", icon: "blocks", title: "Registry + lifecycle checkpoint", subtitle: "Proof, use, retirement, events, snapshots", accent: C.teal, soft: C.tealSoft, w: 84, h: 74, labelWidth: 205, titleSize: 18, subtitleSize: 14 });

  f.annotation(410, 1245, "Routing controls", ["Visible-context metadata only", "Scenario identifiers and historical contribution evidence excluded", "Generated-tool bundle capped at four"], C.violet, { width: 430, size: 16 });
  f.annotation(930, 1245, "Lifecycle timing", ["Immediate incident rules plus periodic reflection", "Pulse every four tasks after the first eight", "Code repair occurs before admission; runtime changes future exposure"], C.red, { width: 470, size: 16 });
  return f;
}

function standaloneAtlasHtml(figures) {
  const tabs = figures.map((item, index) => `<button type="button" class="atlas-tab${index === 0 ? " active" : ""}" data-figure="${item.slug}">${esc(item.shortTitle)}</button>`).join("");
  const panels = figures.map((item, index) => `<section class="atlas-panel${index === 0 ? " active" : ""}" data-panel="${item.slug}"><div class="atlas-viewport"><div class="atlas-canvas">${item.svg}</div></div></section>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SAGE Architecture Atlas</title><style>
    :root{color-scheme:light;--ink:#17243A;--muted:#53657A;--line:#C9D4DF;--bg:#EEF2F5;--paper:#FFFFFF;--active:#215985}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Helvetica Neue",Helvetica,Arial,sans-serif}.atlas{max-width:1800px;margin:0 auto;padding:20px}.atlas-nav{position:sticky;top:0;z-index:2;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 0;background:var(--bg)}button{appearance:none;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:600 15px/1.2 inherit;padding:10px 14px;border-radius:6px;cursor:pointer}button.active{background:var(--active);border-color:var(--active);color:#fff}.atlas-zoom{display:flex;gap:8px;align-items:center;margin-left:auto}.atlas-percent{min-width:58px;text-align:center;font-variant-numeric:tabular-nums;color:var(--muted);font-weight:600}.atlas-panel{display:none}.atlas-panel.active{display:block}.atlas-viewport{position:relative;height:860px;overflow:hidden;background:var(--paper);border:1px solid var(--line);cursor:grab;touch-action:none}.atlas-viewport.dragging{cursor:grabbing}.atlas-canvas{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;transform-origin:center center;will-change:transform}.atlas-canvas svg{display:block;width:100%;height:100%;max-width:100%;max-height:100%}@media(max-width:700px){.atlas{padding:8px}.atlas-nav{position:static}.atlas-tab{flex:1 1 100%}.atlas-zoom{margin-left:0;width:100%}.atlas-viewport{height:560px}}
  </style></head><body><main class="atlas"><nav class="atlas-nav" aria-label="Architecture figures">${tabs}</nav>${panels}</main><script>
    const nav=document.querySelector('.atlas-nav');const zoom=document.createElement('div');zoom.className='atlas-zoom';zoom.innerHTML='<button type="button" data-action="out" aria-label="Zoom out">-</button><span class="atlas-percent" aria-live="polite">100%</span><button type="button" data-action="in" aria-label="Zoom in">+</button><button type="button" data-action="reset">Reset view</button>';nav.appendChild(zoom);
    const buttons=[...document.querySelectorAll('.atlas-tab')];const panels=[...document.querySelectorAll('.atlas-panel')];const percent=document.querySelector('.atlas-percent');let scale=1,x=0,y=0,drag=null;
    const activePanel=()=>document.querySelector('.atlas-panel.active');const canvas=()=>activePanel().querySelector('.atlas-canvas');const viewport=()=>activePanel().querySelector('.atlas-viewport');
    function clamp(){const view=viewport();const maxX=view.clientWidth*(scale-1)/2;const maxY=view.clientHeight*(scale-1)/2;x=Math.max(-maxX,Math.min(maxX,x));y=Math.max(-maxY,Math.min(maxY,y));}
    function render(){clamp();canvas().style.transform='translate('+x+'px,'+y+'px) scale('+scale+')';percent.textContent=Math.round(scale*100)+'%';}
    function reset(){scale=1;x=0;y=0;render();}
    for(const button of buttons){button.addEventListener('click',()=>{for(const item of buttons)item.classList.toggle('active',item===button);for(const panel of panels)panel.classList.toggle('active',panel.dataset.panel===button.dataset.figure);reset();});}
    zoom.addEventListener('click',(event)=>{const action=event.target.closest('button')?.dataset.action;if(!action)return;if(action==='in')scale=Math.min(4,scale+.25);if(action==='out')scale=Math.max(1,scale-.25);if(action==='reset'){reset();return;}render();});
    document.addEventListener('pointerdown',(event)=>{const view=event.target.closest('.atlas-viewport');if(!view||scale===1)return;drag={view,startX:event.clientX,startY:event.clientY,x,y};view.classList.add('dragging');view.setPointerCapture(event.pointerId);});
    document.addEventListener('pointermove',(event)=>{if(!drag)return;x=drag.x+event.clientX-drag.startX;y=drag.y+event.clientY-drag.startY;render();});
    document.addEventListener('pointerup',()=>{if(!drag)return;drag.view.classList.remove('dragging');drag=null;});
    document.addEventListener('dblclick',(event)=>{if(!event.target.closest('.atlas-viewport'))return;scale=scale===1?2:1;x=0;y=0;render();});
  </script></body></html>`;
}

function inlineAtlasFragment(figures) {
  const encoded = figures.map((item) => ({ ...item, data: `data:image/svg+xml;base64,${Buffer.from(item.svg).toString("base64")}` }));
  const tabs = encoded.map((item, index) => `<button type="button" class="btn${index === 0 ? " btn-primary" : ""}" data-sage-figure="${item.slug}" aria-pressed="${index === 0}">${esc(item.shortTitle)}</button>`).join("\n");
  const images = encoded.map((item, index) => `<img class="sage-atlas-image" data-sage-panel="${item.slug}" src="${item.data}" alt="${esc(item.shortTitle)}"${index === 0 ? "" : " hidden"}>`).join("\n");
  return `<div id="sage-architecture-atlas">
  <style>
    #sage-architecture-atlas .sage-atlas-viewport{position:relative;height:680px;overflow:hidden;touch-action:none;cursor:grab}
    #sage-architecture-atlas .sage-atlas-viewport.is-dragging{cursor:grabbing}
    #sage-architecture-atlas .sage-atlas-image{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;transform-origin:center center;will-change:transform;user-select:none}
    @media(max-width:600px){#sage-architecture-atlas .sage-atlas-viewport{height:460px}}
  </style>
  <div class="viz-controls" role="group" aria-label="Choose an architecture figure">
${tabs}
    <button type="button" class="btn btn-ghost" data-sage-action="out" data-tooltip="Zoom out" aria-label="Zoom out"><i data-lucide="zoom-out" aria-hidden="true"></i></button>
    <span class="viz-badge" data-sage-zoom aria-live="polite">100%</span>
    <button type="button" class="btn btn-ghost" data-sage-action="in" data-tooltip="Zoom in" aria-label="Zoom in"><i data-lucide="zoom-in" aria-hidden="true"></i></button>
    <button type="button" class="btn btn-ghost" data-sage-action="reset" data-tooltip="Reset view" aria-label="Reset view"><i data-lucide="rotate-ccw" aria-hidden="true"></i></button>
  </div>
  <div class="card"><div class="sage-atlas-viewport" aria-live="polite">${images}</div></div>
</div>
<script>
const sageAtlas=document.getElementById('sage-architecture-atlas');
const sageButtons=[...sageAtlas.querySelectorAll('[data-sage-figure]')];
const sagePanels=[...sageAtlas.querySelectorAll('[data-sage-panel]')];
const sageViewport=sageAtlas.querySelector('.sage-atlas-viewport');
const sageZoomLabel=sageAtlas.querySelector('[data-sage-zoom]');
let sageScale=1,sageX=0,sageY=0,sageDrag=null;
const sageActivePanel=()=>sagePanels.find((panel)=>!panel.hidden);
function sageClamp(){const maxX=sageViewport.clientWidth*(sageScale-1)/2;const maxY=sageViewport.clientHeight*(sageScale-1)/2;sageX=Math.max(-maxX,Math.min(maxX,sageX));sageY=Math.max(-maxY,Math.min(maxY,sageY));}
function sageRender(){sageClamp();sageActivePanel().style.transform='translate('+sageX+'px,'+sageY+'px) scale('+sageScale+')';sageZoomLabel.textContent=Math.round(sageScale*100)+'%';}
function sageReset(){sageScale=1;sageX=0;sageY=0;for(const panel of sagePanels)panel.style.transform='';sageRender();}
for(const sageButton of sageButtons){sageButton.addEventListener('click',()=>{for(const item of sageButtons){const selected=item===sageButton;item.setAttribute('aria-pressed',String(selected));item.classList.toggle('btn-primary',selected);}for(const panel of sagePanels)panel.hidden=panel.dataset.sagePanel!==sageButton.dataset.sageFigure;sageReset();});}
sageAtlas.querySelector('.viz-controls').addEventListener('click',(event)=>{const action=event.target.closest('[data-sage-action]')?.dataset.sageAction;if(!action)return;if(action==='in')sageScale=Math.min(4,sageScale+.25);if(action==='out')sageScale=Math.max(1,sageScale-.25);if(action==='reset'){sageReset();return;}sageRender();});
sageViewport.addEventListener('pointerdown',(event)=>{if(sageScale===1)return;sageDrag={startX:event.clientX,startY:event.clientY,x:sageX,y:sageY};sageViewport.classList.add('is-dragging');sageViewport.setPointerCapture(event.pointerId);});
sageViewport.addEventListener('pointermove',(event)=>{if(!sageDrag)return;sageX=sageDrag.x+event.clientX-sageDrag.startX;sageY=sageDrag.y+event.clientY-sageDrag.startY;sageRender();});
sageViewport.addEventListener('pointerup',()=>{sageDrag=null;sageViewport.classList.remove('is-dragging');});
sageViewport.addEventListener('dblclick',()=>{sageScale=sageScale===1?2:1;sageX=0;sageY=0;sageRender();});
</script>
`;
}

async function exportPdf(svg, outputPath, width, height) {
  const browser = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  try {
    const page = await browser.newPage({ viewport: { width, height } });
    const pageWidth = 8;
    const pageHeight = pageWidth * height / width;
    await page.setContent(`<style>@page{size:${pageWidth}in ${pageHeight}in;margin:0}html,body{margin:0;padding:0;width:100%;height:100%}svg{display:block;width:100%;height:100%}</style>${svg}`, { waitUntil: "load" });
    await page.pdf({ path: outputPath, width: `${pageWidth}in`, height: `${pageHeight}in`, printBackground: true, margin: { top: "0in", right: "0in", bottom: "0in", left: "0in" } });
  } finally {
    await browser.close();
  }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(VIS_OUT, { recursive: true });
  const definitions = [
    { slug: "sage_v061_architecture_overview", shortTitle: "End-to-end architecture", figure: overviewFigure() },
    { slug: "sage_v061_generation_validation", shortTitle: "Generation and validation", figure: generationFigure() },
    { slug: "sage_v061_routing_lifecycle", shortTitle: "Routing and lifecycle", figure: runtimeFigure() },
  ];
  const rendered = [];
  for (const definition of definitions) {
    const svg = definition.figure.finalize();
    const svgPath = path.join(OUT, `${definition.slug}.svg`);
    const pngPath = path.join(OUT, `${definition.slug}.png`);
    const pdfPath = path.join(OUT, `${definition.slug}.pdf`);
    fs.writeFileSync(svgPath, `${svg}\n`, "utf8");
    await sharp(Buffer.from(svg), { density: 216 }).resize({ width: 3600 }).png({ compressionLevel: 9, adaptiveFiltering: true }).toFile(pngPath);
    await exportPdf(svg, pdfPath, definition.figure.width, definition.figure.height);
    rendered.push({ slug: definition.slug, shortTitle: definition.shortTitle, svg, width: definition.figure.width, height: definition.figure.height, checks: definition.figure.checks, paths: { svg: svgPath, png: pngPath, pdf: pdfPath } });
  }
  fs.writeFileSync(path.join(OUT, "sage_v061_architecture_atlas.html"), standaloneAtlasHtml(rendered), "utf8");
  fs.writeFileSync(path.join(VIS_OUT, "sage-v061-architecture-atlas.html"), inlineAtlasFragment(rendered), "utf8");
  fs.writeFileSync(path.join(OUT, "render_manifest.json"), `${JSON.stringify(rendered.map(({ slug, shortTitle, width, height, checks, paths }) => ({ slug, shortTitle, width, height, checks, paths })), null, 2)}\n`, "utf8");
  process.stdout.write(`${rendered.map((item) => item.paths.png).join("\n")}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
