"""`get_branch_review_commits` and `gitwrite review` against real repositories (no mocks).

The old tests mocked the core function, so the unsupported `walk(..., hide=)` call
went unnoticed and every real review failed.
"""

import pygit2
import pytest

from gitwrite_cli.main import cli
from gitwrite_core.exceptions import BranchNotFoundError, GitWriteError, RepositoryNotFoundError
from gitwrite_core.versioning import get_branch_review_commits
from tests.helpers import commit_on, init_repo, save


@pytest.fixture
def project(tmp_path, monkeypatch):
    """main has `base`; `editor` has three commits on top of base; main has one commit editor lacks."""
    path = tmp_path / "proj"
    repo = init_repo(path)
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    base = save(repo, {"draft.md": "base\n"}, "base")
    editor = [
        commit_on(repo, "editor", {"draft.md": f"edit {i}\n"}, f"editor change {i}") for i in (1, 2, 3)
    ]
    save(repo, {"mine.md": "mine\n"}, "my own work")
    monkeypatch.chdir(path)
    return repo, base, editor


def test_returns_only_commits_not_reachable_from_head_oldest_first(project):
    repo, base, editor = project

    commits = get_branch_review_commits(repo.workdir, "editor")

    assert [c["oid"] for c in commits] == [str(o) for o in editor]
    assert [c["message_short"] for c in commits] == ["editor change 1", "editor change 2", "editor change 3"]
    assert commits[0]["short_hash"] == str(editor[0])[:7]
    assert commits[0]["author_name"] == "Test Author"


def test_limit_caps_the_result(project):
    repo, _, editor = project

    commits = get_branch_review_commits(repo.workdir, "editor", limit=2)

    assert len(commits) == 2


def test_branch_already_merged_has_nothing_to_review(project):
    repo, _, _ = project

    assert get_branch_review_commits(repo.workdir, "main") == []


def test_commits_already_in_head_are_hidden(project):
    repo, _, editor = project
    # Merge the first editor commit into main for real, so it becomes reachable from HEAD.
    repo.merge(editor[0])
    repo.index.write()
    tree = repo.index.write_tree()
    sig = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)
    repo.create_commit("HEAD", sig, sig, "merge editor 1", tree, [repo.head.target, editor[0]])
    repo.state_cleanup()

    commits = get_branch_review_commits(repo.workdir, "editor")

    assert [c["oid"] for c in commits] == [str(editor[1]), str(editor[2])]


def test_unknown_branch(project):
    repo, _, _ = project

    with pytest.raises(BranchNotFoundError):
        get_branch_review_commits(repo.workdir, "nope")


def test_unborn_head(tmp_path):
    repo = init_repo(tmp_path / "empty")

    with pytest.raises(GitWriteError, match="unborn"):
        get_branch_review_commits(repo.workdir, "main")


def test_not_a_repository(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(RepositoryNotFoundError):
        get_branch_review_commits(str(plain), "main")


class TestReviewCommand:
    def test_lists_the_branch_commits(self, runner, project):
        result = runner.invoke(cli, ["review", "editor"])

        assert result.exit_code == 0, result.output
        assert "Review: Commits on 'editor' not in HEAD" in " ".join(result.output.split())
        for i in (1, 2, 3):
            assert f"editor change {i}" in result.output
        assert "my own work" not in result.output

    def test_number_option(self, runner, project):
        result = runner.invoke(cli, ["review", "editor", "-n", "1"])

        assert result.exit_code == 0, result.output
        assert result.output.count("editor change") == 1

    def test_nothing_to_review(self, runner, project):
        result = runner.invoke(cli, ["review", "main"])

        assert result.exit_code == 0
        assert "No unique commits found on branch 'main' compared to HEAD." in result.output

    def test_unknown_branch(self, runner, project):
        result = runner.invoke(cli, ["review", "non-existent"])

        assert result.exit_code == 0
        assert "Error: Branch 'non-existent' not found" in result.output

    def test_outside_a_repository(self, runner, tmp_path, monkeypatch):
        plain = tmp_path / "plain"
        plain.mkdir()
        monkeypatch.chdir(plain)

        result = runner.invoke(cli, ["review", "main"])

        assert result.exit_code == 0
        assert "Error: Not a Git repository" in result.output
