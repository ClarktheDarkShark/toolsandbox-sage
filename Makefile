PYTHON := conda run -n toolsandbox-sage env PYTHONPATH=src:. python
RUN_PYTHON := set -a; [ ! -f .secrets/env.sh ] || . .secrets/env.sh; set +a; $(PYTHON)
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff

MANIFEST ?= outputs/splits/sage_campaign_splits.json
MODEL ?= gpt-4o-mini
# MODEL ?= gpt-5-mini
# USER_MODEL ?= GPT_4_o_2024_05_13
USER_MODEL ?= gpt-4o-mini
BASE_TOOL_POLICY ?= recency_reduced
OUTPUT_ROOT ?= outputs/sage_protocol_campaign
REGISTRY ?= outputs/sage_protocol_campaign/latest_registry
OUT ?= artifacts/registries/frozen_registry.json
RUN ?= outputs/sage_protocol_campaign/extended_reuse_100_20260428_125232
MODE ?= evolve
PORT ?= 5520
SAGE_DATASET ?= toolsandbox
SAGE_SAMPLES ?= 2
SAGE_STANDALONE_REGISTRY ?= artifacts/sage_standalone/$(SAGE_DATASET)_cli_registry
SAGE_STANDALONE_OUTPUT_ROOT ?= outputs/sage_agent_standalone
CLAIM_PORTFOLIO_REGISTRY ?= outputs/claim_portfolio_registry
DASHBOARD_OPEN ?= 1
DASHBOARD_FLAGS := $(if $(filter 1,$(DASHBOARD_OPEN)),,--no-dashboard-open)

CACHE_MODE ?= read_write
CACHE_FLAGS := --cache-mode $(CACHE_MODE)

PARALLEL_ARMS ?= 1
PARALLEL_FLAGS := $(if $(filter 1,$(PARALLEL_ARMS)),--parallel-arms,)

PROTOCOL_GENERATION ?= auto
PROTOCOL_GENERATION_FLAGS := --generation $(PROTOCOL_GENERATION)

FROZEN_GENERATION ?= off
FROZEN_GENERATION_FLAGS := --generation $(FROZEN_GENERATION)

RESUME_RUN_ROOT ?=
RESUME_FLAGS := $(if $(RESUME_RUN_ROOT),--resume-run-root $(RESUME_RUN_ROOT),)

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

# ---------------------------------------------------------------------
# Explicit protocol splits by purpose and size.
#
# Current base manifest commonly has:
#   extended_reuse_100
#   mechanism_40
#   transfer_40
#
# This Makefile derives smaller temporary manifests for smoke/viability
# targets instead of silently aliasing one purpose to another.
# ---------------------------------------------------------------------

GENERATED_SPLIT_DIR ?= outputs/splits/generated

SMOKE6_SPLIT ?= smoke_6
SMOKE12_SPLIT ?= smoke_12

VIABILITY12_SPLIT ?= viability_12
MECHANISM12_SPLIT ?= mechanism_12
MECHANISM40_SPLIT ?= mechanism_40
MECHANISM60_SPLIT ?= mechanism_60

TRANSFER40_SPLIT ?= transfer_40
TRANSFER60_SPLIT ?= transfer_60
TRANSFER100_SPLIT ?= extended_reuse_100

CONFIRM100_SPLIT ?= extended_reuse_100
VALIDATE100_SPLIT ?= extended_reuse_100
VALIDATE250_SPLIT ?= validate_250

SPLIT ?= $(VALIDATE250_SPLIT)

# Source splits used to derive smaller or intermediate runs.
SMOKE_SOURCE_MANIFEST ?= $(MANIFEST)
SMOKE_SOURCE_SPLIT ?= transfer_40

VIABILITY_SOURCE_MANIFEST ?= $(MANIFEST)
VIABILITY_SOURCE_SPLIT ?= mechanism_40

MECHANISM12_SOURCE_MANIFEST ?= $(MANIFEST)
MECHANISM12_SOURCE_SPLIT ?= mechanism_40

MECHANISM60_SOURCE_MANIFEST ?= $(MANIFEST)
MECHANISM60_SOURCE_SPLIT ?= extended_reuse_100

TRANSFER60_SOURCE_MANIFEST ?= $(MANIFEST)
TRANSFER60_SOURCE_SPLIT ?= extended_reuse_100

SMOKE6_MANIFEST ?= $(GENERATED_SPLIT_DIR)/smoke_6.json
SMOKE12_MANIFEST ?= $(GENERATED_SPLIT_DIR)/smoke_12.json
VIABILITY12_MANIFEST ?= $(GENERATED_SPLIT_DIR)/viability_12.json
MECHANISM12_MANIFEST ?= $(GENERATED_SPLIT_DIR)/mechanism_12.json
MECHANISM60_MANIFEST ?= $(GENERATED_SPLIT_DIR)/mechanism_60.json
TRANSFER60_MANIFEST ?= $(GENERATED_SPLIT_DIR)/transfer_60.json

