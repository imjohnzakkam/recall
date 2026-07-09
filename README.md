# recall

*Semantic memory for your terminal. When you hit an error, `recall` surfaces the last time you solved something like it — and the exact commands that fixed it.*

Built for the Supermemory Local Hackathon (July 9–13, 2026). It runs entirely on your machine: local embeddings, local extraction (Ollama), local search. Kill Wi-Fi and it still works.

## Why it's not `history | grep`

- **Recall by meaning, not keyword.** A fresh error with zero shared keywords still finds the past incident — hybrid semantic search does what grep can't.
- **It remembers fixes, not just failures.** `recall` stores *problem → resolution* pairs and shows you the commands that made it pass.

## Setup

```bash
# 1. Ollama (extraction model)
ollama pull qwen3:8b

# 2. Supermemory Local — prints an sm_... key on first boot
./scripts/start-server.sh        # boots supermemory-server with the Ollama env

# 3. recall env + install the package
cp env.example ~/.recall/env     # fill in RECALL_KEY
conda create -n recall python=3.12 -y -c conda-forge --override-channels
~/miniconda3/envs/recall/bin/pip install -e .

# 4. prove the round-trip, then wire up the shell
~/miniconda3/envs/recall/bin/recall-seed
~/miniconda3/envs/recall/bin/python tests/smoketest.py   # expect: === PASS ===
echo 'source ~/Projects/recall/shell/init.zsh' >> ~/.zshrc
```

## Use

Capture is **ambient** — once the shell integration is sourced, every command is watched
automatically (no need to prefix anything). A background daemon mirrors each command's stderr
and ingests failures.

```bash
pytest -q            # just work — failures are captured automatically
recall               # recall past fixes for your last failure
recall "port already in use"   # or search by meaning
recall --run         # apply the top remembered fix (asks y/N first)
recall me            # what your terminal knows about how you work

r pytest -q          # optional: force-capture one command (always reliable)
```

**Resolution linking** happens automatically: when a command fails and the same command
later succeeds in that directory, recall stores the commands you ran in between as the fix —
so `recall` returns *problem → fix* pairs, and `recall --run` can replay them.

### Capture modes

- **Ambient (default):** `shell/ambient.zsh` installs `preexec`/`precmd` hooks and mirrors
  **stderr only** (stdout stays a real TTY, so `vim`/`less`/`htop` are unaffected). The
  `recall-daemon` slices each command's stderr by byte offset and ingests failures. Disable
  with `export RECALL_AMBIENT=0` before sourcing.
- **`r <cmd>` wrapper:** explicit, guaranteed capture for a single command — handy when
  ambient is off or you want to be sure.

## Where things live

Runtime state stays in `~/.recall/` (never in the repo): `env` (your keys), `last_error.txt`,
per-directory `state/` for resolution linking, per-shell `session.<id>.{ctl,log}` for ambient
capture, and rotating `logs/recall.log`.

## How it uses Supermemory Local

recall is built entirely on Supermemory Local — the same engine as the hosted platform,
running as one binary on `localhost` with Ollama for extraction and on-device embeddings, so
no terminal data ever leaves the machine. Every captured failure is a `POST /v3/documents`
whose `content` is rendered as a described problem, letting Supermemory's memory extraction
distill it into a searchable fact and its local embeddings index it. `recall` queries
`POST /v4/search` in hybrid mode, so a fresh error finds past incidents with zero shared
keywords, and resolution documents pair each error with the commands that fixed it. A single
`containerTag` per machine isolates the memory space, scalar metadata (`kind`, `cwd`, `session`)
drives filtering, and `recall me` uses `POST /v4/profile` to synthesize how you work from the
same data — all offline.
