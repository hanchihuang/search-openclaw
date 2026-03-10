#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "==> Search OpenClaw one-click installer"
echo "repo: $ROOT"
echo "venv: $VENV_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: $PYTHON_BIN not found"
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null
python -m pip install -e "$ROOT"
python -m playwright install chromium

search-openclaw install
search-openclaw doctor --fix || true

if [ -n "${BRAVE_API_KEY:-}" ]; then
  search-openclaw configure brave_api_key "$BRAVE_API_KEY"
fi

if [ -n "${TAVILY_API_KEY:-}" ]; then
  search-openclaw configure tavily_api_key "$TAVILY_API_KEY"
fi

if [ -n "${ZHIHU_COOKIE:-}" ]; then
  search-openclaw configure zhihu_cookie "$ZHIHU_COOKIE"
fi

if [ "${SMOKE_TEST:-0}" = "1" ]; then
  QUERY="${SMOKE_QUERY:-OpenClaw 搜索配置建议}"
  echo
  echo "==> Running smoke test"
  search-openclaw doctor
  if ! search-openclaw search "$QUERY"; then
    echo "warning: smoke search failed. Check your provider key and rerun with ./scripts/start.sh search \"$QUERY\""
  fi
fi

if [ "${LOGIN_X:-0}" = "1" ]; then
  echo
  echo "==> Starting X login flow"
  search-openclaw login-x
fi

cat <<'EOF'

Install complete.

Try these next:
  1. search-openclaw configure brave_api_key <YOUR_KEY>
  2. search-openclaw doctor
  3. search-openclaw search "latest AI agent news"
  4. search-openclaw login-x
  5. search-openclaw scrape-social "AI Agent" --platform both

Or use the wrapper:
  ./scripts/start.sh doctor
  ./scripts/start.sh search "OpenClaw search setup"
  LOGIN_X=1 ./scripts/install.sh
EOF
