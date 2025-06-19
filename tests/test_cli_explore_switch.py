import pytest # Still needed for test collection and tmp_path
import pygit2 # Used directly in tests
import os # Used directly in tests
# shutil was only for fixtures, now moved to conftest.py
from pathlib import Path # Used directly in tests
from click.testing import CliRunner # Used by runner fixture in conftest.py, but tests type hint it.

from gitwrite_cli.main import cli
# Fixtures (runner, cli_test_repo, cli_repo_with_remote) and make_commit helper are now in conftest.py
from .conftest import make_commit # Import the helper function
from gitwrite_core.branching import create_and_switch_branch, list_branches, switch_to_branch
from gitwrite_core.exceptions import BranchAlreadyExistsError, BranchNotFoundError, RepositoryEmptyError, RepositoryNotFoundError
from rich.table import Table # Used by switch command output formatting


#######################################
# Explore Command Tests (CLI Runner)
#######################################
class TestExploreCommandCLI:
    def test_explore_success_cli(self, runner: CliRunner, cli_test_repo: Path): # Fixtures from conftest
        os.chdir(cli_test_repo)
        branch_name = "my-new-adventure"
        result = runner.invoke(cli, ["explore", branch_name]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to a new exploration: {branch_name}" in result.output
        repo = pygit2.Repository(str(cli_test_repo))
        assert repo.head.shorthand == branch_name
        assert not repo.head_is_detached

    def test_explore_branch_exists_cli(self, runner: CliRunner, cli_test_repo: Path): # Fixtures from conftest
        os.chdir(cli_test_repo)
        branch_name = "existing-feature-branch"
        repo = pygit2.Repository(str(cli_test_repo))
        repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit))
        result = runner.invoke(cli, ["explore", branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Error: Branch '{branch_name}' already exists." in result.output

    def test_explore_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_repo_for_cli_explore" # tmp_path is a built-in pytest fixture
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)
        result = runner.invoke(cli, ["explore", "some-branch"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot create branch: HEAD is unborn. Commit changes first." in result.output

    def test_explore_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_repo_for_cli_explore.git" # tmp_path is a built-in pytest fixture
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["explore", "any-branch"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_explore_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path):
        non_git_dir = tmp_path / "non_git_dir_for_cli_explore" # tmp_path is a built-in pytest fixture
        non_git_dir.mkdir()
        os.chdir(non_git_dir)
        result = runner.invoke(cli, ["explore", "any-branch"]) # runner from conftest
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

    def test_switch_list_empty_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        empty_repo_dir = tmp_path / "empty_for_cli_switch_list"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No explorations (branches) yet." in result.output

    def test_switch_list_bare_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        bare_repo_dir = tmp_path / "bare_for_cli_switch_list.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_list_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
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

    def test_switch_to_remote_branch_detached_head_cli(self, runner: CliRunner, cli_repo_with_remote: Path): # Fixtures from conftest
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

    def test_switch_in_bare_repo_action_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        bare_repo_dir = tmp_path / "bare_for_cli_switch_action.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)
        result = runner.invoke(cli, ["switch", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_in_empty_repo_action_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
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
        # make_commit is now in conftest.py and will be used from there.
        make_commit(repo, "conflict_file.txt", "Version on develop", "Commit on develop")
        main_branch_name = "main"
        if not repo.branches.local.get(main_branch_name):
            main_branch_name = repo.branches.local[0].branch_name
        repo.checkout(repo.branches.local[main_branch_name].name)
        repo.set_head(repo.branches.local[main_branch_name].name)
        (Path(str(cli_test_repo)) / "conflict_file.txt").write_text("Dirty version on main")
        result = runner.invoke(cli, ["switch", "develop"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Checkout failed: Your local changes to tracked files would be overwritten by checkout of 'develop'." in result.output
