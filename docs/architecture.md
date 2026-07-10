# Architecture

Recall has three boundaries: zsh capture hooks, a Python ingest daemon, and Supermemory
Local. Hooks write command metadata and stderr offsets to per-shell files. The daemon pairs
command/exit records, slices only that command's stderr, redacts it, and posts a described
failure document. The CLI performs hybrid search and renders resolutions before unmatched
failure memories.

Per-directory JSON state links a failed command to a later successful rerun. Runtime state,
logs, and shell session files live in `~/.recall`; the repository contains no user history.
Supermemory owns extracted memories and its vector index.
