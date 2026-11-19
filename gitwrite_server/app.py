"""The WSGI stack: auth middleware → validated resolver → dulwich smart HTTP.

Every request is authenticated before the resolver runs, so auto-creating a
bare repository on first push never depends on the client being anonymous.
All error bodies are generic: the old API leaked absolute filesystem paths in
responses (docs/AUDIT.md) and this layer is where that is designed out.
"""

from pathlib import Path
from typing import Iterator

from dulwich.errors import NotGitRepository
from dulwich.protocol import CAPABILITY_THIN_PACK
from dulwich.repo import Repo
from dulwich.server import Backend, UploadPackHandler
from dulwich.web import make_wsgi_chain

from gitwrite_server.auth import authenticate
from gitwrite_server.resolver import resolve_repo

_GENERIC_401_BODY = b"Unauthorized\n"
_GENERIC_403_BODY = b"Forbidden\n"
_GENERIC_404_BODY = b"Not Found\n"
_UNAUTHORIZED_HEADERS = [
    ("Content-Type", "text/plain"),
    ("WWW-Authenticate", 'Basic realm="GitWrite"'),
]


def is_push(environ: dict) -> bool:
    """True when the request belongs to a push (git-receive-pack).

    Covers both the service POST and the info/refs advertisement GET that
    every git client sends first — auto-create must trigger on the GET, or
    the client is told 404 before it ever gets to POST.
    """
    path = environ.get("PATH_INFO", "")
    if path.endswith("git-receive-pack"):
        return True
    return path.endswith("/info/refs") and "service=git-receive-pack" in environ.get(
        "QUERY_STRING", ""
    )


class RepoRootBackend(Backend):
    """Opens bare repositories under one root, by the URL prefix dulwich hands it."""

    def __init__(self, repos_root: Path) -> None:
        self.repos_root = repos_root

    def open_repository(self, path: str | bytes) -> Repo:
        # dulwich hands the URL prefix as bytes from the receive/upload-pack
        # service handlers and as str from the info/refs handler.
        if isinstance(path, bytes):
            path = path.decode("utf-8")
        repo_path = resolve_repo(path, repos_root=self.repos_root)
        if repo_path is None or not repo_path.is_dir():
            # Generic on purpose: dulwich echoes str(exc) into 404 bodies.
            raise NotGitRepository("repository not found")
        return Repo(str(repo_path))


class _NoThinPackUploadPackHandler(UploadPackHandler):
    """Upload-pack that tolerates clients which never request thin-pack.

    isomorphic-git — the client the Veneer plugin syncs with — does not send
    the thin-pack capability, and dulwich rejects any client missing a
    capability in required_capabilities(), which turned every clone/pull
    from that client into a 500. Thin packs are only a wire-size
    optimization for delta objects, so nothing here needs them.
    """

    @classmethod
    def required_capabilities(cls) -> tuple[bytes, ...]:
        return tuple(
            capability
            for capability in super().required_capabilities()
            if capability != CAPABILITY_THIN_PACK
        )


def _dulwich_handlers() -> dict:
    """dulwich's default service handlers with the tolerant upload-pack swapped in."""
    return {b"git-upload-pack": _NoThinPackUploadPackHandler}


class GitWriteApp:
    """Auth, resolution and auto-create, then dulwich's smart-HTTP application."""

    def __init__(self, repos_root: Path, tokens_file: Path) -> None:
        self.repos_root = repos_root
        self.tokens_file = tokens_file
        self._dulwich_app = make_wsgi_chain(
            RepoRootBackend(repos_root), handlers=_dulwich_handlers()
        )

    def __call__(self, environ: dict, start_response) -> Iterator[bytes]:
        if not authenticate(environ, tokens_file=self.tokens_file):
            return self._respond(start_response, "401 Unauthorized", _UNAUTHORIZED_HEADERS,
                                 _GENERIC_401_BODY)
        repo_path = resolve_repo(environ.get("PATH_INFO", ""), repos_root=self.repos_root)
        if repo_path is None:
            return self._respond(start_response, "403 Forbidden",
                                 [("Content-Type", "text/plain")], _GENERIC_403_BODY)
        if not repo_path.is_dir():
            if is_push(environ):
                # init_bare(mkdir=True) creates only the final directory, not
                # the root or nested owner directories.
                repo_path.parent.mkdir(parents=True, exist_ok=True)
                # default_branch keeps clones from landing on a HEAD that
                # points at a nonexistent master ref.
                Repo.init_bare(str(repo_path), mkdir=True, default_branch=b"refs/heads/main")
            else:
                return self._respond(start_response, "404 Not Found",
                                     [("Content-Type", "text/plain")], _GENERIC_404_BODY)
        return self._dulwich_app(environ, start_response)

    @staticmethod
    def _respond(start_response, status: str, headers, body: bytes) -> Iterator[bytes]:
        headers = [*headers, ("Content-Length", str(len(body)))]
        start_response(status, headers)
        return iter([body])


def create_app(repos_root: Path, tokens_file: Path) -> GitWriteApp:
    """Build the full WSGI stack for the given root and token file."""
    return GitWriteApp(repos_root, tokens_file)
