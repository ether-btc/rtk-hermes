# RTK-Hermes adapter

Standalone Hermes integration for RTK. It owns the Hermes plugin boundary; RTK remains the upstream owner of the Rust CLI, rewrite rules, formatters, and binaries.

## Verified contract

- `pre_tool_call` rewrites terminal commands through `rtk rewrite`.
- `transform_tool_result` receives serialized JSON and returns a serialized replacement string when safe to transform.
- `output`, `code`, `exit_code`, `returncode`, `error`, and unknown metadata are preserved.
- JSON, unsupported shapes, compressor failures, missing RTK, and RTK failures pass through without blocking command execution.

The optional output compressor is `rust_cave_001`; it is not a mandatory package dependency.

## Development

```bash
uv run --with pytest pytest -q
./scripts/verify.sh
```

## Installation

Preferred source/entry-point installation for a canary:

```bash
uv pip install --system .
```

Or use the staged directory installer:

```bash
./scripts/install.sh --source . --target "$HOME/.hermes/plugins/rtk-rewrite"
```

The installer creates a backup before replacement and prints the rollback command. It never changes Hermes global configuration and does not activate telemetry.

## RTK compatibility

See `UPSTREAM.md`. Stable releases pin and test explicit RTK versions. A scheduled workflow checks new RTK releases and a non-blocking development branch; no upstream change is deployed automatically.
