"""Server tests: real git over real HTTP against the live WSGI app.

No mocks — pygit2 builds the commits, the real `git` CLI drives push/clone/
pull over HTTP, and the server runs in-process on an ephemeral port (the
spec's verification rules; see CLAUDE.md for the no-mocking house rule).
Plain http is correct in tests: the plugin alone enforces https at its edge.
"""

import base64
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner

from gitwrite_server.app import _NoThinPackUploadPackHandler, is_push
from gitwrite_server.auth import authenticate, create_token, list_tokens, revoke_token
from gitwrite_server.cli import cli
from gitwrite_server.resolver import parse_repo_segments, resolve_repo
from tests.helpers import init_repo, save


class Server:
    def __init__(self, repos_root: Path, tokens_file: Path, port: int, token: str) -> None:
        self.repos_root = repos_root
        self.tokens_file = tokens_file
        self.port = port
        self.token = token
        self.base_url = f"http://127.0.0.1:{port}"


# The live-server fixture that builds this lives in conftest.py so both test
# modules can reach it; Server stays here with its domain.


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", "-c", "user.name=Test Author", "-c", "user.email=author@example.com", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=60,
    )


def authed_url(server: Server, repo_path: str, token: str | None = None) -> str:
    token = token if token is not None else server.token
    return f"http://writer:{token}@127.0.0.1:{server.port}{repo_path}"


