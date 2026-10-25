"""`gitwrite cherry-pick` against real repositories (no mocks)."""

import pathlib

import pygit2
import pytest

from gitwrite_cli.main import cli
from tests.helpers import commit_on, init_repo, save


@pytest.fixture
def project(tmp_path, monkeypatch):
    """main has one commit; `feature` adds notes.md on top of it. Returns (repo, base, feature_tip)."""
    path = tmp_path / "proj"
    repo = init_repo(path)
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    base = save(repo, {"draft.md": "line one\nline two\n"}, "base")
    feature_tip = commit_on(repo, "feature", {"notes.md": "a note\n"}, "add notes")
    monkeypatch.chdir(path)
    return repo, base, feature_tip


class TestCherryPick:
    def test_picks_a_commit_onto_head(self, runner, project):
        repo, base, picked = project

        result = runner.invoke(cli, ["cherry-pick", str(picked)])

        assert result.exit_code == 0, result.output
        head = repo.head.peel(pygit2.Commit)
        assert head.id != picked  # a new commit, not the original
        assert head.message.strip() == "add notes"
        assert [p.id for p in head.parents] == [base]
        assert (pathlib.Path(repo.workdir) / "notes.md").read_text() == "a note\n"
        assert f"New commit: {str(head.id)[:7]}" in result.output
        assert repo.references["refs/heads/feature"].target == picked  # source branch untouched

    def test_unknown_commit(self, runner, project):
        repo, base, _ = project

        result = runner.invoke(cli, ["cherry-pick", "0123456789abcdef0123456789abcdef01234567"])

        assert result.exit_code == 0
        assert "Error:" in result.output and "not found" in result.output
        assert repo.head.target == base

    def test_conflict_reports_files_and_leaves_head_alone(self, runner, project):
        repo, base, _ = project
        clash = commit_on(repo, "other", {"draft.md": "line one\nTHEIR line two\n"}, "their edit")
        mine = save(repo, {"draft.md": "line one\nMY line two\n"}, "my edit")

        result = runner.invoke(cli, ["cherry-pick", str(clash)])

        assert result.exit_code == 0
        assert f"Cherry-pick of commit '{clash}' resulted in conflicts." in result.output
        assert "Conflicting files:" in result.output and "draft.md" in result.output
        assert repo.head.target == mine

    def test_merge_commit_needs_mainline(self, runner, project):
        repo, base, feature_tip = project
        merged = commit_on(repo, "merged", {"notes.md": "a note\n"}, "merge feature", extra_parents=(feature_tip,))

        result = runner.invoke(cli, ["cherry-pick", str(merged)])

        assert result.exit_code == 0
        assert "Error during cherry-pick:" in result.output
        assert "mainline" in result.output.lower()
        assert repo.head.target == base

    def test_merge_commit_with_mainline(self, runner, project):
        repo, base, feature_tip = project
        merged = commit_on(repo, "merged", {"extra.md": "x\n"}, "merge feature", extra_parents=(feature_tip,))

        result = runner.invoke(cli, ["cherry-pick", str(merged), "--mainline", "1"])

        assert result.exit_code == 0, result.output
        head = repo.head.peel(pygit2.Commit)
        assert head.id != base
        assert "extra.md" in [e.name for e in head.tree]

    def test_outside_a_repository(self, runner, tmp_path, monkeypatch):
        outside = tmp_path / "plain"
        outside.mkdir()
        monkeypatch.chdir(outside)

        result = runner.invoke(cli, ["cherry-pick", "abc1234"])

        assert result.exit_code == 0
        assert "Error: Not a Git repository" in result.output
