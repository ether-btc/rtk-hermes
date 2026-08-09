#!/usr/bin/env python3
"""Portable deterministic fidelity gate for the serialized Hermes seam.

CI uses a deterministic stand-in compressor to test envelope preservation and
fail-open behavior. The host project separately runs the real rust_cave_001
compressor and records host-local performance observations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import rtk_hermes


def compress(output: str) -> str:
    return "compressed: " + output[:48]


def main() -> int:
    rtk_hermes._RUST_AVAILABLE = True
    rtk_hermes._rust_compress = compress
    fixtures = {
        "repetitive": "diagnostic line: unchanged\n" * 100,
        "json": json.dumps({"items": [{"id": i} for i in range(40)]}),
        "failing": "failure detail\n" * 100,
    }
    for name, output in fixtures.items():
        payload = {
            "output": output,
            "code": 7 if name == "failing" else 0,
            "exit_code": 7 if name == "failing" else 0,
            "returncode": 7 if name == "failing" else 0,
            "error": "failed" if name == "failing" else None,
            "fixture": name,
            "opaque": {"n": 42},
        }
        raw = json.dumps(payload)
        transformed = rtk_hermes._pre_tool_call_result("terminal", raw)
        result = payload if transformed is None else json.loads(transformed)
        for field in ("code", "exit_code", "returncode", "error", "fixture", "opaque"):
            assert result[field] == payload[field], f"{name}.{field} changed"
        if name == "json":
            assert result["output"] == output
            json.loads(result["output"])
        if name == "failing" and result["output"] != output:
            assert result["output"].startswith("[rc=7] ")
    print("PASS: portable serialized-result fidelity gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
