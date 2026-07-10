# Security and privacy

Recall is local-first, but terminal output is sensitive even on localhost. Captured stderr is
redacted before ingestion using patterns for common cloud keys, bearer tokens, passwords,
and API secrets. The original terminal output remains visible to the command and may exist
briefly in the session capture file under `~/.recall`.

Remembered fixes are untrusted shell text. Always inspect commands before approving
`recall --run`; a fix can be stale, project-specific, or destructive. Keep `~/.recall/env`
mode `0600`, bind Supermemory to loopback, and never commit its API key.

To stop collection, set `RECALL_AMBIENT=0` or remove the shell integration. Delete
`~/.recall` for Recall runtime state and use Supermemory's document deletion facilities for
indexed memories.
