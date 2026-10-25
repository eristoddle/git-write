"""`save_and_commit_file` must never write into .git/ or outside the repository (audit: remote-API readiness)."""

import os
from pathlib import Path

import pygit2
import pytest

from gitwrite_core.repository import save_and_commit_file
from tests.helpers import init_repo, save


@pytest.fixture
def repo(tmp_path) -> pygit2.Repository:
    r = init_repo(tmp_path / "repo")
    r.config["user.name"] = "Tester"
    r.config["user.email"] = "tester@example.com"
    save(r, {"keep.md": "keep\n"}, "initial")
    return r


def _head_and_git_state(repo):
    return repo.head.target, (Path(repo.path) / "config").read_text()


def test_a_normal_nested_path_is_saved(repo):
    result = save_and_commit_file(repo.workdir, "chapters/one.md", "text", "add chapter")

    assert result["status"] == "success", result
    assert (Path(repo.workdir) / "chapters" / "one.md").read_text() == "text"
    assert repo.head.peel(pygit2.Commit).message.strip() == "add chapter"


@pytest.mark.parametrize("bad", [".git/config", ".git/hooks/pre-commit", "sub/../.git/HEAD", ".GIT/config", ".git"])
def test_paths_into_dot_git_are_rejected(repo, bad):
    before = _head_and_git_state(repo)

    result = save_and_commit_file(repo.workdir, bad, "[core]\n\tevil = true\n", "sneaky")

    assert result["status"] == "error", result
    assert _head_and_git_state(repo) == before
    assert not (Path(repo.path) / "hooks" / "pre-commit").exists()


def test_parent_traversal_is_rejected(repo, tmp_path):
    result = save_and_commit_file(repo.workdir, "../x", "escaped", "sneaky")

    assert result["status"] == "error", result
    assert not (tmp_path / "x").exists()


def test_sibling_directory_sharing_the_repo_name_prefix_is_rejected(repo, tmp_path):
    sibling = tmp_path / "repo-evil"
    sibling.mkdir()

    result = save_and_commit_file(repo.workdir, "../repo-evil/x.txt", "escaped", "sneaky")

    assert result["status"] == "error", result
    assert not (sibling / "x.txt").exists()


def test_absolute_path_outside_the_repo_is_rejected(repo, tmp_path):
    target = tmp_path / "elsewhere.txt"

    result = save_and_commit_file(repo.workdir, str(target), "escaped", "sneaky")

    assert result["status"] == "error", result
    assert not target.exists()


def test_symlinked_parent_pointing_outside_is_rejected(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, Path(repo.workdir) / "link")

    result = save_and_commit_file(repo.workdir, "link/x.txt", "escaped", "sneaky")

    assert result["status"] == "error", result
    assert not (outside / "x.txt").exists()


def test_symlinked_parent_pointing_into_dot_git_is_rejected(repo):
    os.symlink(Path(repo.path), Path(repo.workdir) / "gitlink")
    before = _head_and_git_state(repo)

    result = save_and_commit_file(repo.workdir, "gitlink/config", "[core]\n\tevil = true\n", "sneaky")

    assert result["status"] == "error", result
    assert _head_and_git_state(repo) == before


def test_the_repo_root_itself_is_rejected(repo):
    result = save_and_commit_file(repo.workdir, ".", "text", "sneaky")

    assert result["status"] == "error", result
