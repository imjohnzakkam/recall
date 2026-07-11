# recall packaged shell integration. Canonical copy: src/recall/resources/init.zsh
[[ -f "$HOME/.recall/env" ]] && source "$HOME/.recall/env"
export RECALL_SESSION="$$"
RECALL_BIN="${RECALL_BIN:-${commands[recall]:h}}"

r() {
  local out rendered
  out=$(mktemp)
  rendered="${(q)@}"
  "$@" 2> >(tee "$out" >&2); local ec=$?
  "$RECALL_BIN/recall-ingest" "$rendered" "$PWD" "$ec" "$out" &!
  return $ec
}

if [[ "${RECALL_AMBIENT:-1}" != "0" ]]; then
  if [[ -x "$RECALL_BIN/recall" ]]; then
    "$RECALL_BIN/recall" daemon start >/dev/null 2>&1
  fi
  source "${${(%):-%x}:A:h}/ambient.zsh"
fi
