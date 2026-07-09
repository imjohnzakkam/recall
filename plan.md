# recall — build spec & 5-day plan

*Semantic memory for your terminal. When you hit an error, `recall` surfaces the last time you solved something like it — and the exact commands that fixed it.*

Supermemory Local Hackathon · build window **July 9–13, 2026**

---

## The one thing that makes it not a toy

Anyone can build `history | grep`. Two things separate `recall`:

1. **Recall by meaning, not keyword.** A fresh error with *zero* shared keywords still finds the past incident — the engine's hybrid semantic search does what grep can't. This is the line you say to judges.
2. **It remembers fixes, not just failures.** `recall` stores *problem → resolution* pairs. It doesn't show you the old error; it shows you the old error **and the commands that made it pass**. That's the difference between a log viewer and a memory.

**Why local is load-bearing** (say this too): your shell output is private, it's high-volume, and embedding all of it continuously is only free and offline on the local binary. A metered cloud API makes this workload absurd. `recall` can only exist because Supermemory runs on your machine.

---

## Architecture

```
  ┌──────────────┐    command + exit + cwd + git      ┌───────────────┐
  │  zsh hooks   │───────────────────────────────────▶│               │
  │ preexec/     │    stderr on failure               │  ingest       │
  │ precmd       │───────────────────────────────────▶│  daemon       │
  └──────────────┘                                     │  (python)     │
                                                       │               │
                        failure→success detection ─────│  redact +     │
                                                       │  render +     │
                                                       │  POST         │
                                                       └───────┬───────┘
                                                               │ /v3/documents
                                                               ▼
                                                     ┌───────────────────┐
   `recall`  ──── /v4/search (hybrid + rerank) ─────▶│ Supermemory Local │
   CLI       ◀──── problem + fix + when/where ───────│  localhost:6767   │
                                                     └───────────────────┘
                                                          (offline, Ollama)
```

Three components: **capture** (shell), **ingest daemon** (python), **`recall` CLI** (python). All talk to the local binary.

---

## 0. Supermemory Local setup (Day 1, first hour)

Get the binary running per the quickstart, pointed at a local Ollama model for extraction + embeddings. Everything below assumes:

```bash
export RECALL_BASE="http://localhost:6767"
export RECALL_TAG="recall_$(hostname -s)"   # one memory space per machine
export RECALL_KEY="sm_..."                  # the key the binary prints on first boot
```

> **Auth:** Local generates an API key (`sm_...`) and prints it on first boot — every request needs `Authorization: Bearer $RECALL_KEY`. All Python snippets below assume this shared header:
>
> ```python
> import os
> HEADERS = {"Authorization": f"Bearer {os.environ['RECALL_KEY']}"}
> ```

Seed the extractor once so it knows what it's looking at. `entityContext` persists on the container tag and steers memory extraction (max 1500 chars):

```python
import requests, os
BASE, TAG = os.environ["RECALL_BASE"], os.environ["RECALL_TAG"]
HEADERS = {"Authorization": f"Bearer {os.environ['RECALL_KEY']}"}

requests.post(f"{BASE}/v3/documents", headers=HEADERS, json={
    "content": "Terminal session bootstrap for recall.",
    "containerTag": TAG,
    "entityContext": (
        "These documents are terminal command events. Each has a command, "
        "an exit code, a working directory, and (on failure) an error message. "
        "Some documents are RESOLUTIONS: they pair an error signature with the "
        "commands that fixed it. Extract the error's meaning and the fix steps."
    ),
})
```

---

## 1. Capture layer (zsh)

Two capture paths. Build both; they serve different needs.

**Path A — ambient (the "it just watches everything" story).** `preexec`/`precmd` record command + exit + cwd + git ref with 100% reliability, and a background mirror tees session output to a per-session log the daemon reads.

```zsh
# ~/.recall/init.zsh  — sourced from .zshrc
mkdir -p ~/.recall
export RECALL_SESSION="$$"
export RECALL_LOG="$HOME/.recall/session.$RECALL_SESSION.log"
export RECALL_CTL="$HOME/.recall/session.$RECALL_SESSION.ctl"

# mirror stdout+stderr of this interactive shell to a log (separate process,
# so command exit codes are preserved)
if [[ -o interactive ]]; then
  exec > >(tee -a "$RECALL_LOG") 2>&1
fi

# before each command: write a boundary marker + metadata
recall_preexec() {
  print -r -- "###CMD\t$(date +%s)\t$PWD\t$(git rev-parse --short HEAD 2>/dev/null)\t$1" >> "$RECALL_CTL"
}
# after each command: write the exit code of what just ran
recall_precmd() {
  local ec=$?
  print -r -- "###EXIT\t$(date +%s)\t$ec" >> "$RECALL_CTL"
}
autoload -Uz add-zsh-hook
add-zsh-hook preexec recall_preexec
add-zsh-hook precmd  recall_precmd
```

