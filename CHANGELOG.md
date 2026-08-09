# Changelog

## Unreleased

- Reconcile the source repository with the verified Hermes serialized-result adapter.
- Add fail-open contract tests, staged installation, rollback, and RTK upstream compatibility automation.

## 1.3.0

- Adds the verified `transform_tool_result` output seam.
- Preserves serialized result metadata and fails open on unsupported or unsafe output.
- Keeps pre-execution RTK rewriting fail-open.
- Tested locally with RTK 0.42.4; compatibility with RTK 0.45.0 is a release gate.

## Prior releases

See the published PyPI history for pre-1.3.0 package releases. The GitHub source history before this migration contained a pip-only implementation and skill-validation workflow; it is not treated as evidence of the current verified adapter contract.
