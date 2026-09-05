"""Task-specific comparison dashboard template."""

from __future__ import annotations

TASK_COMPARE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Task Compare - SAGE</title>
  <style>
    :root {
      --bg: #0b1118;
      --panel: #111a24;
      --panel2: #172332;
      --panel3: #0f1722;
      --line: #2b3a4d;
      --text: #e7edf5;
      --muted: #93a4b8;
      --green: #41d996;
      --red: #ff6b73;
      --amber: #ffc857;
      --blue: #77bdff;
      --ink: #dce7f3;
      --shadow: rgba(0, 0, 0, .35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow-x: hidden;
    }
    button, input, select {
      font: inherit;
    }
    header {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 22px 14px;
      position: relative;
      z-index: 5;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
    }
    .title-line {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .env-badge {
      border: 1px solid #3f80bd;
      background: #102c45;
      color: #bfeaff;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .header-row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
    }
    .dashboard-switch {
      flex: 0 0 auto;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel2);
      color: var(--blue);
      padding: 7px 10px;
      font-size: 12px;
      font-weight: 800;
      min-width: 140px;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }
    .runtime-line { margin-top: 3px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 10px;
      max-width: 960px;
    }
	    .live-tool-panel {
	      display: none;
	      max-width: 960px;
	      margin-top: 10px;
	      border: 1px solid var(--line);
	      background: var(--panel2);
	      border-radius: 8px;
	      padding: 10px 12px;
	      box-shadow: 0 8px 22px var(--shadow);
	    }
	    .live-tool-panel.active {
	      display: block;
	    }
	    .live-tool-head {
	      display: flex;
	      justify-content: space-between;
	      gap: 12px;
	      align-items: baseline;
	      color: var(--muted);
	      font-size: 12px;
	    }
	    .live-tool-head strong {
	      color: var(--text);
	      font-size: 13px;
	      text-transform: uppercase;
	      letter-spacing: .06em;
	    }
	    .live-tool-table {
	      width: 100%;
	      border-collapse: collapse;
	      margin-top: 8px;
	      font-size: 12px;
	      font-variant-numeric: tabular-nums;
	    }
	    .live-tool-table th,
	    .live-tool-table td {
	      border-top: 1px solid var(--line);
	      padding: 6px 5px;
	      text-align: left;
	      vertical-align: top;
	    }
	    .live-tool-table th {
	      color: var(--muted);
	      font-size: 10px;
	      text-transform: uppercase;
	      letter-spacing: .06em;
	    }
    .live-tool-name {
      max-width: 270px;
      overflow-wrap: anywhere;
      color: var(--ink);
      font-weight: 750;
    }
    .header-dashboard-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 360px);
      gap: 12px;
      align-items: start;
      margin-top: 12px;
      min-width: 0;
      max-width: 100%;
    }
    .summary-stack {
      min-width: 0;
      max-width: 100%;
    }
    .sage-status-stack {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .sage-thinking-box {
      width: 100%;
      margin-top: 12px;
      border: 1px solid rgba(119, 189, 255, .38);
      background:
        linear-gradient(90deg, rgba(119, 189, 255, .10), rgba(65, 217, 150, .08), rgba(119, 189, 255, .10)),
        var(--panel2);
      background-size: 240% 100%, auto;
      border-radius: 8px;
      padding: 16px 36px 16px 24px;
      box-shadow: 0 8px 22px var(--shadow);
      display: grid;
      align-content: center;
      gap: 8px;
      height: 126px;
      min-height: 126px;
      max-height: 126px;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
      position: relative;
      animation: sageStatusPanelFlow 5.6s ease-in-out infinite;
    }
    .sage-thinking-box::before {
      content: "";
      position: absolute;
      left: 10px;
      top: 14px;
      width: 4px;
      height: calc(100% - 28px);
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(119, 189, 255, .18), rgba(119, 189, 255, .82), rgba(65, 217, 150, .24));
      animation: sageStatusScan 1.8s ease-in-out infinite;
    }
    .sage-thinking-box::after {
      content: "";
      position: absolute;
      right: 12px;
      top: 12px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: rgba(119, 189, 255, .92);
      box-shadow: 0 0 0 0 rgba(119, 189, 255, .46);
      animation: sageStatusPulse 1.6s ease-out infinite;
    }
    .sage-thinking-title {
      color: var(--blue);
      font-size: 11px;
      font-weight: 950;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .sage-thinking-text {
      color: var(--text);
      font-size: 13px;
      font-weight: 750;
      line-height: 1.35;
      max-width: 1120px;
      overflow-wrap: anywhere;
      word-break: normal;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
      padding-right: 10px;
    }
    @keyframes sageStatusPanelFlow {
      0%, 100% { background-position: 0% 50%, 0 0; }
      50% { background-position: 100% 50%, 0 0; }
    }
    @keyframes sageStatusScan {
      0%, 100% { opacity: .45; transform: scaleY(.72); }
      50% { opacity: 1; transform: scaleY(1); }
    }
    @keyframes sageStatusPulse {
      0% { box-shadow: 0 0 0 0 rgba(119, 189, 255, .44); }
      70% { box-shadow: 0 0 0 9px rgba(119, 189, 255, 0); }
      100% { box-shadow: 0 0 0 0 rgba(119, 189, 255, 0); }
    }
    .tool-generation-card {
      width: 280px;
      max-width: 100%;
      min-width: 0;
      min-height: 338px;
      border: 1px solid #3f80bd;
      background: linear-gradient(180deg, #162a3d 0%, #101a27 100%);
      color: var(--text);
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 8px 22px var(--shadow);
      text-align: left;
      cursor: pointer;
      display: grid;
      align-content: start;
      gap: 9px;
      overflow: hidden;
    }
    .tool-generation-card.state-idle,
    .tool-generation-card.state-scanning {
      border-color: #3f80bd;
      background: linear-gradient(180deg, #162a3d 0%, #101a27 100%);
    }
    .tool-generation-card.state-gap {
      border-color: rgba(119, 189, 255, .78);
      background: linear-gradient(180deg, #143453 0%, #101a27 100%);
    }
    .tool-generation-card.state-generating {
      border-color: rgba(255, 200, 87, .68);
      background: linear-gradient(180deg, #33270f 0%, #171c23 100%);
    }
    .tool-generation-card.state-validating {
      border-color: rgba(180, 151, 255, .72);
      background: linear-gradient(180deg, #2b2350 0%, #131b2a 100%);
    }
    .tool-generation-card.state-repairing {
      border-color: rgba(255, 143, 82, .76);
      background: linear-gradient(180deg, #3c2414 0%, #171a23 100%);
    }
    .tool-generation-card.state-using {
      border-color: rgba(65, 217, 150, .68);
      background: linear-gradient(180deg, #123827 0%, #101a24 100%);
    }
    .tool-generation-card.state-accepted {
      border-color: rgba(65, 217, 150, .68);
      background: linear-gradient(180deg, #123827 0%, #101a24 100%);
    }
    .tool-generation-card.state-complete {
      border-color: rgba(65, 217, 150, .72);
      background: linear-gradient(180deg, #102f27 0%, #101a24 100%);
    }
    .tool-generation-card.state-rejected {
      border-color: rgba(255, 107, 115, .72);
      background: linear-gradient(180deg, #3a171d 0%, #171a23 100%);
    }
    .tool-generation-card:hover,
    .tool-generation-card:focus-visible {
      outline: 2px solid rgba(119, 189, 255, .55);
      outline-offset: 2px;
    }
    .tool-gen-stage {
      color: var(--blue);
      font-size: 11px;
      font-weight: 950;
      letter-spacing: .08em;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }
    .tool-gen-status-main {
      color: var(--text);
      font-size: 25px;
      font-weight: 950;
      line-height: 1.05;
      overflow-wrap: anywhere;
    }
    .state-repairing .tool-gen-status-main { color: #ffbf95; }
    .state-validating .tool-gen-status-main { color: #d0c2ff; }
    .state-generating .tool-gen-status-main,
    .state-gap .tool-gen-status-main { color: var(--amber); }
    .state-accepted .tool-gen-status-main,
    .state-complete .tool-gen-status-main,
    .state-using .tool-gen-status-main { color: var(--green); }
    .state-rejected .tool-gen-status-main { color: var(--red); }
    .tool-gen-kicker {
      color: var(--muted);
      font-size: 10px;
      font-weight: 950;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .tool-gen-title {
      color: var(--text);
      font-size: 18px;
      font-weight: 900;
      line-height: 1.08;
      overflow-wrap: anywhere;
      min-width: 0;
    }
    .tool-gen-body {
      color: var(--ink);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
      min-width: 0;
    }
    .tool-gen-purpose {
      border: 1px solid rgba(255,255,255,.08);
      background: rgba(10, 16, 24, .36);
      border-radius: 8px;
      padding: 9px;
      color: var(--ink);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .tool-gen-step-row {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.3;
    }
    .tool-gen-step-row strong {
      color: var(--text);
      font-size: 12px;
    }
    .tool-gen-timeline {
      display: grid;
      gap: 6px;
      margin-top: 2px;
    }
    .tool-gen-timeline-row {
      display: grid;
      grid-template-columns: 14px minmax(0, 1fr);
      gap: 7px;
      align-items: start;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
      min-width: 0;
    }
    .tool-gen-timeline-dot {
      width: 9px;
      height: 9px;
      margin-top: 3px;
      border-radius: 50%;
      border: 1px solid rgba(147, 164, 184, .55);
      background: rgba(147, 164, 184, .22);
    }
    .tool-gen-timeline-row.done .tool-gen-timeline-dot {
      border-color: rgba(65, 217, 150, .72);
      background: rgba(65, 217, 150, .85);
    }
    .tool-gen-timeline-row.current .tool-gen-timeline-dot {
      border-color: rgba(255, 200, 87, .9);
      background: var(--amber);
      box-shadow: 0 0 0 4px rgba(255, 200, 87, .16);
    }
    .tool-gen-timeline-row.next .tool-gen-timeline-dot {
      border-style: dashed;
    }
    .tool-gen-timeline-label {
      color: var(--text);
      font-weight: 850;
      overflow-wrap: anywhere;
    }
    .tool-gen-timeline-detail {
      color: var(--muted);
      margin-top: 1px;
      overflow-wrap: anywhere;
    }
    .tool-gen-meta {
      display: grid;
      gap: 5px;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      font-variant-numeric: tabular-nums;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .tool-gen-status-pill {
      display: inline-flex;
      width: fit-content;
      border: 1px solid rgba(65, 217, 150, .45);
      background: rgba(13, 45, 32, .75);
      color: var(--green);
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 10px;
      font-weight: 950;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    .tool-gen-status-pill.idle {
      border-color: rgba(119, 189, 255, .46);
      background: rgba(16, 44, 69, .78);
      color: var(--blue);
    }
    .tool-gen-status-pill.warn {
      border-color: rgba(255, 200, 87, .48);
      background: rgba(49, 37, 13, .82);
      color: var(--amber);
    }
    .tool-gen-status-pill.validating {
      border-color: rgba(180, 151, 255, .48);
      background: rgba(40, 31, 79, .82);
      color: #c8b8ff;
    }
    .tool-gen-status-pill.repairing {
      border-color: rgba(255, 143, 82, .52);
      background: rgba(58, 31, 16, .82);
      color: #ffb17f;
    }
    .tool-gen-status-pill.bad {
      border-color: rgba(255, 107, 115, .48);
      background: rgba(55, 18, 24, .82);
      color: var(--red);
    }
    .tool-gen-detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .tool-gen-detail-card {
      border: 1px solid var(--line);
      background: var(--panel3);
      border-radius: 8px;
      padding: 10px;
      min-width: 0;
    }
    .tool-gen-detail-card h3 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .tool-gen-code {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0a1018;
      color: var(--ink);
      max-height: 440px;
      overflow: auto;
      padding: 12px;
      white-space: pre;
      font-size: 12px;
      line-height: 1.35;
    }
    .tool-gen-drawer-timeline {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .tool-gen-drawer-timeline .tool-gen-timeline-row {
      border: 1px solid var(--line);
      background: var(--panel3);
      border-radius: 8px;
      padding: 9px;
      grid-template-columns: 16px minmax(0, 1fr);
    }
	    .run-progress {
	      display: inline-flex;
	      align-items: baseline;
	      gap: 10px;
      margin-top: 12px;
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 999px;
      padding: 7px 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .run-progress .label {
      font-size: 10px;
    }
    .run-progress strong {
      color: var(--text);
      font-size: 15px;
      font-variant-numeric: tabular-nums;
    }
    .metric {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 8px;
      padding: 10px 12px;
      min-height: 78px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .metric.clickable {
      cursor: pointer;
      border-color: #3f80bd;
      background: #162a3d;
    }
    .label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .value {
      font-size: 24px;
      font-weight: 800;
      margin-top: 8px;
      font-variant-numeric: tabular-nums;
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      line-height: 1.3;
    }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .warn { color: var(--amber); }
    .neutral { color: var(--muted); }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      min-height: calc(100vh - 150px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #0d151f;
      padding: 14px;
      position: sticky;
      top: 12px;
      align-self: start;
      height: calc(100vh - 24px);
      overflow: auto;
    }
    .search {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      background: var(--panel);
      color: var(--text);
      margin-bottom: 10px;
    }
    .task-list {
      display: grid;
      gap: 6px;
    }
    .task-btn {
      width: 100%;
      text-align: left;
      border: 1px solid transparent;
      background: transparent;
      border-radius: 7px;
      padding: 8px;
      cursor: pointer;
      color: var(--text);
    }
    .task-btn:hover,
    .task-btn.active {
      background: #162a3d;
      border-color: #3f80bd;
    }
    .task-name {
      font-size: 13px;
      font-weight: 750;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: normal;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      line-height: 1.25;
    }
    .task-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 11px;
      margin-top: 3px;
      font-variant-numeric: tabular-nums;
    }
    .meta-pill {
      display: inline-flex;
      align-items: baseline;
      gap: 4px;
      min-width: 0;
    }
    .meta-label {
      color: var(--muted);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    .tool-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
      min-height: 18px;
    }
    .tool-chip {
      border: 1px solid #345371;
      background: #102337;
      color: var(--blue);
      border-radius: 999px;
      padding: 2px 6px;
      font-size: 10px;
      font-weight: 800;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tool-chip.born {
      border-color: #8b6b20;
      background: #31250d;
      color: var(--amber);
    }
    .tool-chip.called {
      border-color: #21794e;
      background: #0d2d20;
      color: var(--green);
    }
    .tool-chip.visible {
      color: #b7c8dc;
    }
    .tool-chip.observed {
      color: var(--muted);
    }
    .detail {
      padding: 18px 22px 28px;
      overflow: visible;
    }
    .section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .task-title {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }
    .task-title h2 {
      margin: 0;
      font-size: 26px;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }
    .pill {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .compare-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .mini {
      border: 1px solid var(--line);
      background: var(--panel3);
      border-radius: 8px;
      padding: 11px;
      min-height: 74px;
    }
    .mini .value { font-size: 21px; }
    .split {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .check-split {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
    }
    .transaction-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
    .transaction-head h3 { margin: 0; }
    .transaction-select { border: 1px solid var(--line); border-radius: 999px; background: var(--panel2); color: var(--blue); padding: 7px 10px; font-size: 12px; font-weight: 800; min-width: 150px; }
    .box {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel3);
      padding: 12px;
      min-height: 110px;
    }
    .box h3 {
      margin: 0 0 9px;
      font-size: 14px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .section-head h3 {
      margin: 0;
      font-size: 19px;
      letter-spacing: 0;
    }
    .check-explainer {
      max-width: 720px;
    }
    .check-summary {
      display: grid;
      gap: 10px;
    }
    .check-totals {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .check-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(15, 23, 34, .72);
      padding: 10px;
    }
    .check-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }
    .check-title {
      flex: 1 1 100%;
      min-width: 0;
      font-weight: 800;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .status-pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .05em;
      white-space: nowrap;
      align-self: flex-start;
    }
    .status-matched,
    .status-clear {
      border-color: rgba(65, 217, 150, .45);
      background: rgba(13, 45, 32, .8);
      color: var(--green);
    }
    .status-partial {
      border-color: rgba(255, 200, 87, .45);
      background: rgba(49, 37, 13, .8);
      color: var(--amber);
    }
    .status-missed,
    .status-triggered {
      border-color: rgba(255, 107, 115, .45);
      background: rgba(55, 18, 24, .8);
      color: var(--red);
    }
    .check-evidence {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 9px;
    }
    .evidence-block {
      min-width: 0;
      border-top: 1px solid rgba(43, 58, 77, .75);
      padding-top: 7px;
    }
    .evidence-label {
      color: var(--muted);
      font-size: 10px;
      font-weight: 900;
      letter-spacing: .07em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .evidence-line {
      color: var(--ink);
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .evidence-readable {
      border: 1px solid rgba(43, 58, 77, .65);
      background: rgba(17, 26, 36, .72);
      border-radius: 7px;
      padding: 7px;
      margin-bottom: 6px;
    }
    .evidence-main {
      color: var(--ink);
      font-size: 12px;
      font-weight: 750;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .evidence-kind {
      display: inline-block;
      border: 1px solid rgba(119, 189, 255, .32);
      background: rgba(16, 35, 55, .85);
      color: var(--blue);
      border-radius: 999px;
      padding: 1px 6px;
      margin-right: 5px;
      font-size: 9px;
      font-weight: 900;
      letter-spacing: .06em;
      text-transform: uppercase;
      vertical-align: 1px;
    }
    .evidence-kind.result {
      border-color: rgba(65, 217, 150, .35);
      background: rgba(13, 45, 32, .78);
      color: var(--green);
    }
    .evidence-kind.state {
      border-color: rgba(255, 200, 87, .35);
      background: rgba(49, 37, 13, .78);
      color: var(--amber);
    }
    .kv-row {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 5px;
    }
    .kv-chip {
      border: 1px solid #345371;
      background: #102337;
      color: #c9dbed;
      border-radius: 999px;
      padding: 2px 6px;
      font-size: 10px;
      font-weight: 750;
      max-width: 100%;
      overflow-wrap: anywhere;
    }
    .raw-evidence {
      margin-top: 5px;
      color: var(--muted);
      font-size: 10px;
    }
    .raw-evidence summary {
      cursor: pointer;
      width: max-content;
      color: var(--muted);
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .06em;
    }
    .raw-evidence pre {
      margin-top: 4px;
      max-height: 96px;
      overflow: auto;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.35;
    }
    .more-lines {
      color: var(--muted);
      font-size: 11px;
      margin-top: 3px;
    }
    .small {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      line-height: 1.45;
      color: var(--ink);
    }
    .transcript { max-height: 640px; overflow: auto; display: grid; gap: 8px; padding-right: 4px; }
    .msg { display: flex; }
    .msg.user, .msg.system, .msg.tool { justify-content: flex-start; }
    .msg.assistant { justify-content: flex-end; }
    .bubble { max-width: min(780px, 92%); border: 1px solid var(--line); border-radius: 13px; padding: 8px 12px; background: rgba(15,23,34,.9); }
    .msg.assistant .bubble { background: rgba(24,64,103,.78); border-color: rgba(119,189,255,.3); }
    .msg.tool .bubble { background: rgba(15,23,34,.9); border-color: var(--line); }
    .msg.generated-tool .bubble { background: rgba(12,49,42,.88); border-color: rgba(65,217,150,.38); box-shadow: 0 0 0 2px rgba(65,217,150,.25); }
    .msg-lbl { color: var(--muted); font-size: 10px; font-weight: 800; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .08em; }
    .tbadge { display: inline-block; margin: 0 5px 6px 0; border: 1px solid rgba(65,217,150,.45); border-radius: 999px; padding: 2px 7px; color: var(--green); font-size: 11px; font-weight: 800; }
    .empty-transcript { color: var(--muted); font-size: 13px; line-height: 1.5; }
    .message-text {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      line-height: 1.45;
      color: var(--ink);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .drawer {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, .62);
      z-index: 20;
      display: none;
    }
    .drawer.open {
      display: block;
    }
    .drawer-panel {
      margin-left: auto;
      width: min(900px, 94vw);
      height: 100%;
      background: var(--panel);
      border-left: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
    }
    .drawer-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }
    .close {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
    }
    .tool-code-link {
      appearance: none;
      border: 0;
      background: transparent;
      color: var(--ink);
      cursor: pointer;
      display: inline;
      font: inherit;
      font-weight: 800;
      padding: 0;
      text-align: left;
      overflow-wrap: anywhere;
    }
    .tool-code-link:hover,
    .tool-code-link:focus-visible {
      color: var(--blue);
      text-decoration: underline;
      outline: none;
    }
    .code-panel {
      width: min(1040px, 96vw);
    }
    .code-meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
    .code-explanation {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel2);
      color: var(--ink);
      font-size: 13px;
      line-height: 1.5;
      margin-bottom: 12px;
      padding: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .code-explanation-title {
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .08em;
      margin-bottom: 7px;
      text-transform: uppercase;
    }
    .code-block {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0a1018;
      color: var(--ink);
      max-height: calc(100vh - 150px);
      overflow: auto;
      padding: 14px;
      white-space: pre;
    }
    a {
      color: var(--blue);
      text-decoration: none;
    }
    @media (max-width: 1100px) {
      .metrics { grid-template-columns: repeat(3, minmax(140px, 1fr)); }
    }
    @media (max-width: 760px) {
      .metrics, .compare-grid, .split, .transaction-grid, .check-evidence { grid-template-columns: 1fr; }
      header { padding: 16px 12px 12px; }
      .header-dashboard-grid { grid-template-columns: minmax(0, 1fr); width: 100%; overflow: hidden; }
      .sage-status-stack { width: 100%; }
      .sage-thinking-box { height: 146px; min-height: 146px; max-height: 146px; padding-right: 30px; }
      .sage-thinking-text { -webkit-line-clamp: 5; }
      .tool-generation-card { width: 100%; min-height: 220px; }
      main { grid-template-columns: 1fr; }
      aside {
        position: relative;
        top: auto;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .task-list {
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      }
      .detail { padding: 14px; }
      header { position: relative; }
      .header-row { flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div>
        <div class="title-line">
          <h1>Task Compare</h1>
          <span class="env-badge" id="envBadge">ToolSandbox</span>
        </div>
        <div class="subtitle" id="subtitle">Loading run data...</div>
        <div class="subtitle runtime-line" id="runtimeLine"></div>
      </div>
    </div>
    <div class="sage-thinking-box" id="sageThinkingBox">
      <div class="sage-thinking-title">Agent Actions</div>
      <div class="sage-thinking-text" id="sageThinkingText" aria-live="polite">Waiting for live SAGE lifecycle events.</div>
    </div>
    <div class="header-dashboard-grid">
      <div class="summary-stack">
        <div class="run-progress" id="runProgress"></div>
        <div class="metrics" id="metrics"></div>
        <div class="metrics tool-metrics" id="toolMetrics"></div>
        <div class="live-tool-panel" id="liveToolPanel"></div>
      </div>
      <div class="sage-status-stack">
        <button type="button" class="tool-generation-card state-idle" id="toolGenerationCard">
          <div class="tool-gen-stage" id="toolGenStage">Current Lifecycle Status</div>
          <div class="tool-gen-status-main" id="toolGenStatusMain">Monitoring</div>
          <div>
            <div class="tool-gen-kicker">Tool</div>
            <div class="tool-gen-title" id="toolGenTitle">Waiting for tool activity</div>
          </div>
          <div class="tool-gen-purpose" id="toolGenPurpose">Waiting for the next gap, generated tool, or validation event.</div>
          <div class="tool-gen-step-row">
            <strong id="toolGenCurrentStep">Current step: waiting</strong>
            <span id="toolGenNextStep">Next: watch for a generated-tool lifecycle event.</span>
          </div>
          <div class="tool-gen-timeline" id="toolGenTimeline"></div>
          <div class="tool-gen-status-pill" id="toolGenStatus">Idle</div>
          <div class="tool-gen-meta" id="toolGenMeta"></div>
        </button>
      </div>
    </div>
	  </header>
  <main>
    <aside>
      <input id="search" class="search" placeholder="Filter tasks" />
      <div class="task-list" id="taskList"></div>
    </aside>
    <section class="detail" id="detail"></section>
  </main>
  <div class="drawer" id="toolDrawer" aria-hidden="true">
    <div class="drawer-panel">
      <div class="drawer-head">
        <div>
          <h2 style="margin:0">Generated And Retained Tools</h2>
          <div class="small" id="toolDrawerSub"></div>
        </div>
        <button class="close" id="closeTools">Close</button>
      </div>
      <div id="toolTable"></div>
    </div>
  </div>
  <div class="drawer" id="toolCodeDrawer" aria-hidden="true">
    <div class="drawer-panel code-panel">
      <div class="drawer-head">
        <div>
          <h2 id="toolCodeTitle" style="margin:0">Tool Code</h2>
          <div class="code-meta" id="toolCodeMeta"></div>
        </div>
        <button class="close" id="closeToolCode">Close</button>
      </div>
      <div class="code-explanation">
        <div class="code-explanation-title">Explanation</div>
        <div id="toolCodeExplanation"></div>
      </div>
      <pre class="code-block" id="toolCodeBlock"></pre>
    </div>
  </div>
  <div class="drawer" id="toolGenerationDrawer" aria-hidden="true">
    <div class="drawer-panel code-panel">
      <div class="drawer-head">
        <div>
          <h2 style="margin:0">SAGE Tool Generation Status</h2>
          <div class="code-meta" id="toolGenerationSub"></div>
        </div>
        <button class="close" id="closeToolGeneration">Close</button>
      </div>
      <div id="toolGenerationDetail"></div>
    </div>
  </div>
  <script>
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    function envDisplayName(value) {
      const raw = String(value || "ToolSandbox").trim();
      const normalized = raw.toLowerCase().replaceAll("_", "-");
      if (normalized.includes("toolsandbox")) return "ToolSandbox";
      if (normalized.includes("minigrid")) return "MiniGrid";
      return raw ? raw.replaceAll("-", " ") : "ToolSandbox";
    }
    const finite = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
    const pct = (v) => finite(v) ? (Number(v) * 100).toFixed(1) + "%" : "-";
    const ZERO_BASELINE_LIFT_FLOOR = 0.1;
    const signedPct = (v) => finite(v) ? (Number(v) >= 0 ? "+" : "") + (Number(v) * 100).toFixed(1) + "%" : "-";
    const liftPct = (v, approximate = false) => {
      const rendered = signedPct(v);
      return approximate && rendered !== "-" ? `~${rendered}` : rendered;
    };
    const num = (v, d = 3) => finite(v) ? Number(v).toFixed(d) : "-";
    const signedNum = (v, d = 3) => finite(v) ? (Number(v) >= 0 ? "+" : "") + Number(v).toFixed(d) : "-";
    const intNum = (v) => finite(v) ? new Intl.NumberFormat("en-US", {maximumFractionDigits: 0}).format(Number(v)) : "-";
    const tokenNum = (v) => {
      if (!finite(v)) return "-";
      const n = Number(v);
      if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
      if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}K`;
      return intNum(n);
    };
    const durationText = (seconds) => {
      if (!finite(seconds)) return "N/A";
      const total = Math.max(0, Math.round(Number(seconds)));
      const hours = Math.floor(total / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      const secs = total % 60;
      if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
      if (minutes > 0) return `${minutes}m ${String(secs).padStart(2, "0")}s`;
      return `${secs}s`;
    };
    const llmRecorded = (rowOrSummary, prefix = "") => {
      const key = prefix ? `${prefix}_llm_usage_recorded` : "llm_usage_recorded";
      const callsKey = prefix ? `${prefix}_llm_call_count` : "llm_call_count";
      const tokensKey = prefix ? `${prefix}_llm_total_tokens` : "llm_total_tokens";
      return Boolean(rowOrSummary?.[key]) || finite(rowOrSummary?.[callsKey]) || finite(rowOrSummary?.[tokensKey]);
    };
    const llmPairValue = (controlValue, candidateValue, formatter) => `${formatter(controlValue)} / ${formatter(candidateValue)}`;
    const totalTimePairValue = (summary) => {
      return `${durationText(summary.control_wall_time_seconds)} / ${durationText(summary.candidate_wall_time_seconds)}`;
    };
    const totalTimeHint = (summary) => {
      const baselineNote = finite(summary.control_wall_time_seconds)
        ? "baseline wall time"
        : "baseline time not recorded";
      const sageNote = finite(summary.candidate_wall_time_seconds)
        ? finite(summary.candidate_wall_time_resume_offset_seconds) && Number(summary.candidate_wall_time_resume_offset_seconds) > 0
          ? "SAGE wall time including checkpoint"
          : "SAGE wall time"
        : "SAGE time not recorded";
      return `${baselineNote}; ${sageNote}`;
    };
    const relLift = (delta, baseline) => {
      if (!finite(delta) || !finite(baseline)) return null;
      const d = Number(delta);
      const b = Number(baseline);
      if (Math.abs(b) > 1e-12) return d / b;
      if (Math.abs(d) <= 1e-12) return 0;
      return d / ZERO_BASELINE_LIFT_FLOOR;
    };
    const approxZeroBaselineLift = (delta, baseline) => finite(delta) && finite(baseline) && Math.abs(Number(baseline)) <= 1e-12 && Math.abs(Number(delta)) > 1e-12;
    const liftHint = (delta, baseline, unit) => {
      if (approxZeroBaselineLift(delta, baseline)) {
        return `approx using 0.100 floor; true baseline is 0; ${signedNum(delta)} ${unit} absolute lift`;
      }
      return `${signedNum(delta)} ${unit} delta`;
    };
    const formatRuntimeLine = () => {
      const raw = payload?.runtime_at || payload?.created_at || payload?.started_at || payload?.start_time || payload?.run_started_at || payload?.summary?.created_at || "";
      if (!raw) return "";
      const date = new Date(raw);
      if (Number.isNaN(date.getTime())) return "";
      const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
        timeZone: "America/New_York",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      }).formatToParts(date).map((part) => [part.type, part.value]));
      return `Runtime: ${parts.hour}${parts.minute}, ${parts.day} ${parts.month} ${parts.year}`;
    };
    const cls = (v) => {
      const numeric = Number(v);
      if (!Number.isFinite(numeric)) return "";
      if (Math.abs(numeric) <= 1e-12) return "neutral";
      return numeric > 0 ? "good" : "bad";
    };
    const outcome = (row) => row?.outcome_similarity ?? null;
    const armLabel = (arm) => String(
      payload?.arm_labels?.[arm]
        || (arm === "control" ? "Non-learning" : "SAGE")
    );
    const completeStatus = (row) => row?.status === "complete" || row?.status === "done";
    const toolEvents = (pair) => pair?.candidate?.generated_tool_events || pair?.candidate?.generated_tools?.map((tool) => ({kind: "called", tool})) || [];
    const toolEventLabel = (event) => `${event.kind || "tool"}: ${event.tool || ""}`;
    const compactToolName = (name) => String(name || "").replace(/^.*:/, "").replace(/_/g, " ");
    const mean = (values) => {
      const nums = values.filter(finite).map(Number);
      return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
    };
    const pairedMetricRows = () => pairs.filter((pair) => completeStatus(pair.control) && completeStatus(pair.candidate));
    function pairedMetrics(summary) {
      const paired = pairedMetricRows();
      const outcomeRows = paired.filter((pair) => finite(outcome(pair.control)) && finite(outcome(pair.candidate)));
      const baselineOutcome = mean(outcomeRows.map((pair) => outcome(pair.control)));
      const sageOutcome = mean(outcomeRows.map((pair) => outcome(pair.candidate)));
      return {
        pairedCount: paired.length,
        outcomeCount: outcomeRows.length,
        baselineOutcome: baselineOutcome ?? summary.balanced_control_mean_outcome_similarity ?? null,
        sageOutcome: sageOutcome ?? summary.balanced_candidate_mean_outcome_similarity ?? null,
      };
    }
    let payload = null;
    let pairs = [];
    let selected = 0;
    let transactionArm = "candidate";
    let handlersBound = false;
    let refreshTimer = null;
    let toolGenerationRefreshTimer = null;
    let lastAgentActionText = "";
    let lastAgentActionRenderedAt = 0;
    const AGENT_ACTION_MIN_DISPLAY_MS = 5000;
    let toolGenerationStatus = {
      state: "idle",
      stage: "SAGE Tool Generation",
      title: "Monitoring",
      body: "Waiting for the next gap, generated tool, or validation event.",
      thinkingText: "Waiting for live SAGE lifecycle events.",
      meta: [],
      details: [],
      code: "",
      toolName: "",
    };

    function metric(label, value, hint, className = "", clickable = false) {
      return `<div class="metric ${clickable ? "clickable" : ""}" ${clickable ? 'id="toolsMetric" role="button" tabindex="0"' : ""}>
        <div class="label">${esc(label)}</div>
        <div class="value ${className}">${esc(value)}</div>
        <div class="hint">${esc(hint)}</div>
      </div>`;
    }

	    function renderToolSummaryPanel() {
	      const panel = document.getElementById("liveToolPanel");
	      if (!panel) return;
	      const tools = payload?.tool_summary || {};
	      const rows = Array.isArray(tools.tools) ? tools.tools : [];
	      if (!rows.length) {
	        panel.innerHTML = "";
	        panel.classList.remove("active");
	        return;
	      }
	      const topRows = rows.slice(0, 8).map((tool) => `<tr>
	        <td class="live-tool-name">${toolNameButton(tool)}<div class="small">${esc(tool.decision || "")}</div></td>
	        <td>${esc(maybeValue(tool.visible_count, "pending"))}</td>
	        <td>${esc(tool.called_count ?? 0)}</td>
	        <td class="${cls(tool.called_subset_mean_outcome_delta)}">${esc(contributionDeltaText(tool))}</td>
	        <td>${esc(gainLossText(tool.outcome_gains, tool.outcome_regressions, tool.contribution_pending))}</td>
	        <td>${esc(tool.side_effect_incident_count ?? 0)} safety<br><span class="small">${esc(tool.runtime_incident_count ?? 0)} runtime</span></td>
	      </tr>`).join("");
	      const visibilitySummary = tools.visible_tool_count === null || tools.visible_tool_count === undefined
	        ? "visibility pending"
	        : `${intNum(tools.visible_tool_count)} visible`;
	      const contributionSummary = tools.outcome_gains === null || tools.outcome_gains === undefined || tools.outcome_regressions === null || tools.outcome_regressions === undefined
	        ? "contribution pending"
	        : `${intNum(tools.outcome_gains)} gains / ${intNum(tools.outcome_regressions)} regressions`;
	      const summary = [
	        visibilitySummary,
	        `${intNum(tools.called_tool_count ?? 0)} called`,
	        contributionSummary,
	        `${intNum(tools.side_effect_incident_count ?? 0)} safety rows`,
	        `${intNum(tools.runtime_incident_count ?? 0)} runtime incidents`,
	      ].join(" / ");
	      panel.innerHTML = `<div class="live-tool-head"><strong>Live Tool Contribution</strong><span>${esc(summary)}</span></div>
	        <table class="live-tool-table">
	          <thead><tr><th>Tool</th><th>Visible</th><th>Called</th><th>Outcome Delta</th><th>Gain / Regression</th><th>Safety</th></tr></thead>
	          <tbody>${topRows}</tbody>
	        </table>`;
	      panel.classList.add("active");
	    }

	    function toolNameButton(tool) {
	      const name = tool?.name || "-";
	      return `<button type="button" class="tool-code-link" data-tool-code-name="${esc(name)}">${esc(name)}</button>`;
	    }

	    function maybeValue(value, missingLabel) {
	      return value === null || value === undefined ? (missingLabel || "n/a") : value;
    }

    function contributionDeltaText(tool) {
      if (tool?.contribution_pending) return "pending";
      return signedNum(tool?.called_subset_mean_outcome_delta);
    }

    function gainLossText(gains, regressions, pending) {
      if (pending) return "pending";
      if (gains === null && regressions === null) return "n/a";
      if (gains === undefined && regressions === undefined) return "n/a";
      return `${gains ?? 0} gains / ${regressions ?? 0} regressions`;
    }

    function runRootPath() {
      return String(payload?.run_root || ".").replace(/\/+$/, "");
    }

    function candidateRunDir() {
      return payload?.arm_progress?.candidate?.run_dir || null;
    }

    function relativeToDashboard(path) {
      const root = runRootPath();
      if (!path) return null;
      const value = String(path);
      if (value.startsWith(root + "/")) return "../" + value.slice(root.length + 1);
      if (value.startsWith("outputs/")) return null;
      return value;
    }

    async function fetchTextMaybe(path) {
      const rel = relativeToDashboard(path);
      if (!rel) return "";
      try {
        const response = await fetch(`${rel}?ts=${Date.now()}`, {cache: "no-store"});
        if (!response.ok) return "";
        return await response.text();
      } catch {
        return "";
      }
    }

    function parseJsonLines(text) {
      return String(text || "")
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          try { return JSON.parse(line); } catch { return null; }
        })
        .filter(Boolean);
    }

    function statusLabelForState(state) {
      const labels = {
        idle: "Waiting",
        scanning: "Scanning",
        gap: "Gap Found",
        generating: "Generating",
        validating: "Validating",
        repairing: "Repairing",
        accepted: "Accepted",
        rejected: "Blocked",
        using: "Using Tool",
        complete: "Complete",
      };
      return labels[state] || "Monitoring";
    }

    function toolGenerationStateClass(state) {
      if (state === "accepted") return "state-accepted";
      if (state === "rejected") return "state-rejected";
      if (state === "gap") return "state-gap";
      if (state === "generating") return "state-generating";
      if (state === "validating") return "state-validating";
      if (state === "repairing") return "state-repairing";
      if (state === "using") return "state-using";
      if (state === "complete") return "state-complete";
      if (state === "scanning") return "state-scanning";
      return "state-idle";
    }

    function toolGenerationCardClass(state) {
      return `tool-generation-card ${toolGenerationStateClass(state)}`;
    }

    function toolGenerationStateForEvent(event) {
      const name = String(event?.event || "");
      if (name === "run_finished") return "complete";
      if (["validation_passed", "tool_birth_succeeded", "registry_saved", "registry_save"].includes(name)) return "accepted";
      if (["validation_failed", "tool_birth_rejected", "generation_error"].includes(name)) return "rejected";
      if (name === "jit_proactive_inadequacy_detected" || name === "proactive_inadequacy_detected") return "gap";
      if (name === "tool_birth_started" || name === "tool_generation_completed") return "generating";
      if (name === "validation_started") return "validating";
      if (name.startsWith("tool_repair")) return "repairing";
      if (name === "generated_tool_invoked" || name === "jit_birth_tools_available_for_same_task") return "using";
      if (name.includes("skipped") || name.includes("reflection_completed")) return "scanning";
      if (event?.accepted === true) return "accepted";
      if (event?.accepted === false) return "rejected";
      return "idle";
    }

    function humanToolStage(event) {
      if (!event) return "Monitoring";
      if (!event.event && event.scenario) return "Current task";
      if (event.event === "run_finished") return "Run complete";
      if (event.accepted === true) return "Tool accepted";
      if (event.accepted === false) return "Validation rejected";
      if (event.event === "jit_proactive_inadequacy_detected") return "Gap identified";
      if (event.event === "proactive_inadequacy_detected") return "Gap identified";
      if (event.event === "tool_birth_started") return "Gap identified";
      if (event.event === "tool_generation_completed") return "Tool generated";
      if (event.event === "validation_started") return "Validation running";
      if (event.event === "tool_repair_started") return "Repair running";
      if (event.event === "tool_repair_attempted") return "Repair checked";
      if (event.event === "validation_passed") return "Tool accepted";
      if (event.event === "validation_failed") return "Validation rejected";
      if (event.event === "tool_birth_succeeded") return "Tool stored";
      if (event.event === "tool_birth_rejected") return "Birth rejected";
      if (event.event === "registry_saved") return "Registry updated";
      if (event.event === "registry_save") return "Tool stored";
      if (event.event === "generated_tool_invoked") return "Generated tool in use";
      if (event.event === "jit_birth_tools_available_for_same_task") return "Tool ready for task";
      if (event.event === "jit_proactive_scenario_reflection_completed") return "Task scanned";
      if (String(event.event || "").includes("skipped")) return "Birth skipped";
      return event.event ? String(event.event).replaceAll("_", " ") : "Tool generation";
    }

    function eventPriority(event) {
      const state = toolGenerationStateForEvent(event);
      const order = {
        complete: 100,
        rejected: 90,
        accepted: 80,
        repairing: 70,
        validating: 65,
        generating: 60,
        gap: 50,
        using: 45,
        scanning: 20,
        idle: 0,
      };
      return order[state] ?? 0;
    }

    function latestMeaningfulRunEvent(runEvents) {
      const noisy = new Set(["registry_checkpoint_written"]);
      for (let index = runEvents.length - 1; index >= 0; index -= 1) {
        const event = runEvents[index];
        if (!event || noisy.has(String(event.event || ""))) continue;
        return event;
      }
      return null;
    }

    function reuseEventForScenario(reuseEvents, scenario) {
      if (!scenario) return null;
      for (let index = reuseEvents.length - 1; index >= 0; index -= 1) {
        const event = reuseEvents[index];
        if (String(event?.scenario || "") === String(scenario)) return event;
      }
      return null;
    }

    function sameScenarioText(left, right) {
      const a = String(left || "").trim();
      const b = String(right || "").trim();
      return Boolean(a && b && (a === b || a.includes(b) || b.includes(a)));
    }

    function eventMatchesCurrentTask(event, current, liveStatus) {
      if (!event || !current?.scenario) return false;
      const currentScenario = current.scenario;
      const liveLabels = [
        liveStatus?.scenario,
        liveStatus?.task_context_label,
      ].filter(Boolean);
      const eventLabels = [
        event.scenario,
        event.birth_scenario,
        event.task_context_label,
      ].filter(Boolean);
      return eventLabels.some((label) => sameScenarioText(label, currentScenario))
        || eventLabels.some((label) => liveLabels.some((liveLabel) => sameScenarioText(label, liveLabel)));
    }

    function chooseCurrentToolLifecycleEvent({current, liveStatus, latestRunEvent, latestBirth, latestReuse}) {
      if (latestRunEvent?.event === "run_finished") {
        return {event: latestRunEvent, state: "complete"};
      }
      const liveState = liveStatus ? toolGenerationStateForEvent(liveStatus) : "idle";
      const birthState = latestBirth ? toolGenerationStateForEvent(latestBirth) : "idle";
      const activeBirthStates = new Set(["gap", "generating", "validating", "repairing"]);
      const terminalBirthStates = new Set(["accepted", "rejected"]);
      if (liveStatus && activeBirthStates.has(liveState) && eventMatchesCurrentTask(liveStatus, current, liveStatus)) {
        return {event: liveStatus, state: liveState};
      }
      if (latestBirth && activeBirthStates.has(birthState) && eventMatchesCurrentTask(latestBirth, current, liveStatus)) {
        return {event: latestBirth, state: birthState};
      }
      if (latestReuse) {
        return {event: latestReuse, state: "using"};
      }
      if (current?.scenario) {
        if (liveStatus && terminalBirthStates.has(liveState) && eventMatchesCurrentTask(liveStatus, current, liveStatus)) {
          return {event: liveStatus, state: liveState};
        }
        if (latestBirth && terminalBirthStates.has(birthState) && eventMatchesCurrentTask(latestBirth, current, liveStatus)) {
          return {event: latestBirth, state: birthState};
        }
        if (liveStatus && eventMatchesCurrentTask(liveStatus, current, liveStatus)) {
          return {event: liveStatus, state: liveState === "idle" ? "scanning" : liveState};
        }
        return {event: current, state: "scanning"};
      }
      const fallback = latestRunEvent || latestBirth || liveStatus;
      return {event: fallback, state: fallback ? toolGenerationStateForEvent(fallback) : "idle"};
    }

    function chooseToolTileLifecycleEvent({liveStatus, latestRunEvent, latestBirth, latestReuse}) {
      if (latestRunEvent?.event === "run_finished") {
        return {event: latestRunEvent, state: "complete"};
      }
      const activeStates = new Set(["gap", "generating", "validating", "repairing"]);
      const liveState = liveStatus ? toolGenerationStateForEvent(liveStatus) : "idle";
      const birthState = latestBirth ? toolGenerationStateForEvent(latestBirth) : "idle";
      if (liveStatus && activeStates.has(liveState)) return {event: liveStatus, state: liveState};
      if (latestBirth && activeStates.has(birthState)) return {event: latestBirth, state: birthState};
      if (latestReuse) return {event: latestReuse, state: "using"};
      const candidates = [liveStatus, latestBirth, latestRunEvent]
        .filter(Boolean)
        .filter((event) => {
          const state = toolGenerationStateForEvent(event);
          return !["idle", "scanning"].includes(state);
        });
      const event = candidates.length
        ? candidates.reduce((best, item) => eventPriority(item) >= eventPriority(best) ? item : best)
        : null;
      return {event, state: event ? toolGenerationStateForEvent(event) : "idle"};
    }

    function extractedRequestText(text) {
      const match = String(text || "").match(/request='([^']+)'/);
      return match?.[1] || "";
    }

    function taskKindLabel(name) {
      const request = extractedRequestText(name);
      if (request) {
        return request.length > 76 ? `the request "${request.slice(0, 73)}..."` : `the request "${request}"`;
      }
      const text = String(name || "").toLowerCase();
      if (text.includes("message") && text.includes("recency")) return "a message recency task";
      if (text.includes("message")) return "a message task";
      if (text.includes("reminder") && text.includes("recency")) return "a reminder recency task";
      if (text.includes("reminder")) return "a reminder task";
      if (text.includes("relationship")) return "a contact relationship task";
      if (text.includes("phone")) return "a phone-number lookup task";
      if (text.includes("contact")) return "a contact task";
      if (text.includes("wifi") || text.includes("cellular") || text.includes("battery") || text.includes("location")) return "a device status task";
      return "the current task";
    }

    function compactScenarioName(name) {
      return taskKindLabel(name);
    }

    function conciseGapText(event) {
      const raw = event?.observation_reason || event?.canonical_key || event?.gap || "";
      const text = String(raw).replace("visible_task_context:", "").trim();
      if (!text) return "";
      return text.length > 70 ? `${text.slice(0, 67)}...` : text;
    }

    function toolNameForLifecycleEvent(event) {
      if (event?.tool_name) return String(event.tool_name);
      const key = String(event?.canonical_key || "");
      if (key.includes(":")) return key.split(":").pop();
      return key;
    }

    function lifecycleStatusHeadline(event, state) {
      const name = String(event?.event || "");
      if (name === "tool_repair_started") return "Tool Repair Started";
      if (name === "tool_repair_attempted") return "Repair Attempt Checked";
      if (state === "repairing") return "Tool Repair Running";
      if (name === "validation_started" || state === "validating") return "Validation Running";
      if (name === "tool_generation_completed") return "Tool Draft Generated";
      if (name === "tool_birth_started" || state === "generating") return "Tool Generation Started";
      if (name === "jit_proactive_inadequacy_detected" || name === "proactive_inadequacy_detected" || state === "gap") return "Gap Identified";
      if (event?.accepted === true || state === "accepted") return "Tool Accepted";
      if (event?.accepted === false || state === "rejected") return "Tool Rejected";
      if (state === "using") return "Tool Being Used";
      if (state === "complete") return "Run Complete";
      if (state === "scanning") return "Task Being Scanned";
      return "Monitoring";
    }

    function readableGapPurpose(event, current) {
      const key = String(event?.canonical_key || "").toLowerCase();
      const reason = String(event?.observation_reason || "").replace("visible_task_context:", "").replaceAll("_", " ").trim();
      const scenario = event?.scenario || event?.birth_scenario || current?.scenario || "";
      const taskText = compactScenarioName(scenario);
      if (key.includes("prepare_add_contact_args")) {
        return "Why: SAGE needs a reusable tool that converts the visible add-contact request into validated contact arguments or a validated direct action.";
      }
      if (key.includes("prepare_direct_contact_action_args")) {
        return "Why: SAGE needs a reusable tool that turns visible contact details into a safe, structured action without requiring a particular native route.";
      }
      if (key.includes("prepare_reminder_creation_args")) {
        return "Why: SAGE needs a reusable tool that turns visible reminder content, dates, times, and locations into structured reminder arguments.";
      }
      if (key.includes("relative") && key.includes("timestamp")) {
        return "Why: SAGE needs a deterministic time tool so relative dates can become exact timestamps without guessing.";
      }
      if (key.includes("weekday") && key.includes("timestamp")) {
        return "Why: SAGE needs a deterministic weekday-time tool so phrases like next Friday can become exact timestamps.";
      }
      if (key.includes("select_record_by_timestamp") || key.includes("recency")) {
        return "Why: SAGE needs a reusable ranking tool to select the right visible record by recency or timestamp.";
      }
      if (key.includes("message_counterparty")) {
        return "Why: SAGE needs a reusable tool to identify the correct message counterparty before a contact or message action.";
      }
      if (key.includes("location")) {
        return "Why: SAGE needs a reusable tool to turn a visible location phrase into structured search or action arguments.";
      }
      if (key.includes("plan_")) {
        return `Why: SAGE needs a reusable planning tool for ${taskText} so the actor can choose an outcome-correct action.`;
      }
      if (reason) {
        return `Why: ${reason}.`;
      }
      const tool = toolNameForLifecycleEvent(event);
      return tool
        ? `Why: SAGE identified a reusable tool gap for ${taskText}: ${compactToolName(tool)}.`
        : "Why: SAGE is checking whether a reusable generated tool is needed for the current task.";
    }

    function nextStepForState(state, event) {
      if (state === "gap") return "Next: generate a candidate tool only if the gap is reusable.";
      if (state === "generating") return "Next: validate the generated tool against schema and runtime checks.";
      if (state === "validating") return "Next: accept the tool, reject it, or repair it if validation finds a fixable issue.";
      if (state === "repairing") return "Next: re-run validation on the repaired tool.";
      if (state === "accepted") return "Next: route the stored tool when later visible task context matches.";
      if (state === "rejected") return "Next: continue without storing this candidate tool.";
      if (state === "using") return "Next: use the tool output to complete the task with original environment actions.";
      if (state === "complete") return "Next: review final paired metrics and generated-tool contribution evidence.";
      return event ? "Next: continue monitoring SAGE lifecycle events." : "Next: wait for a generated-tool lifecycle event.";
    }

    function timelineRowsForLifecycle(event, state) {
      const key = String(event?.canonical_key || "");
      const tool = compactToolName(toolNameForLifecycleEvent(event) || "generated tool");
      const base = [
        ["gap", "Gap identified", key ? `Reusable capability gap: ${key}` : "SAGE found a possible reusable tool gap."],
        ["generating", "Tool generation", `Create a candidate for ${tool}.`],
        ["validating", "Validation", "Check schema, contract, examples, and runtime behavior."],
        ["repairing", "Repair", "Use validation errors to fix the candidate tool."],
        ["accepted", "Registry decision", "Store accepted tools for later routing and reuse."],
      ];
      const order = {gap: 0, generating: 1, validating: 2, repairing: 3, accepted: 4, rejected: 4, using: 5, complete: 5, scanning: -1, idle: -1};
      const currentIndex = order[state] ?? -1;
      return base.map(([step, label, detail], index) => {
        let status = "next";
        if (currentIndex < 0) status = "next";
        else if (index < currentIndex) status = "done";
        else if (index === currentIndex) status = "current";
        if (state === "rejected" && index === 4) {
          label = "Rejected";
          detail = "Candidate did not pass validation or contract checks.";
        }
        if (state === "using" && index === 4) {
          status = "done";
          detail = "Tool is available for the actor in this task.";
        }
        if (state === "complete") status = "done";
        return {status, label, detail};
      });
    }

    function renderTimelineRows(rows, limit = 5) {
      const visible = rows.slice(0, limit);
      return visible.map((row) => `
        <div class="tool-gen-timeline-row ${esc(row.status || "next")}">
          <div class="tool-gen-timeline-dot"></div>
          <div>
            <div class="tool-gen-timeline-label">${esc(row.label)}</div>
            <div class="tool-gen-timeline-detail">${esc(row.detail)}</div>
          </div>
        </div>
      `).join("");
    }

    function sageThinkingMessage(state, latest, current, toolName) {
      const scenario = current?.scenario || latest?.scenario || latest?.birth_scenario || "";
      const tool = toolName ? compactToolName(toolName) : "the generated tool";
      const gapText = conciseGapText(latest);
      const taskText = compactScenarioName(scenario);
      let text = "SAGE is waiting for the next live lifecycle event.";
      if (state === "scanning") {
        text = `SAGE is working on ${taskText}. It is checking whether an existing generated tool fits or whether a new tool gap exists.`;
      } else if (state === "gap") {
        text = gapText
          ? `SAGE found a possible tool gap for ${taskText}: ${gapText}. It is deciding whether to generate a new tool.`
          : `SAGE found a possible tool gap for ${taskText}. It is deciding whether to generate a new tool.`;
      } else if (state === "generating") {
        text = `SAGE is generating "${tool}" for the detected gap. The tool must pass validation before it can be reused.`;
      } else if (state === "validating") {
        text = `SAGE is validating "${tool}" against its schema, examples, and runtime behavior.`;
      } else if (state === "repairing") {
        text = `SAGE is repairing "${tool}" using validation errors. The repaired tool must pass the same checks.`;
      } else if (state === "accepted") {
        text = `SAGE accepted "${tool}" into the registry. It can be routed later when visible context matches.`;
      } else if (state === "rejected") {
        text = `SAGE rejected "${tool}" because validation or contract checks did not pass.`;
      } else if (state === "using") {
        text = `SAGE is using "${tool}" to help with ${taskText}. Generated tools may complete the action directly when their validated contract permits it.`;
      } else if (state === "complete") {
        text = "The SAGE arm is complete. Final paired metrics and generated-tool contribution data are available below.";
      }
      return {
        text,
      };
    }

    function throttledAgentActionText(nextText, force = false) {
      const text = String(nextText || "SAGE is monitoring the current task.").trim();
      const now = Date.now();
      if (force || !lastAgentActionText || text === lastAgentActionText || (now - lastAgentActionRenderedAt) >= AGENT_ACTION_MIN_DISPLAY_MS) {
        lastAgentActionText = text;
        lastAgentActionRenderedAt = now;
      }
      return lastAgentActionText;
    }

    async function loadToolCodeForEvent(event, candidateDir) {
      if (event?.code) return String(event.code);
      if (event?.snapshot_path) return await fetchTextMaybe(event.snapshot_path);
      const tool = event?.tool_name;
      if (!tool || !candidateDir) return "";
      return await fetchTextMaybe(`${candidateDir}/generated_tool_snapshots/${tool}_v1.py`);
    }

    async function updateToolGenerationStatus() {
      const candidateDir = candidateRunDir();
      if (!candidateDir) {
        toolGenerationStatus = {
          state: "idle",
          stage: "SAGE Tool Generation",
          statusHeadline: "Waiting For SAGE",
          title: "No active generated tool",
          body: "Candidate run artifacts are not available yet.",
          purpose: "Why: candidate run artifacts are not available yet.",
          currentStep: "Current step: waiting for candidate artifacts",
          nextStep: "Next: load live SAGE lifecycle files when they are created.",
          timeline: timelineRowsForLifecycle(null, "idle"),
          thinkingText: "Waiting for candidate run artifacts before live SAGE status can be displayed.",
          meta: [],
          details: [],
          code: "",
          toolName: "",
        };
        renderToolGenerationStatus();
        return;
      }
      const [currentText, birthText, eventText, statusText, reuseText] = await Promise.all([
        fetchTextMaybe(`${candidateDir}/currently_running.json`),
        fetchTextMaybe(`${candidateDir}/tool_birth_events.jsonl`),
        fetchTextMaybe(`${candidateDir}/sage_run_events.jsonl`),
        fetchTextMaybe(`${candidateDir}/tool_generation_status.json`),
        fetchTextMaybe(`${candidateDir}/reuse_events.jsonl`),
      ]);
      let current = null;
      let liveStatus = null;
      try { current = currentText.trim() ? JSON.parse(currentText) : null; } catch { current = null; }
      try { liveStatus = statusText.trim() ? JSON.parse(statusText) : null; } catch { liveStatus = null; }
      const birthEvents = parseJsonLines(birthText);
      const runEvents = parseJsonLines(eventText);
      const reuseEvents = parseJsonLines(reuseText);
      const latestBirth = birthEvents.length ? birthEvents[birthEvents.length - 1] : null;
      const latestRunEvent = latestMeaningfulRunEvent(runEvents);
      const latestReuse = reuseEventForScenario(reuseEvents, current?.scenario);
      const actionChoice = chooseCurrentToolLifecycleEvent({current, liveStatus, latestRunEvent, latestBirth, latestReuse});
      const tileChoice = chooseToolTileLifecycleEvent({liveStatus, latestRunEvent, latestBirth, latestReuse});
      const actionLatest = actionChoice.event;
      const latest = tileChoice.event;
      const state = tileChoice.state;
      const displayScenario = latest?.scenario || latest?.birth_scenario || current?.scenario || "";
      const toolName = toolNameForLifecycleEvent(latest);
      const stage = humanToolStage(latest);
      const acceptedCount = birthEvents.filter((event) => event.accepted === true).length;
      const rejectedCount = birthEvents.filter((event) => event.accepted === false).length;
      const actionToolName = toolNameForLifecycleEvent(actionLatest) || toolName;
      const thinking = sageThinkingMessage(actionChoice.state, actionLatest, current, actionToolName);
      const timeline = timelineRowsForLifecycle(latest, state);
      const currentTimeline = timeline.find((row) => row.status === "current") || timeline.find((row) => row.status === "next") || timeline[timeline.length - 1];
      const purpose = readableGapPurpose(latest, current);
      const statusHeadline = lifecycleStatusHeadline(latest, state);
      const bodyParts = [];
      if (latest?.observation_reason) bodyParts.push(String(latest.observation_reason).replace("visible_task_context:", ""));
      if (latest?.canonical_key) bodyParts.push(`Gap: ${latest.canonical_key}`);
      if (latest?.event === "generated_tool_invoked" && latest?.tool_name) bodyParts.push(`Calling ${latest.tool_name}`);
      if (!bodyParts.length && latest?.replacement_strategy) bodyParts.push(latest.replacement_strategy);
      if (!bodyParts.length) bodyParts.push("Waiting for the next generated-tool lifecycle event.");
      const code = await loadToolCodeForEvent(latest, candidateDir);
      toolGenerationStatus = {
        state,
        stage: "Current Lifecycle Status",
        statusHeadline,
        title: toolName ? compactToolName(toolName) : "No active generated tool",
        body: bodyParts.join(" · "),
        purpose,
        currentStep: currentTimeline ? `Current step: ${currentTimeline.label}` : `Current step: ${stage}`,
        nextStep: nextStepForState(state, latest),
        timeline,
        thinkingText: throttledAgentActionText(thinking.text, actionChoice.state === "complete"),
        meta: [
          `scenario ${current?.completed_count ?? payload?.summary?.candidate_completed ?? 0}/${current?.scenario_count ?? payload?.summary?.scenario_count ?? 0}`,
          `${acceptedCount} accepted · ${rejectedCount} rejected`,
          latest?.event ? String(latest.event).replaceAll("_", " ") : "no active birth event",
        ],
        details: [
          ["Current status", statusHeadline],
          ["Why this tool exists", purpose.replace(/^Why:\s*/i, "")],
          ["Current step", currentTimeline?.label || stage],
          ["Next step", nextStepForState(state, latest).replace(/^Next:\s*/i, "")],
          ["Current scenario", displayScenario || "n/a"],
          ["Latest stage", stage],
          ["Tool", toolName || "n/a"],
          ["Gap key", latest?.canonical_key || "n/a"],
          ["Validation", latest?.accepted === true ? "accepted" : latest?.accepted === false ? "rejected" : "n/a"],
          ["Validation errors", Array.isArray(latest?.errors) && latest.errors.length ? latest.errors.join("; ") : "none"],
          ["Repair attempts", latest?.repair_attempt_count ?? latest?.attempt ?? "n/a"],
          ["Accepted / rejected births", `${acceptedCount} / ${rejectedCount}`],
        ],
        code,
        toolName,
      };
      renderToolGenerationStatus();
    }

    function renderToolGenerationStatus() {
      const status = toolGenerationStatus;
      const card = document.getElementById("toolGenerationCard");
      if (!card) return;
      card.className = toolGenerationCardClass(status.state);
      const thinkingText = document.getElementById("sageThinkingText");
      if (thinkingText) thinkingText.textContent = status.thinkingText || "Waiting for live SAGE lifecycle events.";
      document.getElementById("toolGenStage").textContent = status.stage;
      document.getElementById("toolGenStatusMain").textContent = status.statusHeadline || statusLabelForState(status.state);
      document.getElementById("toolGenTitle").textContent = status.title;
      document.getElementById("toolGenPurpose").textContent = status.purpose || status.body;
      document.getElementById("toolGenCurrentStep").textContent = status.currentStep || `Current step: ${statusLabelForState(status.state)}`;
      document.getElementById("toolGenNextStep").textContent = status.nextStep || "Next: continue monitoring SAGE lifecycle events.";
      document.getElementById("toolGenTimeline").innerHTML = renderTimelineRows(status.timeline || []);
      const pill = document.getElementById("toolGenStatus");
      pill.textContent = statusLabelForState(status.state);
      const pillClass = status.state === "rejected"
        ? "bad"
        : status.state === "repairing"
          ? "repairing"
          : status.state === "validating"
            ? "validating"
            : ["gap", "generating"].includes(status.state)
              ? "warn"
              : ["idle", "scanning"].includes(status.state)
                ? "idle"
                : "";
      pill.className = `tool-gen-status-pill ${pillClass}`;
      document.getElementById("toolGenMeta").innerHTML = (status.meta || []).map((item) => `<div>${esc(item)}</div>`).join("");
    }

    function openToolGenerationDrawer() {
      const status = toolGenerationStatus;
      document.getElementById("toolGenerationSub").textContent = `${statusLabelForState(status.state)} · ${status.toolName || "no active tool"}`;
      const rows = (status.details || []).map(([label, value]) => `<div class="tool-gen-detail-card"><h3>${esc(label)}</h3><div class="small">${esc(value)}</div></div>`).join("");
      document.getElementById("toolGenerationDetail").innerHTML = `
        <div class="tool-gen-detail-grid">${rows}</div>
        <div class="section" style="margin-top:12px">
          <div class="section-head"><h3>Lifecycle Timeline</h3><div class="small">${esc(status.statusHeadline || statusLabelForState(status.state))}</div></div>
          <div class="tool-gen-drawer-timeline">${renderTimelineRows(status.timeline || [], 8)}</div>
        </div>
        <div class="section" style="margin-top:12px">
          <div class="section-head"><h3>Current Generated Tool Code</h3><div class="small">${esc(status.toolName || "No generated tool snapshot available")}</div></div>
          <pre class="tool-gen-code">${esc(status.code || "No generated code is available for the latest status yet.")}</pre>
        </div>`;
      document.getElementById("toolGenerationDrawer").classList.add("open");
      document.getElementById("toolGenerationDrawer").setAttribute("aria-hidden", "false");
    }

    function closeToolGenerationDrawer() {
      document.getElementById("toolGenerationDrawer").classList.remove("open");
      document.getElementById("toolGenerationDrawer").setAttribute("aria-hidden", "true");
    }

    function plannedTaskCount(summary) {
      const modeMatch = String(payload?.mode || "").match(/_(\d+)$/);
      const modeCap = modeMatch ? Number(modeMatch[1]) : 0;
      const explicit = [
        payload?.scenario_count,
        payload?.planned_scenario_count,
        summary.planned_scenario_count,
        payload?.requested_samples,
        summary.requested_samples,
        payload?.requested_limit,
        summary.requested_limit,
        payload?.arm_progress?.control?.scenario_count,
        payload?.arm_progress?.candidate?.scenario_count,
        modeCap,
      ].map((value) => Number(value || 0)).find((value) => value > 0);
      if (explicit) return explicit;
      return Math.max(Number(summary.scenario_count || 0), Number(pairs.length || 0));
    }

    function armProgress(arm, summaryKey) {
      const s = payload?.summary || {};
      const progress = payload?.arm_progress?.[arm] || {};
      const total = plannedTaskCount(s);
      const completedRaw = progress.completed_count ?? s[summaryKey] ?? 0;
      const plannedRaw = progress.scenario_count ?? total;
      const planned = Number(plannedRaw || total || 0);
      const completed = Math.min(Number(completedRaw || 0), planned || Number(completedRaw || 0));
      return {
        completed,
        planned,
        status: progress.status || (completed > 0 ? "running" : "pending"),
      };
    }

    function renderMetrics() {
      const s = payload.summary || {};
      const tools = payload.tool_summary || {};
      const totalTasks = plannedTaskCount(s);
      const baselineProgress = armProgress("control", "control_completed");
      const sageProgress = armProgress("candidate", "candidate_completed");
      const baselineDone = baselineProgress.completed;
      const sageDone = sageProgress.completed;
      const matched = Math.min(baselineDone, sageDone);
      const paired = pairedMetrics(s);
      const baselineOutcome = paired.baselineOutcome;
      const sageOutcome = paired.sageOutcome;
      const outcomeDelta = finite(baselineOutcome) && finite(sageOutcome) ? Number(sageOutcome) - Number(baselineOutcome) : null;
      const outcomeLift = relLift(outcomeDelta, baselineOutcome);
      const used = tools.called_tool_count ?? 0;
      const total = (tools.registry_tool_count || tools.tool_count || 0);
      const contributionTools = tools.contribution_tool_count || tools.tool_count || total;
      const bornEvents = Math.max(
        Number(tools.generated_tool_birth_count || 0),
        Number(tools.generated_tool_birth_event_count || 0),
      );
      const controlUsageRecorded = llmRecorded(s, "control");
      const candidateUsageRecorded = llmRecorded(s, "candidate");
      const llmCallsValue = controlUsageRecorded || candidateUsageRecorded
        ? llmPairValue(s.control_llm_call_count, s.candidate_llm_call_count, intNum)
        : "- / -";
      const llmTokensValue = controlUsageRecorded || candidateUsageRecorded
        ? llmPairValue(s.control_llm_total_tokens, s.candidate_llm_total_tokens, tokenNum)
        : "- / -";
      const llmCallsHint = controlUsageRecorded || candidateUsageRecorded
        ? `live ${intNum(s.control_llm_live_call_count)} / ${intNum(s.candidate_llm_live_call_count)} · stored-response replays ${intNum(s.control_llm_cached_call_count)} / ${intNum(s.candidate_llm_cached_call_count)}`
        : "usage not recorded in this run";
      const llmTokensHint = controlUsageRecorded || candidateUsageRecorded
        ? `prompt ${tokenNum(s.control_llm_prompt_tokens)} / ${tokenNum(s.candidate_llm_prompt_tokens)} · provider-prefix cached ${tokenNum(s.control_llm_provider_cached_prompt_tokens)} / ${tokenNum(s.candidate_llm_provider_cached_prompt_tokens)} · provider metadata ${intNum(s.control_llm_provider_cached_prompt_tokens_available_count)} / ${intNum(s.candidate_llm_provider_cached_prompt_tokens_available_count)} calls · completion ${tokenNum(s.control_llm_completion_tokens)} / ${tokenNum(s.candidate_llm_completion_tokens)}`
        : "OpenAI usage metadata unavailable";
      document.getElementById("runProgress").innerHTML = `<span class="label">Run Progress</span><strong>${matched || 0}/${totalTasks || 0}</strong><span>${esc(armLabel("control"))} ${baselineDone}/${totalTasks || 0} ${esc(baselineProgress.status)} · ${esc(armLabel("candidate"))} ${sageDone}/${totalTasks || 0} ${esc(sageProgress.status)}</span>`;
      document.getElementById("metrics").innerHTML = [
        metric(`${armLabel("control")} Outcome`, num(baselineOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric(`${armLabel("candidate")} Outcome`, num(sageOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric("Outcome Lift", liftPct(outcomeLift, approxZeroBaselineLift(outcomeDelta, baselineOutcome)), liftHint(outcomeDelta, baselineOutcome, "outcome"), cls(outcomeDelta)),
        metric("Total Time B / S", totalTimePairValue(s), totalTimeHint(s)),
        metric("LLM Calls B / S", llmCallsValue, llmCallsHint),
        metric("Tokens B / S", llmTokensValue, llmTokensHint),
      ].join("");
	      document.getElementById("toolMetrics").innerHTML = metric(
	        "New Tools / Called",
	        `${bornEvents} / ${used}`,
	        `${total} registry tools present · ${contributionTools} contribution tools; click for contribution`,
	        bornEvents > 0 ? "good" : "warn",
	        true,
	      );
	      const cell = document.getElementById("toolsMetric");
	      cell?.addEventListener("click", openTools);
	      cell?.addEventListener("keydown", (event) => {
	        if (event.key === "Enter" || event.key === " ") openTools();
	      });
	      renderToolSummaryPanel();
	    }

    function pairDelta(pair) {
      const c = pair.control || {};
      const s = pair.candidate || {};
      const outcomeDelta = finite(outcome(c)) && finite(outcome(s)) ? Number(outcome(s)) - Number(outcome(c)) : null;
      return {outcomeDelta};
    }

    function renderList() {
      const query = document.getElementById("search").value.trim().toLowerCase();
      const filtered = pairs
        .map((pair, index) => ({pair, index}))
        .filter(({pair}) => !query || String(pair.short_name || pair.scenario).toLowerCase().includes(query) || String(pair.scenario).toLowerCase().includes(query));
      document.getElementById("taskList").innerHTML = filtered.map(({pair, index}) => {
        const d = pairDelta(pair);
        const events = toolEvents(pair);
        const chips = events.slice(0, 3).map((event) => `<span class="tool-chip ${esc(event.kind)}" title="${esc(toolEventLabel(event))}">${esc(event.kind || "tool")} · ${esc(compactToolName(event.tool))}</span>`).join("");
        const overflow = events.length > 3 ? `<span class="tool-chip" title="${esc(events.slice(3).map(toolEventLabel).join("\\n"))}">+${events.length - 3}</span>` : "";
        return `<button class="task-btn ${index === selected ? "active" : ""}" data-index="${index}">
          <div class="task-name">${esc(pair.display_index || index + 1)}. ${esc(pair.short_name || pair.scenario)}</div>
          <div class="task-meta">
            <span class="meta-pill"><span class="meta-label">outcome</span><span class="${cls(d.outcomeDelta)}">${signedNum(d.outcomeDelta)}</span></span>
          </div>
          ${events.length ? `<div class="tool-badges">${chips}${overflow}</div>` : ""}
        </button>`;
      }).join("");
      document.querySelectorAll(".task-btn").forEach((btn) => btn.addEventListener("click", () => {
        selected = Number(btn.dataset.index);
        renderList();
        renderDetail();
      }));
    }

    function cleanToolName(name) {
      return String(name || "").replace(/^.*:/, "");
    }

    function humanKey(key) {
      const labels = {
        person_id: "person ID",
        reminder_id: "reminder ID",
        phone_number: "phone",
        creation_timestamp: "created",
        reminder_timestamp: "reminder time",
        location_service: "location",
        low_battery_mode: "low battery",
        is_self: "self",
      };
      return labels[key] || String(key || "").replace(/_/g, " ");
    }

    function humanValue(value, key = "") {
      if (value === null || value === undefined || value === "" || value === "None" || value === "null") return "missing";
      const text = String(value);
      if (/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(text)) return `${text.slice(0, 8)}...`;
      if (String(key).includes("timestamp") && finite(text)) {
        const seconds = Number(text);
        if (seconds > 1000000000 && seconds < 4102444800) {
          return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
        }
      }
      if (/^-?\d+(?:\.\d+)?$/.test(text) && text.length >= 10) return Number(text).toLocaleString(undefined, {maximumFractionDigits: 0});
      return text.length > 64 ? `${text.slice(0, 61)}...` : text;
    }

    function extractFields(text) {
      const fields = {};
      const pattern = /['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?\s*[:=]\s*(?:'([^']*)'|"([^"]*)"|([^,}\]\)\s]+))/g;
      let match;
      while ((match = pattern.exec(String(text || ""))) !== null) {
        const key = match[1];
        if (!key || key in fields) continue;
        fields[key] = (match[2] ?? match[3] ?? match[4] ?? "").replace(/[}\]\)]*$/, "");
      }
      return fields;
    }

    function fieldSummary(fields, keys) {
      return keys
        .filter((key) => Object.prototype.hasOwnProperty.call(fields, key))
        .filter((key) => !(key === "is_self" && String(fields[key]).toLowerCase() === "false"))
        .slice(0, 6)
        .map((key) => `<span class="kv-chip">${esc(humanKey(key))}: ${esc(humanValue(fields[key], key))}</span>`)
        .join("");
    }

    function preferredKeysForTool(tool) {
      const name = String(tool || "").toLowerCase();
      if (name.includes("contact")) return ["name", "phone_number", "relationship", "person_id", "is_self"];
      if (name.includes("reminder")) return ["content", "reminder_timestamp", "resolved_reminder_timestamp", "day_offset", "hour", "minute", "should_call_add_reminder", "location_status", "creation_timestamp", "reminder_id", "latitude", "longitude"];
      if (name.includes("message")) return ["sender", "recipient", "content", "phone_number", "timestamp"];
      if (name.includes("setting") || name.includes("wifi") || name.includes("cellular")) return ["wifi", "cellular", "location_service", "low_battery_mode"];
      return ["name", "content", "phone_number", "relationship", "person_id", "reminder_timestamp", "sender", "recipient"];
    }

    function entityForTool(tool) {
      const name = String(tool || "").toLowerCase();
      if (name.includes("contact")) return "contact";
      if (name.includes("reminder")) return "reminder";
      if (name.includes("message")) return "message";
      if (name.includes("setting") || name.includes("wifi") || name.includes("cellular")) return "setting";
      if (name.includes("stock")) return "stock result";
      return "record";
    }

    function evidenceCard(kind, main, raw, fieldsHtml = "") {
      const rawText = String(raw || "");
      const needsRaw = rawText && rawText !== main;
      return `<div class="evidence-readable">
        <div class="evidence-main"><span class="evidence-kind ${esc(kind)}">${esc(kind)}</span> ${esc(main)}</div>
        ${fieldsHtml ? `<div class="kv-row">${fieldsHtml}</div>` : ""}
        ${needsRaw ? `<details class="raw-evidence"><summary>Raw</summary><pre>${esc(rawText)}</pre></details>` : ""}
      </div>`;
    }

    function summarizeToolCall(line) {
      const call = String(line || "").match(/^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$/s);
      if (!call) return null;
      const tool = cleanToolName(call[1]);
      const args = extractFields(call[2]);
      const keys = Object.keys(args);
      const fields = fieldSummary(args, keys);
      const main = keys.length ? `${tool} called with ${keys.length} input${keys.length === 1 ? "" : "s"}` : `${tool} called without arguments`;
      return evidenceCard("call", main, line, fields);
    }

    function summarizeStateLine(line) {
      const state = String(line || "").match(/^([A-Z][A-Z_]+):\s*(.+)$/s);
      if (!state) return null;
      const namespace = state[1].replace(/_/g, " ").toLowerCase();
      const fields = extractFields(state[2]);
      const keys = Object.keys(fields);
      const fieldsHtml = fieldSummary(fields, keys);
      const main = keys.length ? `${namespace} state matched: ${keys.map(humanKey).join(", ")}` : `${namespace} state evidence`;
      return evidenceCard("state", main, line, fieldsHtml);
    }

    function summarizeToolResult(line) {
      const result = String(line || "").match(/^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/s);
      if (!result) return null;
      const tool = cleanToolName(result[1]);
      const payloadText = result[2] || "";
      if (payloadText.trim() === "[]") return evidenceCard("result", `${tool} returned no results`, line);
      const recordCount = (payloadText.match(/\{[^{}]*\}/g) || []).length;
      const fields = extractFields(payloadText);
      if (!recordCount && !Object.keys(fields).length) {
        const scalar = payloadText.trim().replace(/^['"]|['"]$/g, "");
        if (scalar && scalar !== "{}") {
          const lowerTool = tool.toLowerCase();
          const key = lowerTool.includes("timestamp")
            ? "timestamp"
            : lowerTool.includes("reminder")
              ? "reminder_id"
              : lowerTool.includes("contact")
                ? "person_id"
                : "value";
          const label = key === "timestamp" ? "time" : humanKey(key);
          return evidenceCard("result", `${tool} returned: ${label}`, line, `<span class="kv-chip">${esc(label)}: ${esc(humanValue(scalar, key))}</span>`);
        }
      }
      const keys = preferredKeysForTool(tool);
      const fieldsHtml = fieldSummary(fields, keys.length ? keys : Object.keys(fields));
      const entity = entityForTool(tool);
      const countText = recordCount ? `${recordCount} ${entity}${recordCount === 1 ? "" : "s"}` : entity;
      const main = `${tool} returned: ${countText}`;
      return evidenceCard("result", main, line, fieldsHtml);
    }

    function evidenceLineHtml(line) {
      const raw = String(line ?? "").trim();
      if (!raw) return "";
      const summarized = summarizeStateLine(raw) || summarizeToolResult(raw) || summarizeToolCall(raw);
      if (summarized) return summarized;
      const clipped = raw.length > 220 ? `${raw.slice(0, 217)}...` : raw;
      return evidenceCard("text", clipped, raw);
    }

    function transcriptFallback(row) {
      const checks = row?.outcome_checks || [];
      const observed = checks.flatMap((check) => check.observed_messages || []).slice(-3);
      return observed.join("\\n\\n") || "No transcript messages exported.";
    }

    function messageRole(message) {
      const role = String(message.role || "").toLowerCase();
      const label = String(message.label || message.sender || "").toLowerCase();
      const raw = `${role} ${label}`;
      if (role === "assistant" || raw.includes("assistant")) return "assistant";
      if (role === "user" || raw.includes("user")) return "user";
      if (role === "tool" || raw.includes("tool:")) return "tool";
      return "system";
    }

    function messageTools(message) {
      const tools = [...(message.generated_tools || [])];
      if (!tools.length && message.uses_generated_tool) {
        const label = String(message.label || "");
        const content = String(message.content || message.message || "");
        const labelMatch = label.match(/tool(?: call)?:\s*([A-Za-z0-9_]+)/i);
        const contentMatch = content.match(/^\s*([A-Za-z0-9_]+)\s*\(/);
        const tool = labelMatch?.[1] || contentMatch?.[1] || "";
        if (tool) tools.push(tool);
      }
      return tools;
    }

    function messageToolName(message, tools) {
      const label = String(message.label || "");
      const content = String(message.content || message.message || "");
      const labelMatch = label.match(/(?:tool call|tool):\s*([A-Za-z0-9_]+)/i);
      const contentMatch = content.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(/);
      return cleanToolName(message.name || tools[0] || labelMatch?.[1] || contentMatch?.[1] || "");
    }

    function toolResultHtml(tool, content) {
      const raw = String(content ?? "").trim();
      if (!raw) return evidenceCard("result", `${tool || "tool"} returned no visible content`, raw);
      const result = tool ? summarizeToolResult(`${tool}: ${raw}`) : null;
      if (result) return result;
      const clipped = raw.length > 180 ? `${raw.slice(0, 177)}...` : raw;
      return evidenceCard("result", `${tool || "tool"} returned: ${clipped}`, raw);
    }

    function messageBodyHtml(message, role, tools) {
      const content = String(message.content || message.message || "[empty]");
      const label = String(message.label || "");
      const tool = messageToolName(message, tools);
      const isToolCall = /tool call/i.test(label) || /^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(/.test(content);
      if (isToolCall) {
        return summarizeToolCall(content) || evidenceCard("call", `${tool || "tool"} called`, content);
      }
      if (role === "tool") {
        return toolResultHtml(tool, content);
      }
      return `<div class="message-text">${esc(content)}</div>`;
    }

    function messageHtml(message) {
      const role = messageRole(message);
      const tools = messageTools(message);
      const label = message.label || message.sender || message.role || role;
      return `<div class="msg ${role}${tools.length ? " generated-tool" : ""}">
        <div class="bubble">
          <div class="msg-lbl">${esc(`#${Number(message.index ?? 0) + 1} · ${label}`)}</div>
          ${tools.map((tool) => `<span class="tbadge">⚡ ${esc(tool)}</span>`).join("")}
          ${messageBodyHtml(message, role, tools)}
        </div>
      </div>`;
    }

    function transcriptHtml(row) {
      const messages = row?.messages || [];
      if (!messages.length) return `<div class="empty-transcript">${esc(transcriptFallback(row))}</div>`;
      return `<div class="transcript">${messages.map(messageHtml).join("")}</div>`;
    }

    function toolEventHtml(pair) {
      const events = toolEvents(pair);
      if (!events.length) return "<span class='small'>No generated-tool birth, visibility, or call event recorded for this task.</span>";
      return events.map((event) => `<span class="tool-chip ${esc(event.kind)}" title="${esc(toolEventLabel(event))}">${esc(event.kind || "tool")} · ${esc(event.tool || "")}</span>`).join("");
    }

    function transcriptSource(row) {
      const source = row?.transcript_source;
      if (!source) return "";
      const bits = [source.source, source.record_id ? `record ${source.record_id}` : "", source.transcript_path || ""].filter(Boolean);
      return bits.length ? `<div class="small" style="margin-bottom:8px">${esc(bits.join(" · "))}</div>` : "";
    }

    function transactionPanelHtml(control, candidate) {
      const row = transactionArm === "control" ? control : candidate;
      const title = `${armLabel(transactionArm)} Transaction`;
      return `<div class="section">
        <div class="transaction-head">
          <h3>Full Transaction</h3>
          <select id="transactionArm" class="transaction-select" aria-label="Transaction view">
            <option value="control" ${transactionArm === "control" ? "selected" : ""}>${esc(armLabel("control"))}</option>
            <option value="candidate" ${transactionArm === "candidate" ? "selected" : ""}>${esc(armLabel("candidate"))}</option>
          </select>
        </div>
        <div class="box">
          <h3>${title}</h3>
          ${transcriptSource(row)}
          ${transcriptHtml(row)}
        </div>
      </div>`;
    }

    function bindTransactionArm() {
      const select = document.getElementById("transactionArm");
      if (!select) return;
      select.addEventListener("change", () => {
        transactionArm = select.value;
        renderDetail();
      });
    }

    function renderDetail() {
      const pair = pairs[selected];
      if (!pair) {
        document.getElementById("detail").innerHTML = "<div class='section'>No task pairs exported.</div>";
        return;
      }
      const control = pair.control || {};
      const candidate = pair.candidate || {};
      const d = pairDelta(pair);
      const cats = [...new Set([...(control.categories || []), ...(candidate.categories || [])])];
      document.getElementById("detail").innerHTML = `
        <div class="section">
          <div class="task-title">
            <div>
              <h2>${esc(pair.short_name || pair.scenario)}</h2>
              <div class="small">${esc(pair.scenario)}</div>
            </div>
            <div class="small">Task ${esc(pair.display_index || selected + 1)}</div>
          </div>
          <div class="pill-row">${cats.map((cat) => `<span class="pill">${esc(cat)}</span>`).join("")}</div>
          <div class="compare-grid">
            <div class="mini"><div class="label">${esc(armLabel("control"))} Outcome</div><div class="value">${pct(outcome(control))}</div></div>
            <div class="mini"><div class="label">${esc(armLabel("candidate"))} Outcome</div><div class="value">${pct(outcome(candidate))}</div></div>
            <div class="mini"><div class="label">Outcome Lift</div><div class="value ${cls(d.outcomeDelta)}">${liftPct(relLift(d.outcomeDelta, outcome(control)), approxZeroBaselineLift(d.outcomeDelta, outcome(control)))}</div><div class="hint">${approxZeroBaselineLift(d.outcomeDelta, outcome(control)) ? liftHint(d.outcomeDelta, outcome(control), "outcome") : `${num(outcome(control))} -> ${num(outcome(candidate))}; delta ${signedNum(d.outcomeDelta)}`}</div></div>
            <div class="mini"><div class="label">Turns B / S</div><div class="value">${esc(control.turn_count ?? "-")} / ${esc(candidate.turn_count ?? "-")}</div></div>
            <div class="mini"><div class="label">LLM Calls B / S</div><div class="value">${esc(llmPairValue(control.llm_call_count, candidate.llm_call_count, intNum))}</div><div class="hint">live ${esc(llmPairValue(control.llm_live_call_count, candidate.llm_live_call_count, intNum))}</div></div>
            <div class="mini"><div class="label">Tokens B / S</div><div class="value">${esc(llmPairValue(control.llm_total_tokens, candidate.llm_total_tokens, tokenNum))}</div><div class="hint">prompt ${esc(llmPairValue(control.llm_prompt_tokens, candidate.llm_prompt_tokens, tokenNum))} · provider-prefix cached ${esc(llmPairValue(control.llm_provider_cached_prompt_tokens, candidate.llm_provider_cached_prompt_tokens, tokenNum))} · provider metadata ${esc(llmPairValue(control.llm_provider_cached_prompt_tokens_available_count, candidate.llm_provider_cached_prompt_tokens_available_count, intNum))} calls</div></div>
            <div class="mini"><div class="label">SAGE Tool Events</div><div class="value">${esc(toolEvents(pair).length)}</div></div>
          </div>
        </div>
        <div class="section">
          <h3 style="margin-top:0">Generated Tool Events On This Task</h3>
          <div class="pill-row">${toolEventHtml(pair)}</div>
        </div>
        ${transactionPanelHtml(control, candidate)}
      `;
      bindTransactionArm();
    }

    function openTools() {
      const tools = payload.tool_summary || {};
      const rows = tools.tools || [];
      const visibilityKnown = Boolean(tools.visibility_known ?? rows.some((tool) => tool.visible_count !== null && tool.visible_count !== undefined));
      const contributionKnown = Boolean(tools.contribution_known ?? rows.some((tool) => tool.called_subset_mean_outcome_delta !== null && tool.called_subset_mean_outcome_delta !== undefined));
      document.getElementById("toolDrawerSub").textContent = `${rows.length} tools; ${tools.called_tool_count || 0} called naturally in this run.${visibilityKnown ? "" : " Visibility counts are pending until live selection artifacts are available."}${contributionKnown ? "" : " Contribution columns are pending until completed paired called-tool tasks are available."}`;
      document.getElementById("toolTable").innerHTML = `<table>
        <thead><tr><th>Tool</th><th>Origin</th><th>Visible</th><th>Called</th><th>VNC</th><th>Outcome Contribution</th><th>Safety</th></tr></thead>
        <tbody>${rows.map((tool) => `<tr>
          <td><strong>${toolNameButton(tool)}</strong><div class="small">${esc(tool.decision || "")}</div></td>
          <td>${esc(tool.origin || "-")}</td>
          <td>${esc(maybeValue(tool.visible_count, "pending"))}</td>
          <td>${esc(tool.called_count ?? 0)}</td>
          <td>${esc(maybeValue(tool.visible_not_called_count, "pending"))}</td>
          <td class="${cls(tool.called_subset_mean_outcome_delta)}">${esc(contributionDeltaText(tool))}<div class="small">${esc(gainLossText(tool.outcome_gains, tool.outcome_regressions, tool.contribution_pending))}</div></td>
          <td>${esc(tool.side_effect_incident_count ?? 0)} safety incidents<br><span class="small">${esc(tool.runtime_incident_count ?? 0)} runtime incidents</span></td>
        </tr>`).join("")}</tbody>
      </table>`;
      document.getElementById("toolDrawer").classList.add("open");
      document.getElementById("toolDrawer").setAttribute("aria-hidden", "false");
    }

    function closeTools() {
      document.getElementById("toolDrawer").classList.remove("open");
      document.getElementById("toolDrawer").setAttribute("aria-hidden", "true");
    }

    function toolByName(name) {
      const rows = payload?.tool_summary?.tools || [];
      return rows.find((tool) => tool.name === name) || null;
    }

    function openToolCode(name) {
      const tool = toolByName(name);
      const code = tool?.code || "Code unavailable in this dashboard payload.";
      const meta = [
        tool?.family,
        tool?.code_hash ? `hash ${tool.code_hash}` : "",
        tool?.description || "",
      ].filter(Boolean).join(" · ");
      document.getElementById("toolCodeTitle").textContent = name || "Tool Code";
      document.getElementById("toolCodeMeta").textContent = meta;
      document.getElementById("toolCodeExplanation").textContent = tool?.plain_language_explanation || "No explanation is available for this tool.";
      document.getElementById("toolCodeBlock").textContent = code;
      document.getElementById("toolCodeDrawer").classList.add("open");
      document.getElementById("toolCodeDrawer").setAttribute("aria-hidden", "false");
    }

    function closeToolCode() {
      document.getElementById("toolCodeDrawer").classList.remove("open");
      document.getElementById("toolCodeDrawer").setAttribute("aria-hidden", "true");
    }

    function captureScrollState() {
      return {
        windowX: window.scrollX,
        windowY: window.scrollY,
        asideY: document.querySelector("aside")?.scrollTop || 0,
        transcriptY: document.querySelector(".transcript")?.scrollTop || 0,
      };
    }

    function restoreScrollState(state) {
      if (!state) return;
      window.requestAnimationFrame(() => {
        const aside = document.querySelector("aside");
        const transcript = document.querySelector(".transcript");
        if (aside) aside.scrollTop = state.asideY;
        if (transcript) transcript.scrollTop = state.transcriptY;
        window.scrollTo(state.windowX, state.windowY);
      });
    }

    function runIsComplete() {
      if (!payload) return false;
      const status = String(payload.status || "").toLowerCase();
      if (["complete", "completed", "done", "failed", "error"].includes(status)) return true;
      const s = payload.summary || {};
      const totalTasks = plannedTaskCount(s);
      const baselineDone = armProgress("control", "control_completed").completed;
      const sageDone = armProgress("candidate", "candidate_completed").completed;
      return totalTasks > 0 && Math.min(baselineDone, sageDone) >= totalTasks;
    }

    function updateRefreshTimer() {
      if (runIsComplete()) {
        if (refreshTimer !== null) {
          window.clearInterval(refreshTimer);
          refreshTimer = null;
        }
        if (toolGenerationRefreshTimer !== null) {
          window.clearInterval(toolGenerationRefreshTimer);
          toolGenerationRefreshTimer = null;
        }
        return;
      }
      if (refreshTimer === null) {
        refreshTimer = window.setInterval(() => {
          refresh({preserveScroll: true}).catch((error) => {
            if (!isTransientDataError(error)) console.error(error);
          });
        }, 5000);
      }
      if (toolGenerationRefreshTimer === null) {
        toolGenerationRefreshTimer = window.setInterval(() => {
          updateToolGenerationStatus().catch((error) => {
            if (!isTransientDataError(error)) console.error(error);
          });
        }, 2000);
      }
    }

    function isTransientDataError(error) {
      const message = String(error?.message || error || "");
      return error instanceof SyntaxError || message.includes("empty dashboard data");
    }

    const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

    async function fetchDashboardJson(url) {
      const response = await fetch(url, {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const text = await response.text();
      if (!text.trim()) throw new SyntaxError("empty dashboard data");
      return JSON.parse(text);
    }

    async function refresh(options = {}) {
      const scrollState = options.preserveScroll ? captureScrollState() : null;
      let lastError = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          payload = await fetchDashboardJson(`task_compare_data.json?ts=${Date.now()}`);
          lastError = null;
          break;
        } catch (error) {
          lastError = error;
          if (!isTransientDataError(error)) throw error;
          await sleep(250);
        }
      }
      if (lastError) {
        if (payload && isTransientDataError(lastError)) return;
        throw lastError;
      }
      pairs = payload.pairs || [];
      const s = payload.summary || {};
      const totalTasks = plannedTaskCount(s);
      const baselineDone = armProgress("control", "control_completed").completed;
      const sageDone = armProgress("candidate", "candidate_completed").completed;
      const matched = Math.min(baselineDone, sageDone);
      const matchedText = `${matched || 0}/${totalTasks || 0} matched tasks`;
      const environmentName = envDisplayName(payload.environment || payload.benchmark || s.environment || "ToolSandbox");
      const startedAt = payload.started_at ? new Date(payload.started_at).toLocaleString() : "unknown start";
      document.title = `Task Compare - ${environmentName} - SAGE`;
      document.getElementById("envBadge").textContent = environmentName;
      document.getElementById("subtitle").textContent = `${payload.mode || "run"} · ${payload.status || "unknown"} · ${payload.agent || ""} · ${matchedText} · started ${startedAt} · refreshed ${new Date().toLocaleTimeString()}`;
      document.getElementById("runtimeLine").textContent = formatRuntimeLine();
      if (selected >= pairs.length) selected = Math.max(0, pairs.length - 1);
      renderMetrics();
      await updateToolGenerationStatus();
      renderList();
      renderDetail();
      restoreScrollState(scrollState);
      updateRefreshTimer();
    }

    async function load() {
      await refresh();
      if (!handlersBound) {
        handlersBound = true;
        document.getElementById("search").addEventListener("input", renderList);
        document.getElementById("closeTools").addEventListener("click", closeTools);
        document.getElementById("closeToolCode").addEventListener("click", closeToolCode);
        document.getElementById("toolGenerationCard").addEventListener("click", openToolGenerationDrawer);
        document.getElementById("closeToolGeneration").addEventListener("click", closeToolGenerationDrawer);
        document.getElementById("toolDrawer").addEventListener("click", (event) => {
          if (event.target.id === "toolDrawer") closeTools();
        });
        document.getElementById("toolCodeDrawer").addEventListener("click", (event) => {
          if (event.target.id === "toolCodeDrawer") closeToolCode();
        });
        document.getElementById("toolGenerationDrawer").addEventListener("click", (event) => {
          if (event.target.id === "toolGenerationDrawer") closeToolGenerationDrawer();
        });
        document.addEventListener("click", (event) => {
          const target = event.target?.closest?.("[data-tool-code-name]");
          if (!target) return;
          event.preventDefault();
          openToolCode(target.getAttribute("data-tool-code-name"));
        });
        window.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            closeToolCode();
            closeTools();
            closeToolGenerationDrawer();
          }
        });
        updateRefreshTimer();
      }
    }

    load().catch((error) => {
      if (isTransientDataError(error)) {
        window.setTimeout(load, 1000);
        return;
      }
      document.getElementById("detail").innerHTML = `<div class="section"><strong>Dashboard load failed.</strong><pre>${esc(error.stack || error.message || error)}</pre></div>`;
      console.error(error);
    });
  </script>
</body>
</html>
"""
