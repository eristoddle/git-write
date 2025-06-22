import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, ANY
import pygit2

from gitwrite_cli.main import cli
# Assuming exceptions are correctly defined in core.exceptions
from gitwrite_core.exceptions import RepositoryNotFoundError, BranchNotFoundError as CoreBranchNotFoundError, CommitNotFoundError as CoreCommitNotFoundError, MergeConflictError as CoreMergeConflictError, GitWriteError

# Fixtures like runner, local_repo_path, make_commit can be used if defined in conftest.py
# For now, this test file will define its own mocks or use basic runner.

class TestCliReviewCommand:
    def test_review_success(self, runner: CliRunner):
        mock_commits_data = [
            {"short_hash": "abc1234", "author_name": "Author 1", "date": "2023-01-01", "message_short": "Commit 1"},
            {"short_hash": "def5678", "author_name": "Author 2", "date": "2023-01-02", "message_short": "Commit 2"},
        ]
        with patch("gitwrite_cli.main.get_branch_review_commits", return_value=mock_commits_data) as mock_core_review:
            result = runner.invoke(cli, ["review", "feature-branch"])
            assert result.exit_code == 0
            # Normalize whitespace for title check
            normalized_output = " ".join(result.output.split())
            assert "Review: Commits on 'feature-branch' not in HEAD" in normalized_output
            assert "abc1234" in result.output
            assert "Commit 1" in result.output
            assert "def5678" in result.output
            assert "Commit 2" in result.output
            mock_core_review.assert_called_once_with(ANY, "feature-branch", limit=None)

    def test_review_no_unique_commits(self, runner: CliRunner):
        with patch("gitwrite_cli.main.get_branch_review_commits", return_value=[]) as mock_core_review:
            result = runner.invoke(cli, ["review", "main"])
            assert result.exit_code == 0
            assert "No unique commits found on branch 'main' compared to HEAD." in result.output
            mock_core_review.assert_called_once_with(ANY, "main", limit=None)

    def test_review_branch_not_found(self, runner: CliRunner):
        with patch("gitwrite_cli.main.get_branch_review_commits", side_effect=CoreBranchNotFoundError("Branch 'non-existent' not found.")) as mock_core_review:
            result = runner.invoke(cli, ["review", "non-existent"])
            assert result.exit_code == 0 # CLI commands often exit 0 even on handled app errors, printing to stderr
            assert "Error: Branch 'non-existent' not found." in result.output
            mock_core_review.assert_called_once_with(ANY, "non-existent", limit=None)

    def test_review_not_a_git_repository(self, runner: CliRunner):
        with patch("gitwrite_cli.main.get_branch_review_commits", side_effect=RepositoryNotFoundError("Not a repo.")) as mock_core_review:
            result = runner.invoke(cli, ["review", "some-branch"])
            assert result.exit_code == 0 # As above
            assert "Error: Not a Git repository" in result.output
            mock_core_review.assert_called_once_with(ANY, "some-branch", limit=None)

    def test_review_with_limit(self, runner: CliRunner):
        mock_commits_data = [
            {"short_hash": "abc1234", "author_name": "Author 1", "date": "2023-01-01", "message_short": "Commit 1"},
        ] # Assume core function respects limit
        with patch("gitwrite_cli.main.get_branch_review_commits", return_value=mock_commits_data) as mock_core_review:
            result = runner.invoke(cli, ["review", "feature-branch", "-n", "1"])
            assert result.exit_code == 0
            assert "abc1234" in result.output
            mock_core_review.assert_called_once_with(ANY, "feature-branch", limit=1)

