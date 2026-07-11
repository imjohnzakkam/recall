# Troubleshooting

## Recall cannot reach Supermemory

Confirm `RECALL_BASE`, start `supermemory-server`, and check `~/.recall/logs/recall.log`.
Every local request still requires the `sm_...` key printed on first boot.
Run `recall doctor` to validate the key against Supermemory, confirm the configured Ollama
model is installed, inspect the daemon, and check the packaged shell hook.

## Searches are empty

Indexing is asynchronous. Run `recall-seed` once for a demo corpus, wait for extraction,
and confirm Ollama has the configured model. The end-to-end smoketest documents the
expected semantic round trip.

## Ambient capture misses an error

Ambient mode captures stderr. Some tools report failures on stdout; use `r <command>` for
explicit capture. Set `RECALL_AMBIENT=0` if a terminal application behaves unexpectedly.

## Reset

Remove the shell `source` line, stop the daemon, and delete `~/.recall`. This does not delete
documents already stored by Supermemory Local.
