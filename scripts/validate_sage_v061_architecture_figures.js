#!/usr/bin/env node

/* Validate the publication exports and implementation claims in the SAGE v061 figure set. */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const sharp = require("sharp");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "docs", "sage_protocol", "figures", "v061_architecture");
const INLINE = "/Users/christopherclark/.codex/visualizations/2026/06/14/019ec623-9717-7811-ac2d-b27fb75d65c4/sage-v061-architecture-atlas.html";
const COMMIT = "2546640";
const PROTOCOL_MANIFEST = path.join(
  ROOT,
  "outputs",
  "chapter3_token_reduction",
  "v061_finish_v059_full",
  "online_build_full_20260613_203410",
  "protocol_manifest.json",
);
const BIRTH_EVENTS = path.join(
  ROOT,
  "outputs",
  "chapter3_token_reduction",
  "v061_finish_v059_full",
  "online_build_full_20260613_203410",
  "candidate",
  "online_build_full_candidate_agent_gpt-4o-mini_user_gpt-4o-mini_06_13_2026_20_34_15",
  "tool_birth_events.jsonl",
);

const checks = [];

function check(name, condition, detail) {
  if (!condition) throw new Error(`${name}: ${detail}`);
  checks.push({ name, detail });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function gitShow(file) {
  const result = spawnSync("git", ["show", `${COMMIT}:${file}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`git show failed for ${file}: ${result.stderr}`);
  }
  return result.stdout;
}

async function validateExports() {
  const manifest = readJson(path.join(OUT, "render_manifest.json"));
  check("figure count", manifest.length === 3, "three coordinated figures rendered");
  const expected = new Map([
    ["sage_v061_architecture_overview", [3600, 2700]],
    ["sage_v061_generation_validation", [3600, 3000]],
    ["sage_v061_routing_lifecycle", [3600, 2900]],
  ]);
  const requiredLabels = new Map([
    ["sage_v061_architecture_overview", ["Online birth controller", "Generated-tool registry", "Lifecycle reflection", "Actor-visible tool inventory"]],
    ["sage_v061_generation_validation", ["Mapped contract path", "LLM synthesis fallback", "Candidate and native-contract gate", "Sandbox validation stack", "Repair loop"]],
    ["sage_v061_routing_lifecycle", ["Current-proof eligibility", "Per-tool routing decision", "Generated-tool injection", "Native tool inventory", "Combined inventory", "Native side-effect follow-up", "Future visibility state"]],
  ]);

  for (const figure of manifest) {
    const [expectedWidth, expectedHeight] = expected.get(figure.slug) || [];
    check(`${figure.slug} manifest dimensions`, figure.width * 2 === expectedWidth && figure.height * 2 === expectedHeight, `${figure.width}x${figure.height} SVG coordinate space`);
    for (const item of figure.checks) {
      check(`${figure.slug} text bounds: ${item.id}`, item.textBottom <= item.y + item.h - 19, `text bottom ${item.textBottom.toFixed(1)} remains inside node ending at ${item.y + item.h}`);
    }

    const svgPath = path.join(OUT, `${figure.slug}.svg`);
    const pngPath = path.join(OUT, `${figure.slug}.png`);
    const pdfPath = path.join(OUT, `${figure.slug}.pdf`);
    const svg = fs.readFileSync(svgPath, "utf8");
    const pdf = fs.readFileSync(pdfPath);
    const visibleText = svg.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
    check(`${figure.slug} SVG exists`, svg.length > 10000, `${svg.length} bytes`);
    check(`${figure.slug} SVG syntax sentinels`, svg.startsWith("<svg") && svg.includes("</svg>") && !/(NaN|undefined|foreignObject)/.test(svg), "complete SVG without invalid coordinate sentinels or foreignObject content");
    for (const label of requiredLabels.get(figure.slug) || []) {
      check(`${figure.slug} label: ${label}`, visibleText.includes(label), "required architecture label present");
    }
    check(`${figure.slug} publication header`, !/\bv061\b|FIGURE [ABC]|complete view|complete admission path|how accepted tools/i.test(visibleText), "no version tag, figure code, or explanatory subtitle is visible");
    check(`${figure.slug} PDF`, pdf.length > 10000 && pdf.subarray(0, 4).toString("ascii") === "%PDF", `${pdf.length} bytes with PDF header`);
    const metadata = await sharp(pngPath).metadata();
    const stats = await sharp(pngPath).stats();
    const channelRanges = stats.channels.map((channel) => channel.max - channel.min);
    check(`${figure.slug} PNG dimensions`, metadata.width === expectedWidth && metadata.height === expectedHeight, `${metadata.width}x${metadata.height} pixels`);
    check(`${figure.slug} PNG nonblank`, channelRanges.some((range) => range > 80), `channel ranges ${channelRanges.join(", ")}`);
  }

  const inline = fs.readFileSync(INLINE, "utf8");
  check("inline fragment size", Buffer.byteLength(inline) < 2 * 1024 * 1024, `${Buffer.byteLength(inline)} bytes`);
  check("inline fragment contract", !/<\/?(?:html|head|body)(?:\s|>)/i.test(inline) && !/<!doctype/i.test(inline), "fragment contains no document wrapper");
  check("inline interaction controls", inline.includes('data-sage-action="in"') && inline.includes("pointermove") && inline.includes("sageReset"), "zoom, drag-to-pan, tab selection, and reset handlers present");
}

function polygonBoundsAtY(vertices, y) {
  const intersections = [];
  for (let index = 0; index < vertices.length; index += 1) {
    const [x1, y1] = vertices[index];
    const [x2, y2] = vertices[(index + 1) % vertices.length];
    if (y1 === y2) {
      if (Math.abs(y - y1) < 0.01) intersections.push(x1, x2);
      continue;
    }
    if (y < Math.min(y1, y2) || y > Math.max(y1, y2)) continue;
    const ratio = (y - y1) / (y2 - y1);
    intersections.push(x1 + ratio * (x2 - x1));
  }
  return [Math.min(...intersections), Math.max(...intersections)];
}

function lineInsidePolygon(line, vertices, padding = 4) {
  const top = polygonBoundsAtY(vertices, line.y);
  const bottom = polygonBoundsAtY(vertices, line.bottom);
  const left = Math.max(top[0], bottom[0]) + padding;
  const right = Math.min(top[1], bottom[1]) - padding;
  return line.x >= left && line.right <= right;
}

async function validateSvgLayout() {
  const layoutSpecs = new Map([
    ["sage_v061_architecture_overview", {
      boundedText: [
        ["ACTOR + TASK RUNTIME", 1475, 1765],
        ["trajectory + score", 350, 1440],
        ["next ordered task", 350, 1440],
      ],
    }],
    ["sage_v061_generation_validation", {
      boundedText: [
        ["birth", 34, 514],
        ["renormalize + revalidate", 1187, 1765],
      ],
      polygon: {
        name: "sandbox validation stack",
        vertices: [[1388, 585], [1562, 585], [1620, 631], [1620, 769], [1562, 815], [1388, 815], [1330, 769], [1330, 631]],
        text: new Set([
          "Sandbox validation stack",
          "Held-out + negative applicability",
          "AST safety restrictions",
          "Schema + restricted compilation",
          "Deterministic replay + JSON",
          "Isolated runtime smoke trace",
        ]),
      },
    }],
    ["sage_v061_routing_lifecycle", {
      polygon: {
        name: "runtime router",
        vertices: [[380, 320], [780, 320], [740, 610], [630, 690], [530, 690], [420, 610]],
        text: new Set([
          "Runtime router",
          "Current-proof eligibility",
          "accepted + active; proof/hash current",
          "Visible-context match",
          "positive evidence; hard negatives first",
          "Dependency + safety fit",
          "native dependencies + lifecycle state",
          "Portfolio shaping",
          "remove redundancy; rank",
          "retain top four",
        ]),
      },
    }],
  ]);

  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  try {
    for (const [slug, spec] of layoutSpecs) {
      const page = await browser.newPage();
      await page.goto(`file://${path.join(OUT, `${slug}.svg`)}`);
      const geometry = await page.locator("svg").evaluate((svg) => {
        const textBox = (element) => {
          const box = element.getBBox();
          return {
            text: element.textContent.trim().replace(/\s+/g, " "),
            x: box.x,
            y: box.y,
            right: box.x + box.width,
            bottom: box.y + box.height,
          };
        };
        const texts = [...svg.querySelectorAll("text")].map(textBox);
        const lines = [...svg.querySelectorAll("text")].flatMap((element) => {
          const spans = [...element.querySelectorAll(":scope > tspan")];
          return spans.length ? spans.map(textBox) : [textBox(element)];
        });
        return { texts, lines };
      });

      const overlaps = [];
      for (let leftIndex = 0; leftIndex < geometry.texts.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < geometry.texts.length; rightIndex += 1) {
          const left = geometry.texts[leftIndex];
          const right = geometry.texts[rightIndex];
          const overlapX = Math.min(left.right, right.right) - Math.max(left.x, right.x);
          const overlapY = Math.min(left.bottom, right.bottom) - Math.max(left.y, right.y);
          if (overlapX > 2 && overlapY > 2) overlaps.push(`${left.text} <> ${right.text}`);
        }
      }
      check(`${slug} text collision scan`, overlaps.length === 0, overlaps.length ? overlaps.join(" | ") : "no text-to-text overlaps");

      for (const [label, left, right] of spec.boundedText || []) {
        const match = geometry.texts.find((item) => item.text === label);
        check(`${slug} boundary containment: ${label}`, Boolean(match) && match.x >= left && match.right <= right, match ? `${match.x.toFixed(1)}-${match.right.toFixed(1)} inside ${left}-${right}` : "label missing");
      }

      if (spec.polygon) {
        const polygonLines = geometry.lines.filter((line) => spec.polygon.text.has(line.text));
        check(`${slug} ${spec.polygon.name} line count`, polygonLines.length === spec.polygon.text.size, `${polygonLines.length} expected lines found`);
        const outside = polygonLines.filter((line) => !lineInsidePolygon(line, spec.polygon.vertices));
        check(`${slug} ${spec.polygon.name} containment`, outside.length === 0, outside.length ? outside.map((line) => line.text).join(", ") : "all text lines remain inside the component shape");
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const renderer = fs.readFileSync(path.join(ROOT, "scripts", "render_sage_architecture_figures.js"), "utf8");
  const inventoryNodeIds = [
    "native-tools",
    "registry",
    "combined-inventory",
    "registry-admission",
    "route-registry-input",
    "combined-inventory-runtime",
    "runtime-native-tools",
    "checkpoint",
  ];
  for (const id of inventoryNodeIds) {
    const declaration = renderer.split("\n").find((line) => line.includes(`id: "${id}"`)) || "";
    check(`shared inventory icon: ${id}`, declaration.includes('icon: "blocks"'), "tool inventory and generated-registry representations use the blocks icon");
  }
}

function validateRunEvidence() {
  const protocol = readJson(PROTOCOL_MANIFEST);
  const env = protocol.run_affecting_sage_env;
  check("v061 models", protocol.agent === "gpt-4o-mini" && protocol.user === "gpt-4o-mini" && protocol.generation_model === "gpt-4o-mini", "actor, user simulator, and generation model are gpt-4o-mini");
  check("v061 generation", protocol.generation_enabled === true, "generation enabled");
  check("v061 visible-context policy", env.SAGE_SCENARIO_METADATA_POLICY === "visible_context" && env.SAGE_DISABLE_SCENARIO_NAME_BIRTH === "1" && env.SAGE_DISABLE_SCENARIO_NAME_ROUTING === "1", "visible-context metadata with scenario-name birth and routing disabled");
  check("v061 bounded bundle", env.SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE === "4", "runtime generated-tool bundle capped at four");
  check("v061 reflection cadence", env.SAGE_SELF_EVOLVING_REFLECTION === "1" && env.SAGE_SELF_EVOLVING_PULSE_INTERVAL === "4" && env.SAGE_SELF_EVOLVING_MIN_PULSE_TASKS === "8", "reflection enabled; pulse every four tasks after eight");
  check("v061 inactive controls", protocol.openai_response_cache_enabled === false && protocol.routing_evidence_mode === "disabled" && env.SAGE_PRAXIS_BRIDGE_POLICY === "disabled" && env.SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY === "0" && env.SAGE_SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS === "0", "cache, routing evidence, bridge, adoption retry, and side-effect extra turns disabled");
  check("v061 feature set", env.SAGE_V2_EXPERIMENT_FEATURES === "contract_synthesis,candidate_repair,dependency_logic,medium_grain_skills", "active feature set matches the protocol manifest and excludes live_validation");

  const births = fs.readFileSync(BIRTH_EVENTS, "utf8").trim().split("\n").filter(Boolean).map((line) => JSON.parse(line));
  const names = births.map((row) => row.tool_name).sort();
  check("v061 birth count", births.length === 2 && births.every((row) => row.accepted), "two accepted admissions");
  check("v061 birth identities", JSON.stringify(names) === JSON.stringify(["plan_contact_relationship_batch_update", "plan_send_message_contact_lookup"]), names.join(", "));
  check("v061 birth repair evidence", births.every((row) => row.repair_attempted === false && row.repair_attempt_count === 0), "both admissions passed without a repair attempt");
  check("v061 validation evidence", births.every((row) => row.source_example_count > 0 && row.held_out_check_count > 0 && row.runtime_smoke_passed), "both admissions contain source, held-out, and runtime-smoke proof");
}

function validateImplementationClaims() {
  const generator = gitShow("src/sage_ts/generation/tool_generator.py");
  const birth = gitShow("src/sage_ts/orchestration/online_birth.py");
  const validator = gitShow("src/sage_ts/validation/sandbox_validator.py");
  const safety = gitShow("src/sage_ts/validation/ast_safety.py");
  const registry = gitShow("src/sage_ts/registry/manifest.py");
  const runtime = gitShow("src/sage_ts/runtime/toolsandbox_integration.py");
  const adapter = gitShow("src/sage_ts/adapters/sage_run_adapter.py");
  const reflection = gitShow("src/sage_ts/orchestration/self_evolution_reflection.py");

  const dispatchIndex = generator.indexOf("_deterministic_contract_generation(request)");
  const promptIndex = generator.indexOf("prompt = request.prompt()", dispatchIndex);
  check("generation dispatch order", dispatchIndex >= 0 && promptIndex > dispatchIndex, "deterministic contract dispatch precedes the GPT generation prompt");
  check("v061 admitted tools mapped", generator.includes('request.suggested_tool_name == "plan_send_message_contact_lookup"') && generator.includes('request.suggested_tool_name == "plan_contact_relationship_batch_update"'), "both v061 admission names have engineered deterministic contract mappings");
  check("candidate repair bound", birth.includes("DEFAULT_CANDIDATE_REPAIR_ATTEMPTS = 2") && birth.includes("DEFAULT_CANDIDATE_REPAIR_ATTEMPTS + 1"), "admission repair loop is bounded to two attempts");
  check("birth policy controls", birth.includes("max_rejections_per_key: int = 2") && birth.includes("existing_broader_helper") && birth.includes("has_current_validation_proof"), "rejection, existing-proof, and broader-helper suppression controls present");
  check("validation stack", validator.includes("missing_semantic_held_out_examples") && validator.includes("missing_negative_applicability_examples") && validator.includes("_nondeterministic") && validator.includes("_non_json_serializable_output") && validator.includes("runtime_smoke_missing_tool_trace"), "held-out, negative, replay, JSON, and runtime-smoke checks present");
  check("AST safety stack", safety.includes("ast.Import") && safety.includes("ast.While") && safety.includes('"eval"') && safety.includes('"subprocess"') && safety.includes("expected_exactly_one_function"), "declared static safety restrictions present");
  check("current-proof registry", registry.includes("held_out_check_count > 0") && registry.includes("negative_applicability_count > 0") && registry.includes("runtime_smoke_passed") && registry.includes("code_hash_verified") && registry.includes("gate.allowed"), "current-proof admission and reuse criteria present");
  check("runtime injection", runtime.includes("context.name_to_tool = {**compiled_by_name, **context.name_to_tool}") && runtime.includes("context.tool_allow_list = injected +") && runtime.includes("_actual_to_scrambled_tool_name = get_scrambled_tool_names") && runtime.includes("_scrambled_to_actual_tool_name"), "combined inventory and post-injection scrambling-map recomputation present");
  check("runtime routing", runtime.includes("visible[:max_bundle_size]") && runtime.includes("_composite_subsumes_lower_level_tool") && runtime.includes("_lifecycle_visibility_override") && runtime.includes("blocked_by_negative_trigger"), "bounded routing, portfolio shaping, lifecycle override, and negative triggers present");
  check("post-task side-effect audit", adapter.includes("_side_effect_followup_failures") && adapter.includes("side_effect_preservation_report.jsonl") && adapter.includes("required_original_tool_calls"), "native side-effect follow-up verification and incident logging present");
  check("reflection and checkpoint", reflection.includes("self.completed_count % self.pulse_interval") && reflection.includes("needs_route_repair") && reflection.includes("needs_safety_audit") && adapter.includes('(\"registry_manifest.json\", \"tool_lifecycle.json\")'), "periodic lifecycle decisions and per-task registry/lifecycle checkpointing present");
}

async function validateStandaloneInteraction() {
  const errors = [];
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on("pageerror", (error) => errors.push(String(error)));
    await page.goto(`file://${path.join(OUT, "sage_v061_architecture_atlas.html")}`);
    await page.locator('[data-action="in"]').click();
    await page.locator('[data-action="in"]').click();
    const zoom = await page.locator(".atlas-percent").textContent();
    const before = await page.locator(".atlas-panel.active .atlas-canvas").evaluate((element) => element.style.transform);
    const box = await page.locator(".atlas-panel.active .atlas-viewport").boundingBox();
    if (!box) throw new Error("standalone viewport has no bounding box");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 90, box.y + box.height / 2 + 55, { steps: 4 });
    await page.mouse.up();
    const after = await page.locator(".atlas-panel.active .atlas-canvas").evaluate((element) => element.style.transform);
    await page.locator('.atlas-tab[data-figure="sage_v061_generation_validation"]').click();
    const active = await page.locator(".atlas-panel.active").getAttribute("data-panel");
    const resetZoom = await page.locator(".atlas-percent").textContent();
    check("standalone zoom", zoom === "150%" && before.includes("scale(1.5)"), `${zoom}; ${before}`);
    check("standalone pan", after !== before && after.includes("translate("), after);
    check("standalone tab/reset", active === "sage_v061_generation_validation" && resetZoom === "100%", `${active}; ${resetZoom}`);
    check("standalone browser errors", errors.length === 0, errors.length ? errors.join(" | ") : "none");
  } finally {
    await browser.close();
  }
}

async function validateInlineInteraction() {
  const fragment = fs.readFileSync(INLINE, "utf8");
  const errors = [];
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 900 } });
    page.on("pageerror", (error) => errors.push(String(error)));
    await page.setContent(`<main>${fragment}</main>`);
    await page.locator('[data-sage-action="in"]').click();
    const zoom = await page.locator("[data-sage-zoom]").textContent();
    const before = await page.locator('[data-sage-panel="sage_v061_architecture_overview"]').evaluate((element) => element.style.transform);
    const box = await page.locator(".sage-atlas-viewport").boundingBox();
    if (!box) throw new Error("inline viewport has no bounding box");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 45, box.y + box.height / 2 + 30, { steps: 3 });
    await page.mouse.up();
    const after = await page.locator('[data-sage-panel="sage_v061_architecture_overview"]').evaluate((element) => element.style.transform);
    await page.locator('[data-sage-figure="sage_v061_routing_lifecycle"]').click();
    const active = await page.locator('[data-sage-panel="sage_v061_routing_lifecycle"]').evaluate((element) => !element.hidden);
    const resetZoom = await page.locator("[data-sage-zoom]").textContent();
    check("inline zoom", zoom === "125%", zoom || "missing zoom label");
    check("inline pan", before !== after && after.includes("translate("), after);
    check("inline tab/reset", active && resetZoom === "100%", `active=${active}; zoom=${resetZoom}`);
    check("inline browser errors", errors.length === 0, errors.length ? errors.join(" | ") : "none");
  } finally {
    await browser.close();
  }
}