def get(server: Server, path: str, *, token: str | None = None) -> tuple[int, str, bytes]:
    """GET a path with optional Basic auth; returns (status, WWW-Authenticate header, body)."""
    request = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}")
    if token is not None:
        encoded = base64.b64encode(f"writer:{token}".encode()).decode()
        request.add_header("Authorization", f"Basic {encoded}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers.get("WWW-Authenticate", ""), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("WWW-Authenticate", ""), error.read()


def make_source_repo(path: Path, files: dict[str, str], message: str):
    repo = init_repo(path, bare=False, branch="main")
    save(repo, files, message)
    return repo


# --- push → clone → pull round trip ---------------------------------------------------


def test_push_clone_pull_round_trip(server: Server, tmp_path: Path) -> None:
    url = authed_url(server, "/novel.git")
    repo_a = make_source_repo(tmp_path / "a", {"novel.txt": "chapter one"}, "first")

    pushed = run_git("-C", str(tmp_path / "a"), "push", url, "main")
    assert pushed.returncode == 0, pushed.stderr

    cloned = run_git("clone", url, str(tmp_path / "b"))
    assert cloned.returncode == 0, cloned.stderr
    assert (tmp_path / "b" / "novel.txt").read_text() == "chapter one"

    save(repo_a, {"novel.txt": "chapter one and two"}, "second")
    pushed_again = run_git("-C", str(tmp_path / "a"), "push", url, "main")
    assert pushed_again.returncode == 0, pushed_again.stderr

    pulled = run_git("-C", str(tmp_path / "b"), "pull")
    assert pulled.returncode == 0, pulled.stderr
    assert (tmp_path / "b" / "novel.txt").read_text() == "chapter one and two"


def test_first_push_auto_creates_bare_repo(server: Server, tmp_path: Path) -> None:
    url = authed_url(server, "/autocreated.git")
    make_source_repo(tmp_path / "src", {"story.txt": "once"}, "first")

    pushed = run_git("-C", str(tmp_path / "src"), "push", url, "main")
    assert pushed.returncode == 0, pushed.stderr

    bare = server.repos_root / "autocreated.git"
    assert (bare / "HEAD").is_file()
    assert "bare = true" in (bare / "config").read_text()
    assert (bare / "HEAD").read_text().strip() == "ref: refs/heads/main"

    cloned = run_git("clone", url, str(tmp_path / "clone"))
    assert cloned.returncode == 0, cloned.stderr
    assert (tmp_path / "clone" / "story.txt").read_text() == "once"


def test_push_to_owner_path_auto_creates_nested_bare_repo(
    server: Server, tmp_path: Path
) -> None:
    url = authed_url(server, "/writer/novel.git")
    make_source_repo(tmp_path / "src", {"story.txt": "once"}, "first")

    pushed = run_git("-C", str(tmp_path / "src"), "push", url, "main")
    assert pushed.returncode == 0, pushed.stderr
    assert (server.repos_root / "writer" / "novel.git" / "HEAD").is_file()

    cloned = run_git("clone", url, str(tmp_path / "clone"))
    assert cloned.returncode == 0, cloned.stderr
    assert (tmp_path / "clone" / "story.txt").read_text() == "once"


def test_fetch_of_missing_repo_is_404(server: Server) -> None:
    status, _, _ = get(server, "/ghost.git/info/refs?service=git-upload-pack", token=server.token)
    assert status == 404
    assert not (server.repos_root / "ghost.git").exists()
    assert run_git("ls-remote", authed_url(server, "/ghost.git")).returncode != 0


# --- auth rejection --------------------------------------------------------------------


def test_missing_credentials_rejected(server: Server) -> None:
    status, www_authenticate, body = get(server, "/novel.git/info/refs?service=git-upload-pack")
    assert status == 401
    assert www_authenticate.startswith("Basic ")
    # Generic body; no-path-echo is asserted in test_error_bodies_contain_no_filesystem_paths.
    assert body


def test_wrong_token_rejected(server: Server, tmp_path: Path) -> None:
    status, www_authenticate, _ = get(
        server, "/novel.git/info/refs?service=git-upload-pack", token="wrong-token"
    )
    assert status == 401
    assert www_authenticate.startswith("Basic ")

    make_source_repo(tmp_path / "src", {"story.txt": "once"}, "first")
    url = authed_url(server, "/novel.git", token="wrong-token")
    pushed = run_git("-C", str(tmp_path / "src"), "push", url, "main")
    assert pushed.returncode != 0
    assert not (server.repos_root / "novel.git").exists()


def test_revoked_token_rejected(server: Server, tmp_path: Path) -> None:
    token = create_token("laptop", tokens_file=server.tokens_file)
    assert revoke_token("laptop", tokens_file=server.tokens_file) is True

    status, _, _ = get(server, "/novel.git/info/refs?service=git-upload-pack", token=token)
    assert status == 401

    make_source_repo(tmp_path / "src", {"story.txt": "once"}, "first")
    pushed = run_git(
        "-C", str(tmp_path / "src"), "push", authed_url(server, "/novel.git", token=token), "main"
    )
    assert pushed.returncode != 0


def test_auth_before_resolver_invalid_name_still_401(server: Server) -> None:
    # Auth runs before resolution: even a traversal attempt without a token is 401.
    status, www_authenticate, _ = get(server, "/%2e%2e/evil.git/info/refs")
    assert status == 401
    assert www_authenticate.startswith("Basic ")


# --- traversal and error-body hygiene --------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/evil.git/info/refs",  # the AUDIT's percent-encoded escape
        "/../evil.git/info/refs",
        "/novel.git/../evil.git/info/refs",
        "/a/b/c.git/info/refs",  # more than two segments
        "/.hidden.git/info/refs",  # starts with a dot
        "/no%20spaces.git/info/refs",
        "/info/refs",  # no repo path at all
    ],
)
def test_invalid_names_rejected_nothing_created_outside_root(
    server: Server, tmp_path: Path, path: str
) -> None:
    before = sorted(p.name for p in tmp_path.rglob("*"))
    status, _, body = get(server, path, token=server.token)
    assert status in (403, 404)
    after = sorted(p.name for p in tmp_path.rglob("*"))
    assert before == after
    assert not (tmp_path / "evil.git").exists()
    assert b"tmp" not in body and b"/" not in body.replace(b".git", b"")


def test_push_to_traversal_name_creates_nothing(server: Server, tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.rglob("*"))
    status, _, body = get(server, "/%2e%2e/evil.git/git-receive-pack", token=server.token)
    assert status in (403, 404)
    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    assert b"tmp" not in body


def test_error_bodies_contain_no_filesystem_paths(server: Server) -> None:
    root_str = str(server.repos_root.resolve()).encode()
    bodies = [
        get(server, "/ghost.git/info/refs?service=git-upload-pack")[2],
        get(server, "/%2e%2e/evil.git/info/refs")[2],
        get(server, "/novel.git/info/refs?service=git-upload-pack")[2],
    ]
    for body in bodies:
        assert root_str not in body
        assert b"/tmp/" not in body


# --- token hygiene ----------------------------------------------------------------------


def test_tokens_file_contains_only_label_hash_lines(server: Server) -> None:
    create_token("second", tokens_file=server.tokens_file)
    content = server.tokens_file.read_text()
    assert server.token not in content
    for line in content.splitlines():
        label, sep, stored = line.partition(":")
        assert sep
        assert label in ("veneer", "second")
        assert len(stored) == 64 and all(c in "0123456789abcdef" for c in stored)


