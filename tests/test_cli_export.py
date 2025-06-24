from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from click.testing import CliRunner # Changed from typer.testing

from gitwrite_cli.main import cli as app # app is the click.Group instance
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, FileNotFoundInCommitError, PandocError

runner = CliRunner()

def test_export_epub_success():
    # Removed patch for "gitwrite_cli.main.Path"
    with patch("gitwrite_cli.main.export_to_epub") as mock_export_core:

        # Simulate the core function returning a success dictionary
        mock_export_core.return_value = {"status": "success", "message": "Exported EPUB to output/my_export.epub"}

        result = runner.invoke(
            app,
            [
                "export",
                "epub",
                "test_repo",
                "file1.md",
                "file2.md",
                "-o",
                "output/my_export.epub",
                "--commit",
                "test_commit"
            ],
        )

        assert result.exit_code == 0
        assert "Exported EPUB to output/my_export.epub" in result.stdout

        mock_path_constructor.assert_called_once_with("output/my_export.epub")
        mock_export_core.assert_called_once_with(
            repo_path_str="test_repo",
            file_paths=("file1.md", "file2.md"), # Typer converts multiple args to a tuple
            output_path=mock_output_path_instance,
            commit_id="test_commit"
        )

def test_export_epub_success_default_commit_id():
    # Removed patch for "gitwrite_cli.main.Path"
    with patch("gitwrite_cli.main.export_to_epub") as mock_export_core:

        # Simulate the core function returning a success dictionary
        mock_export_core.return_value = {"status": "success", "message": "Exported EPUB to output/my_export.epub"}

        result = runner.invoke(
            app,
            [
                "export",
                "epub",
                "test_repo",
                "file1.md",
                "-o",
                "output/my_export.epub",
                # --commit is omitted, should default to "HEAD" or similar in core
            ],
        )

        assert result.exit_code == 0
        assert "Exported EPUB to output/my_export.epub" in result.stdout

        mock_path_constructor.assert_called_once_with("output/my_export.epub")
        mock_export_core.assert_called_once_with(
            repo_path_str="test_repo",
            file_paths=("file1.md",),
            output_path=mock_output_path_instance,
            commit_id=None # CLI passes None if not specified, core defaults to HEAD
        )


def test_export_epub_missing_output_path():
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
    assert "Missing option '--output-path' / '-o'." in result.stdout # Typer's error message

def test_export_epub_missing_files():
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
    assert "Missing argument 'FILES'." in result.stdout # Typer's error message

def test_export_epub_repository_not_found():
    # Removed patch for "gitwrite_cli.main.Path"
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
        assert result.exit_code == 1
        assert "Error: Repository not found: Repo not found" in result.stdout
        mock_export_core.assert_called_once()

def test_export_epub_commit_not_found():
    # Removed patch for "gitwrite_cli.main.Path"
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
        assert "Error: Commit not found: Commit SHA not found" in result.stdout
        mock_export_core.assert_called_once()

def test_export_epub_file_not_found_in_commit():
    # Removed patch for "gitwrite_cli.main.Path"
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
            ],
        )
        assert result.exit_code == 1
        assert "Error: File not found in commit: file.md not in commit" in result.stdout
        mock_export_core.assert_called_once()

def test_export_epub_pandoc_not_found_error():
    # Removed patch for "gitwrite_cli.main.Path"
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
        assert "Error: Pandoc not found. Please ensure Pandoc is installed and in your PATH." in result.stdout
        mock_export_core.assert_called_once()

def test_export_epub_pandoc_conversion_error():
    # Removed patch for "gitwrite_cli.main.Path"
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
        assert "Error: Pandoc conversion error: Pandoc conversion failed with error" in result.stdout
        mock_export_core.assert_called_once()

def test_export_epub_generic_exception():
    with patch("gitwrite_cli.main.export_to_epub", side_effect=Exception("A generic unexpected error")) as mock_export_core, \
         patch("gitwrite_cli.main.Path"):
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
        assert "An unexpected error occurred: A generic unexpected error" in result.stdout
        mock_export_core.assert_called_once()

def test_cli_basic_invocation(runner: CliRunner): # Added runner type hint
    """Checks if the basic CLI group can be invoked without error."""
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.stdout
