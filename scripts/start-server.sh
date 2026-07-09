#!/usr/bin/env bash
# Boot Supermemory Local pointed at Ollama for extraction + embeddings.
# Values default to the local Ollama setup but stay overridable via ~/.recall/env
# or the environment.
set -euo pipefail

[[ -f "$HOME/.recall/env" ]] && source "$HOME/.recall/env"

OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://localhost:11434/v1}" \
OPENAI_API_KEY="${OPENAI_API_KEY:-ollama}" \
OPENAI_MODEL="${OPENAI_MODEL:-qwen3:8b}" \
  exec "$HOME/.local/bin/supermemory-server"
