from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from click.testing import CliRunner # Changed from typer.testing

from gitwrite_cli.main import cli as app # app is the click.Group instance
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, FileNotFoundInCommitError, PandocError

runner = CliRunner()

def test_export_epub_success():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir() # Create dummy repo_path for Click's Path(exists=True) check
        with patch("gitwrite_cli.main.export_to_epub") as mock_export_core:

            # Simulate the core function returning a success dictionary
            mock_export_core.return_value = {"status": "success", "message": "Exported EPUB to output/my_export.epub"}

            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo", # This will now be found by Click in the temp_dir
                    "file1.md",
                    "file2.md",
                    "-o",
                    "output/my_export.epub", # Output path can be relative to temp_dir
                    "--commit",
                    "test_commit"
                ],
            )
            # print(f"Output for test_export_epub_success: {result.output}") # For debugging
            # print(f"Exit code for test_export_epub_success: {result.exit_code}") # For debugging
            # if result.exception:
            #    print(f"Exception for test_export_epub_success: {result.exception}")


            assert result.exit_code == 0
        assert "Exported EPUB to output/my_export.epub" in result.stdout

        # mock_path_constructor.assert_called_once_with("output/my_export.epub") # Removed as per instructions
        mock_export_core.assert_called_once_with(
            repo_path_str="test_repo",
            file_list=["file1.md", "file2.md"], # Core function expects a list
            output_epub_path_str="output/my_export.epub", # Use the correct keyword and string value
            commit_ish_str="test_commit" # Correct keyword from core function
        )

def test_export_epub_success_default_commit_id():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir() # Create dummy repo_path for Click's Path(exists=True) check
        with patch("gitwrite_cli.main.export_to_epub") as mock_export_core:

            # Simulate the core function returning a success dictionary
            mock_export_core.return_value = {"status": "success", "message": "Exported EPUB to output/my_export.epub"}

            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo", # This will now be found by Click in the temp_dir
                    "file1.md",
                    "-o",
                    "output/my_export.epub", # Output path can be relative to temp_dir
                    # --commit is omitted, should default to "HEAD" or similar in core
                ],
            )
            # print(f"Output for test_export_epub_success_default_commit_id: {result.output}") # For debugging
            # print(f"Exit code for test_export_epub_success_default_commit_id: {result.exit_code}") # For debugging
            # if result.exception:
            #    print(f"Exception for test_export_epub_success_default_commit_id: {result.exception}")


            assert result.exit_code == 0
        assert "Exported EPUB to output/my_export.epub" in result.stdout

        # mock_path_constructor.assert_called_once_with("output/my_export.epub") # Removed as per instructions
        mock_export_core.assert_called_once_with(
            repo_path_str="test_repo",
            file_list=["file1.md"], # Core function expects a list
            output_epub_path_str="output/my_export.epub", # Use the correct keyword and string value
            commit_ish_str="HEAD" # CLI passes "HEAD" by default to core if not specified
        )


def test_export_epub_missing_output_path():
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        result = runner.invoke(
            app,
            [
                "export",
                "epub",
                "test_repo",
                "file1.md",
                # -o is missing
            ],
        )
        assert result.exit_code != 0 # Typer's default exit code for missing option is 2
    assert "Error: Missing option '-o' / '--output-path'." in result.output # Adjusted to match Click's actual error

def test_export_epub_missing_files():
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        result = runner.invoke(
            app,
            [
                "export",
                "epub",
                "test_repo",
                # FILES are missing
                "-o",
                "output/my_export.epub",
            ],
        )
        assert result.exit_code != 0 # Typer's default exit code for missing argument is 2
    assert "Error: Missing argument 'FILES...'." in result.output # Adjusted to match Click's actual error (with ellipsis)

