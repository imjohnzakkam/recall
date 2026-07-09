"""Fixed values shared across modules — no magic literals inline.

Endpoint paths and search defaults live here so the client, CLI, and tests all agree
on one source of truth.
"""

# Supermemory Local REST endpoints
DOCUMENTS_PATH = "/v3/documents"
SEARCH_PATH = "/v4/search"
PROFILE_PATH = "/v4/profile"

# HTTP
HTTP_TIMEOUT = 15

# Search defaults
SEARCH_MODE = "hybrid"
DEFAULT_THRESHOLD = 0.55
DEFAULT_LIMIT = 5
# Reranking relies on a Cloudflare Workers-AI binding that Supermemory Local
# doesn't ship (search-time rerank throws `x.AI.run undefined` and falls back),
# so it's off by default here. Flip to True only against the hosted platform.
DEFAULT_RERANK = False

# Ingest
DREAMING_MODE = "instant"        # each command is its own unit; free locally
MAX_ERROR_CHARS = 4000           # trailing window of scrubbed error text to keep
MAX_COMMAND_CHARS = 500          # command string cap stored in metadata

# Resolution linking (failure -> later success in the same cwd)
STALE_SECONDS = 3600             # ignore an open failure older than this
MAX_FIX_CANDIDATES = 20          # cap on commands remembered between fail and fix
ERROR_SIG_CHARS = 1500           # trailing window of the error signature to store
FIX_CMD_DELIM = " ;; "           # scalar-safe join of fix commands in metadata
