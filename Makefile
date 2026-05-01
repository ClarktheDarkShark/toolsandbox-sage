PYTHON := conda run -n toolsandbox-sage env PYTHONPATH=src:. python
RUN_PYTHON := set -a; [ ! -f .secrets/env.sh ] || . .secrets/env.sh; set +a; $(PYTHON)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff

MANIFEST ?= outputs/splits/sage_campaign_splits.json
MODEL ?= gpt-4o-mini
LEGACY_MODEL ?= gpt-5-mini
USER_MODEL ?= GPT_4_o_2024_05_13
BASE_TOOL_POLICY ?= recency_reduced
OUTPUT_ROOT ?= outputs/sage_protocol_campaign
REGISTRY ?= outputs/sage_protocol_campaign/latest_registry
OUT ?= artifacts/registries/frozen_registry.json
RUN ?= outputs/sage_protocol_campaign/extended_reuse_100_20260428_125232
MODE ?= evolve
PORT ?= 5520
CLAIM_PORTFOLIO_REGISTRY ?= outputs/claim_portfolio_registry
DASHBOARD_OPEN ?= 1
DASHBOARD_FLAGS := $(if $(filter 1,$(DASHBOARD_OPEN)),,--no-dashboard-open)
CACHE_MODE ?= read_write
CACHE_FLAGS := --cache-mode $(CACHE_MODE)
PARALLEL_ARMS ?= 1
PARALLEL_FLAGS := $(if $(filter 1,$(PARALLEL_ARMS)),--parallel-arms,)
PROTOCOL_GENERATION ?= auto
PROTOCOL_GENERATION_FLAGS := --generation $(PROTOCOL_GENERATION)
FROZEN_GENERATION_FLAGS := --generation off
RESUME_RUN_ROOT ?=
RESUME_FLAGS := $(if $(RESUME_RUN_ROOT),--resume-run-root $(RESUME_RUN_ROOT),)
MIN_GATE_SCENARIOS ?= 12
CATEGORY ?= general
ifeq ($(CATEGORY),state)
CATEGORY_MANIFEST ?= outputs/splits/sage_state_precondition_splits.json
else ifeq ($(CATEGORY),temperature)
CATEGORY_MANIFEST ?= outputs/splits/sage_temperature_splits.json
else ifeq ($(CATEGORY),contact)
CATEGORY_MANIFEST ?= outputs/splits/contact_message_discovery_protocol.json
else ifeq ($(CATEGORY),holiday)
CATEGORY_MANIFEST ?= outputs/splits/holiday_discovery_protocol.json
else ifeq ($(CATEGORY),record_extreme)
CATEGORY_MANIFEST ?= outputs/splits/record_extreme_discovery_protocol.json
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

.PHONY: test lint dashboard reproduce_poc transfer_recency transfer_relative_time smoke4 smoke12 viability12 mechanism40 transfer40 transfer60 confirm100 validate100 validate250 summarize cache_stats cache_validate freeze_registry campaign-init coverage_map top_tool_audit claim_portfolio_registry record_extreme_splits

define CHECK_GATE_SIZE
	@$(RUN_PYTHON) -c "from pathlib import Path; from sage_ts.config.splits import load_split_names; manifest=Path('$(1)'); split='$(2)'; count=len(load_split_names(manifest, split)); minimum=int('$(MIN_GATE_SCENARIOS)'); print(f'{manifest} {split}: {count} scenarios (minimum {minimum})'); raise SystemExit(0 if count >= minimum else 2)"
endef

test:
	$(PYTEST) tests/unit tests/integration

lint:
	$(RUFF) check scripts src/sage_ts tests/unit tests/integration

campaign-init:
	$(RUN_PYTHON) scripts/campaign_artifacts.py init

coverage_map:
	$(RUN_PYTHON) scripts/build_task_stratum_coverage.py \
		--run-root outputs/regression_reduction_clean_gate3_typed_visibility_v3_20260430/extended_reuse_100_20260430_120219 \
		--run-root outputs/final_validate250_20260430/promotion_250_20260430_004125 \
		--output-dir artifacts

top_tool_audit:
	$(RUN_PYTHON) scripts/audit_top_tools.py --output-dir artifacts/summaries

