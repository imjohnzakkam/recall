# recall packaged shell integration
[[ -f "$HOME/.recall/env" ]] && source "$HOME/.recall/env"
export RECALL_SESSION="$$"
RECALL_BIN="${RECALL_BIN:-${commands[recall]:h}}"

r() {
  local out; out=$(mktemp)
  "$@" 2> >(tee "$out" >&2); local ec=$?
  "$RECALL_BIN/recall-ingest" "$*" "$PWD" "$ec" "$out" &!
  return $ec
}

if [[ "${RECALL_AMBIENT:-1}" != "0" ]]; then
  source "${${(%):-%x}:A:h}/ambient.zsh"
fi