class TestCliCherryPickCommand:
    def test_cherry_pick_success(self, runner: CliRunner):
        mock_success_result = {
            "status": "success",
            "message": "Commit 'orig123' cherry-picked successfully as 'new456'.",
            "new_commit_oid": "new456abc"
        }
        with patch("gitwrite_cli.main.cherry_pick_commit", return_value=mock_success_result) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "orig123"])
            assert result.exit_code == 0
            assert "Commit 'orig123' cherry-picked successfully as 'new456'." in result.output
            assert "New commit: new456a" in result.output # CLI shows short OID
            mock_core_cherry_pick.assert_called_once_with(ANY, "orig123", mainline=None)

    def test_cherry_pick_success_with_mainline(self, runner: CliRunner):
        mock_success_result = {
            "status": "success",
            "message": "Commit 'merge123' cherry-picked successfully as 'new789'.",
            "new_commit_oid": "new789def"
        }
        with patch("gitwrite_cli.main.cherry_pick_commit", return_value=mock_success_result) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "merge123", "--mainline", "2"])
            assert result.exit_code == 0
            assert "Commit 'merge123' cherry-picked successfully as 'new789'." in result.output
            assert "New commit: new789d" in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "merge123", mainline=2)

    def test_cherry_pick_commit_not_found(self, runner: CliRunner):
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=CoreCommitNotFoundError("Commit 'nonexistent' not found.")) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "nonexistent"])
            assert result.exit_code == 0 # CLI handles error
            assert "Error: Commit 'nonexistent' not found." in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "nonexistent", mainline=None)

    def test_cherry_pick_conflict(self, runner: CliRunner):
        conflict_files = ["file1.txt", "path/to/file2.md"]
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=CoreMergeConflictError("Cherry-pick resulted in conflicts.", conflicting_files=conflict_files)) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "conflict123"])
            assert result.exit_code == 0 # CLI handles error
            assert "Error: Cherry-pick of commit 'conflict123' resulted in conflicts." in result.output
            assert "Cherry-pick resulted in conflicts." in result.output # Core message
            assert "Conflicting files:" in result.output
            assert "file1.txt" in result.output
            assert "path/to/file2.md" in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "conflict123", mainline=None)

    def test_cherry_pick_not_a_git_repository(self, runner: CliRunner):
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=RepositoryNotFoundError("Not a repo.")) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "somecommit"])
            assert result.exit_code == 0 # CLI handles error
            assert "Error: Not a Git repository" in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "somecommit", mainline=None)

    def test_cherry_pick_merge_commit_without_mainline_error_from_core(self, runner: CliRunner):
        # Assuming core raises GitWriteError for this
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=GitWriteError("Commit is a merge commit. Please specify --mainline.")) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "mergecommit"])
            assert result.exit_code == 0 # CLI handles error
            assert "Error during cherry-pick: Commit is a merge commit. Please specify --mainline." in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "mergecommit", mainline=None)

    def test_cherry_pick_merge_commit_invalid_mainline_error_from_core(self, runner: CliRunner):
        # Assuming core raises GitWriteError for this
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=GitWriteError("Invalid mainline number 3 for merge commit.")) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "mergecommit", "--mainline", "3"])
            assert result.exit_code == 0 # CLI handles error
            assert "Error during cherry-pick: Invalid mainline number 3 for merge commit." in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "mergecommit", mainline=3)

    def test_cherry_pick_generic_gitwrite_error(self, runner: CliRunner):
        with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=GitWriteError("A generic core error occurred.")) as mock_core_cherry_pick:
            result = runner.invoke(cli, ["cherry-pick", "somecommit"])
            assert result.exit_code == 0
            assert "Error during cherry-pick: A generic core error occurred." in result.output
            mock_core_cherry_pick.assert_called_once_with(ANY, "somecommit", mainline=None)

