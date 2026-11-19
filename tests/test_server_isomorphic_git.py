"""The server against isomorphic-git — the client the Veneer plugin actually uses.

tests/test_server.py drives the real git CLI; this module drives isomorphic-git
(from interop/node_modules, via tests/iso_client.mjs) so the suite covers the
protocol behavior of the plugin's own client: push, clone, pull and token
rejection. The thin-pack capability negotiation is exactly the kind of thing
only a real client exposes (isomorphic-git does not request thin-pack; the
git CLI always does).

Needs `node` and `npm ci` run in interop/. Locally the tests skip with a message
when those are missing; with GITWRITE_REQUIRE_INTEROP=1 (set in CI) a missing
prerequisite is a failure instead.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_server import Server

INTEROP = Path(__file__).parent.parent / "interop"
ISO_CLIENT = Path(__file__).parent / "iso_client.mjs"


@pytest.fixture(scope="module", autouse=True)
def iso_ready():
    problem = None
    if shutil.which("node") is None:
        problem = "node is not installed"
    elif not (INTEROP / "node_modules" / "isomorphic-git").is_dir():
        problem = f"run `npm ci` in {INTEROP} first"
    if problem:
        if os.environ.get("GITWRITE_REQUIRE_INTEROP") == "1":
            pytest.fail(f"interop prerequisites missing in CI: {problem}")
        pytest.skip(f"isomorphic-git server tests skipped: {problem}")


def test_isomorphic_git_push_clone_pull_round_trip(server: Server) -> None:
    done = subprocess.run(
        ["node", str(ISO_CLIENT), str(server.port), server.token],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"iso_client.mjs failed:\n{done.stdout}\n{done.stderr}"
    seen = json.loads(done.stdout)
    assert seen == {"push": True, "clone": True, "pull": True, "badTokenRejected": True}
