"""`gitwrite tag add` and core `create_tag` against real repositories (no mocks).

The old suite mocked pygit2 and handed the mock commit an `.oid` attribute, so it
stayed green while tag creation crashed on real commits (`.oid` is `.id`).
"""

import pygit2
import pytest

from gitwrite_cli.main import cli
from gitwrite_core.exceptions import CommitNotFoundError, GitWriteError, TagAlreadyExistsError
from gitwrite_core.tagging import create_tag, list_tags
from tests.helpers import init_repo, save


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Real repo with two commits on main, as the current directory. Returns (repo, first, second)."""
    path = tmp_path / "proj"
    repo = init_repo(path)
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    first = save(repo, {"draft.md": "one"}, "save 0")
    second = save(repo, {"draft.md": "two"}, "save 1")
    monkeypatch.chdir(path)
    return repo, first, second


class TestCoreCreateTag:
    def test_lightweight_tag_points_at_head(self, project):
        repo, _, second = project

        info = create_tag(repo.workdir, "v1")

        assert info == {"name": "v1", "type": "lightweight", "target": str(second)}
        assert repo.references["refs/tags/v1"].target == second

    def test_annotated_tag_is_a_real_tag_object(self, project):
        repo, first, _ = project
        tagger = pygit2.Signature("Tagger", "tagger@example.com", 946684800, 0)

        info = create_tag(repo.workdir, "v0.1", target_commit_ish=str(first), message="First draft", tagger=tagger)

        assert info["type"] == "annotated" and info["target"] == str(first)
        tag_obj = repo.get(repo.references["refs/tags/v0.1"].target)
        assert isinstance(tag_obj, pygit2.Tag)
        assert tag_obj.target == first
        assert tag_obj.message.strip() == "First draft"
        assert tag_obj.tagger.name == "Tagger"

    def test_annotated_tag_without_a_tagger_gets_the_core_default(self, project):
        repo, _, _ = project

        create_tag(repo.workdir, "v1", message="no tagger given")

        tag_obj = repo.get(repo.references["refs/tags/v1"].target)
        assert tag_obj.tagger.name == "GitWrite Core"

    def test_tag_on_a_branch_name(self, project):
        repo, _, second = project

        create_tag(repo.workdir, "from-branch", target_commit_ish="main")

        assert repo.references["refs/tags/from-branch"].target == second

    def test_existing_tag_is_refused_without_force(self, project):
        repo, first, second = project
        create_tag(repo.workdir, "v1", target_commit_ish=str(first))

        with pytest.raises(TagAlreadyExistsError):
            create_tag(repo.workdir, "v1")

        assert repo.references["refs/tags/v1"].target == first

    def test_force_moves_an_existing_tag(self, project):
        repo, first, second = project
        create_tag(repo.workdir, "v1", target_commit_ish=str(first))

        create_tag(repo.workdir, "v1", force=True)

        assert repo.references["refs/tags/v1"].target == second

    def test_unknown_commit(self, project):
        repo, _, _ = project

        with pytest.raises(CommitNotFoundError):
            create_tag(repo.workdir, "v1", target_commit_ish="no-such-ref")

        assert "refs/tags/v1" not in repo.references

    def test_unborn_head(self, tmp_path):
        repo = init_repo(tmp_path / "empty")

        with pytest.raises(CommitNotFoundError):
            create_tag(repo.workdir, "v1")

    def test_bare_repository(self, tmp_path):
        init_repo(tmp_path / "bare.git", bare=True)

        with pytest.raises(GitWriteError, match="bare repository"):
            create_tag(str(tmp_path / "bare.git"), "v1")

    def test_created_tags_round_trip_through_list_tags(self, project):
        repo, first, second = project
        create_tag(repo.workdir, "light", target_commit_ish=str(first))
        create_tag(repo.workdir, "note", message="Milestone", tagger=pygit2.Signature("T", "t@example.com", 0, 0))

        tags = {t["name"]: t for t in list_tags(repo.workdir)}

        assert tags["light"] == {"name": "light", "type": "lightweight", "target": str(first)}
        assert tags["note"] == {"name": "note", "type": "annotated", "target": str(second), "message": "Milestone"}


class TestTagAddCommand:
    def test_lightweight(self, runner, project):
        repo, _, second = project

        result = runner.invoke(cli, ["tag", "add", "v1.0"])

        assert result.exit_code == 0, result.output
        assert f"Successfully created lightweight tag 'v1.0' pointing to {str(second)[:7]}." in result.output
        assert repo.references["refs/tags/v1.0"].target == second

    def test_annotated_uses_the_repo_identity(self, runner, project):
        repo, _, second = project

        result = runner.invoke(cli, ["tag", "add", "v1.0", "-m", "First published version"])

        assert result.exit_code == 0, result.output
        tag_obj = repo.get(repo.references["refs/tags/v1.0"].target)
        assert isinstance(tag_obj, pygit2.Tag) and tag_obj.target == second
        assert tag_obj.message.strip() == "First published version"
        assert (tag_obj.tagger.name, tag_obj.tagger.email) == ("Tester", "tester@example.com")

    def test_tag_a_specific_commit(self, runner, project):
        repo, first, _ = project

        result = runner.invoke(cli, ["tag", "add", "early", "--commit", str(first)])

        assert result.exit_code == 0, result.output
        assert repo.references["refs/tags/early"].target == first

    def test_existing_tag_exits_nonzero_and_changes_nothing(self, runner, project):
        repo, first, _ = project
        create_tag(repo.workdir, "v1.0", target_commit_ish=str(first))

        result = runner.invoke(cli, ["tag", "add", "v1.0"])

        assert result.exit_code != 0
        assert "Error: Tag 'v1.0' already exists" in result.output
        assert repo.references["refs/tags/v1.0"].target == first

    def test_force_replaces_an_existing_tag(self, runner, project):
        repo, first, second = project
        create_tag(repo.workdir, "v1.0", target_commit_ish=str(first))

        result = runner.invoke(cli, ["tag", "add", "v1.0", "--force"])

        assert result.exit_code == 0, result.output
        assert repo.references["refs/tags/v1.0"].target == second

    def test_unknown_commit(self, runner, project):
        result = runner.invoke(cli, ["tag", "add", "v1.0", "-c", "nonexistent-commit"])

        assert result.exit_code != 0
        assert "Error: Commit-ish 'nonexistent-commit' not found" in result.output

    def test_empty_repository(self, runner, tmp_path, monkeypatch):
        path = tmp_path / "empty"
        init_repo(path)
        monkeypatch.chdir(path)

        result = runner.invoke(cli, ["tag", "add", "v1.0"])

        assert result.exit_code != 0
        assert "Error: Commit-ish 'HEAD' not found" in result.output

    def test_bare_repository(self, runner, tmp_path, monkeypatch):
        path = tmp_path / "bare.git"
        init_repo(path, bare=True)
        monkeypatch.chdir(path)

        result = runner.invoke(cli, ["tag", "add", "v1.0"])

        assert result.exit_code != 0
        assert "Error: Cannot create tags in a bare repository." in result.output

    def test_outside_a_repository(self, runner, tmp_path, monkeypatch):
        plain = tmp_path / "plain"
        plain.mkdir()
        monkeypatch.chdir(plain)

        result = runner.invoke(cli, ["tag", "add", "v1.0"])

        assert result.exit_code != 0
        assert "Error: Not a git repository (or any of the parent directories)." in result.output
