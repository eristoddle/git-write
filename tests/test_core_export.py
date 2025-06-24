import pytest
import pygit2
import pypandoc
import os
import shutil
import pathlib
import time
from unittest import mock

from gitwrite_core.export import export_to_epub
from gitwrite_core.exceptions import (
    PandocError,
    RepositoryNotFoundError,
    CommitNotFoundError,
    FileNotFoundInCommitError,
    GitWriteError,
)

def init_test_repo_corrected(tmp_path: pathlib.Path, add_files: dict = None, commit_message: str = "Initial commit"):
    try:
        repo = pygit2.Repository(str(tmp_path))
        if not add_files and not repo.is_empty and not repo.head_is_unborn :
            return repo
    except pygit2.GitError:
        tmp_path.mkdir(parents=True, exist_ok=True)
        pygit2.init_repository(str(tmp_path), bare=False)
        repo = pygit2.Repository(str(tmp_path))

    if add_files:
        index = repo.index
        index.read()
        for file_path_str, content in add_files.items():
            full_file_path = tmp_path / file_path_str
            full_file_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                with open(full_file_path, "wb") as f:
                    f.write(content)
            else:
                with open(full_file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            index.add(file_path_str)

        index.write()
        tree_id = index.write_tree()

        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "test@example.com")

        parents = []
        if not repo.head_is_unborn:
            parents = [repo.head.target]

        repo.create_commit("HEAD", author, committer, commit_message, tree_id, parents)
    return repo

@pytest.fixture
def temp_git_repo_path(tmp_path: pathlib.Path):
    repo_dir = tmp_path / "test_repo_for_export"
    repo_dir.mkdir()
    return repo_dir

@pytest.fixture
def mock_pypandoc_path_found(monkeypatch):
    mock_get_path = mock.Mock(return_value="/usr/bin/pandoc")
    monkeypatch.setattr(pypandoc, "get_pandoc_path", mock_get_path)
    return mock_get_path

@pytest.fixture
def mock_pypandoc_convert_text(monkeypatch):
    mock_convert = mock.Mock()
    monkeypatch.setattr(pypandoc, "convert_text", mock_convert)
    return mock_convert

def test_export_to_epub_success(temp_git_repo_path, mock_pypandoc_path_found, mock_pypandoc_convert_text):
    files_content = {"file1.md": "# Chapter 1\nHello", "file2.md": "# Chapter 2\nWorld"}
    init_test_repo_corrected(temp_git_repo_path, files_content, "Add markdown files")
    output_epub = temp_git_repo_path / "output.epub"
    file_list = ["file1.md", "file2.md"]
    result = export_to_epub(str(temp_git_repo_path), "HEAD", file_list, str(output_epub))
    assert result["status"] == "success"
    assert "EPUB successfully generated" in result["message"]
    expected_combined_content = "# Chapter 1\nHello\n\n---\n\n# Chapter 2\nWorld"
    mock_pypandoc_convert_text.assert_called_once_with(
        source=expected_combined_content, to='epub', format='md',
        outputfile=str(output_epub.resolve()), extra_args=['--standalone']
    )
    mock_pypandoc_path_found.assert_called_once()

def test_export_to_epub_pandoc_not_found(temp_git_repo_path, monkeypatch):
    monkeypatch.setattr(pypandoc, "get_pandoc_path", mock.Mock(side_effect=OSError("Pandoc not found simulation")))
    init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(PandocError, match="Pandoc not found. Please ensure pandoc is installed"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["file1.md"], str(output_epub))

def test_export_to_epub_repo_dir_not_found(tmp_path):
    with pytest.raises(RepositoryNotFoundError, match="Repository directory not found"):
        export_to_epub(str(tmp_path / "non_existent_repo"), "HEAD", ["f.md"], str(tmp_path / "o.epub"))

def test_export_to_epub_not_a_git_repo(temp_git_repo_path, mock_pypandoc_path_found):
    with pytest.raises(RepositoryNotFoundError, match="Not a valid Git repository"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["f.md"], str(temp_git_repo_path / "o.epub"))

def test_export_to_epub_empty_repository(temp_git_repo_path, mock_pypandoc_path_found):
    pygit2.init_repository(str(temp_git_repo_path), bare=False)
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(GitWriteError, match="Repository at .* is empty and has no commits to export from."):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["file.md"], str(output_epub))

