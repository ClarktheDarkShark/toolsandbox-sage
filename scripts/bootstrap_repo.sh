#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(git remote get-url upstream 2>/dev/null || true)" != "https://github.com/apple/ToolSandbox.git" ]]; then
  echo "Expected upstream remote to be https://github.com/apple/ToolSandbox.git" >&2
  exit 1
fi

mkdir -p .secrets outputs
chmod 700 .secrets

if [[ ! -f .secrets/env.sh ]]; then
  cat > .secrets/env.sh <<'EOF'
#!/usr/bin/env bash
# Local only. Do not commit.
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export SAGE_TS_MODEL="${SAGE_TS_MODEL:-gpt-4o-mini}"
EOF
  chmod 600 .secrets/env.sh
fi

python scripts/check_no_secrets.py .env.example scripts docs src

echo "Repository bootstrap checks passed"
