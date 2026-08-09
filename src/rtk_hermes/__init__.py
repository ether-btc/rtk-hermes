"""Hermes plugin adapter for RTK command rewriting.

All rewrite logic lives in RTK's Rust ``rtk rewrite`` command; this module
only bridges Hermes ``pre_tool_call`` payloads to that command and fails open.

Also provides post-execution output compression via the ``transform_tool_result``
hook, delegating to rust_cave_001 when available (Layer 1 output-side
compression, complementary to pre-execution Layer 0 command rewriting).

Design decisions:
  - Thread-safe metrics via threading.RLock (fixes BUG-3 pattern from audit).
  - Exit code forwarding: returncode from terminal tool calls is stored
    so the output transformer can annotate failures.
  - All exceptions caught and logged; plugin never raises into agent loop.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

# Try to import rust_cave_001 for output-side compression (Layer 1).
# Keep the symbol defined when the optional extension is absent so contract
# tests and downstream diagnostics can inject/inspect the optional backend.
def _unavailable_compressor(_output: str) -> str:
    raise RuntimeError("rust_cave_001 is unavailable")


_rust_compress: Callable[[str], str] = _unavailable_compressor
try:
    from rust_cave_001 import compress_adaptive as _rust_compress

    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False


ACCEPTED_REWRITE_RETURN_CODES = frozenset({0, 3})
EXPECTED_PASSTHROUGH_RETURN_CODES = frozenset({1, 2})
_rtk_available: bool | None = None
_rtk_missing_warned = False


def _warn(message: str) -> None:
    print(f"rtk: hermes plugin warning: {message}", file=sys.stderr)


# ── RTK binary check ────────────────────────────────────────────────

def _check_rtk() -> bool:
    """Return whether the rtk binary is in PATH, warning once when missing."""
    global _rtk_available, _rtk_missing_warned

    if _rtk_available is None:
        _rtk_available = shutil.which("rtk") is not None

    if not _rtk_available and not _rtk_missing_warned:
        _warn("rtk binary not found in PATH; Hermes hook not registered")
        _rtk_missing_warned = True

    return _rtk_available


# ── Pre-execution command rewriting (Layer 0 input-side) ────────────

def _pre_tool_call(tool_name=None, args=None, **_kwargs):
    """Rewrite mutable Hermes terminal command args when RTK provides a change."""
    try:
        if tool_name != "terminal" or not isinstance(args, dict):
            return

        command = args.get("command")
        # R5-4: bump total_calls AFTER the empty/non-string check, so the
        # invariant total_calls == total_rewrites + total_passthrough +
        # total_errors + total_timeouts + total_skipped_empty holds.
        if not isinstance(command, str) or not command.strip():
            _bump("total_calls")
            _bump("total_skipped_empty")
            return

        _bump("total_calls")

        try:
            result = subprocess.run(
                ["rtk", "rewrite", command],
                shell=False,
                timeout=2,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            _warn("rtk rewrite timed out")
            _bump("total_timeouts")
            return

        if result.returncode not in ACCEPTED_REWRITE_RETURN_CODES:
            if result.returncode not in EXPECTED_PASSTHROUGH_RETURN_CODES:
                details = f"rtk rewrite failed with exit {result.returncode}"
                stderr = result.stderr.strip()
                if stderr:
                    details = f"{details}: {stderr}"
                _warn(details)
                _bump("total_errors")
            else:
                _bump("total_passthrough")
            return

        rewritten = result.stdout.strip()
        if rewritten and rewritten != command:
            args["command"] = rewritten
            _bump("total_rewrites")
            _bump("total_bytes_in", len(command))
            _bump("total_bytes_out", len(rewritten))
        else:
            _bump("total_passthrough")
    except Exception as e:  # noqa: BLE001 - plugin boundary is intentionally fail-open
        _warn(str(e))
        _bump("total_errors")
        return


# ── Metrics (thread-safe) ──────────────────────────────────────────

@dataclass
class RtkMetrics:
    """Thread-safe metrics for the rtk-rewrite plugin.

    The dataclass remains deliberately compatible with Python 3.9, the
    package minimum; metric field names are still validated by _bump.
    """
    total_calls: int = 0
    total_rewrites: int = 0
    total_passthrough: int = 0
    total_timeouts: int = 0
    total_errors: int = 0
    total_bytes_in: int = 0
    total_bytes_out: int = 0
    total_output_compressed: int = 0
    total_disabled: int = 0
    total_skipped_empty: int = 0


_METRICS_LOCK = threading.RLock()
_metrics = RtkMetrics()


def get_metrics() -> RtkMetrics:
    """Return a snapshot of current metrics (thread-safe copy)."""
    with _METRICS_LOCK:
        return RtkMetrics(
            total_calls=_metrics.total_calls,
            total_rewrites=_metrics.total_rewrites,
            total_passthrough=_metrics.total_passthrough,
            total_timeouts=_metrics.total_timeouts,
            total_errors=_metrics.total_errors,
            total_bytes_in=_metrics.total_bytes_in,
            total_bytes_out=_metrics.total_bytes_out,
            total_output_compressed=_metrics.total_output_compressed,
            total_disabled=_metrics.total_disabled,
            total_skipped_empty=_metrics.total_skipped_empty,
        )


def reset_metrics() -> None:
    """Reset all metrics to zero (thread-safe)."""
    global _metrics
    with _METRICS_LOCK:
        _metrics = RtkMetrics()


def _bump(field: str, amount: int = 1) -> None:
    """Thread-safe metric increment.

    Relies on RtkMetrics(slots=True) to raise AttributeError on a typo,
    so a wrong field name is caught here and logged instead of propagating
    into the agent pipeline. Fail-open: if a metric field is mistyped,
    log a warning and continue — the plugin should never crash the agent
    loop because of a counter typo. See R5-3.
    """
    with _METRICS_LOCK:
        try:
            current = getattr(_metrics, field)  # no default — typo raises
            setattr(_metrics, field, current + amount)
        except AttributeError as e:
            _warn(f"metric typo: {e}")


# ── Post-execution output compression (Layer 1 — rust_cave_001) ──────

# Patterns that indicate structured data we should not compress
_JSON_RE = re.compile(r'^\s*[\{\[]')
_TOOL_OUTPUT_RE = re.compile(
    r'(exit_code|stderr|stdout|return_code|error)\s*:',
    re.IGNORECASE,
)

# Minimum output length to attempt compression
_MIN_OUTPUT_CHARS = 200


def _transform_terminal_output(
    output: str,
    returncode: int = 0,
    **_kwargs,
) -> str | None:
    """Compress terminal output via rust_cave_001 (Layer 1).

    Called from the transform_tool_result hook. Returns compressed text
    or None if output should pass through unchanged.
    """
    if not output or not output.strip():
        return None

    if len(output) < _MIN_OUTPUT_CHARS:
        return None

    # Skip structured data (JSON, tool output format)
    if _JSON_RE.match(output) or _TOOL_OUTPUT_RE.search(output):
        return None

    if not _RUST_AVAILABLE:
        return None

    try:
        compressed = _rust_compress(output)
    except Exception:
        # Symmetric with rust_cave_output: catch all from the Rust ext so
        # one transient error in rust_cave_001 cannot poison the agent loop.
        logger.debug("rust_cave_001 compression failed", exc_info=True)
        return None

    if not compressed or len(compressed) >= len(output):
        return None

    _bump("total_output_compressed")
    _bump("total_bytes_in", len(output.encode("utf-8")))
    _bump("total_bytes_out", len(compressed.encode("utf-8")))

    # Annotate failure outputs
    if returncode != 0:
        return f"[rc={returncode}] {compressed}"

    return compressed


# ── Hook registration ──────────────────────────────────────────────

def register(ctx):
    """Register Hermes hooks for this plugin.

    Registers:
      - pre_tool_call: rewrites terminal commands via ``rtk rewrite`` (Layer 0 input)
        - transform_tool_result: compresses terminal output via
          rust_cave_001 (Layer 1 output)

    Both hooks are registered when RTK binary is available.
    Output compression is registered even without RTK binary if rust_cave_001
    is available, so the two layers are independently operable.

    Fail-open: if a hook name doesn't exist in this Hermes version (raises
    AttributeError or TypeError from ``register_hook``), log a warning and
    continue rather than crashing the plugin loader.
    """
    rtk_ok = _check_rtk()

    if rtk_ok:
        try:
            ctx.register_hook("pre_tool_call", _pre_tool_call)
        except (AttributeError, TypeError) as e:
            _warn(f"pre_tool_call hook unavailable in this Hermes version: {e}")

    # Always try to register output compression if rust_cave is available
    if _RUST_AVAILABLE:
        _register_output_hook(ctx)
    elif not rtk_ok:
        _warn("Neither rtk binary nor rust_cave_001 available; plugin has no effect")


def _register_output_hook(ctx):
    """Register the active Hermes result-transform hook.

    Hermes' current dispatcher invokes ``transform_tool_result`` and passes
    the serialized tool result string.  ``register_hook`` accepts arbitrary
    names, so trying a speculative alias first does not provide a reliable
    compatibility check: it can silently register a hook that Hermes never
    dispatches.  Keep the active contract explicit and fail open if it is
    unavailable.
    """
    try:
        ctx.register_hook("transform_tool_result", _pre_tool_call_result)
    except (AttributeError, TypeError) as e:
        _warn(f"transform_tool_result hook unavailable: {e}")


def _pre_tool_call_result(tool_name: str = "", result=None, **_kwargs):
    """Hook: compress terminal tool output after execution (Layer 1).

    Hermes passes a serialized result string and expects a replacement string.
    The current terminal result uses ``output`` plus a numeric ``code``;
    ``exit_code`` and ``returncode`` are accepted for compatibility.  A dict
    shape is also supported for direct callers and older local tests.
    Returns None when no transformation is appropriate.
    """
    if not result or tool_name != "terminal":
        return None

    serialized = isinstance(result, str)
    if serialized:
        try:
            payload = json.loads(result)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        output = payload.get("output", "")
        returncode = payload.get(
            "exit_code", payload.get("returncode", payload.get("code", 0))
        )
        compressed = _transform_terminal_output(str(output or ""), int(returncode or 0))
        if compressed is None:
            return None
        payload["output"] = compressed
        return json.dumps(payload, ensure_ascii=False)

    if not isinstance(result, dict):
        return None

    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    if not stdout and not stderr and "output" in result:
        compressed = _transform_terminal_output(
            str(result.get("output") or ""),
            int(result.get("exit_code", result.get("code", 0)) or 0),
        )
        if compressed is None:
            return None
        result["output"] = compressed
        return result

    returncode = result.get("returncode", result.get("exit_code", result.get("code", 0)))

    # Combine stdout + stderr for classification
    combined = stdout if stdout else ""
    if stderr:
        combined = f"{combined}\n{stderr}" if combined else stderr

    if not combined.strip():
        return None

    compressed = _transform_terminal_output(combined, returncode)

    if compressed is None:
        return None

    # Write back compressed output
    if stdout and stderr:
        result["stdout"] = compressed
        result["stderr"] = ""
    elif stdout:
        result["stdout"] = compressed
    elif stderr:
        result["stderr"] = compressed

    return result
