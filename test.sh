#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

python3 - "$ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
skip_parts = {"output", ".git", ".pytest_cache", "__pycache__"}
md_files = sorted(
    path for path in root.rglob("*.md") if not any(part in skip_parts for part in path.relative_to(root).parts)
)
if not md_files:
    raise SystemExit("No markdown files found")

link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
bad = []

for md in md_files:
    text = md.read_text(encoding="utf-8")
    for _, target in link_re.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = (md.parent / target).resolve()
        if not path.exists():
            bad.append(f"{md.relative_to(root)} -> {target}")

required = [
    root / "README.md",
    root / "CONTRIBUTING.md",
    root / "LICENSE",
    root / "docs" / "web-search.md",
    root / "docs" / "search-routes.md",
    root / "docs" / "faq.md",
]

missing = [str(p.relative_to(root)) for p in required if not p.exists()]

if missing:
    print("Missing required files:")
    for item in missing:
        print(f"  - {item}")
    raise SystemExit(1)

if bad:
    print("Broken markdown links:")
    for item in bad:
        print(f"  - {item}")
    raise SystemExit(1)

print(f"Checked {len(md_files)} markdown files")
print("All required files exist")
print("All local markdown links are valid")
PY

if [ -f "$ROOT/pyproject.toml" ]; then
  PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q
fi
