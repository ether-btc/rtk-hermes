#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m py_compile "$ROOT/src/rtk_hermes/__init__.py"
python3 - <<'PY' "$ROOT/plugin.yaml"
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
for required in ("name: rtk-rewrite", 'version: "1.3.0"', "pre_tool_call", "transform_tool_result"):
    assert required in text, required
assert "transform_tool_call_result" not in text
PY
uv run --with pytest pytest -q
python3 "$ROOT/tests/verify_fidelity.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
"$ROOT/scripts/install.sh" --source "$ROOT" --target "$TMP/plugins/rtk-rewrite" --backup-root "$TMP/backups" >/tmp/rtk-hermes-install.log
[[ -f "$TMP/plugins/rtk-rewrite/__init__.py" ]]
[[ -f "$TMP/plugins/rtk-rewrite/plugin.yaml" ]]
python3 -m py_compile "$TMP/plugins/rtk-rewrite/__init__.py"
printf 'PASS: standalone adapter verification complete\n'
