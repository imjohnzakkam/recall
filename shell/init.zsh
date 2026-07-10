# recall — shell integration.  Source this from ~/.zshrc:
#     source ~/Projects/recall/shell/init.zsh
#
# Two capture paths: the always-on ambient daemon (default), and the explicit
# r() wrapper for one-off guaranteed capture. Disable ambient with RECALL_AMBIENT=0.

# --- config: RECALL_BASE / RECALL_TAG / RECALL_KEY live here ---
[[ -f "$HOME/.recall/env" ]] && source "$HOME/.recall/env"

# one session id per shell (used to filter out the error you're staring at)
export RECALL_SESSION="$$"

# console scripts installed by `pip install -e .` live in the conda env's bin dir;
# calling them directly avoids needing the env activated.
RECALL_BIN="${RECALL_BIN:-$HOME/miniconda3/envs/recall/bin}"

# r <command...>  — run a command, capture its stderr cleanly, ingest on failure.
# Returns the wrapped command's real exit code. Capture never blocks the shell.
# Redundant when ambient capture is on, but always reliable.
r() {
  local out; out=$(mktemp)
  local rendered="${(q)@}"
  "$@" 2> >(tee "$out" >&2); local ec=$?
  "$RECALL_BIN/recall-ingest" "$rendered" "$PWD" "$ec" "$out" &!
  return $ec
}

# recall / recall "text" / recall --run / recall me
alias recall="$RECALL_BIN/recall"

# --- ambient capture (always on) ---
# Start one shared daemon (across all shells) and install the per-shell hooks.
if [[ "${RECALL_AMBIENT:-1}" != "0" ]]; then
  if [[ -x "$RECALL_BIN/recall" ]]; then
    "$RECALL_BIN/recall" daemon start >/dev/null 2>&1
  fi
  source "${${(%):-%x}:A:h}/ambient.zsh"
fi
