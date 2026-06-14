PYTHON ?= python
PYTHONPATH ?= src:.
MODEL ?= gpt-4o-mini
USER_MODEL ?= gpt-4o-mini
GENERATION_MODEL ?= gpt-4o-mini
PORT ?= 62624

MANIFEST_FULL ?= docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json
MANIFEST_500 ?= docs/sage_protocol/manifests/v2_1_formal_500.json
REGISTRY ?= artifacts/sage/manual_registry
OUTPUT_ROOT ?= outputs/sage/manual_run
ARTIFACT_ROOT ?= artifacts/sage/manual_run_artifacts
CONTROL_CACHE_ROOT ?= artifacts/baselines/control_task_baselines

COMMON_ENV = PYTHONPATH=$(PYTHONPATH) \
	SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
	TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
	TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json \
	POLARS_MAX_THREADS=1

SAGE_RUN_ENV = $(COMMON_ENV) \
	SAGE_PRAXIS_BRIDGE_POLICY=disabled \
	SAGE_SCENARIO_METADATA_POLICY=visible_context \
	SAGE_DISABLE_SCENARIO_NAME_BIRTH=1 \
	SAGE_DISABLE_SCENARIO_NAME_ROUTING=1 \
	SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=0 \
	SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY=0 \
	SAGE_SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS=0 \
	SAGE_GENERATED_TOOL_GUIDANCE_MODE=minimal \
	SAGE_GENERATED_TOOL_DOCSTRING_MODE=compact \
	SAGE_GENERATED_TOOL_FIRST_ATTEMPT_CHOICE=1 \
	SAGE_GENERATED_TOOL_CONTINUATION_CHOICE=1 \
	SAGE_GENERATED_TOOL_CONTRACT_RETRY_ATTEMPTS=0 \
	SAGE_GENERATED_TOOL_SYNTHETIC_REPAIR=0 \
	SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE=4 \
	SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS=120

.PHONY: compile test-core test full500 full figures dashboard

compile:
	$(COMMON_ENV) $(PYTHON) -m py_compile \
		scripts/run_sage_protocol.py \
		scripts/prepare_toolsandbox_full_self_evolving_run.py \
		src/sage_ts/adapters/sage_run_adapter.py \
		src/sage_ts/runtime/toolsandbox_integration.py \
		src/sage_ts/generation/tool_generator.py

test-core:
	$(COMMON_ENV) $(PYTHON) -m pytest \
		tests/unit/test_sage_run_adapter.py \
		tests/unit/test_online_birth.py \
		tests/unit/test_openai_toolsandbox_roles.py \
		tests/unit/test_tool_generator.py \
		tests/unit/test_helper_contribution.py \
		tests/unit/test_dashboard_exporters.py \
		tests/unit/test_control_baseline_cache.py \
		tests/integration/test_toolsandbox_generated_tool_injection.py \
		-q

test:
	$(COMMON_ENV) $(PYTHON) -m pytest tests/unit tests/integration -q

full500:
	$(SAGE_RUN_ENV) $(PYTHON) scripts/run_sage_protocol.py \
		--mode online_build_500 \
		--manifest $(MANIFEST_500) \
		--registry-dir $(REGISTRY) \
		--sage-policy self-evolving-praxis \
		--agent $(MODEL) \
		--user $(USER_MODEL) \
		--generation-model $(GENERATION_MODEL) \
		--generation on \
		--disable-openai-response-cache \
		--cache-mode off \
		--control-cache use-if-eligible \
		--control-cache-root $(CONTROL_CACHE_ROOT) \
		--routing-evidence-mode disabled \
		--freeze-toolsandbox-clock \
		--dashboard-port $(PORT) \
		--output-root $(OUTPUT_ROOT) \
		--artifact-root $(ARTIFACT_ROOT)

full:
	$(SAGE_RUN_ENV) $(PYTHON) scripts/run_sage_protocol.py \
		--mode online_build_full \
		--manifest $(MANIFEST_FULL) \
		--registry-dir $(REGISTRY) \
		--sage-policy self-evolving-praxis \
		--agent $(MODEL) \
		--user $(USER_MODEL) \
		--generation-model $(GENERATION_MODEL) \
		--generation on \
		--disable-openai-response-cache \
		--cache-mode off \
		--control-cache use-if-eligible \
		--control-cache-root $(CONTROL_CACHE_ROOT) \
		--routing-evidence-mode disabled \
		--freeze-toolsandbox-clock \
		--dashboard-port $(PORT) \
		--output-root $(OUTPUT_ROOT) \
		--artifact-root $(ARTIFACT_ROOT)

figures:
	$(PYTHON) scripts/render_chapter3_sage_figures.py

dashboard:
	$(COMMON_ENV) $(PYTHON) scripts/export_dashboard_data.py --protocol-run-root $(RUN)
