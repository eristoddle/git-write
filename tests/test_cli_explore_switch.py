import pytest
import pygit2
import os
import shutil # Required for some fixtures if they clean up paths
from pathlib import Path
from click.testing import CliRunner

from gitwrite_cli.main import cli
from gitwrite_core.branching import create_and_switch_branch, list_branches, switch_to_branch
from gitwrite_core.exceptions import BranchAlreadyExistsError, BranchNotFoundError, RepositoryEmptyError, RepositoryNotFoundError
from rich.table import Table # Used by switch command output formatting

# Helper to create a commit
def make_commit(repo, filename, content, message):
    file_path = Path(repo.workdir) / filename
    file_path.write_text(content)
    repo.index.add(filename)
    repo.index.write()
    author = pygit2.Signature("Test Author", "test@example.com", 946684800, 0)
    committer = pygit2.Signature("Test Committer", "committer@example.com", 946684800, 0)
    parents = [repo.head.target] if not repo.head_is_unborn else []
    tree = repo.index.write_tree()
    return repo.create_commit("HEAD", author, committer, message, tree, parents)

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def cli_test_repo(tmp_path: Path):
    """Creates a standard initialized repo for CLI tests, returning its path."""
    repo_path = tmp_path / "cli_git_repo_explore_switch" # Unique name
    repo_path.mkdir()
    repo = pygit2.init_repository(str(repo_path), bare=False)
    # Initial commit
    file_path = repo_path / "initial.txt"
    file_path.write_text("initial content for explore/switch tests")
    repo.index.add("initial.txt")
    repo.index.write()
    author_sig = pygit2.Signature("Test Author CLI", "testcli@example.com") # Use one signature obj
    tree = repo.index.write_tree()
    repo.create_commit("HEAD", author_sig, author_sig, "Initial commit for CLI explore/switch", tree, [])
    return repo_path

@pytest.fixture
def cli_repo_with_remote(tmp_path: Path, runner: CliRunner): # Added runner fixture for potential CLI use
    local_repo_path = tmp_path / "cli_local_for_remote_switch"
    local_repo_path.mkdir()
    local_repo = pygit2.init_repository(str(local_repo_path))
    make_commit(local_repo, "main_file.txt", "content on main", "Initial commit on main")

    bare_remote_path = tmp_path / "cli_remote_server_switch.git"
    pygit2.init_repository(str(bare_remote_path), bare=True)

    origin_remote = local_repo.remotes.create("origin", str(bare_remote_path))
    main_branch_name = local_repo.head.shorthand
    origin_remote.push([f"refs/heads/{main_branch_name}:refs/heads/{main_branch_name}"])

    main_commit = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-x", main_commit)
    local_repo.checkout("refs/heads/feature-x")
    make_commit(local_repo, "fx_file.txt", "feature-x content", "Commit on feature-x")
    origin_remote.push(["refs/heads/feature-x:refs/heads/feature-x"])

    local_repo.checkout(f"refs/heads/{main_branch_name}")
    main_commit_again = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-y-local", main_commit_again)
    local_repo.checkout("refs/heads/feature-y-local")
    make_commit(local_repo, "fy_file.txt", "feature-y content", "Commit for feature-y")
    origin_remote.push(["refs/heads/feature-y-local:refs/heads/feature-y"])
    local_repo.branches.local.delete("feature-y-local")
    local_repo.checkout(f"refs/heads/{main_branch_name}")
    return local_repo_path