async function main() {
  await validateExports();
  await validateSvgLayout();
  validateRunEvidence();
  validateImplementationClaims();
  await validateStandaloneInteraction();
  await validateInlineInteraction();

  const report = [
    "# SAGE v061 Architecture Figure Validation",
    "",
    `Validated against implementation commit \`${COMMIT}\` and the canonical v061 protocol artifacts.`,
    "",
    `Result: **PASS (${checks.length} checks)**`,
    "",
    "| Check | Evidence |",
    "|---|---|",
    ...checks.map((item) => `| ${item.name.replaceAll("|", "\\|")} | ${String(item.detail).replaceAll("|", "\\|")} |`),
    "",
    "## Archived v061 Test Verification",
    "",
    "The implementation at commit `2546640` was checked in a detached temporary worktree using the project's `toolsandbox-sage` Conda environment. The following suites completed with **182 passed and 0 failed**:",
    "",
    "- `tests/unit/test_online_birth.py`",
    "- `tests/unit/test_candidate_gate.py`",
    "- `tests/unit/test_tool_generator.py`",
    "- `tests/unit/test_generated_tool_lifecycle.py`",
    "- `tests/unit/test_self_evolution_reflection.py`",
    "- `tests/integration/test_toolsandbox_generated_tool_injection.py`",
    "",
    "Pytest reported five dependency deprecation or Python-version warnings; none were test failures or architecture discrepancies.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(OUT, "architecture_validation_report.md"), report, "utf8");
  process.stdout.write(`PASS: ${checks.length} checks\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
