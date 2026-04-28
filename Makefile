PYTHON := conda run -n toolsandbox-sage env PYTHONPATH=src:. python
RUN_PYTHON := set -a; [ ! -f .secrets/env.sh ] || . .secrets/env.sh; set +a; $(PYTHON)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff

MANIFEST ?= outputs/splits/sage_campaign_splits.json
MODEL ?= gpt-5-mini
USER_MODEL ?= GPT_4_o_2024_05_13
BASE_TOOL_POLICY ?= recency_reduced
OUTPUT_ROOT ?= outputs/sage_protocol_campaign
REGISTRY ?= outputs/sage_protocol_campaign/latest_registry
RUN ?= outputs/sage_protocol_campaign/extended_reuse_100_20260428_125232
MODE ?= evolve
PORT ?= 5520

.PHONY: test lint dashboard mechanism40 transfer40 validate100 summarize campaign-init

test:
	$(PYTEST) tests/unit tests/integration

lint:
	$(RUFF) check scripts src/sage_ts tests/unit tests/integration

campaign-init:
	$(RUN_PYTHON) scripts/campaign_artifacts.py init

dashboard:
	$(RUN_PYTHON) scripts/export_dashboard_data.py --protocol-run-root $(RUN)
	$(RUN_PYTHON) -c "from pathlib import Path; from sage_ts.dashboard.exporters import ensure_dashboard_server, dashboard_url; p=Path('$(RUN)')/'dashboard'/'index.html'; ensure_dashboard_server(port=$(PORT)); print(dashboard_url(p, port=$(PORT)))"

mechanism40:
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode mechanism_40 --manifest $(MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT)

transfer40:
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT)

validate100:
	@if [ "$(MODE)" = "control" ]; then \
		$(RUN_PYTHON) scripts/run_baseline.py --manifest $(MANIFEST) --split extended_reuse_100 --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) -o outputs/validate100_control; \
	else \
		$(RUN_PYTHON) scripts/run_sage_online.py --manifest $(MANIFEST) --split extended_reuse_100 --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --enable-generation --generation-model $(MODEL) -o outputs/validate100_evolve; \
	fi

summarize:
	@if [ -f "$(RUN)/protocol_manifest.json" ]; then \
		$(RUN_PYTHON) scripts/export_dashboard_data.py --protocol-run-root $(RUN); \
		$(RUN_PYTHON) -c "import json; from pathlib import Path; p=Path('$(RUN)')/'paired_comparison.json'; print(json.dumps(json.loads(p.read_text()), indent=2)[:12000])"; \
	else \
		$(RUN_PYTHON) scripts/export_sage_metrics.py --run-dir $(RUN) -o artifacts/summaries/run_summary.json; \
	fi
