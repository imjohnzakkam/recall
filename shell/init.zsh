# recall — shell integration.  Source this from ~/.zshrc:
#     source ~/Projects/recall/shell/init.zsh
#
# Day 1 scope: the bulletproof r() wrapper only. No ambient tee-mirror yet
# (that's the fragile Day 2 path) — so nothing here can hang your shell.

# --- config: RECALL_BASE / RECALL_TAG / RECALL_KEY live here ---
[[ -f "$HOME/.recall/env" ]] && source "$HOME/.recall/env"

# one session id per shell (used to filter out the error you're staring at)
export RECALL_SESSION="$$"

# console scripts installed by `pip install -e .` live in the conda env's bin dir;
# calling them directly avoids needing the env activated.
RECALL_BIN="${RECALL_BIN:-$HOME/miniconda3/envs/recall/bin}"

# r <command...>  — run a command, capture its stderr cleanly, ingest on failure.
# Returns the wrapped command's real exit code. Capture never blocks the shell.
r() {
  local out; out=$(mktemp)
  "$@" 2> >(tee "$out" >&2); local ec=$?
  "$RECALL_BIN/recall-ingest" "$*" "$PWD" "$ec" "$out" &!
  return $ec
}

# recall / recall "text" / recall me
alias recall="$RECALL_BIN/recall"
