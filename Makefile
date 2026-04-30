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
OUT ?= artifacts/registries/frozen_registry.json
RUN ?= outputs/sage_protocol_campaign/extended_reuse_100_20260428_125232
MODE ?= evolve
PORT ?= 5520
DASHBOARD_OPEN ?= 1
DASHBOARD_FLAGS := $(if $(filter 1,$(DASHBOARD_OPEN)),,--no-dashboard-open)
CACHE_MODE ?= read_write
CACHE_FLAGS := --cache-mode $(CACHE_MODE)
PARALLEL_ARMS ?= 1
PARALLEL_FLAGS := $(if $(filter 1,$(PARALLEL_ARMS)),--parallel-arms,)
MIN_GATE_SCENARIOS ?= 12
CATEGORY ?= general
ifeq ($(CATEGORY),state)
CATEGORY_MANIFEST ?= outputs/splits/sage_state_precondition_splits.json
else ifeq ($(CATEGORY),temperature)
CATEGORY_MANIFEST ?= outputs/splits/sage_temperature_splits.json
else ifeq ($(CATEGORY),recency)
CATEGORY_MANIFEST ?= outputs/splits/sage_campaign_splits.json
else
CATEGORY_MANIFEST ?= $(MANIFEST)
endif
SPLIT ?= extended_reuse_100
GENERATION ?= 0
GENERATION_FLAGS := $(if $(filter 1,$(GENERATION)),--enable-generation,)
POC_MANIFEST ?= outputs/splits/relative_datetime_probe.json
POC_PROTOCOL_MANIFEST ?= outputs/splits/relative_datetime_protocol.json
RECENCY_TRANSFER_MANIFEST ?= outputs/splits/sage_campaign_splits.json
RELATIVE_TIME_TRANSFER_MANIFEST ?= outputs/splits/relative_datetime_transfer.json

.PHONY: test lint dashboard reproduce_poc transfer_recency transfer_relative_time smoke4 smoke12 viability12 mechanism40 transfer40 transfer60 confirm100 validate100 validate250 summarize cache_stats cache_validate freeze_registry campaign-init

define CHECK_GATE_SIZE
	@$(RUN_PYTHON) -c "from pathlib import Path; from sage_ts.config.splits import load_split_names; manifest=Path('$(1)'); split='$(2)'; count=len(load_split_names(manifest, split)); minimum=int('$(MIN_GATE_SCENARIOS)'); print(f'{manifest} {split}: {count} scenarios (minimum {minimum})'); raise SystemExit(0 if count >= minimum else 2)"
endef

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
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),mechanism_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode mechanism_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

smoke4: smoke12

smoke12:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

viability12:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

reproduce_poc:
	$(call CHECK_GATE_SIZE,$(POC_PROTOCOL_MANIFEST),mechanism_40)
	@if [ -f "$(REGISTRY)/registry_manifest.json" ]; then \
		echo "Refusing to reproduce POC into non-empty REGISTRY=$(REGISTRY). Pass a fresh REGISTRY=..."; \
		exit 2; \
	fi
	@$(RUN_PYTHON) -c "import json; from pathlib import Path; src=Path('$(POC_MANIFEST)'); dst=Path('$(POC_PROTOCOL_MANIFEST)'); data=json.loads(src.read_text()); rows=data['splits']['relative_datetime_probe']; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(json.dumps({'manifest_type':'sage_protocol_poc','splits':{'mechanism_40':rows}}, indent=2)+'\n')"
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode mechanism_40 --manifest $(POC_PROTOCOL_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

transfer_recency:
	$(call CHECK_GATE_SIZE,$(RECENCY_TRANSFER_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(RECENCY_TRANSFER_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

transfer_relative_time:
	$(call CHECK_GATE_SIZE,$(RELATIVE_TIME_TRANSFER_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(RELATIVE_TIME_TRANSFER_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

transfer40:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

transfer60:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(DASHBOARD_FLAGS)

confirm100: validate100

validate100:
	@if [ "$(MODE)" = "control" ]; then \
		$(RUN_PYTHON) scripts/run_baseline.py --manifest $(MANIFEST) --split extended_reuse_100 --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) $(CACHE_FLAGS) -o outputs/validate100_control; \
	else \
		$(RUN_PYTHON) scripts/run_sage_online.py --manifest $(MANIFEST) --split extended_reuse_100 --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) $(GENERATION_FLAGS) --generation-model $(MODEL) $(CACHE_FLAGS) -o outputs/validate100_evolve; \
	fi

validate250:
	@if [ "$(MODE)" = "control" ]; then \
		$(RUN_PYTHON) scripts/run_baseline.py --manifest $(MANIFEST) --split $(SPLIT) --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) $(CACHE_FLAGS) -o outputs/validate250_control; \
	else \
		$(RUN_PYTHON) scripts/run_sage_online.py --manifest $(MANIFEST) --split $(SPLIT) --agent $(MODEL) --user $(USER_MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) $(GENERATION_FLAGS) --generation-model $(MODEL) $(CACHE_FLAGS) -o outputs/validate250_evolve; \
	fi

summarize:
	@if [ -f "$(RUN)/protocol_manifest.json" ]; then \
		$(RUN_PYTHON) scripts/export_dashboard_data.py --protocol-run-root $(RUN); \
		$(RUN_PYTHON) -c "import json; from pathlib import Path; p=Path('$(RUN)')/'paired_comparison.json'; print(json.dumps(json.loads(p.read_text()), indent=2)[:12000])"; \
	else \
		$(RUN_PYTHON) scripts/export_sage_metrics.py --run-dir $(RUN) -o artifacts/summaries/run_summary.json; \
	fi

cache_stats:
	$(RUN_PYTHON) -c "import json; from pathlib import Path; p=Path('$(RUN)'); files=sorted(p.glob('**/openai_response_cache_metrics.json')); print(json.dumps({str(f): json.loads(f.read_text()) for f in files}, indent=2))"

cache_validate:
	$(RUN_PYTHON) -c "from pathlib import Path; required=[Path('artifacts/cache/openai_response_cache.sqlite'),Path('artifacts/cache/cache_manifest.json'),Path('artifacts/cache/cache_stats.json'),Path('artifacts/cache/cache_events.jsonl')]; missing=[str(p) for p in required if not p.exists()]; print('cache artifacts valid' if not missing else 'missing: '+', '.join(missing)); raise SystemExit(1 if missing else 0)"

freeze_registry:
	$(RUN_PYTHON) -c "import hashlib, json, shutil; from pathlib import Path; reg=Path('$(REGISTRY)')/'registry_manifest.json'; out=Path('$(OUT)'); out.parent.mkdir(parents=True, exist_ok=True); data=reg.read_bytes(); shutil.copy2(reg,out); lock=out.with_suffix('.lock.json'); lock.write_text(json.dumps({'registry_manifest':str(out),'sha256':hashlib.sha256(data).hexdigest()}, indent=2)+'\n'); print(lock)"
