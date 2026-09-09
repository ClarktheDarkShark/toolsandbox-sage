PYTHON ?= python
PYTHONPATH ?= src:.
PORT ?= 63105
DIST_DIR ?= dist

RUN ?=
REFLECTION_EXPECTATION ?= same-run-fresh
CAMPAIGN_MANIFEST ?=
CAMPAIGN_ARGS ?=
SAMPLE_REPORT ?=
ANALYSIS_OUTPUT ?=
EVIDENCE_DATA ?=
TABLE_OUTPUT ?=
VALIDATION_THRESHOLDS ?= docs/sage_protocol/publication_validation_thresholds_v2.json

COMMON_ENV = PYTHONPATH=$(PYTHONPATH) POLARS_MAX_THREADS=1

.PHONY: \
	compile lint test-core test package \
	paper-online paper-frozen sample full \
	prepare-paper-rerun verify-publication verify-sample verify-campaign verify-environment verify-inputs verify-freeze \
	analyze render-paper \
	require-run require-sample-report require-campaign-manifest require-analysis-output \
	require-evidence-data require-table-output

compile:
	$(PYTHON) -m compileall -q -x '(^|/)(__pycache__|build)/' \
		src/sage_ts tool_sandbox scripts

lint:
	$(PYTHON) -m ruff check --exclude '*.ipynb' \
		src/sage_ts tool_sandbox scripts tests
	$(PYTHON) -m ruff format --check --exclude '*.ipynb' \
		src/sage_ts tool_sandbox scripts tests

test-core:
	$(COMMON_ENV) $(PYTHON) -m pytest \
		tests/unit/test_sage_run_adapter.py \
		tests/unit/test_toolsandbox_adapter.py \
		tests/unit/test_openai_toolsandbox_roles.py \
		tests/unit/test_online_birth.py \
		tests/unit/test_tool_generator.py \
		tests/unit/test_control_baseline_cache.py \
		tests/unit/test_self_evolution_reflection.py \
		tests/unit/test_online_feedback_score.py \
		tests/unit/test_outcome_score.py \
		tests/unit/test_outcome_score_v4_evidence.py \
		tests/unit/test_outcome_score_v4_state_safety.py \
		tests/unit/test_protocol_generation_policy.py \
		tests/unit/test_publication_run_verifier.py \
		tests/unit/test_publication_sample_verifier.py \
		tests/unit/test_publication_campaign.py \
		tests/unit/test_publication_environment.py \
		tests/unit/test_publication_inputs.py \
		tests/unit/test_publication_freeze.py \
		tests/unit/test_rapid_api_cache.py \
		tests/unit/test_dashboard_exporters.py \
		tests/integration/test_toolsandbox_generated_tool_injection.py \
		-q

test:
	$(COMMON_ENV) $(PYTHON) -m pytest tests/unit tests/integration -q

package:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir $(DIST_DIR) .

# One complete 1,032-task online-build sample. The launcher starts the control
# and policy-directed SAGE in isolated concurrent processes, streams each fresh
# control row at the matched task boundary, disables task/result replay, opens
# the verified Task Compare dashboard, and verifies the completed pair.
paper-online:
	bash scripts/run_native_action_4omini_ab.sh full $(PORT) native-only

# Evaluate one already-built registry with the same strict fresh-control rules.
# Set RESUME_REGISTRY_CHECKPOINT to the source registry before invoking.
paper-frozen:
	bash scripts/run_native_action_4omini_ab.sh full $(PORT) frozen-only

sample: paper-online

# Backwards-compatible name; unlike the historical target, this cannot enable
# the hybrid baseline cache.
full: paper-online

# This only writes a timestamped campaign plan. It never starts model calls.
# Add preparation overrides through CAMPAIGN_ARGS when needed.
require-sample-report:
	@test -n "$(SAMPLE_REPORT)" || \
		(echo "Set SAMPLE_REPORT to a passing publication_validation_report.json." >&2; exit 2)

prepare-paper-rerun: require-sample-report
	$(COMMON_ENV) $(PYTHON) scripts/run_chapter4_evidence_campaign.py prepare \
		--repo-root . \
		--sample-validation-report "$(SAMPLE_REPORT)" \
		$(CAMPAIGN_ARGS)

require-run:
	@test -n "$(RUN)" || \
		(echo "Set RUN to the publication run search root." >&2; exit 2)

verify-publication: require-run
	$(COMMON_ENV) $(PYTHON) scripts/verify_publication_run.py \
		--search-root "$(RUN)" \
		--expected-tasks 1032 \
		--expect-reflection "$(REFLECTION_EXPECTATION)"

verify-sample: require-run
	$(COMMON_ENV) $(PYTHON) scripts/verify_publication_sample.py \
		--search-root "$(RUN)" \
		--thresholds "$(VALIDATION_THRESHOLDS)"

require-campaign-manifest:
	@test -n "$(CAMPAIGN_MANIFEST)" || \
		(echo "Set CAMPAIGN_MANIFEST to a prepared campaign_manifest.json." >&2; exit 2)

verify-campaign: require-campaign-manifest
	$(COMMON_ENV) $(PYTHON) scripts/run_chapter4_evidence_campaign.py verify \
		--repo-root . \
		--campaign-manifest "$(CAMPAIGN_MANIFEST)"

# Exact interpreter/platform/distribution check for strict publication runs.
verify-environment:
	$(PYTHON) scripts/verify_publication_environment.py

# Clean-clone check of only the compact inputs published in Git.
verify-inputs:
	$(COMMON_ENV) $(PYTHON) scripts/verify_publication_inputs.py

# Optional deep audit of the ignored 23 MB local recovery bundle.
verify-freeze:
	$(COMMON_ENV) $(PYTHON) scripts/build_publication_freeze.py verify

require-analysis-output:
	@test -n "$(ANALYSIS_OUTPUT)" || \
		(echo "Set ANALYSIS_OUTPUT to a new, timestamped output directory." >&2; exit 2)

analyze: require-campaign-manifest require-analysis-output
	$(COMMON_ENV) $(PYTHON) scripts/build_chapter4_evidence_dashboard.py \
		--repo-root . \
		--campaign-manifest "$(CAMPAIGN_MANIFEST)" \
		--output-dir "$(ANALYSIS_OUTPUT)"

require-evidence-data:
	@test -n "$(EVIDENCE_DATA)" || \
		(echo "Set EVIDENCE_DATA to a versioned chapter4_evidence_data.json." >&2; exit 2)

require-table-output:
	@test -n "$(TABLE_OUTPUT)" || \
		(echo "Set TABLE_OUTPUT to a new, timestamped table directory." >&2; exit 2)

render-paper: require-evidence-data require-table-output
	$(COMMON_ENV) $(PYTHON) scripts/render_chapter4_evidence_tables.py \
		--data "$(EVIDENCE_DATA)" \
		--output-dir "$(TABLE_OUTPUT)"