GENERATION ?= 0
GENERATION_FLAGS := $(if $(filter 1,$(GENERATION)),--enable-generation,)

POC_MANIFEST ?= outputs/splits/relative_datetime_probe.json
POC_PROTOCOL_MANIFEST ?= outputs/splits/relative_datetime_protocol.json
RECENCY_TRANSFER_MANIFEST ?= outputs/splits/sage_campaign_splits.json
RELATIVE_TIME_TRANSFER_MANIFEST ?= outputs/splits/relative_datetime_transfer.json

.PHONY: \
	test \
	lint \
	sage_agent \
	dashboard \
	campaign-init \
	coverage_map \
	top_tool_audit \
	claim_portfolio_registry \
	contact_splits \
	holiday_splits \
	record_extreme_splits \
	reproduce_poc \
	smoke6 \
	smoke12 \
	viability12 \
	mechanism12 \
	mechanism40 \
	mechanism60 \
	transfer_recency \
	transfer_relative_time \
	transfer40 \
	transfer60 \
	transfer100 \
	confirm100 \
	validate100 \
	validate250 \
	summarize \
	cache_stats \
	cache_validate \
	freeze_registry

define CHECK_GATE_SIZE
	@$(RUN_PYTHON) -c 'from pathlib import Path; from sage_ts.config.splits import load_split_names; manifest=Path("$(1)"); split="$(2)"; count=len(load_split_names(manifest, split)); minimum=int("$(3)"); print(f"{manifest} {split}: {count} scenarios (minimum {minimum})"); raise SystemExit(0 if count >= minimum else 2)'
endef

define WRITE_DERIVED_SPLIT
	@$(RUN_PYTHON) -c 'import json; from pathlib import Path; src=Path("$(1)"); dst=Path("$(2)"); source_split="$(3)"; target_split="$(4)"; n=int("$(5)"); data=json.loads(src.read_text()); rows=list(data["splits"][source_split]); assert len(rows) >= n, f"{source_split} only has {len(rows)} rows; cannot derive {n}"; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(json.dumps({"manifest_type":"derived_sage_protocol_split","source_manifest":str(src),"source_split":source_split,"splits":{target_split:rows[:n]}}, indent=2) + "\n"); print(f"Wrote {dst} with {n} scenarios as {target_split} from {source_split}")'
endef

define RUN_PROTOCOL
	$(call CHECK_GATE_SIZE,$(1),$(2),$(4))
	$(RUN_PYTHON) scripts/run_sage_protocol.py \
		--mode $(2) \
		--manifest $(1) \
		--agent $(MODEL) \
		--user $(USER_MODEL) \
		--generation-model $(MODEL) \
		--base-tool-policy $(BASE_TOOL_POLICY) \
		--registry-dir $(REGISTRY) \
		--output-root $(OUTPUT_ROOT) \
		--dashboard-port $(PORT) \
		$(CACHE_FLAGS) \
		$(PARALLEL_FLAGS) \
		$(3) \
		$(RESUME_FLAGS) \
		$(DASHBOARD_FLAGS)
endef

test:
	$(PYTEST) tests/unit tests/integration

lint:
	$(RUFF) check scripts src/sage_ts tests/unit tests/integration

sage_agent:
	$(RUN_PYTHON) scripts/run_sage_agent_smoke.py \
		--dataset $(SAGE_DATASET) \
		--samples $(SAGE_SAMPLES) \
		--registry-dir $(SAGE_STANDALONE_REGISTRY) \
		--output-root $(SAGE_STANDALONE_OUTPUT_ROOT) \
		--reset-registry \
		$(DASHBOARD_FLAGS)

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

# ---------------------------------------------------------------------
# Smoke runs
# ---------------------------------------------------------------------

smoke6:
	$(call WRITE_DERIVED_SPLIT,$(SMOKE_SOURCE_MANIFEST),$(SMOKE6_MANIFEST),$(SMOKE_SOURCE_SPLIT),$(SMOKE6_SPLIT),6)
	$(call RUN_PROTOCOL,$(SMOKE6_MANIFEST),$(SMOKE6_SPLIT),$(PROTOCOL_GENERATION_FLAGS),6)

smoke12:
	$(call WRITE_DERIVED_SPLIT,$(SMOKE_SOURCE_MANIFEST),$(SMOKE12_MANIFEST),$(SMOKE_SOURCE_SPLIT),$(SMOKE12_SPLIT),12)
	$(call RUN_PROTOCOL,$(SMOKE12_MANIFEST),$(SMOKE12_SPLIT),$(PROTOCOL_GENERATION_FLAGS),12)

# ---------------------------------------------------------------------
# Viability / mechanism runs
# ---------------------------------------------------------------------

