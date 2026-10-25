"""`gitwrite tag list` against real repositories (no mocks)."""

import pygit2
import pytest

from gitwrite_cli.main import cli
from tests.helpers import init_repo

SIG = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A real repo with two commits on main, as the current directory."""
    repo = init_repo(tmp_path / "proj")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    workdir = tmp_path / "proj"
    commits = []
    for i, text in enumerate(["one", "two"]):
        (workdir / "draft.md").write_text(text)
        repo.index.add("draft.md")
        repo.index.write()
        parents = [commits[-1]] if commits else []
        commits.append(repo.create_commit("HEAD", SIG, SIG, f"save {i}", repo.index.write_tree(), parents))
    monkeypatch.chdir(workdir)
    return repo, commits


def test_list_no_tags(runner, project):
    result = runner.invoke(cli, ["tag", "list"])
    assert result.exit_code == 0
    assert "No tags found in the repository." in result.output


def test_list_lightweight_and_annotated_sorted(runner, project):
    repo, (first, second) = project
    repo.create_reference("refs/tags/zeta", first)
    repo.create_reference("refs/tags/alpha", second)
    repo.create_tag("beta", second, pygit2.enums.ObjectType.COMMIT, SIG, "Second milestone")

    result = runner.invoke(cli, ["tag", "list"])

    assert result.exit_code == 0, result.output
    out = result.output
    assert out.index("alpha") < out.index("beta") < out.index("zeta")
    assert "lightweight" in out and "annotated" in out
    assert "Second milestone" in out
    assert str(first)[:7] in out and str(second)[:7] in out


def test_list_skips_tag_that_points_at_a_blob(runner, project):
    repo, (first, _) = project
    blob = repo.create_blob(b"not a commit")
    repo.create_reference("refs/tags/blobby", blob)
    repo.create_reference("refs/tags/real", first)

    result = runner.invoke(cli, ["tag", "list"])

    assert result.exit_code == 0, result.output
    assert "real" in result.output
    assert "blobby" not in result.output


def test_list_outside_a_repository(runner, tmp_path, monkeypatch):
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.chdir(outside)

    result = runner.invoke(cli, ["tag", "list"])

    assert result.exit_code != 0
    assert "Not a git repository" in result.output


def test_list_in_a_bare_repository(runner, tmp_path, monkeypatch):
    bare = tmp_path / "bare.git"
    init_repo(bare, bare=True)
    monkeypatch.chdir(bare)

    result = runner.invoke(cli, ["tag", "list"])

    assert result.exit_code == 0, result.output
    assert "No tags found in the repository." in result.output
