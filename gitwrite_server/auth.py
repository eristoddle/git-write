"""Token store and HTTP Basic authentication.

Tokens are long-lived secrets, one per Veneer install. Only their sha256
hashes are stored, as ``label:hash`` lines in a 0600 flat file; the plaintext
token is returned exactly once by :func:`create_token`. The username sent by
the client is ignored (the Veneer plugin keeps it in a separate setting and
any value is accepted) — the token, sent as the Basic-auth password, is the
credential. Comparisons are constant-time.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
from collections.abc import Mapping
from pathlib import Path

# Labels appear before the colon in file lines, so they must never contain one.
_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_TOKEN_FILE_MODE = 0o600


class InvalidTokenLabel(ValueError):
    """Raised when a token label cannot appear unambiguously in the token file."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _read_entries(tokens_file: Path) -> list[tuple[str, str]]:
    """Read ``label:hash`` entries; malformed lines are skipped, not trusted."""
    if not tokens_file.exists():
        return []
    entries: list[tuple[str, str]] = []
    for line in tokens_file.read_text().splitlines():
        label, sep, stored = line.partition(":")
        if sep and _LABEL_RE.match(label) and stored:
            entries.append((label, stored))
    return entries


def _write_entries(entries: list[tuple[str, str]], tokens_file: Path) -> None:
    tokens_file.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{label}:{stored}\n" for label, stored in entries)
    # O_CREAT with 0o600 only applies the mode at creation; chmod keeps the
    # guarantee when the file already exists with looser permissions.
    fd = os.open(tokens_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _TOKEN_FILE_MODE)
    with os.fdopen(fd, "w") as fh:
        fh.write(payload)
    os.chmod(tokens_file, _TOKEN_FILE_MODE)


def _append_entry(label: str, stored_hash: str, tokens_file: Path) -> None:
    tokens_file.parent.mkdir(parents=True, exist_ok=True)
    line = f"{label}:{stored_hash}\n"
    fd = os.open(tokens_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _TOKEN_FILE_MODE)
    with os.fdopen(fd, "a") as fh:
        fh.write(line)
    os.chmod(tokens_file, _TOKEN_FILE_MODE)


def create_token(label: str, *, tokens_file: Path) -> str:
    """Mint a token, store only its hash, and return the plaintext exactly once.

    Creating a token under an existing label rotates it: the old token's hash
    is replaced by the new one.
    """
    if not _LABEL_RE.match(label):
        raise InvalidTokenLabel(
            "labels must match [A-Za-z0-9][A-Za-z0-9._-]* and cannot contain ':'"
        )
    token = secrets.token_urlsafe(32)
    entries = [
        (existing, stored) for existing, stored in _read_entries(tokens_file) if existing != label
    ]
    _write_entries(entries, tokens_file)
    _append_entry(label, _hash_token(token), tokens_file)
    return token


def revoke_token(label: str, *, tokens_file: Path) -> bool:
    """Remove a token by label. Returns True when a token was removed."""
    entries = _read_entries(tokens_file)
    kept = [(existing, stored) for existing, stored in entries if existing != label]
    if len(kept) == len(entries):
        return False
    _write_entries(kept, tokens_file)
    return True


def list_tokens(*, tokens_file: Path) -> list[str]:
    """Return the labels of all stored tokens."""
    return sorted(label for label, _ in _read_entries(tokens_file))


def _parse_basic_credentials(authorization: str) -> tuple[str, str] | None:
    """Decode a ``Basic`` Authorization header value into (username, password)."""
    scheme, _, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    username, sep, password = decoded.partition(":")
    if not sep:
        return None
    return username, password


def authenticate(headers: Mapping[str, str], *, tokens_file: Path) -> bool:
    """Check Basic credentials, accepting the token as the password.

    ``headers`` is a mapping with ``HTTP_AUTHORIZATION``-style keys — a WSGI
    environ works as-is. Any non-empty username is accepted; the password must
    hash to one of the stored token hashes, compared in constant time.
    """
    authorization = headers.get("HTTP_AUTHORIZATION", "")
    credentials = _parse_basic_credentials(authorization) if authorization else None
    if credentials is None:
        return False
    supplied_hash = _hash_token(credentials[1])
    return any(
        hmac.compare_digest(supplied_hash, stored)
        for _, stored in _read_entries(tokens_file)
    )