viability12:
	$(call WRITE_DERIVED_SPLIT,$(VIABILITY_SOURCE_MANIFEST),$(VIABILITY12_MANIFEST),$(VIABILITY_SOURCE_SPLIT),$(VIABILITY12_SPLIT),12)
	$(call RUN_PROTOCOL,$(VIABILITY12_MANIFEST),$(VIABILITY12_SPLIT),$(PROTOCOL_GENERATION_FLAGS),12)

mechanism12:
	$(call WRITE_DERIVED_SPLIT,$(MECHANISM12_SOURCE_MANIFEST),$(MECHANISM12_MANIFEST),$(MECHANISM12_SOURCE_SPLIT),$(MECHANISM12_SPLIT),12)
	$(call RUN_PROTOCOL,$(MECHANISM12_MANIFEST),$(MECHANISM12_SPLIT),$(PROTOCOL_GENERATION_FLAGS),12)

mechanism40:
	$(call RUN_PROTOCOL,$(CATEGORY_MANIFEST),$(MECHANISM40_SPLIT),$(PROTOCOL_GENERATION_FLAGS),40)

mechanism60:
	$(call WRITE_DERIVED_SPLIT,$(MECHANISM60_SOURCE_MANIFEST),$(MECHANISM60_MANIFEST),$(MECHANISM60_SOURCE_SPLIT),$(MECHANISM60_SPLIT),60)
	$(call RUN_PROTOCOL,$(MECHANISM60_MANIFEST),$(MECHANISM60_SPLIT),$(PROTOCOL_GENERATION_FLAGS),60)

# ---------------------------------------------------------------------
# POC reproduction
# ---------------------------------------------------------------------

reproduce_poc:
	@if [ -f "$(REGISTRY)/registry_manifest.json" ]; then \
		echo "Refusing to reproduce POC into non-empty REGISTRY=$(REGISTRY). Pass a fresh REGISTRY=..."; \
		exit 2; \
	fi
	@$(RUN_PYTHON) -c 'import json; from pathlib import Path; src=Path("$(POC_MANIFEST)"); dst=Path("$(POC_PROTOCOL_MANIFEST)"); data=json.loads(src.read_text()); rows=data["splits"]["relative_datetime_probe"]; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(json.dumps({"manifest_type":"sage_protocol_poc","splits":{"$(MECHANISM40_SPLIT)":rows}}, indent=2)+"\n"); print(f"Wrote {dst} with {len(rows)} scenarios as $(MECHANISM40_SPLIT)")'
	$(call RUN_PROTOCOL,$(POC_PROTOCOL_MANIFEST),$(MECHANISM40_SPLIT),$(PROTOCOL_GENERATION_FLAGS),40)

# ---------------------------------------------------------------------
# Transfer runs
# ---------------------------------------------------------------------

transfer_recency:
	$(call RUN_PROTOCOL,$(RECENCY_TRANSFER_MANIFEST),$(TRANSFER40_SPLIT),$(FROZEN_GENERATION_FLAGS),40)

transfer_relative_time:
	$(call RUN_PROTOCOL,$(RELATIVE_TIME_TRANSFER_MANIFEST),$(TRANSFER40_SPLIT),$(FROZEN_GENERATION_FLAGS),40)

transfer40:
	$(call RUN_PROTOCOL,$(CATEGORY_MANIFEST),$(TRANSFER40_SPLIT),$(FROZEN_GENERATION_FLAGS),40)

transfer60:
	$(call WRITE_DERIVED_SPLIT,$(TRANSFER60_SOURCE_MANIFEST),$(TRANSFER60_MANIFEST),$(TRANSFER60_SOURCE_SPLIT),$(TRANSFER60_SPLIT),60)
	$(call RUN_PROTOCOL,$(TRANSFER60_MANIFEST),$(TRANSFER60_SPLIT),$(FROZEN_GENERATION_FLAGS),60)

transfer100:
	$(call RUN_PROTOCOL,$(MANIFEST),$(TRANSFER100_SPLIT),$(FROZEN_GENERATION_FLAGS),100)

# ---------------------------------------------------------------------
# Confirmation / validation runs
# ---------------------------------------------------------------------

confirm100:
	$(call RUN_PROTOCOL,$(MANIFEST),$(CONFIRM100_SPLIT),$(FROZEN_GENERATION_FLAGS),100)

validate100:
	$(call RUN_PROTOCOL,$(MANIFEST),$(VALIDATE100_SPLIT),$(FROZEN_GENERATION_FLAGS),100)

validate250:
	$(call RUN_PROTOCOL,$(MANIFEST),$(VALIDATE250_SPLIT),$(FROZEN_GENERATION_FLAGS),250)

# ---------------------------------------------------------------------
# Reporting / utilities
# ---------------------------------------------------------------------

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
