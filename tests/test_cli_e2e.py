"""One writer's whole session through the real `gitwrite` CLI on a real repository.

Every step checks repository state (refs, commits, files), not just the exit code (D10).
"""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pygit2
import pytest
from click.testing import CliRunner

from gitwrite_cli.main import cli


def run(runner: CliRunner, *args: str) -> str:
    result = runner.invoke(cli, list(args))
    assert result.exit_code == 0, f"gitwrite {' '.join(args)} failed ({result.exit_code}):\n{result.output}"
    return result.output


def commit_count(repo: pygit2.Repository, ref: str = "HEAD") -> int:
    return sum(1 for _ in repo.walk(repo.revparse_single(ref).peel(pygit2.Commit).id))


def head_branch(repo: pygit2.Repository) -> str:
    return repo.head.shorthand


def tree_names(repo: pygit2.Repository, ref: str = "HEAD") -> set[str]:
    return {entry.name for entry in repo.revparse_single(ref).peel(pygit2.Commit).tree}


def test_a_writing_session_end_to_end(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # init
    run(runner, "init", "novel")
    project = tmp_path / "novel"
    assert (project / ".git").is_dir()
    repo = pygit2.Repository(str(project))
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    monkeypatch.chdir(project)
    main = head_branch(repo)
    base_commits = commit_count(repo) if not repo.head_is_unborn else 0

    # save
    (project / "chapter1.md").write_text("# Chapter One\n\nIt was a dark night.\n")
    run(runner, "save", "Chapter 1 draft")
    assert commit_count(repo) == base_commits + 1
    assert repo.head.peel(pygit2.Commit).message.strip() == "Chapter 1 draft"
    assert "chapter1.md" in tree_names(repo)

    # history
    assert "Chapter 1 draft" in run(runner, "history")

    # explore (create a branch) and save on it
    run(runner, "explore", "alt-ending")
    assert "alt-ending" in repo.branches.local
    assert head_branch(repo) == "alt-ending"
    (project / "ending.md").write_text("# Ending\n\nShe left at dawn.\n")
    run(runner, "save", "Alternate ending")
    alt_tip = repo.branches.local["alt-ending"].target
    assert "ending.md" in tree_names(repo, "alt-ending")
    assert repo.branches.local[main].target != alt_tip

    # switch back, work on main
    run(runner, "switch", main)
    assert head_branch(repo) == main
    assert not (project / "ending.md").exists()
    (project / "chapter1.md").write_text("# Chapter One\n\nIt was a very dark night.\n")
    run(runner, "save", "Main revision")
    assert repo.head.peel(pygit2.Commit).message.strip() == "Main revision"
    main_before_merge = repo.head.target

    # merge the exploration into main
    run(runner, "merge", "alt-ending")
    merged = repo.head.peel(pygit2.Commit)
    assert {p.id for p in merged.parents} == {main_before_merge, alt_tip}
    assert (project / "ending.md").read_text() == "# Ending\n\nShe left at dawn.\n"
    assert "very dark night" in (project / "chapter1.md").read_text()
    assert repo.state() == pygit2.enums.RepositoryState.NONE

    # tag
    run(runner, "tag", "add", "v1", "-m", "First complete draft")
    tag_obj = repo.get(repo.references["refs/tags/v1"].target)
    assert isinstance(tag_obj, pygit2.Tag) and tag_obj.target == merged.id
    assert "v1" in run(runner, "tag", "list")

    # review a branch with work main does not have
    run(runner, "explore", "editor-notes")
    (project / "notes.md").write_text("Tighten chapter one.\n")
    run(runner, "save", "Editor notes")
    run(runner, "switch", main)
    review = run(runner, "review", "editor-notes")
    assert "Editor notes" in review
    assert "Main revision" not in review

    # export (needs pandoc)
    if shutil.which("pandoc") is None:
        pytest.skip("pandoc is not installed; everything up to export passed")
    out = tmp_path / "novel.epub"
    run(runner, "export", "epub", ".", "chapter1.md", "ending.md", "-o", str(out))
    with zipfile.ZipFile(out) as z:
        assert z.read("mimetype") == b"application/epub+zip"
        text = " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xhtml"))
    assert text.index("very dark night") < text.index("left at dawn")


def test_the_console_script_runs():
    """`uv run gitwrite --help` works: the [project.scripts] entry points at the real Click group."""
    exe = shutil.which("gitwrite")
    if exe is None:
        pytest.skip("gitwrite console script is not on PATH (package not installed)")
    done = subprocess.run([exe, "--help"], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "GitWrite: Version control for writers." in done.stdout
