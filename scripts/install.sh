#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${HOME}/.hermes/plugins/rtk-rewrite"
BACKUP_ROOT="${HOME}/.hermes/backups/rtk-rewrite"

usage() { printf 'usage: %s [--source DIR] [--target DIR] [--backup-root DIR]\n' "$0" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --source) SOURCE="$2"; shift 2;;
    --target) TARGET="$2"; shift 2;;
    --backup-root) BACKUP_ROOT="$2"; shift 2;;
    *) usage;;
  esac
done

SOURCE="$(cd -- "$SOURCE" && pwd)"
[[ -f "$SOURCE/src/rtk_hermes/__init__.py" ]] || { printf 'missing source adapter\n' >&2; exit 1; }
[[ -f "$SOURCE/plugin.yaml" ]] || { printf 'missing plugin manifest\n' >&2; exit 1; }

mkdir -p "$BACKUP_ROOT" "$(dirname -- "$TARGET")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/$STAMP"
if [[ -e "$TARGET" ]]; then
  cp -a "$TARGET" "$BACKUP"
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/rtk-hermes-install.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE"
cp "$SOURCE/src/rtk_hermes/__init__.py" "$STAGE/__init__.py"
cp "$SOURCE/plugin.yaml" "$STAGE/plugin.yaml"
python3 -m py_compile "$STAGE/__init__.py"

if [[ -e "$TARGET" ]]; then rm -rf "$TARGET"; fi
mv "$STAGE" "$TARGET"
printf 'installed %s\n' "$TARGET"
if [[ -n "${BACKUP:-}" && -e "$BACKUP" ]]; then
  printf 'rollback: rm -rf %q && mv %q %q\n' "$TARGET" "$BACKUP" "$TARGET"
else
  printf 'rollback: rm -rf %q\n' "$TARGET"
fi