def test_export_epub_repository_not_found():
    # This test now checks Click's error for a non-existent repo_path,
    # because `type=click.Path(exists=True)` will catch it first.
    # The mock for export_to_epub is not strictly needed if Click errors out first,
    # but we keep it to show intent if Click's validation were different.
    with runner.isolated_filesystem() as temp_dir: # To ensure "non_existent_repo" truly doesn't exist
        # Don't create "non_existent_repo" here
        with patch("gitwrite_cli.main.export_to_epub", side_effect=RepositoryNotFoundError("Repo not found")) as mock_export_core:
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "non_existent_repo",
                    "file1.md",
                    "-o",
                    "output.epub"
                ],
            )
            assert result.exit_code == 2 # Click's exit code for invalid param
            assert "Invalid value for 'REPO_PATH': Directory 'non_existent_repo' does not exist." in result.output
            mock_export_core.assert_not_called() # Core function shouldn't be called if Click validation fails

def test_export_epub_commit_not_found():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        with patch("gitwrite_cli.main.export_to_epub", side_effect=CommitNotFoundError("Commit SHA not found")) as mock_export_core:
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo",
                    "file1.md",
                    "-o",
                    "output.epub",
                    "--commit",
                    "invalid_sha"
                ],
            )
            assert result.exit_code == 1
            assert "Error: Commit 'invalid_sha' not found: Commit SHA not found" in result.output # Updated expected message
            mock_export_core.assert_called_once()

def test_export_epub_file_not_found_in_commit():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        with patch("gitwrite_cli.main.export_to_epub", side_effect=FileNotFoundInCommitError("file.md not in commit")) as mock_export_core:
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo",
                    "non_existent_file.md",
                    "-o",
                    "output.epub"
                    # commit_ish defaults to HEAD
                ],
            )
            assert result.exit_code == 1
            # The CLI prepends "File not found in commit '{commit_ish}':"
            assert "Error: File not found in commit 'HEAD': file.md not in commit" in result.output
            mock_export_core.assert_called_once()

def test_export_epub_pandoc_not_found_error():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        with patch("gitwrite_cli.main.export_to_epub", side_effect=PandocError("Pandoc not found. Please ensure Pandoc is installed and in your PATH.")) as mock_export_core:
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo",
                    "file1.md",
                    "-o",
                    "output.epub"
                ],
            )
            assert result.exit_code == 1
            # The CLI prepends "Error during EPUB generation: " and adds a hint
            assert "Error during EPUB generation: Pandoc not found. Please ensure Pandoc is installed and in your PATH." in result.output
            assert "Hint: Please ensure Pandoc is installed and accessible in your system's PATH." in result.output
            mock_export_core.assert_called_once()

def test_export_epub_pandoc_conversion_error():
    # Removed patch for "gitwrite_cli.main.Path"
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        with patch("gitwrite_cli.main.export_to_epub", side_effect=PandocError("Pandoc conversion failed with error")) as mock_export_core:
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo",
                    "file1.md",
                    "-o",
                    "output.epub"
                ],
            )
            assert result.exit_code == 1
            # The CLI prepends "Error during EPUB generation: "
            assert "Error during EPUB generation: Pandoc conversion failed with error" in result.output
            mock_export_core.assert_called_once()

def test_export_epub_generic_exception():
    with runner.isolated_filesystem() as temp_dir:
        Path("test_repo").mkdir()
        with patch("gitwrite_cli.main.export_to_epub", side_effect=Exception("A generic unexpected error")) as mock_export_core, \
             patch("gitwrite_cli.main.Path"): # Path mock might not be needed anymore
            result = runner.invoke(
                app,
                [
                    "export",
                    "epub",
                    "test_repo",
                    "file1.md",
                    "-o",
                    "output.epub"
                ],
            )
            assert result.exit_code == 1
            assert "An unexpected error occurred during EPUB export: A generic unexpected error" in result.output
        mock_export_core.assert_called_once()

def test_cli_basic_invocation(runner: CliRunner): # Added runner type hint
    """Checks if the basic CLI group can be invoked without error."""
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.stdout
