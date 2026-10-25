"""Shared test helpers."""

import pygit2


def init_repo(path, bare: bool = False, branch: str = "main") -> pygit2.Repository:
    """Create a repo whose initial branch is explicit.

    Never rely on the machine's ``init.defaultBranch``: libgit2 reads the
    global git config, so a bare ``init_repository`` makes the suite pass or
    fail depending on who runs it (D12).
    """
    return pygit2.init_repository(str(path), bare=bare, initial_head=branch)
