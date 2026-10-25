"""`gitwrite export epub` against real repositories and the real pandoc."""

import shutil
import zipfile

import pygit2
import pytest

from gitwrite_cli.main import cli
from tests.helpers import init_repo

SIG = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")


@pytest.fixture
def book(tmp_path):
    """A repo with two chapters saved in one commit; returns (path, commit id)."""
    path = tmp_path / "book"
    repo = init_repo(path)
    (path / "ch1.md").write_text("# Chapter One\n\nIt was a dark night.\n")
    (path / "ch2.md").write_text("# Chapter Two\n\nMorning came.\n")
    repo.index.add_all()
    repo.index.write()
    oid = repo.create_commit("HEAD", SIG, SIG, "two chapters", repo.index.write_tree(), [])
    return path, oid


def _epub_text(epub_path) -> str:
    with zipfile.ZipFile(epub_path) as z:
        assert z.read("mimetype") == b"application/epub+zip"
        return " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xhtml"))


@needs_pandoc
def test_export_epub_writes_a_valid_epub_in_file_order(runner, book, tmp_path):
    path, _ = book
    out = tmp_path / "out" / "book.epub"

    result = runner.invoke(cli, ["export", "epub", str(path), "ch2.md", "ch1.md", "-o", str(out)])

    assert result.exit_code == 0, result.output
    text = _epub_text(out)
    assert text.index("Morning came") < text.index("dark night")


@needs_pandoc
def test_export_epub_uses_the_committed_text_not_the_working_copy(runner, book, tmp_path):
    path, oid = book
    (path / "ch1.md").write_text("# Chapter One\n\nUNSAVED EDIT\n")
    out = tmp_path / "book.epub"

    result = runner.invoke(cli, ["export", "epub", str(path), "ch1.md", "-o", str(out), "--commit", str(oid)])

    assert result.exit_code == 0, result.output
    text = _epub_text(out)
    assert "dark night" in text
    assert "UNSAVED EDIT" not in text


@needs_pandoc  # core checks for pandoc before it resolves the commit
def test_export_epub_unknown_commit(runner, book, tmp_path):
    path, _ = book
    out = tmp_path / "book.epub"

    result = runner.invoke(cli, ["export", "epub", str(path), "ch1.md", "-o", str(out), "-c", "no-such-ref"])

    assert result.exit_code == 1
    assert "Error: Commit 'no-such-ref' not found" in result.output
    assert not out.exists()


@needs_pandoc
def test_export_epub_file_not_in_commit(runner, book, tmp_path):
    path, _ = book
    out = tmp_path / "book.epub"

    result = runner.invoke(cli, ["export", "epub", str(path), "missing.md", "-o", str(out)])

    assert result.exit_code == 1
    assert "File not found in commit 'HEAD'" in result.output
    assert not out.exists()


def test_export_epub_without_pandoc_fails_with_a_pandoc_error(runner, book, tmp_path, monkeypatch):
    path, _ = book
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    result = runner.invoke(cli, ["export", "epub", str(path), "ch1.md", "-o", str(tmp_path / "b.epub")])

    assert result.exit_code == 1
    assert "Error during EPUB generation" in result.output
    assert "pandoc" in result.output.lower()


def test_export_epub_repo_path_must_exist(runner, tmp_path):
    result = runner.invoke(cli, ["export", "epub", str(tmp_path / "nope"), "f.md", "-o", str(tmp_path / "b.epub")])

    assert result.exit_code == 2
    assert "Invalid value for 'REPO_PATH'" in result.output


def test_export_epub_requires_output_path(runner, book):
    path, _ = book

    result = runner.invoke(cli, ["export", "epub", str(path), "ch1.md"])

    assert result.exit_code != 0
    assert "Missing option '-o' / '--output-path'" in result.output


def test_export_epub_requires_files(runner, book, tmp_path):
    path, _ = book

    result = runner.invoke(cli, ["export", "epub", str(path), "-o", str(tmp_path / "b.epub")])

    assert result.exit_code != 0
    assert "Missing argument 'FILES...'" in result.output


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.stdout
