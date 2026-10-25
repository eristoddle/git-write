"""Shared test helpers."""

import pathlib

import pygit2


def init_repo(path, bare: bool = False, branch: str = "main") -> pygit2.Repository:
    """Create a repo whose initial branch is explicit.

    Never rely on the machine's ``init.defaultBranch``: libgit2 reads the
    global git config, so a bare ``init_repository`` makes the suite pass or
    fail depending on who runs it (D12).
    """
    return pygit2.init_repository(str(path), bare=bare, initial_head=branch)


SIGNATURE = pygit2.Signature("Test Author", "author@example.com", 946684800, 0)


def save(repo: pygit2.Repository, files: dict[str, str], message: str) -> pygit2.Oid:
    """Write files into the working tree and commit them on HEAD (works for the first commit too)."""
    for name, text in files.items():
        target = pathlib.Path(repo.workdir) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        repo.index.add(name)
    repo.index.write()
    parents = [] if repo.head_is_unborn else [repo.head.target]
    return repo.create_commit("HEAD", SIGNATURE, SIGNATURE, message, repo.index.write_tree(), parents)


def commit_on(repo: pygit2.Repository, branch: str, files: dict[str, str], message: str,
              extra_parents: tuple[pygit2.Oid, ...] = ()) -> pygit2.Oid:
    """Commit files on top of `branch` (created at HEAD if missing) without touching the working tree."""
    ref = f"refs/heads/{branch}"
    if branch not in repo.branches.local:
        repo.branches.local.create(branch, repo.head.peel(pygit2.Commit))
    tip = repo.references[ref].peel(pygit2.Commit)
    builder = repo.TreeBuilder(tip.tree)
    for name, text in files.items():
        builder.insert(name, repo.create_blob(text.encode()), pygit2.enums.FileMode.BLOB)
    return repo.create_commit(ref, SIGNATURE, SIGNATURE, message, builder.write(), [tip.id, *extra_parents])
