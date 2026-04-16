#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.codex/skills/check-ssh-gpu"
mkdir -p "$(dirname "${TARGET_DIR}")"
rm -rf "${TARGET_DIR}"
ln -s "${ROOT_DIR}/skills/check-ssh-gpu" "${TARGET_DIR}"
printf 'Installed skill at %s
' "${TARGET_DIR}"
