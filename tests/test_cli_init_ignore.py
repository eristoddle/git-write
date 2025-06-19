import pytest # Still needed for @pytest.fixture if any local fixtures remain (none expected for now) and for tmp_path
import pygit2 # Used directly in some tests
import os # Used directly in some tests
# shutil was for fixtures, now in conftest
from pathlib import Path # Used directly in some tests
from click.testing import CliRunner # For type hinting runner fixture from conftest
from .conftest import make_commit, _assert_gitwrite_structure, _assert_common_gitignore_patterns

from gitwrite_cli.main import cli
# COMMON_GITIGNORE_PATTERNS is now imported in conftest.py for helpers.
# Keep other gitwrite_core.repository imports if tests use them directly.
from gitwrite_core.repository import initialize_repository, add_pattern_to_gitignore, list_gitignore_patterns

# Helper functions (make_commit, _assert_gitwrite_structure, _assert_common_gitignore_patterns) are in conftest.py
# Fixtures (runner, init_test_dir, local_repo_path, local_repo) are in conftest.py


#######################
# Init Command Tests (CLI Runner)
#######################
class TestGitWriteInit:

    def test_init_in_empty_directory_no_project_name(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite init` in an empty directory (uses current dir)."""
        test_dir = tmp_path / "current_dir_init"
        test_dir.mkdir()
        os.chdir(test_dir)

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        dir_name = test_dir.name
        assert f"Initialized empty Git repository in {dir_name}" in result.output
        assert f"Created GitWrite directory structure in {dir_name}" in result.output
        assert f"Staged GitWrite files in {dir_name}" in result.output
        assert f"Created GitWrite structure commit in {dir_name}" in result.output
        assert (test_dir / ".git").is_dir()
        # _assert_gitwrite_structure and _assert_common_gitignore_patterns are in conftest.py
        # These can be called directly if needed, e.g. _assert_gitwrite_structure(test_dir)


    def test_init_with_project_name(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite init project_name`."""
        project_name = "my_new_book"
        base_dir = tmp_path / "base_for_named_project"
        base_dir.mkdir()
        project_dir = base_dir / project_name

        os.chdir(base_dir)

        result = runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert project_dir.exists(), "Project directory was not created by CLI call"
        assert project_dir.is_dir()
        assert f"Initialized empty Git repository in {project_name}" in result.output
        assert f"Created GitWrite directory structure in {project_name}" in result.output
        assert f"Created GitWrite structure commit in {project_name}" in result.output
        assert (project_dir / ".git").is_dir()

    def test_init_error_project_directory_is_a_file(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test error when `gitwrite init project_name` and project_name is an existing file."""
        project_name = "existing_file_name"
        base_dir = tmp_path / "base_for_file_conflict"
        base_dir.mkdir()
        file_path = base_dir / project_name
        file_path.write_text("I am a file.")
        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", project_name])
        assert f"Error: A file named '{project_name}' already exists" in result.output
        assert result.exit_code == 0
        assert not (base_dir / project_name / ".git").exists()

    def test_init_error_project_directory_exists_not_empty_not_git(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `init project_name` where project_name dir exists, is not empty, and not a Git repo."""
        project_name = "existing_non_empty_dir"
        base_dir = tmp_path / "base_for_non_empty_conflict"
        base_dir.mkdir()
        project_dir_path = base_dir / project_name
        project_dir_path.mkdir()
        (project_dir_path / "some_file.txt").write_text("Hello")
        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", project_name])
        assert f"Error: Directory '{project_name}' already exists, is not empty, and is not a Git repository." in result.output
        assert result.exit_code == 0
        assert not (project_dir_path / ".git").exists()

    def test_init_in_existing_git_repository(self, runner: CliRunner, local_repo: pygit2.Repository, local_repo_path: Path): # runner, local_repo, local_repo_path from conftest
        """Test `gitwrite init` in an existing Git repository."""
        os.chdir(local_repo_path)
        repo_name = local_repo_path.name
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Created GitWrite directory structure in {repo_name}" in result.output
        assert f"Added GitWrite structure to {repo_name}" in result.output
        assert (local_repo_path / "drafts").is_dir()

    def test_init_in_existing_non_empty_dir_not_git_no_project_name(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite init` in current dir if it's non-empty and not a Git repo."""
        test_dir = tmp_path / "existing_non_empty_current_dir"
        test_dir.mkdir()
        (test_dir / "my_random_file.txt").write_text("content")
        dir_name = test_dir.name
        os.chdir(test_dir)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert f"Error: Current directory '{dir_name}' is not empty and not a Git repository." in result.output
        assert not (test_dir / ".git").exists()

    def test_init_gitignore_appends_not_overwrites(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test that init appends to existing .gitignore rather than overwriting."""
        test_dir = tmp_path / "gitignore_append_test"
        test_dir.mkdir()
        os.chdir(test_dir)
        gitignore_path = test_dir / ".gitignore"
        user_entry = "# User specific ignore\n*.mydata\n"
        gitignore_path.write_text(user_entry)
        pygit2.init_repository(str(test_dir)) # pygit2 import is still needed
        repo = pygit2.Repository(str(test_dir))
        make_commit(repo, ".gitignore", user_entry, "Add initial .gitignore with user entry") # make_commit from conftest
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # _assert_gitwrite_structure and _assert_common_gitignore_patterns are in conftest.py
        _assert_gitwrite_structure(test_dir)
        _assert_common_gitignore_patterns(gitignore_path)
        final_gitignore_content = gitignore_path.read_text()
        assert user_entry.strip() in final_gitignore_content
        assert COMMON_GITIGNORE_PATTERNS[0] in final_gitignore_content
        last_commit = repo.head.peel(pygit2.Commit)
        if ".gitignore" in last_commit.tree:
            gitignore_blob = repo.get(last_commit.tree[".gitignore"].id)
            assert user_entry.strip() in gitignore_blob.data.decode('utf-8')

    def test_init_is_idempotent_for_structure(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test that running init multiple times doesn't create multiple commits if structure is identical."""
        test_dir = tmp_path / "idempotent_test"
        test_dir.mkdir()
        os.chdir(test_dir)
        result1 = runner.invoke(cli, ["init"])
        assert result1.exit_code == 0, f"First init failed: {result1.output}"
        assert "Created GitWrite structure commit." in result1.output
        repo = pygit2.Repository(str(test_dir)) # pygit2 import is still needed
        commit1_hash = repo.head.target
        result2 = runner.invoke(cli, ["init"])
        assert result2.exit_code == 0, f"Second init failed: {result2.output}"
        assert "GitWrite structure already present and tracked." in result2.output or \
               "GitWrite structure already present and up-to-date." in result2.output
        commit2_hash = repo.head.target
        assert commit1_hash == commit2_hash, "No new commit should have been made on second init."
        _assert_gitwrite_structure(test_dir) # _assert_gitwrite_structure from conftest


#######################
# Ignore Command Tests (CLI Runner)
#######################

def test_ignore_add_new_pattern_cli(runner: CliRunner): # runner from conftest
    """CLI: Test adding a new pattern."""
    with runner.isolated_filesystem() as temp_dir:
        result = runner.invoke(cli, ['ignore', 'add', '*.log'])
        assert result.exit_code == 0
        assert "Pattern '*.log' added to .gitignore." in result.output
        assert (Path(temp_dir) / ".gitignore").exists()

def test_ignore_add_duplicate_pattern_cli(runner: CliRunner): # runner from conftest
    """CLI: Test adding a duplicate pattern."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore" # Path import is still needed
        initial_pattern = "existing_pattern"
        gitignore_file.write_text(f"{initial_pattern}\n")
        result = runner.invoke(cli, ['ignore', 'add', initial_pattern])
        assert result.exit_code == 0
        assert f"Pattern '{initial_pattern}' already exists in .gitignore." in result.output

def test_ignore_add_pattern_strips_whitespace_cli(runner: CliRunner): # runner from conftest
    """CLI: Test adding a pattern strips leading/trailing whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        result = runner.invoke(cli, ['ignore', 'add', '  *.tmp  '])
        assert result.exit_code == 0
        assert "Pattern '*.tmp' added to .gitignore." in result.output
        assert (Path(temp_dir) / ".gitignore").exists()

def test_ignore_add_empty_pattern_cli(runner: CliRunner): # runner from conftest
    """CLI: Test adding an empty or whitespace-only pattern."""
    with runner.isolated_filesystem():
        result_empty = runner.invoke(cli, ['ignore', 'add', ''])
        assert result_empty.exit_code == 0
        assert "Pattern cannot be empty." in result_empty.output
        result_whitespace = runner.invoke(cli, ['ignore', 'add', '   '])
        assert result_whitespace.exit_code == 0
        assert "Pattern cannot be empty." in result_whitespace.output

def test_ignore_list_existing_gitignore_cli(runner: CliRunner): # runner from conftest
    """CLI: Test listing patterns from an existing .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore" # Path import is still needed
        patterns = ["pattern1", "*.log", "another/path/"]
        gitignore_content = "\n".join(patterns) + "\n"
        gitignore_file.write_text(gitignore_content)
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore Contents" in result.output
        for pattern in patterns:
            assert pattern in result.output

def test_ignore_list_non_existent_gitignore_cli(runner: CliRunner): # runner from conftest
    """CLI: Test listing when .gitignore does not exist."""
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore file not found." in result.output

def test_ignore_list_empty_gitignore_cli(runner: CliRunner): # runner from conftest
    """CLI: Test listing an empty .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore" # Path import is still needed
        gitignore_file.touch()
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore is empty." in result.output

def test_ignore_list_gitignore_with_only_whitespace_cli(runner: CliRunner): # runner from conftest
    """CLI: Test listing a .gitignore file that contains only whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore" # Path import is still needed
        gitignore_file.write_text("\n   \n\t\n")
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore is empty." in result.output