claim_portfolio_registry:
	$(RUN_PYTHON) scripts/build_claim_portfolio_registry.py \
		--source-registry outputs/relative_datetime_probe_registry_20260429_2/registry_manifest.json \
		--source-registry outputs/record_ranking20_livegen_registry_20260501_042246/registry_manifest.json \
		--source-registry outputs/holiday_calendar_confirm30_registry_20260430/registry_manifest.json \
		--source-registry outputs/contact_message_constraint20_livegen_registry_20260501/registry_manifest.json \
		--source-registry outputs/claim_portfolio_reminder_argprep_v2_only_registry_20260501/registry_manifest.json \
		--output-registry $(CLAIM_PORTFOLIO_REGISTRY) \
		--report artifacts/summaries/claim_portfolio_validation.json

contact_splits:
	$(RUN_PYTHON) scripts/make_contact_message_discovery_split.py

holiday_splits:
	$(RUN_PYTHON) scripts/make_holiday_discovery_split.py

record_extreme_splits:
	$(RUN_PYTHON) scripts/make_record_extreme_discovery_split.py

dashboard:
	$(RUN_PYTHON) scripts/export_dashboard_data.py --protocol-run-root $(RUN)
	$(RUN_PYTHON) -c "from pathlib import Path; from sage_ts.dashboard.exporters import open_dashboard; d=Path('$(RUN)')/'dashboard'; print(open_dashboard(d/'index.html', port=$(PORT))); print(open_dashboard(d/'task_focus.html', port=$(PORT)))"

mechanism40:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),mechanism_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode mechanism_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

smoke4:
	@echo "smoke4 requires an explicit smoke_4 split; it no longer aliases to smoke12."
	@exit 2

smoke12:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

viability12:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

reproduce_poc:
	$(call CHECK_GATE_SIZE,$(POC_PROTOCOL_MANIFEST),mechanism_40)
	@if [ -f "$(REGISTRY)/registry_manifest.json" ]; then \
		echo "Refusing to reproduce POC into non-empty REGISTRY=$(REGISTRY). Pass a fresh REGISTRY=..."; \
		exit 2; \
	fi
	@$(RUN_PYTHON) -c "import json; from pathlib import Path; src=Path('$(POC_MANIFEST)'); dst=Path('$(POC_PROTOCOL_MANIFEST)'); data=json.loads(src.read_text()); rows=data['splits']['relative_datetime_probe']; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(json.dumps({'manifest_type':'sage_protocol_poc','splits':{'mechanism_40':rows}}, indent=2)+'\n')"
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode mechanism_40 --manifest $(POC_PROTOCOL_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

transfer_recency:
	$(call CHECK_GATE_SIZE,$(RECENCY_TRANSFER_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(RECENCY_TRANSFER_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(FROZEN_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

transfer_relative_time:
	$(call CHECK_GATE_SIZE,$(RELATIVE_TIME_TRANSFER_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(RELATIVE_TIME_TRANSFER_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(FROZEN_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

transfer40:
	$(call CHECK_GATE_SIZE,$(CATEGORY_MANIFEST),transfer_40)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode transfer_40 --manifest $(CATEGORY_MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

transfer60:
	@echo "transfer60 requires an explicit transfer_60 split/protocol mode; it no longer aliases to transfer40."
	@exit 2

confirm100:
	$(call CHECK_GATE_SIZE,$(MANIFEST),extended_reuse_100)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode extended_reuse_100 --manifest $(MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

validate100:
	$(call CHECK_GATE_SIZE,$(MANIFEST),extended_reuse_100)
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode extended_reuse_100 --manifest $(MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

validate250:
	$(call CHECK_GATE_SIZE,$(MANIFEST),$(SPLIT))
	$(RUN_PYTHON) scripts/run_sage_protocol.py --mode $(SPLIT) --manifest $(MANIFEST) --agent $(MODEL) --generation-model $(MODEL) --base-tool-policy $(BASE_TOOL_POLICY) --registry-dir $(REGISTRY) --output-root $(OUTPUT_ROOT) --dashboard-port $(PORT) $(CACHE_FLAGS) $(PARALLEL_FLAGS) $(PROTOCOL_GENERATION_FLAGS) $(RESUME_FLAGS) $(DASHBOARD_FLAGS)

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
