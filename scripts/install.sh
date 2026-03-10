#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TARGET="${TARGET:-both}"

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

echo
echo "Install complete."
echo
echo "Suggested next step for TARGET=$TARGET:"
case "$TARGET" in
  x)
    cat <<'EOF'
  ./scripts/start.sh login-x
  ./scripts/start.sh scrape-social "AI Agent" --platform x --max-items 200 --max-scrolls 80
EOF
    ;;
  zhihu)
    cat <<'EOF'
  ./scripts/start.sh scrape-social "AI Agent" --platform zhihu --max-items 220 --max-scrolls 160 --no-new-stop 24 --page-delay-ms 1300 --stage1-only
EOF
    ;;
  both)
    cat <<'EOF'
  ./scripts/start.sh login-x
  ./scripts/start.sh scrape-social "AI Agent" --platform x --max-items 200 --max-scrolls 80
  ./scripts/start.sh scrape-social "AI Agent" --platform zhihu --max-items 220 --max-scrolls 160 --no-new-stop 24 --page-delay-ms 1300 --stage1-only
EOF
    ;;
  *)
    cat <<'EOF'
  ./scripts/start.sh doctor
  ./scripts/start.sh search "OpenClaw search setup"
EOF
    ;;
esac

cat <<'EOF'

You can also rerun:
  TARGET=x ./scripts/install.sh
  TARGET=zhihu ./scripts/install.sh
  TARGET=both ./scripts/install.sh
  LOGIN_X=1 ./scripts/install.sh
EOF
