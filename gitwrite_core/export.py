# This module will contain functions for exporting repository content to various formats.

import pathlib
import tempfile
from typing import Dict, List, Union

import pygit2
import pypandoc

from gitwrite_core.exceptions import (
    GitWriteError,
    RepositoryNotFoundError,
    CommitNotFoundError,
    FileNotFoundInCommitError,
    PandocError,
)


def export_to_epub(
    repo_path_str: str,
    commit_ish_str: str,
    file_list: List[str],
    output_epub_path_str: str,
) -> Dict[str, str]:
    """
    Exports specified markdown files from a Git repository at a given commit-ish
    to an EPUB file.

    Args:
        repo_path_str: Path to the Git repository.
        commit_ish_str: The commit hash, branch name, or tag to export from.
        file_list: A list of paths to markdown files (relative to repo root) to include in the EPUB.
        output_epub_path_str: The full path where the EPUB file will be saved.

    Returns:
        A dictionary with 'status': 'success' and 'message' on successful EPUB generation.

    Raises:
        RepositoryNotFoundError: If the repository path is invalid or not a Git repository.
        CommitNotFoundError: If the commit_ish cannot be resolved to a valid commit.
        FileNotFoundInCommitError: If a file in file_list is not found in the commit or is not a file.
        PandocError: If Pandoc is not found or if there's an error during EPUB conversion.
        GitWriteError: For other generic errors (e.g., empty file list, non-UTF-8 content, empty repo).
    """
    # Ensure pandoc is available first
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        raise PandocError(
            "Pandoc not found. Please ensure pandoc is installed and in your PATH."
        )

    repo_path = pathlib.Path(repo_path_str)
    if not repo_path.is_dir():
        raise RepositoryNotFoundError(f"Repository directory not found: {repo_path_str}")

    try:
        abs_repo_path = str(repo_path.resolve())
        repo = pygit2.Repository(abs_repo_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Not a valid Git repository: {abs_repo_path} - {e}")
    except Exception as e:
        raise RepositoryNotFoundError(f"Invalid repository path: {repo_path_str} - {e}")

    if repo.is_empty:
        raise GitWriteError(f"Repository at {repo_path_str} is empty and has no commits to export from.")

    commit: pygit2.Commit

    try:
        resolved_object = repo.revparse_single(commit_ish_str)
        if resolved_object is None:
            raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' could not be resolved.")

        if resolved_object.type == pygit2.GIT_OBJECT_TAG:
            target_object = repo.get(resolved_object.target)
            if target_object is None or not isinstance(target_object, pygit2.Commit):
                raise CommitNotFoundError(f"Tag '{commit_ish_str}' does not point to a valid commit.")
            commit = target_object
        elif resolved_object.type == pygit2.GIT_OBJECT_COMMIT:
            commit = resolved_object
        else:
            object_type_display_str = "unknown"
            if hasattr(resolved_object, 'type_str'):
                object_type_display_str = resolved_object.type_str
            elif hasattr(resolved_object, 'type'):
                type_map = {
                    pygit2.GIT_OBJECT_BLOB: "blob",
                    pygit2.GIT_OBJECT_TREE: "tree",
                }
                object_type_display_str = type_map.get(resolved_object.type, f"unknown_type_int_{resolved_object.type}")
            raise CommitNotFoundError(
                f"Commit-ish '{commit_ish_str}' resolved to an object of type '{object_type_display_str}' which is not a commit or a tag pointing to a commit."
            )
    except (KeyError, pygit2.GitError) as e:
        raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' not found or invalid in repository: {e}")
    except Exception as e:
        raise CommitNotFoundError(f"Error resolving commit-ish '{commit_ish_str}': {e}")

    tree = commit.tree
    markdown_content_parts = []

    if not file_list:
        raise GitWriteError("File list cannot be empty for EPUB export.")

    for file_path_str in file_list:
        try:
            entry = tree[file_path_str]
            if entry.type_str != 'blob':
                raise FileNotFoundInCommitError(
                    f"Entry '{file_path_str}' is not a file (blob) in commit '{commit.short_id}'. It is a '{entry.type_str}'."
                )
            blob = repo[entry.id]
            content_bytes = blob.data
            try:
                markdown_content_parts.append(content_bytes.decode('utf-8'))
            except UnicodeDecodeError:
                raise GitWriteError(
                    f"File '{file_path_str}' in commit '{commit.short_id}' is not UTF-8 encoded, which is required for EPUB conversion."
                )
        except KeyError:
            raise FileNotFoundInCommitError(
                f"File '{file_path_str}' not found in commit '{commit.short_id}' (tree ID: {tree.id})."
            )
        except pygit2.GitError as e:
            raise GitWriteError(f"Error accessing file '{file_path_str}' in commit '{commit.short_id}': {e}")

    if not markdown_content_parts:
        raise GitWriteError("No content found: All specified files were missing or could not be read from the commit.")

    meaningful_content_exists = any(part.strip() for part in markdown_content_parts)
    if not meaningful_content_exists:
        raise GitWriteError("No content found to export: All specified files are empty or contain only whitespace.")

    full_markdown_content = "\n\n---\n\n".join(markdown_content_parts)

    output_path = pathlib.Path(output_epub_path_str)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise GitWriteError(f"Could not create output directory '{output_path.parent}': {e}")

    try:
        pypandoc.convert_text(
            source=full_markdown_content,
            to='epub',
            format='md',
            outputfile=str(output_path.resolve()),
            extra_args=['--standalone']
        )
        return {
            "status": "success",
            "message": f"EPUB successfully generated at '{output_epub_path_str}'.",
        }
    except RuntimeError as e:
        if "pandoc document conversion failed" in str(e) and "No such file or directory" in str(e):
            raise PandocError(f"Pandoc execution failed. It might indicate Pandoc is not installed correctly or missing dependencies: {e}")
        raise PandocError(f"Pandoc conversion failed: {e}")
    except Exception as e:
        raise PandocError(f"An unexpected error occurred during EPUB conversion: {e}")

# End of function.


def export_to_pdf(
    repo_path_str: str,
    commit_ish_str: str,
    file_list: List[str],
    output_pdf_path_str: str,
    **pandoc_options: Dict[str, Union[str, List[str]]],
) -> Dict[str, str]:
    """
    Exports specified markdown files from a Git repository at a given commit-ish
    to a PDF file.

    Args:
        repo_path_str: Path to the Git repository.
        commit_ish_str: The commit hash, branch name, or tag to export from.
        file_list: A list of paths to markdown files (relative to repo root) to include in the PDF.
        output_pdf_path_str: The full path where the PDF file will be saved.
        **pandoc_options: Additional pandoc options for PDF generation.

    Returns:
        A dictionary with 'status': 'success' and 'message' on successful PDF generation.

    Raises:
        RepositoryNotFoundError: If the repository path is invalid or not a Git repository.
        CommitNotFoundError: If the commit_ish cannot be resolved to a valid commit.
        FileNotFoundInCommitError: If a file in file_list is not found in the commit or is not a file.
        PandocError: If Pandoc is not found or if there's an error during PDF conversion.
        GitWriteError: For other generic errors (e.g., empty file list, non-UTF-8 content, empty repo).
    """
    # Ensure pandoc is available first
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        raise PandocError(
            "Pandoc not found. Please ensure pandoc is installed and in your PATH."
        )

    repo_path = pathlib.Path(repo_path_str)
    if not repo_path.is_dir():
        raise RepositoryNotFoundError(f"Repository directory not found: {repo_path_str}")

    try:
        abs_repo_path = str(repo_path.resolve())
        repo = pygit2.Repository(abs_repo_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Not a valid Git repository: {abs_repo_path} - {e}")
    except Exception as e:
        raise RepositoryNotFoundError(f"Invalid repository path: {repo_path_str} - {e}")

    if repo.is_empty:
        raise GitWriteError(f"Repository at {repo_path_str} is empty and has no commits to export from.")

    commit: pygit2.Commit

    try:
        resolved_object = repo.revparse_single(commit_ish_str)
        if resolved_object is None:
            raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' could not be resolved.")

        if resolved_object.type == pygit2.GIT_OBJECT_TAG:
            target_object = repo.get(resolved_object.target)
            if target_object is None or not isinstance(target_object, pygit2.Commit):
                raise CommitNotFoundError(f"Tag '{commit_ish_str}' does not point to a valid commit.")
            commit = target_object
        elif resolved_object.type == pygit2.GIT_OBJECT_COMMIT:
            commit = resolved_object
        else:
            object_type_display_str = "unknown"
            if hasattr(resolved_object, 'type_str'):
                object_type_display_str = resolved_object.type_str
            elif hasattr(resolved_object, 'type'):
                type_map = {
                    pygit2.GIT_OBJECT_BLOB: "blob",
                    pygit2.GIT_OBJECT_TREE: "tree",
                }
                object_type_display_str = type_map.get(resolved_object.type, f"unknown_type_int_{resolved_object.type}")
            raise CommitNotFoundError(
                f"Commit-ish '{commit_ish_str}' resolved to an object of type '{object_type_display_str}' which is not a commit or a tag pointing to a commit."
            )
    except (KeyError, pygit2.GitError) as e:
        raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' not found or invalid in repository: {e}")
    except Exception as e:
        raise CommitNotFoundError(f"Error resolving commit-ish '{commit_ish_str}': {e}")

    tree = commit.tree
    markdown_content_parts = []

    if not file_list:
        raise GitWriteError("File list cannot be empty for PDF export.")

    for file_path_str in file_list:
        try:
            entry = tree[file_path_str]
            if entry.type_str != 'blob':
                raise FileNotFoundInCommitError(
                    f"Entry '{file_path_str}' is not a file (blob) in commit '{commit.short_id}'. It is a '{entry.type_str}'."
                )
            blob = repo[entry.id]
            content_bytes = blob.data
            try:
                markdown_content_parts.append(content_bytes.decode('utf-8'))
            except UnicodeDecodeError:
                raise GitWriteError(
                    f"File '{file_path_str}' in commit '{commit.short_id}' is not UTF-8 encoded, which is required for PDF conversion."
                )
        except KeyError:
            raise FileNotFoundInCommitError(
                f"File '{file_path_str}' not found in commit '{commit.short_id}' (tree ID: {tree.id})."
            )
        except pygit2.GitError as e:
            raise GitWriteError(f"Error accessing file '{file_path_str}' in commit '{commit.short_id}': {e}")

    if not markdown_content_parts:
        raise GitWriteError("No content found: All specified files were missing or could not be read from the commit.")

    meaningful_content_exists = any(part.strip() for part in markdown_content_parts)
    if not meaningful_content_exists:
        raise GitWriteError("No content found to export: All specified files are empty or contain only whitespace.")

    full_markdown_content = "\n\n---\n\n".join(markdown_content_parts)

    output_path = pathlib.Path(output_pdf_path_str)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise GitWriteError(f"Could not create output directory '{output_path.parent}': {e}")

    # Set up default PDF options
    default_extra_args = ['--standalone', '--pdf-engine=pdflatex']
    
    # Allow customization via pandoc_options
    extra_args = pandoc_options.get('extra_args', default_extra_args)
    if isinstance(extra_args, str):
        extra_args = [extra_args]
    
    try:
        pypandoc.convert_text(
            source=full_markdown_content,
            to='pdf',
            format='md',
            outputfile=str(output_path.resolve()),
            extra_args=extra_args
        )
        return {
            "status": "success",
            "message": f"PDF successfully generated at '{output_pdf_path_str}'.",
        }
    except RuntimeError as e:
        if "pandoc document conversion failed" in str(e):
            if "pdflatex not found" in str(e) or "No such file or directory" in str(e):
                raise PandocError(
                    f"PDF generation failed. Ensure that Pandoc and a LaTeX engine (like pdflatex) are installed: {e}"
                )
            raise PandocError(f"Pandoc PDF conversion failed: {e}")
        raise PandocError(f"Pandoc conversion failed: {e}")
    except Exception as e:
        raise PandocError(f"An unexpected error occurred during PDF conversion: {e}")


def export_to_docx(
    repo_path_str: str,
    commit_ish_str: str,
    file_list: List[str],
    output_docx_path_str: str,
    **pandoc_options: Dict[str, Union[str, List[str]]],
) -> Dict[str, str]:
    """
    Exports specified markdown files from a Git repository at a given commit-ish
    to a DOCX file.

    Args:
        repo_path_str: Path to the Git repository.
        commit_ish_str: The commit hash, branch name, or tag to export from.
        file_list: A list of paths to markdown files (relative to repo root) to include in the DOCX.
        output_docx_path_str: The full path where the DOCX file will be saved.
        **pandoc_options: Additional pandoc options for DOCX generation.

    Returns:
        A dictionary with 'status': 'success' and 'message' on successful DOCX generation.

    Raises:
        RepositoryNotFoundError: If the repository path is invalid or not a Git repository.
        CommitNotFoundError: If the commit_ish cannot be resolved to a valid commit.
        FileNotFoundInCommitError: If a file in file_list is not found in the commit or is not a file.
        PandocError: If Pandoc is not found or if there's an error during DOCX conversion.
        GitWriteError: For other generic errors (e.g., empty file list, non-UTF-8 content, empty repo).
    """
    # Ensure pandoc is available first
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        raise PandocError(
            "Pandoc not found. Please ensure pandoc is installed and in your PATH."
        )

    repo_path = pathlib.Path(repo_path_str)
    if not repo_path.is_dir():
        raise RepositoryNotFoundError(f"Repository directory not found: {repo_path_str}")

    try:
        abs_repo_path = str(repo_path.resolve())
        repo = pygit2.Repository(abs_repo_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Not a valid Git repository: {abs_repo_path} - {e}")
    except Exception as e:
        raise RepositoryNotFoundError(f"Invalid repository path: {repo_path_str} - {e}")

    if repo.is_empty:
        raise GitWriteError(f"Repository at {repo_path_str} is empty and has no commits to export from.")

    commit: pygit2.Commit

    try:
        resolved_object = repo.revparse_single(commit_ish_str)
        if resolved_object is None:
            raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' could not be resolved.")

        if resolved_object.type == pygit2.GIT_OBJECT_TAG:
            target_object = repo.get(resolved_object.target)
            if target_object is None or not isinstance(target_object, pygit2.Commit):
                raise CommitNotFoundError(f"Tag '{commit_ish_str}' does not point to a valid commit.")
            commit = target_object
        elif resolved_object.type == pygit2.GIT_OBJECT_COMMIT:
            commit = resolved_object
        else:
            object_type_display_str = "unknown"
            if hasattr(resolved_object, 'type_str'):
                object_type_display_str = resolved_object.type_str
            elif hasattr(resolved_object, 'type'):
                type_map = {
                    pygit2.GIT_OBJECT_BLOB: "blob",
                    pygit2.GIT_OBJECT_TREE: "tree",
                }
                object_type_display_str = type_map.get(resolved_object.type, f"unknown_type_int_{resolved_object.type}")
            raise CommitNotFoundError(
                f"Commit-ish '{commit_ish_str}' resolved to an object of type '{object_type_display_str}' which is not a commit or a tag pointing to a commit."
            )
    except (KeyError, pygit2.GitError) as e:
        raise CommitNotFoundError(f"Commit-ish '{commit_ish_str}' not found or invalid in repository: {e}")
    except Exception as e:
        raise CommitNotFoundError(f"Error resolving commit-ish '{commit_ish_str}': {e}")

    tree = commit.tree
    markdown_content_parts = []

    if not file_list:
        raise GitWriteError("File list cannot be empty for DOCX export.")

    for file_path_str in file_list:
        try:
            entry = tree[file_path_str]
            if entry.type_str != 'blob':
                raise FileNotFoundInCommitError(
                    f"Entry '{file_path_str}' is not a file (blob) in commit '{commit.short_id}'. It is a '{entry.type_str}'."
                )
            blob = repo[entry.id]
            content_bytes = blob.data
            try:
                markdown_content_parts.append(content_bytes.decode('utf-8'))
            except UnicodeDecodeError:
                raise GitWriteError(
                    f"File '{file_path_str}' in commit '{commit.short_id}' is not UTF-8 encoded, which is required for DOCX conversion."
                )
        except KeyError:
            raise FileNotFoundInCommitError(
                f"File '{file_path_str}' not found in commit '{commit.short_id}' (tree ID: {tree.id})."
            )
        except pygit2.GitError as e:
            raise GitWriteError(f"Error accessing file '{file_path_str}' in commit '{commit.short_id}': {e}")

    if not markdown_content_parts:
        raise GitWriteError("No content found: All specified files were missing or could not be read from the commit.")

    meaningful_content_exists = any(part.strip() for part in markdown_content_parts)
    if not meaningful_content_exists:
        raise GitWriteError("No content found to export: All specified files are empty or contain only whitespace.")

    full_markdown_content = "\n\n---\n\n".join(markdown_content_parts)

    output_path = pathlib.Path(output_docx_path_str)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise GitWriteError(f"Could not create output directory '{output_path.parent}': {e}")

    # Set up default DOCX options
    default_extra_args = ['--standalone']
    
    # Allow customization via pandoc_options
    extra_args = pandoc_options.get('extra_args', default_extra_args)
    if isinstance(extra_args, str):
        extra_args = [extra_args]
    
    try:
        pypandoc.convert_text(
            source=full_markdown_content,
            to='docx',
            format='md',
            outputfile=str(output_path.resolve()),
            extra_args=extra_args
        )
        return {
            "status": "success",
            "message": f"DOCX successfully generated at '{output_docx_path_str}'.",
        }
    except RuntimeError as e:
        if "pandoc document conversion failed" in str(e) and "No such file or directory" in str(e):
            raise PandocError(f"Pandoc execution failed. It might indicate Pandoc is not installed correctly or missing dependencies: {e}")
        raise PandocError(f"Pandoc DOCX conversion failed: {e}")
    except Exception as e:
        raise PandocError(f"An unexpected error occurred during DOCX conversion: {e}")
