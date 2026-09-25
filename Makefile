PYTHON ?= python
PYTHONPATH ?= src:.
PORT ?= 63105
DIST_DIR ?= dist
ROOT ?= .

COMMON_ENV = PYTHONPATH="$(PYTHONPATH)" POLARS_MAX_THREADS=1

.PHONY: compile package paper-online paper-frozen dashboard

compile:
	"$(PYTHON)" -m compileall -q -x '(^|/)(__pycache__|build)/' \
		src/sage_ts tool_sandbox scripts

package:
	"$(PYTHON)" -m pip wheel --no-deps --wheel-dir "$(DIST_DIR)" .

# Run one complete fresh-control/SAGE pair and open Task Compare externally.
paper-online:
	bash scripts/run_native_action_4omini_ab.sh full $(PORT) native-only

# Evaluate an existing registry. Set RESUME_REGISTRY_CHECKPOINT first.
paper-frozen:
	bash scripts/run_native_action_4omini_ab.sh full $(PORT) frozen-only

# Serve any generated or retained dashboard directory.
dashboard:
	$(COMMON_ENV) "$(PYTHON)" -m sage_ts.dashboard.server \
		--port $(PORT) --root "$(ROOT)"
