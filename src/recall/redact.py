"""Scrub secrets from shell output before it ever reaches Supermemory.

Local *and* it never memorizes your secrets. Runs on every ingest.
"""
import re

PATTERNS = [
    (re.compile(r'(AKIA|ASIA)[0-9A-Z]{16}'), '[AWS_KEY]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9._-]{16,}'), 'Bearer [TOKEN]'),
    (re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+'), r'\1=[REDACTED]'),
    (re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'), '[GH_TOKEN]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), '[SK_KEY]'),
    (re.compile(r'(?i)(authorization\s*[:=]\s*)(?:basic|bearer)\s+\S+'), r'\1[TOKEN]'),
    (re.compile(r'(?i)(?:https?://)([^/@:\s]+):([^/@\s]+)@'), r'https://[USER]:[PASSWORD]@'),
    (re.compile(r'(?i)(--(?:password|token|api-key|secret)(?:=|\s+))\S+'), r'\1[REDACTED]'),
    (re.compile(r'(?i)([A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)=)\S+'), r'\1[REDACTED]'),
]


def scrub(text: str) -> str:
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    return text


if __name__ == "__main__":
    # quick self-check
    sample = (
        "AWS_KEY=AKIAIOSFODNN7EXAMPLE\n"
        "Authorization: Bearer abcdefghijklmnop1234\n"
        "api_key=sk-abcdefghijklmnopqrstuvwxyz012345\n"
        "export GITHUB=ghp_abcdefghijklmnopqrstuvwxyz0123\n"
        "password: hunter2secret\n"
    )
    print(scrub(sample))
