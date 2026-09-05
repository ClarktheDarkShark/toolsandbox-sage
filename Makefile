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
VALIDATION_THRESHOLDS ?=
PILOT_EVIDENCE ?=
SOURCE_REGISTRY_IDENTITY ?=
APPROVE_LIVE_RUN ?= NO
APPROVE_SELECTOR_FULL ?= NO

COMMON_ENV = PYTHONPATH=$(PYTHONPATH) POLARS_MAX_THREADS=1

.PHONY: \
	compile lint test-core test package \
	spotcheck paper-online paper-frozen selector-pilot selector-full sample full \
	prepare-paper-rerun verify-publication verify-sample verify-campaign verify-environment verify-inputs verify-freeze \
	analyze render-paper \
	require-run require-sample-report require-campaign-manifest require-analysis-output \
	require-evidence-data require-table-output require-validation-thresholds \
	require-live-run-approval require-selector-full-approval require-pilot-evidence \
	require-source-registry-identity

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
		tests/unit/test_actor_selection_comparison.py \
		tests/unit/test_outcome_score.py \
		tests/unit/test_outcome_score_v4_evidence.py \
		tests/unit/test_outcome_score_v4_state_safety.py \
		tests/unit/test_historical_outcome_rescore.py \
		tests/unit/test_online_birth.py \
		tests/unit/test_tool_generator.py \
		tests/unit/test_self_evolution_reflection.py \
		tests/unit/test_protocol_generation_policy.py \
		tests/unit/test_registry_content_identity.py \
		tests/unit/test_publication_run_verifier.py \
		tests/unit/test_publication_sample_verifier.py \
		tests/unit/test_publication_campaign.py \
		tests/unit/test_publication_environment.py \
		tests/unit/test_publication_inputs.py \
		tests/unit/test_publication_freeze.py \
		tests/unit/test_dashboard_exporters.py \
		tests/unit/test_rapid_api_cache.py \
		tests/integration/test_toolsandbox_generated_tool_injection.py \
		-q

test:
	$(COMMON_ENV) $(PYTHON) -m pytest tests/unit tests/integration -q

package:
	$(PYTHON) -m build --outdir $(DIST_DIR)

# Outcome-only operational check of the reduced production application. This
# runs the pinned representative 30-task cohort with the normal policy actor,
# a fresh non-learning control, concurrent isolated arms, no application-level
# response/result cache, and the externally opened Task Compare dashboard.
# It is an operational check, not a substitute for a complete 1,032-task run
# or an inferential publication replication.
spotcheck: require-live-run-approval
	bash scripts/run_native_action_4omini_ab.sh spotcheck $(PORT) native-only

# One complete 1,032-task online-build sample. The launcher runs the live
# non-learning control and SAGE concurrently, opens the current Task Compare in
# an external browser, disables application response/task/persistent-output
# replay, checks the pinned fixture, starts from an empty registry, and verifies
# the publication run after completion. Invoke only after researcher approval.
paper-online: require-live-run-approval
	SAGE_APPROVE_LIVE_RUN=YES bash scripts/run_native_action_4omini_ab.sh full $(PORT) native-only

# Evaluate one already-built registry with the same strict fresh-control rules.
# Set RESUME_REGISTRY_CHECKPOINT to the source registry before invoking.
paper-frozen: require-live-run-approval require-source-registry-identity
	SAGE_APPROVE_LIVE_RUN=YES \
	SAGE_EXPECTED_SOURCE_REGISTRY_IDENTITY="$(SOURCE_REGISTRY_IDENTITY)" \
		bash scripts/run_native_action_4omini_ab.sh full $(PORT) frozen-only

# Sealed 30-task policy-vs-auto feasibility pilot. The control and policy SAGE
# donor run concurrently; after donor inventory exists, an independent fresh
# control and matched auto replay run concurrently. Both live-pair dashboards
# open externally before model execution; the policy/auto view opens afterward.
selector-pilot: require-live-run-approval
	SAGE_APPROVE_LIVE_RUN=YES bash scripts/run_native_action_4omini_ab.sh pilot $(PORT) native-only

# Complete matched actor-selection comparison. This requires a verified pilot
# manifest plus a separate, explicit approval for the full selector run.
selector-full: require-live-run-approval require-selector-full-approval require-pilot-evidence
	SAGE_AUTO_SELECTION_EXPERIMENT=1 \
	SAGE_AUTO_SELECTION_PILOT_EVIDENCE="$(PILOT_EVIDENCE)" \
	SAGE_APPROVE_LIVE_RUN=YES \
		bash scripts/run_native_action_4omini_ab.sh full $(PORT) native-only

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

require-live-run-approval:
	@test "$(APPROVE_LIVE_RUN)" = "YES" || \
		(echo "Live model execution requires explicit approval: set APPROVE_LIVE_RUN=YES." >&2; exit 2)

require-selector-full-approval:
	@test "$(APPROVE_SELECTOR_FULL)" = "YES" || \
		(echo "The complete selector comparison needs separate approval: set APPROVE_SELECTOR_FULL=YES." >&2; exit 2)

require-pilot-evidence:
	@test -n "$(PILOT_EVIDENCE)" || \
		(echo "Set PILOT_EVIDENCE to a passing actor_selection_experiment_manifest.json." >&2; exit 2)

require-source-registry-identity:
	@test -n "$(SOURCE_REGISTRY_IDENTITY)" || \
		(echo "Set SOURCE_REGISTRY_IDENTITY to the paired online registry_identity_after_run.json." >&2; exit 2)

verify-publication: require-run
	$(COMMON_ENV) $(PYTHON) scripts/verify_publication_run.py \
		--search-root "$(RUN)" \
		--cohort full \
		--expect-reflection "$(REFLECTION_EXPECTATION)"

require-validation-thresholds:
	@test -n "$(VALIDATION_THRESHOLDS)" || \
		(echo "Set VALIDATION_THRESHOLDS=docs/sage_protocol/publication_validation_thresholds_v4.json." >&2; exit 2)

verify-sample: require-run require-validation-thresholds
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
