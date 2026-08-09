# Contributing

Run the complete local gate before opening a pull request:

```bash
uv run --with pytest pytest -q
./scripts/verify.sh
```

Changes touching RTK or Hermes compatibility must include a focused regression fixture and update `UPSTREAM.md` or `CHANGELOG.md` when the tested compatibility range changes.

Do not vendor RTK Rust source. Do not silently change the installed Hermes plugin. Keep failures fail-open and preserve unknown serialized-result metadata.