The daemon tails `.ctl` for boundaries + exit codes and slices the matching output window out of `.log`. On a non-zero exit, it grabs the last ~40 lines of that command's output as the error text.

> ⚠️ The `exec > >(tee)` mirror is the one fragile part (can confuse full-screen TUIs / TTY detection). Keep it, but **do not let the live demo depend on it** — see Path B and the pre-seed note.

**Path B — the bulletproof wrapper (use this on stage).** An opt-in wrapper that captures a single command's output cleanly, no TTY games:

```zsh
r() {
  local out; out=$(mktemp)
  "$@" 2> >(tee "$out" >&2); local ec=$?
  RECALL_LAST_ERR="$out" RECALL_LAST_EC=$ec \
    python3 ~/.recall/ingest_one.py "$*" "$PWD" "$ec" "$out" &!
  return $ec
}
```

Run `r pytest ...` and capture is guaranteed. Demo with `r`; ship ambient capture for the "always on" narrative.

---

## 2. Ingest (render for *meaning*, then POST)

The content you send should read like a described problem so the embeddings capture semantics — not a raw log dump. Metadata stays scalar-only (no nested objects/arrays).

```python
# ingest_one.py  — called by the daemon or the r() wrapper
import sys, os, time, hashlib, requests
from redact import scrub          # see §4

BASE, TAG = os.environ["RECALL_BASE"], os.environ["RECALL_TAG"]
HEADERS = {"Authorization": f"Bearer {os.environ['RECALL_KEY']}"}

def ingest_failure(command, cwd, exit_code, err_text, git_ref, session):
    err = scrub(err_text)[-4000:]
    content = (
        f"A shell command failed.\n"
        f"Command: {command}\n"
        f"Directory: {cwd}\n"
        f"Exit code: {exit_code}\n"
        f"Error output:\n{err}"
    )
    cid = "cmd_" + hashlib.sha1(f"{session}{time.time()}{command}".encode()).hexdigest()[:16]
    requests.post(f"{BASE}/v3/documents", headers=HEADERS, json={
        "content": content,
        "containerTag": TAG,
        "customId": cid,
        "dreaming": "instant",           # each command is its own unit; free locally
        "metadata": {
            "kind": "failure",
            "command": command[:500],
            "exit_code": int(exit_code),
            "cwd": cwd,
            "git_ref": git_ref or "",
            "session": str(session),
            "ts": int(time.time()),
        },
    }, timeout=10)
```

Ingest is fire-and-forget and processing is async (queued → extracted → embedded → indexed), so a just-captured failure isn't instantly searchable. That's fine: `recall` searches *past* incidents, which are already indexed.

---

## 3. Resolution linking — the differentiator (Day 4)

This is the feature that wins. Detect **failure → later success** and store the fix as its own memory.

Heuristic that's good enough for the window:

- The daemon keeps, per `cwd`, the last failing command and the timestamp.
- When a command later **succeeds (exit 0)** in that `cwd` and is the *same or a similar* command (normalize: strip paths/hashes/numbers, compare), treat everything run in that `cwd` **between the failure and the success** as the candidate fix.
- Ingest a `resolution` document pairing the error signature with the fix commands:

```python
def ingest_resolution(error_sig, fix_commands, cwd, git_ref):
    content = (
        f"RESOLUTION.\n"
        f"Problem: {error_sig}\n"
        f"Directory: {cwd}\n"
        f"Fix — these commands made it pass:\n" +
        "\n".join(f"  $ {c}" for c in fix_commands)
    )
    requests.post(f"{BASE}/v3/documents", headers=HEADERS, json={
        "content": content,
        "containerTag": TAG,
        "dreaming": "instant",
        "metadata": {"kind": "resolution", "cwd": cwd,
                     "git_ref": git_ref or "", "ts": int(time.time())},
    }, timeout=10)
```

`recall` prefers `kind: "resolution"` results — those carry the actual fix. If time is tight, even the naive version (fix = commands between fail and next success in the same dir) demos beautifully.

---

## 4. Redaction (Day 2, cheap, high-value)

Shell output leaks tokens and keys. Scrubbing before ingest is both responsible and a strong judge talking point ("local *and* it never memorizes your secrets").

```python
# redact.py
import re
PATTERNS = [
    (re.compile(r'(AKIA|ASIA)[0-9A-Z]{16}'), '[AWS_KEY]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9._-]{16,}'), 'Bearer [TOKEN]'),
    (re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+'), r'\1=[REDACTED]'),
    (re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'), '[GH_TOKEN]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), '[SK_KEY]'),
]
def scrub(text: str) -> str:
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    return text
```

---

## 5. The `recall` CLI (Day 3 — protect this time, it's the core wow)

