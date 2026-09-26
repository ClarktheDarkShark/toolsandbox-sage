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
	@set -eu; \
	dirty_tree="$$(git status --porcelain=v1 --untracked-files=all)"; \
	if [ -n "$$dirty_tree" ]; then \
		echo "Refusing to package a dirty Git tree:" >&2; \
		printf '%s\n' "$$dirty_tree" >&2; \
		exit 1; \
	fi; \
	package_tmp="$$(mktemp -d "$${TMPDIR:-/tmp}/sage-package.XXXXXX")"; \
	[ -n "$$package_tmp" ] && [ -d "$$package_tmp" ]; \
	trap 'rm -r -- "$$package_tmp"' EXIT; \
	mkdir "$$package_tmp/source" "$$package_tmp/wheels"; \
	git archive --format=tar --output="$$package_tmp/source.tar" HEAD; \
	tar -xf "$$package_tmp/source.tar" -C "$$package_tmp/source"; \
	package_epoch="$$(git show -s --format=%ct HEAD)"; \
	SOURCE_DATE_EPOCH="$$package_epoch" "$(PYTHON)" -m pip wheel --no-deps \
		--wheel-dir "$$package_tmp/wheels" "$$package_tmp/source"; \
	set -- "$$package_tmp"/wheels/*.whl; \
	[ "$$#" -eq 1 ] && [ -f "$$1" ]; \
	mkdir -p "$(abspath $(DIST_DIR))"; \
	cp "$$1" "$(abspath $(DIST_DIR))/"

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