def test_token_file_mode_is_0600(server: Server) -> None:
    assert os.name == "posix"
    assert (server.tokens_file.stat().st_mode & 0o777) == 0o600


# --- resolver and auth units ------------------------------------------------------------


def test_resolver_accepts_valid_names(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert resolve_repo("/novel.git", repos_root=root) == (root / "novel.git").resolve()
    assert resolve_repo("/owner/novel.git/info/refs", repos_root=root) == (
        root / "owner" / "novel.git"
    ).resolve()


@pytest.mark.parametrize(
    "path",
    [
        "/..",
        "/../etc/passwd",
        "/.",
        "/.hidden.git",
        "/a/b/c.git",
        "/novel .git",
        "/novel$.git",
        "/.git",
        "/novel",  # the .git suffix is required on the wire
        "",
        "/info/refs",
    ],
)
def test_resolver_rejects_invalid_names(tmp_path: Path, path: str) -> None:
    assert parse_repo_segments(path) is None
    assert resolve_repo(path, repos_root=tmp_path) is None


def test_resolver_confines_symlinked_names_to_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside)
    resolved = resolve_repo("/link/evil.git", repos_root=root)
    assert resolved is None or not resolved.is_relative_to(root.resolve())


def test_is_push_detects_receive_pack() -> None:
    assert is_push({"PATH_INFO": "/novel.git/git-receive-pack"})
    assert is_push(
        {"PATH_INFO": "/novel.git/info/refs", "QUERY_STRING": "service=git-receive-pack"}
    )
    assert not is_push({"PATH_INFO": "/novel.git/git-upload-pack"})
    assert not is_push({"PATH_INFO": "/novel.git/info/refs", "QUERY_STRING": "service=git-upload-pack"})
    assert not is_push({})


def test_upload_pack_handler_does_not_require_thin_pack() -> None:
    # isomorphic-git (the Veneer plugin's client) never requests thin-pack;
    # dulwich's default UploadPackHandler rejects any client that omits it.
    required = _NoThinPackUploadPackHandler.required_capabilities()
    assert b"thin-pack" not in required
    # The other defaults stay required: side-band and ofs-delta are requested
    # by every real client, including isomorphic-git.
    for capability in (b"side-band-64k", b"ofs-delta"):
        assert capability in required


def test_authenticate_accepts_any_username(server: Server) -> None:
    for username in ("writer", "", "someone-else"):
        encoded = base64.b64encode(f"{username}:{server.token}".encode()).decode()
        assert authenticate({"HTTP_AUTHORIZATION": f"Basic {encoded}"}, tokens_file=server.tokens_file)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"HTTP_AUTHORIZATION": "Basic not-base64!!"},
        {"HTTP_AUTHORIZATION": "Bearer sometoken"},
        {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"nocolon").decode()},
        {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"writer:wrong").decode()},
    ],
)
def test_authenticate_rejects_bad_credentials(server: Server, headers: dict) -> None:
    assert authenticate(headers, tokens_file=server.tokens_file) is False


# --- CLI --------------------------------------------------------------------------------


def test_cli_create_list_revoke(tmp_path: Path) -> None:
    runner = CliRunner()
    tokens_file = tmp_path / "tokens"

    created = runner.invoke(cli, ["create-token", "veneer", "--tokens-file", str(tokens_file)])
    assert created.exit_code == 0, created.output
    token = created.output.strip()
    assert token  # plaintext printed exactly once: it is nowhere else in the command output
    assert token not in tokens_file.read_text()

    listed = runner.invoke(cli, ["list-tokens", "--tokens-file", str(tokens_file)])
    assert listed.exit_code == 0
    assert listed.output.strip() == "veneer"

    revoked = runner.invoke(cli, ["revoke-token", "veneer", "--tokens-file", str(tokens_file)])
    assert revoked.exit_code == 0
    again = runner.invoke(cli, ["revoke-token", "veneer", "--tokens-file", str(tokens_file)])
    assert again.exit_code != 0
    assert list_tokens(tokens_file=tokens_file) == []


def test_cli_env_var_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITWRITE_TOKEN_FILE", str(tmp_path / "tokens"))
    runner = CliRunner()
    created = runner.invoke(cli, ["create-token", "veneer"])
    assert created.exit_code == 0, created.output
    assert (tmp_path / "tokens").exists()