def test_export_to_epub_commit_not_found(temp_git_repo_path, mock_pypandoc_path_found):
    init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(CommitNotFoundError, match="Commit-ish 'non_existent_commit' not found or invalid"):
        export_to_epub(str(temp_git_repo_path), "non_existent_commit", ["file1.md"], str(output_epub))

def test_export_to_epub_file_not_found_in_commit(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub = temp_git_repo_path / "output.epub"
    commit_short_id = repo.head.peel(pygit2.Commit).short_id
    with pytest.raises(FileNotFoundInCommitError, match=f"File 'non_existent_file.md' not found in commit '{commit_short_id}'"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["non_existent_file.md"], str(output_epub))

def test_export_to_epub_entry_is_not_blob(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"is_a_dir/dummy.txt": "content"}, "Add dir with file")
    output_epub = temp_git_repo_path / "output.epub"
    commit_short_id = repo.head.peel(pygit2.Commit).short_id
    with pytest.raises(FileNotFoundInCommitError, match=f"Entry 'is_a_dir' is not a file \\(blob\\) in commit '{commit_short_id}'. It is a 'tree'."):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["is_a_dir"], str(output_epub))

def test_export_to_epub_empty_file_list(temp_git_repo_path, mock_pypandoc_path_found):
    init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(GitWriteError, match="File list cannot be empty"):
        export_to_epub(str(temp_git_repo_path), "HEAD", [], str(output_epub))

def test_export_to_epub_non_utf8_file(temp_git_repo_path, mock_pypandoc_path_found):
    files_to_add = {"non_utf8.md": b"\xff\xfe# Invalid Char"}
    repo = init_test_repo_corrected(temp_git_repo_path, files_to_add, "Add non-UTF-8 file")
    output_epub = temp_git_repo_path / "output.epub"
    commit_short_id = repo.head.peel(pygit2.Commit).short_id
    with pytest.raises(GitWriteError, match=f"File 'non_utf8.md' in commit '{commit_short_id}' is not UTF-8 encoded"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["non_utf8.md"], str(output_epub))

def test_export_to_epub_pandoc_conversion_error(temp_git_repo_path, mock_pypandoc_path_found, mock_pypandoc_convert_text):
    mock_pypandoc_convert_text.side_effect = RuntimeError("Pandoc conversion failed badly")
    init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(PandocError, match="Pandoc conversion failed: Pandoc conversion failed badly"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["file1.md"], str(output_epub))

def test_export_to_epub_output_dir_creation_OSError(temp_git_repo_path, mock_pypandoc_path_found, monkeypatch):
    repo = init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    output_epub_path_str = str(temp_git_repo_path / "uncreatable_dir" / "output.epub")
    target_dir_to_fail = pathlib.Path(output_epub_path_str).parent
    def mock_mkdir_side_effect(path_instance, parents=False, exist_ok=False, mode=0o777):
        if path_instance == target_dir_to_fail:
            raise OSError("Test OSError for mkdir")
    monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir_side_effect)
    with pytest.raises(GitWriteError, match=f"Could not create output directory '{str(target_dir_to_fail)}': Test OSError for mkdir"):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["file1.md"], output_epub_path_str)

def test_export_to_epub_tag_resolves_to_commit(temp_git_repo_path, mock_pypandoc_path_found, mock_pypandoc_convert_text):
    repo = init_test_repo_corrected(temp_git_repo_path, {"file1.md": "# Tagged Content"}, "Commit for tag")
    commit_oid = repo.head.target
    tagger = pygit2.Signature("Tagger", "tag@example.com")
    repo.create_tag("v1.0", commit_oid, pygit2.GIT_OBJECT_COMMIT, tagger, "Tag v1.0 message")
    output_epub = temp_git_repo_path / "output_tagged.epub"
    result = export_to_epub(str(temp_git_repo_path), "v1.0", ["file1.md"], str(output_epub))
    assert result["status"] == "success"
    mock_pypandoc_convert_text.assert_called_once()
    assert mock_pypandoc_convert_text.call_args.kwargs['source'] == "# Tagged Content"