Two modes: bare `recall` (act on the last failure) and `recall "free text"`.

```python
#!/usr/bin/env python3
# recall — semantic recall over your terminal history
import sys, os, json, requests
BASE, TAG = os.environ["RECALL_BASE"], os.environ["RECALL_TAG"]
HEADERS = {"Authorization": f"Bearer {os.environ['RECALL_KEY']}"}
SESSION = os.environ.get("RECALL_SESSION", "")

def last_error_text():
    # read the most recent failure captured for this session from ~/.recall state
    p = os.path.expanduser("~/.recall/last_error.txt")
    return open(p).read() if os.path.exists(p) else ""

def search(query):
    r = requests.post(f"{BASE}/v4/search", headers=HEADERS, json={
        "q": query,
        "containerTag": TAG,
        "searchMode": "hybrid",
        "rerank": True,          # +100ms, big precision win — worth it here
        "threshold": 0.55,
        "limit": 5,
        "filters": {             # don't return the error you're currently staring at
            "AND": [{"key": "session", "value": SESSION, "negate": True}]
        },
    }, timeout=15)
    r.raise_for_status()
    return r.json()["results"]

def render(results):
    if not results:
        print("recall: no prior memory of anything like this.")
        return
    for res in results:
        body = res.get("memory") or res.get("chunk") or ""
        sim, when = res["similarity"], res.get("updatedAt", "")[:10]
        tag = "🔧 FIX" if (res.get("metadata") or {}).get("kind") == "resolution" else "•"
        print(f"\n{tag}  [{sim:.2f}]  {when}\n{body}")

def me():
    # `recall me` — what your terminal knows about you, synthesized for free
    r = requests.post(f"{BASE}/v4/profile", headers=HEADERS,
                      json={"containerTag": TAG}, timeout=15)
    r.raise_for_status()
    p = r.json().get("profile", {})
    print("── your terminal, as recall sees it ──")
    for label, items in (("Recurring", p.get("static", [])),
                         ("Lately", p.get("dynamic", []))):
        for it in items:
            print(f"  {label:9} {it}")

if __name__ == "__main__":
    if sys.argv[1:2] == ["me"]:
        me()
    else:
        query = " ".join(sys.argv[1:]) or last_error_text()
        if not query.strip():
            sys.exit("recall: nothing to recall (no recent failure, no query given).")
        render(search(query))
```

`recall me` hits `/v4/profile`, which auto-maintains a `static` (long-term) + `dynamic` (recent) summary of the container from the same ingested data — zero extra capture work, and a strong demo beat ("my terminal built a profile of how I work"). Slick variant: `/v4/profile` also accepts an optional `q`, returning the profile *and* matching memories in one call, so the main recall path can fetch the specific fix and the ambient profile together.

