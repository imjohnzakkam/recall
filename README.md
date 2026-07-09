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

```bash
r pytest -q          # run anything via r(); failures get captured
recall               # recall past fixes for your last failure
recall "port already in use"   # or search by meaning
recall me            # what your terminal knows about how you work
```

## How it uses Supermemory Local

*(3–5 sentence writeup — Day 5 deliverable.)*
