# Ambient zsh hooks bundled with supermemory-recall.
[[ "${RECALL_AMBIENT:-1}" == "0" ]] && return
[[ -o interactive ]] || return
export RECALL_LOG="$HOME/.recall/session.${RECALL_SESSION}.log"
export RECALL_CTL="$HOME/.recall/session.${RECALL_SESSION}.ctl"
mkdir -p "$HOME/.recall"
: > "$RECALL_LOG"
: > "$RECALL_CTL"
exec 2> >(tee -a "$RECALL_LOG" >&2)

recall_amb_preexec() {
  local tab=$'\t' start ref cmd
  start=$(stat -f%z "$RECALL_LOG" 2>/dev/null || stat -c%s "$RECALL_LOG" 2>/dev/null || echo 0)
  ref=$(git rev-parse --short HEAD 2>/dev/null)
  cmd="${1//$'\n'/ }"
  print -r -- "CMD${tab}$(date +%s)${tab}$PWD${tab}${ref}${tab}${start}${tab}${cmd}" >> "$RECALL_CTL"
}

recall_amb_precmd() {
  local ec=$? tab=$'\t' end
  end=$(stat -f%z "$RECALL_LOG" 2>/dev/null || stat -c%s "$RECALL_LOG" 2>/dev/null || echo 0)
  print -r -- "EXIT${tab}$(date +%s)${tab}${ec}${tab}${end}" >> "$RECALL_CTL"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec recall_amb_preexec
add-zsh-hook precmd recall_amb_precmd