#######################################
# Explore Command Tests (CLI Runner)
#######################################
class TestExploreCommandCLI:
    def test_explore_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        branch_name = "my-new-adventure"
        result = runner.invoke(cli, ["explore", branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to a new exploration: {branch_name}" in result.output
        repo = pygit2.Repository(str(cli_test_repo))
        assert repo.head.shorthand == branch_name
        assert not repo.head_is_detached

    def test_explore_branch_exists_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        branch_name = "existing-feature-branch"
        repo = pygit2.Repository(str(cli_test_repo))
        repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit))
        result = runner.invoke(cli, ["explore", branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Error: Branch '{branch_name}' already exists." in result.output

    def test_explore_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_repo_for_cli_explore"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)
        result = runner.invoke(cli, ["explore", "some-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot create branch: HEAD is unborn. Commit changes first." in result.output

    def test_explore_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_repo_for_cli_explore.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["explore", "any-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_explore_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path):
        non_git_dir = tmp_path / "non_git_dir_for_cli_explore"
        non_git_dir.mkdir()
        os.chdir(non_git_dir)
        result = runner.invoke(cli, ["explore", "any-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Repository not found at or above" in result.output
        assert f"'{str(Path.cwd())}'" in result.output or "'.'" in result.output

#######################################
# Switch Command Tests (CLI Runner)
#######################################
class TestSwitchCommandCLI:
    def test_switch_list_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        main_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create("develop", main_commit)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Available Explorations" in result.output
        output_lines = result.output.splitlines()
        assert any("  develop" in line for line in output_lines)
        assert any(f"* {repo.head.shorthand}" in line for line in output_lines)

    def test_switch_list_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_for_cli_switch_list"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No explorations (branches) yet." in result.output

    def test_switch_list_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_for_cli_switch_list.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_list_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path):
        non_git_dir = tmp_path / "non_git_for_cli_switch_list"
        non_git_dir.mkdir()
        os.chdir(non_git_dir)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Repository not found at or above" in result.output

    def test_switch_to_local_branch_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        repo.branches.local.create("develop", repo.head.peel(pygit2.Commit))
        result = runner.invoke(cli, ["switch", "develop"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to exploration: develop" in result.output
        repo.head.resolve()
        assert repo.head.shorthand == "develop"
        assert not repo.head_is_detached

    def test_switch_already_on_branch_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        current_branch = repo.head.shorthand
        result = runner.invoke(cli, ["switch", current_branch])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Already on exploration: {current_branch}" in result.output

    def test_switch_to_remote_branch_detached_head_cli(self, runner: CliRunner, cli_repo_with_remote: Path):
        os.chdir(cli_repo_with_remote)
        result = runner.invoke(cli, ["switch", "feature-y"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to exploration: origin/feature-y" in result.output
        assert "Note: HEAD is now in a detached state." in result.output
        repo = pygit2.Repository(str(cli_repo_with_remote))
        assert repo.head_is_detached

    def test_switch_branch_not_found_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        result = runner.invoke(cli, ["switch", "no-such-branch-here"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Branch 'no-such-branch-here' not found" in result.output

    def test_switch_in_bare_repo_action_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_for_cli_switch_action.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["switch", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_in_empty_repo_action_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_for_cli_switch_action"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)
        result = runner.invoke(cli, ["switch", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot switch branch in an empty repository to non-existent branch 'anybranch'." in result.output

    def test_switch_dirty_workdir_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        main_commit = repo.head.peel(pygit2.Commit)
        develop_branch = repo.branches.local.create("develop", main_commit)
        repo.checkout(develop_branch.name)
        repo.set_head(develop_branch.name) # Make sure HEAD points to the branch ref
        (Path(str(cli_test_repo)) / "conflict_file.txt").write_text("Version on develop")
        make_commit(repo, "conflict_file.txt", "Version on develop", "Commit on develop")
        main_branch_name = "main" # Assuming 'main' is the default, adjust if needed
        if not repo.branches.local.get(main_branch_name): # Fallback for 'master' or other default
            main_branch_name = repo.branches.local[0].branch_name # A bit fragile, assumes a default exists
        repo.checkout(repo.branches.local[main_branch_name].name)
        repo.set_head(repo.branches.local[main_branch_name].name) # Update HEAD
        (Path(str(cli_test_repo)) / "conflict_file.txt").write_text("Dirty version on main")
        result = runner.invoke(cli, ["switch", "develop"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Checkout failed: Your local changes to tracked files would be overwritten by checkout of 'develop'." in result.output
