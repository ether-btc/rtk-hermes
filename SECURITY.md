# Security policy

## Scope

This repository contains a local Hermes plugin that invokes the `rtk` executable with a command argument and optionally calls the installed `rust_cave_001` compressor.

## Fail-open boundary

The plugin must never prevent a terminal command from running because RTK, the compressor, parsing, or a hook is unavailable. Do not add network calls, command persistence, telemetry, or secret logging to the adapter.

## Reporting

Report vulnerabilities privately through the repository's GitHub security contact. Do not include secrets or command contents in public issues.
