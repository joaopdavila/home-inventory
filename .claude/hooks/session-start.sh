#!/bin/bash
# Installs home-inventory and its dev dependencies so tests/linters work
# in Claude Code on the web sessions. Idempotent and non-interactive.
set -euo pipefail

# Only run in the remote (web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Create a venv once; reuse on subsequent runs (container state is cached).
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/pip install -e ".[dev]"

# Make the venv the default interpreter for this session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"${CLAUDE_PROJECT_DIR:-.}/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
