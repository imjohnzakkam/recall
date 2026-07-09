# recall — ambient capture. Sourced by init.zsh (needs RECALL_SESSION set first).
#
# Watches every command with no need to type `r`. It mirrors only *stderr* to a
# per-shell log, so stdout stays a real TTY and full-screen apps (vim, less, htop)
# are unaffected. preexec/precmd record command + exit + cwd + git and the byte
# offsets that bracket each command's stderr; the recall-daemon slices and ingests.
#
# Opt out entirely with: export RECALL_AMBIENT=0

[[ "${RECALL_AMBIENT:-1}" == "0" ]] && return
[[ -o interactive ]] || return

export RECALL_LOG="$HOME/.recall/session.${RECALL_SESSION}.log"
export RECALL_CTL="$HOME/.recall/session.${RECALL_SESSION}.ctl"
mkdir -p "$HOME/.recall"
: > "$RECALL_LOG"        # fresh per-shell log so byte offsets start at 0
: > "$RECALL_CTL"

# Mirror this shell's stderr to the log while still showing it on the terminal.
# stdout is left untouched, so TUIs and colors keep working.
exec 2> >(tee -a "$RECALL_LOG" >&2)

recall_amb_preexec() {
  local tab=$'\t'
  local start; start=$(stat -f%z "$RECALL_LOG" 2>/dev/null || echo 0)
  local ref; ref=$(git rev-parse --short HEAD 2>/dev/null)
  local cmd="${1//$'\n'/ }"
  print -r -- "CMD${tab}$(date +%s)${tab}$PWD${tab}${ref}${tab}${start}${tab}${cmd}" >> "$RECALL_CTL"
}

recall_amb_precmd() {
  local ec=$?
  local tab=$'\t'
  local end; end=$(stat -f%z "$RECALL_LOG" 2>/dev/null || echo 0)
  print -r -- "EXIT${tab}$(date +%s)${tab}${ec}${tab}${end}" >> "$RECALL_CTL"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec recall_amb_preexec
add-zsh-hook precmd  recall_amb_precmd