# It's good practice to have a conftest.py for shared fixtures like 'runner'
# If not present, these tests assume 'runner' is provided by pytest-click or similar.
# For example, in conftest.py:
# import pytest
# from click.testing import CliRunner
# @pytest.fixture
# def runner():
# return CliRunner()
#
# And ensure pygit2 objects are properly mocked if the core functions are not fully mocked out.
# The `ANY` from `unittest.mock` is used for the repo_path_str argument as it's usually CWD.
# The CLI commands mostly exit with 0 on handled errors, printing messages to stdout/stderr.
# Non-zero exit codes are typically for unhandled exceptions or explicit ctx.exit(1).
# The current CLI error handling for `review` and `cherry-pick` results in exit_code 0.
# This could be changed if desired, but tests should reflect current behavior.
# Note: CoreBranchNotFoundError and CoreCommitNotFoundError are aliases to avoid name clashes.
# Make sure these aliases match the import style in gitwrite_cli.main.py if it also uses aliases.
# The current implementation in main.py uses `from gitwrite_core.exceptions import ... BranchNotFoundError as CoreBranchNotFoundError`
# and `from gitwrite_core.exceptions import ... CommitNotFoundError`. The test should align.
# Corrected above to use `CoreCommitNotFoundError` for consistency if aliased in main.py,
# or just `CommitNotFoundError` if not. The current main.py imports `CommitNotFoundError` directly.
# The test for `cherry_pick_commit_not_found` uses `CoreCommitNotFoundError` which should be `CommitNotFoundError`
# as per main.py's direct import, or `CoreCommitNotFoundError` if main.py was aliasing it.
# Let's assume main.py uses `from gitwrite_core.exceptions import ... CommitNotFoundError` (no alias)
# And `from gitwrite_core.exceptions import ... BranchNotFoundError as CoreBranchNotFoundError` (alias used)
# The test class has been updated to reflect this.
# Actually, main.py imports `CommitNotFoundError` directly, and `BranchNotFoundError as CoreBranchNotFoundError`.
# The test class `TestCliCherryPickCommand` needs to use `CommitNotFoundError` from `gitwrite_core.exceptions`
# or if it's aliased in the test file, use that alias.
# For simplicity, I'll assume the test file imports them directly or with aliases that match its usage.
# The provided snippet imports `CommitNotFoundError as CoreCommitNotFoundError`, so that's used in the test.
# This means `gitwrite_cli.main.cherry_pick_commit` is expected to raise `CoreCommitNotFoundError` if that's how it's caught in `main.py`.
# Let's re-check `main.py`: it catches `CommitNotFoundError` (no alias).
# So, the test should also use `CommitNotFoundError` for `cherry-pick` errors.

# Correcting the import for CommitNotFoundError in the test file based on main.py's usage.
# from gitwrite_core.exceptions import RepositoryNotFoundError, BranchNotFoundError as CoreBranchNotFoundError, CommitNotFoundError, MergeConflictError, GitWriteError
# This is how it should be if CommitNotFoundError is not aliased in main.py for the cherry-pick command.
# The test `test_cherry_pick_commit_not_found` should use `CommitNotFoundError`. I'll adjust this in the next step if needed.
# The current test file uses `CoreCommitNotFoundError`.
# The `main.py` for cherry-pick catches `CommitNotFoundError`.
# So the test should be:
# with patch("gitwrite_cli.main.cherry_pick_commit", side_effect=CommitNotFoundError("Commit 'nonexistent' not found."))
# I will make this correction in the next iteration.
# For now, the file is created with the current version.
# The alias for BranchNotFoundError is CoreBranchNotFoundError in main.py, so that part is correct.
# The alias for CommitNotFoundError is CoreCommitNotFoundError in the test file. This is the mismatch.
# I will proceed with creating the file and then fix this specific detail.

# Final check on imports in main.py relevant to these tests:
# from gitwrite_core.exceptions import ( ... BranchNotFoundError as CoreBranchNotFoundError, CommitNotFoundError, MergeConflictError ... )
# So, the test file should use `CoreBranchNotFoundError` and `CommitNotFoundError`.
# The test file uses `CoreCommitNotFoundError` which is an alias IT defines. This is fine.
# The important part is that `patch("gitwrite_cli.main.cherry_pick_commit", side_effect=CoreCommitNotFoundError(...))`
# means the mocked core function raises `CoreCommitNotFoundError` (the alias for `CommitNotFoundError`).
# And in `gitwrite_cli.main.py`, the `except CommitNotFoundError as e:` block will catch it. This is consistent.
# So the alias `CoreCommitNotFoundError` in the test file is just for local use within that file.
# The actual exception raised (`CommitNotFoundError`) is what matters for the `try-except` in `main.py`.
# The test setup is okay.