def test_export_to_epub_branch_name_commit_ish(temp_git_repo_path, mock_pypandoc_path_found, mock_pypandoc_convert_text):
    repo = init_test_repo_corrected(temp_git_repo_path, {"main.md": "# Main"}, "Commit on main")
    repo.create_branch("feature/new-export", repo.head.peel(pygit2.Commit))
    repo.checkout(repo.branches["feature/new-export"])
    init_test_repo_corrected(temp_git_repo_path, {"feature.md": "# Feature"}, "Commit on feature")
    output_epub = temp_git_repo_path / "output_feature.epub"
    result = export_to_epub(str(temp_git_repo_path), "feature/new-export", ["feature.md"], str(output_epub))
    assert result["status"] == "success"
    mock_pypandoc_convert_text.assert_called_once()
    assert mock_pypandoc_convert_text.call_args.kwargs['source'] == "# Feature"

def test_export_to_epub_empty_file_in_list_success(temp_git_repo_path, mock_pypandoc_path_found, mock_pypandoc_convert_text):
    files_content = {"file1.md": "# C1", "empty.md": "", "file2.md": "# C2"}
    init_test_repo_corrected(temp_git_repo_path, files_content, "Add files with one empty")
    output_epub = temp_git_repo_path / "output_empty_included.epub"
    result = export_to_epub(str(temp_git_repo_path), "HEAD", ["file1.md", "empty.md", "file2.md"], str(output_epub))
    assert result["status"] == "success"
    expected_content = "# C1\n\n---\n\n\n\n---\n\n# C2"
    mock_pypandoc_convert_text.assert_called_once_with(
        source=expected_content, to='epub', format='md',
        outputfile=str(output_epub.resolve()), extra_args=['--standalone']
    )

def test_export_to_epub_all_files_empty_error(temp_git_repo_path, mock_pypandoc_path_found):
    init_test_repo_corrected(temp_git_repo_path, {"e1.md": "", "e2.md": ""}, "Add only empty files")
    output_epub = temp_git_repo_path / "output_all_empty.epub"
    with pytest.raises(GitWriteError, match="No content found to export: All specified files are empty or contain only whitespace."):
        export_to_epub(str(temp_git_repo_path), "HEAD", ["e1.md", "e2.md"], str(output_epub))

def test_export_to_epub_commit_ish_is_blob_oid_error(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"file1.md": "content"}, "Initial")
    blob_oid_str = str(repo.create_blob(b"some blob data"))
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(CommitNotFoundError, match=f"Commit-ish '{blob_oid_str}' resolved to an object of type 'blob'"):
        export_to_epub(str(temp_git_repo_path), blob_oid_str, ["file1.md"], str(output_epub))

def test_export_to_epub_commit_ish_is_tree_oid_error(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"dir/file1.md": "content"}, "Initial")
    tree_oid_str = str(repo.head.peel(pygit2.Commit).tree["dir"].id)
    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(CommitNotFoundError, match=f"Commit-ish '{tree_oid_str}' resolved to an object of type 'tree'"):
        export_to_epub(str(temp_git_repo_path), tree_oid_str, ["dir/file1.md"], str(output_epub))

def test_export_to_epub_lightweight_tag_to_blob_error(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"f.md": "c"}, "Initial")
    blob_oid = repo.create_blob(b"blob data")
    tag_name = "light_tag_to_blob"
    try:
        repo.references.create(f"refs/tags/{tag_name}", blob_oid.hex)
    except Exception as e:
        pytest.skip(f"Could not create lightweight tag to blob for test: {e}")

    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(CommitNotFoundError,
                         match=f"(Tag '{tag_name}' does not point to a valid commit|Commit-ish '{tag_name}' resolved to an object of type 'blob')"):
        export_to_epub(str(temp_git_repo_path), tag_name, ["f.md"], str(output_epub))

def test_export_to_epub_annotated_tag_to_blob_error(temp_git_repo_path, mock_pypandoc_path_found):
    repo = init_test_repo_corrected(temp_git_repo_path, {"f.md": "c"}, "Initial")
    blob_oid = repo.create_blob(b"blob data")
    tag_name = "ann_tag_to_blob"
    tagger = pygit2.Signature("Tagger", "tag@example.com")
    try:
        repo.create_tag(tag_name, blob_oid, pygit2.GIT_OBJECT_BLOB, tagger, "Tagging a blob")
    except Exception as e:
        pytest.skip(f"Could not create annotated tag to blob for test: {e}")

    output_epub = temp_git_repo_path / "output.epub"
    with pytest.raises(CommitNotFoundError, match=f"Tag '{tag_name}' does not point to a valid commit."):
        export_to_epub(str(temp_git_repo_path), tag_name, ["f.md"], str(output_epub))