Optional flourishes if time allows: `recall --run` (apply the top fix's commands after a y/n), and a bare `recall` bound to a keystroke via `bindkey`.

The offline guarantee is free: every call is to `localhost`. **Kill Wi-Fi and it still works** — that's the demo.

---

## 6. Demo script (≤3 min — the video is graded, so rehearse it)

1. **(0:00) Frame it in one line.** "Every engineer re-solves the same errors. `recall` is a memory of your terminal that gives you your own fixes back — and it runs entirely on my machine."
2. **(0:20) The semantic moment.** Paste a fresh, gnarly error into the shell. Run `recall`. It surfaces a past incident with **no shared keywords** — call that out explicitly ("notice: nothing in common, word for word") — and shows the exact fix commands. This is the whole pitch; land it hard.
3. **(1:20) The fix moment.** `recall --run` applies it, the command passes.
4. **(2:00) The offline moment.** Turn off Wi-Fi on camera. Do it again. Still instant. "No cloud. This is why it's local."
5. **(2:30) The privacy beat.** Show a captured event where an API key came through as `[REDACTED]`. "It remembers your fixes, never your secrets."
6. **(2:50) Close** on the repo + one line: what it uses from Supermemory Local.

**Pre-seed before recording.** Load a realistic corpus of ~30–50 past failure+resolution pairs the night before so the demo is never empty and the semantic match is guaranteed to hit. This is your #1 demo safety net — more important than any single feature.

---

## 7. Day-by-day (July 9–13)

- **Day 1 (Wed 9) — spine.** Binary up on `localhost:6767` + Ollama. Prove add → search from a script (round-trip a fake error, get it back semantically). Lock the ingest schema. Ship the zsh hooks writing command/exit/cwd/git to the control file.
- **Day 2 (Thu 10) — capture + ingest.** Daemon slices per-command output from the mirror log; POSTs failures. Add redaction. Verify real failures land as good, searchable memories.
- **Day 3 (Fri 11) — the CLI.** `recall` end-to-end with rerank. Get the **no-keyword-overlap** recall working against seeded data. This is the core; don't move on until it feels magic.
- **Day 4 (Sat 12) — resolution linking.** Failure→success detection, `resolution` docs, `recall` prefers fixes. Add `--run`. **Freeze scope Saturday night.**
- **Day 5 (Sun 13) — ship.** Pre-seed the demo corpus, record the ≤3-min video, write README + the 3–5 sentence "how it uses Supermemory Local", fill the Google Form, post to `#showcase`. **Both must be done by 23:59 PST.**

---

## 8. Traps to avoid

- **Don't ship grep-with-steps.** If a judge could get the same result with `history | grep`, you've lost. Lead every demo beat with *semantic* + *fix pairing*.
- **Don't let capture fragility sink the demo.** Ambient mirror for the story; `r` wrapper + pre-seeded corpus for the stage.
- **Don't demo on an empty memory.** Seed it. The single most common hackathon death.
- **Don't over-scope resolution linking.** The naive heuristic is enough. A perfect fix-detector you didn't finish scores zero.
- **Don't forget the form.** Per the rules: no form, no entry — it's what judges score from. Do it Saturday, not at 23:58.

---

## Submission checklist

- [ ] Public GitHub repo, commits inside the July 9–13 window
- [ ] Demo video ≤ 3 min (semantic hit → fix → Wi-Fi off → redaction)
- [ ] Google Form submitted (this is the official entry)
- [ ] Posted in `#showcase` with the pinned template
- [ ] README explains, in 3–5 sentences, how it uses Supermemory Local

---

## Appendix: Supermemory Local feature utilization

Local is the same engine as the hosted platform as one binary. Here's every feature it ships and exactly how `recall` uses each — the four in **bold** are load-bearing; the rest are free leverage.

| Feature | Endpoint / mechanism | How recall uses it | Gotcha |
|---|---|---|---|
| **Ingestion** | `POST /v3/documents` | The capture path — one document per failure, `content` rendered as a described problem so embeddings capture meaning | Async: returns `queued`, indexed in the background. Fire-and-forget; never blocks the shell. A just-captured error isn't instantly searchable |
| **Memory extraction** | part of ingestion, runs on *your* model | Turns raw stderr into a distilled error *fact* — this is what makes semantic matching work at all | Quality = your local model's quality. Weak recall on Day 3 is usually the model (gpt-oss:20b), not your code. Steer it with `entityContext` |
| **Local embeddings** | on-machine, nothing leaves | The whole "why local" thesis — embed every command continuously, free and offline | None. This is the pitch |
| **Hybrid search** | `POST /v4/search` | The recall query. `searchMode:"hybrid"` returns extracted `memory` *and* raw `chunk`; `rerank:true`; `threshold≈0.55`; `similarity`/`updatedAt` drive the display | Turn `rerank` on (+~100ms, big precision win). Result is `memory` *or* `chunk` — render whichever is present |
| **Metadata + filters** | scalar metadata at ingest; `filters` AND/OR at query | `negate` on `session` (don't echo the current error); prefer `kind:"resolution"` | **Metadata must be primitives** — no arrays/nested. Flatten tags to a delimited string; `array_contains` filters system arrays, not your metadata |
| **Spaces / container tags** | `containerTag` everywhere | One tag per machine (`recall_<host>`) — the isolation + filter key; also the free multi-machine story | Every ingest and search must pass it or you'll cross-contaminate |
| **Graph engine** | embedded, auto-created on boot | Implicit — entity resolution clusters your error families so search connects them; no vector DB to stand up | You get it free via hybrid search; direct traversal is a Day-4 stretch only |
| **User profiles** | `POST /v4/profile` | `recall me` — auto-built `static`/`dynamic` summary of how you work; optional `q` returns profile + memories in one call | Free, zero extra capture. Keep the *core* recall path on `/v4/search` for precision |
| **File ingestion** | file endpoint | Optional stretch: `recall ingest crash.log` / feed CI logs | Not core; skip unless Day 4 has slack |
| **Fully offline** | any OpenAI-compatible model via `OPENAI_BASE_URL` | Extraction + embeddings + graph all local → the Wi-Fi-off demo | Extraction latency = local model speed; async keeps it off the shell's critical path |
| **Auth / config** | `sm_...` key printed on boot | `Authorization: Bearer $RECALL_KEY` on every call | The key is required even locally — don't run keyless |
| **SDK / coding plugins** | `baseURL` override; `SUPERMEMORY_API_URL` | recall uses raw REST (fewer moving parts). Stretch: point Claude Code at the same container so your agent reads your terminal fixes | — |

**Not in Local — don't design around these:** connectors (Google Drive, Notion, Gmail, OneDrive), the Supermemory MCP, and the platform's proprietary long-horizon extraction models (Local extracts with your model instead).