# Upstream compatibility policy

The adapter is a separate Hermes integration. RTK remains the upstream owner of the Rust CLI, rewrite rules, formatters, and binary releases.

## Inputs we track

- RTK releases: `rtk-ai/rtk`, blocking matrix job.
- RTK `develop`/`main`: non-blocking early-warning job.
- Hermes releases and plugin/hook changes, especially `transform_tool_result` and plugin discovery.
- Issues involving JSON, piped output, structured output, exit codes, and formatter changes.

## Compatibility policy

- Adapter releases use independent semantic versions.
- `RTK_MIN_VERSION` and `RTK_TESTED_VERSION` are recorded in CI and release notes.
- Supported-version failures block a release.
- Development-branch failures open/update an issue but do not block stable releases.
- Upstream changes are reviewed semantically; the watcher never deploys or publishes automatically.

## Scheduled workflow

`.github/workflows/upstream-compat.yml` runs weekly and on demand. It reads the latest RTK release through the GitHub API, runs the test matrix, and opens a deduplicated compatibility issue when the latest release or development branch fails.

The workflow intentionally does not use a floating RTK checkout in the blocking job. The release under test is explicit in the matrix, and the development job is marked non-blocking.

## Release gate

1. Read RTK and Hermes release notes.
2. Run unit, serialized-hook, fail-open, fidelity, build, and install-smoke tests.
3. Review any output/formatter changes and add a regression fixture.
4. Record tested RTK and Hermes versions in `CHANGELOG.md`.
5. Build artifacts and inspect them.
6. Stage installation in a temporary Hermes plugin directory.
7. Verify staged files, then activate only through the documented installer.
8. Retain the prior backup and test rollback.

## Ownership routing

- RTK algorithm, formatter, CLI, or binary defect: file upstream in `rtk-ai/rtk`.
- Hermes hook/discovery contract: file upstream in `NousResearch/hermes-agent`.
- Envelope preservation, fail-open behavior, packaging, install, or rollback: fix here.

## Current baseline

At the initial source-repository migration, the host reports RTK `0.42.4`; the latest RTK GitHub release observed by the maintainer was `v0.45.0`. The first compatibility release must test both explicitly rather than assuming the host version is current.
