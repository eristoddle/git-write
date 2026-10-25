"""Reader annotations, stored as commits on a feedback branch.

An annotation is an empty-change commit (same tree as its parent) whose message is a subject line,
a blank line, and a YAML body. A status change is a new commit that points back at the original
through ``original_annotation_id``. Commits are written straight onto ``refs/heads/<branch>`` with
pygit2: HEAD, the index and the working tree are never touched. The format is specified in
``docs/ANNOTATION_FORMAT.md`` (D8, D11).
"""

import re
from typing import Any, Dict, List, Optional

import pygit2
import yaml

from .anchors import apply_anchor
from .exceptions import AnnotationError, RepositoryOperationError
from .models import Annotation, AnnotationStatus

_COMMIT_ID_RE = re.compile(r'[0-9a-f]{4,40}')

_REQUIRED_FIELDS = ["file_path", "highlighted_text", "start_line", "end_line", "comment", "author"]


def _validate_commit_id(commit_id: str) -> str:
    """Only a hex object ID may name a commit (see the argument-safety tests)."""
    if not isinstance(commit_id, str) or not _COMMIT_ID_RE.fullmatch(commit_id):
        raise AnnotationError(f"Invalid commit ID {commit_id!r}: expected 4 to 40 lowercase hex characters.")
    return commit_id


def _validate_branch_name(branch: str) -> str:
    """Reject empty names, names that start with '-', and names git would not accept as a branch."""
    if (not isinstance(branch, str) or not branch or branch.startswith('-')
            or not pygit2.reference_is_valid_name(f'refs/heads/{branch}')):
        raise AnnotationError(f"Invalid feedback branch name {branch!r}.")
    return branch


def _open_repo(repo_path: str) -> pygit2.Repository:
    try:
        return pygit2.Repository(repo_path)
    except pygit2.GitError as e:
        raise RepositoryOperationError(f"'{repo_path}' is not a valid Git repository.") from e


def _signature(repo: pygit2.Repository) -> pygit2.Signature:
    """The repo's configured identity, or a neutral one so annotating never fails on a fresh machine."""
    try:
        return repo.default_signature
    except (KeyError, pygit2.GitError):
        return pygit2.Signature("GitWrite", "gitwrite@example.com")


def _feedback_tip(repo: pygit2.Repository, branch: str) -> Optional[pygit2.Commit]:
    ref = repo.references.get(f'refs/heads/{branch}')
    return ref.peel(pygit2.Commit) if ref is not None else None


def _commit_on_feedback(repo: pygit2.Repository, branch: str, message: str) -> str:
    """Add an empty-change commit to the feedback branch, creating the branch from HEAD if needed."""
    ref_name = f'refs/heads/{branch}'
    tip = _feedback_tip(repo, branch)
    signature = _signature(repo)
    if tip is not None:
        oid = repo.create_commit(ref_name, signature, signature, message, tip.tree_id, [tip.id])
        return str(oid)

    if repo.head_is_unborn:
        raise RepositoryOperationError(
            f"Failed to create feedback branch '{branch}'. "
            "Ensure the repository is initialized and has at least one commit. HEAD has no commits yet."
        )
    base = repo.head.peel(pygit2.Commit)
    # libgit2 refuses to create a new ref through create_commit when the commit has a parent,
    # so write the commit unreferenced and then create the ref (which fails if it appeared meanwhile).
    oid = repo.create_commit(None, signature, signature, message, base.tree_id, [base.id])
    repo.references.create(ref_name, oid)
    return str(oid)


def _split_message(message: str) -> Optional[str]:
    """Return the YAML body of an annotation-shaped message (subject, blank line, body), else None."""
    parts = message.split('\n', 2)
    if len(parts) < 3 or parts[1].strip() != "":
        return None
    return parts[2]


def _annotation_data(annotation: Annotation) -> Dict[str, Any]:
    """The fields that are stored in the commit's YAML body (not the ids).

    The D15 anchor fields are written only when set, so annotations without them stay byte-identical
    to the original format.
    """
    data: Dict[str, Any] = {
        "file_path": annotation.file_path,
        "highlighted_text": annotation.highlighted_text,
        "start_line": annotation.start_line,
        "end_line": annotation.end_line,
        "comment": annotation.comment,
        "author": annotation.author,
        "status": annotation.status.value,
    }
    if annotation.prefix is not None:
        data["prefix"] = annotation.prefix
    if annotation.suffix is not None:
        data["suffix"] = annotation.suffix
    if annotation.offset is not None:
        data["offset"] = annotation.offset
    return data


def _optional_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _file_text_at_head(repo: pygit2.Repository, file_path: str) -> Optional[str]:
    """The text of ``file_path`` in the HEAD commit, or None if it is missing or not UTF-8 text."""
    if repo.head_is_unborn:
        return None
    try:
        entry = repo.head.peel(pygit2.Commit).tree[file_path]
        blob = repo.get(entry.id)
        return blob.data.decode("utf-8") if isinstance(blob, pygit2.Blob) else None
    except (KeyError, UnicodeDecodeError, pygit2.GitError):
        return None


def _dump_yaml(data: Dict[str, Any], what: str) -> str:
    try:
        return yaml.dump(data, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise AnnotationError(f"Failed to serialize {what} to YAML: {e}") from e


def _read_annotation_yaml(message: str) -> Optional[Dict[str, Any]]:
    """Parse and sanity-check an annotation commit message; None if it is not an annotation."""
    body = _split_message(message)
    if body is None:
        return None
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict) or not all(field in data for field in _REQUIRED_FIELDS):
        return None
    return data


def _build_annotation(data: Dict[str, Any], annotation_id: str, commit_id: str,
                      original_id: Optional[str], status: AnnotationStatus) -> Annotation:
    return Annotation(
        id=annotation_id,
        commit_id=commit_id,
        file_path=data["file_path"],
        highlighted_text=data["highlighted_text"],
        start_line=data["start_line"],
        end_line=data["end_line"],
        comment=data["comment"],
        author=data["author"],
        status=status,
        original_annotation_id=original_id,
        # Anchors are optional; a malformed value is ignored rather than dropping the annotation.
        prefix=_optional_str(data.get("prefix")),
        suffix=_optional_str(data.get("suffix")),
        offset=_optional_int(data.get("offset")),
    )


def create_annotation_commit(repo_path: str, feedback_branch: str, annotation_data: Annotation) -> str:
    """
    Creates a new commit on the feedback branch with the annotation data.

    The branch is created from HEAD if it does not exist. HEAD, the index and the working tree
    are not changed.

    Args:
        repo_path: The path to the Git repository.
        feedback_branch: The name of the branch to commit the annotation to.
        annotation_data: The annotation to record. Its ``id`` and ``commit_id`` are set on return.
            If it has no anchor (D15), one is computed from the file's text in HEAD when the
            highlighted text is found there.

    Returns:
        The SHA of the newly created annotation commit.

    Raises:
        RepositoryOperationError: If the repository is invalid or has no commit to branch from.
        AnnotationError: For issues specific to annotation processing.
    """
    repo = _open_repo(repo_path)
    _validate_branch_name(feedback_branch)

    # Anchor the highlight to the text it was made on (the HEAD version of the file), unless the
    # caller already supplied an anchor (for example from an unsaved editor buffer).
    if annotation_data.prefix is None and annotation_data.suffix is None and annotation_data.offset is None:
        file_text = _file_text_at_head(repo, annotation_data.file_path)
        if file_text is not None:
            apply_anchor(annotation_data, file_text)

    yaml_content = _dump_yaml(_annotation_data(annotation_data), "annotation data")
    subject = f"Annotation: {annotation_data.file_path} (Lines {annotation_data.start_line}-{annotation_data.end_line})"
    new_commit_sha = _commit_on_feedback(repo, feedback_branch, f"{subject}\n\n{yaml_content}")

    annotation_data.id = new_commit_sha
    annotation_data.commit_id = new_commit_sha
    return new_commit_sha


def list_annotations(repo_path: str, feedback_branch: str) -> List[Annotation]:
    """
    Lists the annotations on the feedback branch, each at its latest status.

    Commits that are not annotation-shaped are skipped. A missing branch means no annotations.
    Annotations come back oldest first; ``id`` is the creation commit and ``commit_id`` the commit
    that recorded the current status.

    Raises:
        RepositoryOperationError: If the repository is invalid.
        AnnotationError: If the branch name is invalid.
    """
    repo = _open_repo(repo_path)
    _validate_branch_name(feedback_branch)

    tip = _feedback_tip(repo, feedback_branch)
    if tip is None:
        return []

    threads: Dict[str, Annotation] = {}  # keyed by the creation commit of each annotation
    for commit in repo.walk(tip.id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE):
        data = _read_annotation_yaml(commit.message)
        if data is None:
            continue
        commit_sha = str(commit.id)
        try:
            status = AnnotationStatus(data.get("status"))
            original_id = data.get("original_annotation_id")
            if original_id:
                # A status change: it carries the full annotation again and replaces the earlier state.
                threads[original_id] = _build_annotation(data, original_id, commit_sha, original_id, status)
            else:
                threads[commit_sha] = _build_annotation(data, commit_sha, commit_sha, None, status)
        except (ValueError, TypeError):
            continue  # unknown status or a field of the wrong type: not an annotation we understand

    return list(threads.values())


def update_annotation_status(repo_path: str, feedback_branch: str, annotation_commit_id: str,
                             new_status: AnnotationStatus) -> str:
    """
    Records a new status for an annotation as a new commit that points back at the original.

    Args:
        repo_path: The path to the Git repository.
        feedback_branch: The name of the feedback branch.
        annotation_commit_id: The (possibly abbreviated, lowercase hex) SHA of the annotation's
            creation commit. A status commit's SHA is also accepted and resolved to its annotation.
        new_status: The new status for the annotation.

    Returns:
        The SHA of the new commit that records the status update.

    Raises:
        RepositoryOperationError: If the repository is invalid or the branch or commit is not found.
        AnnotationError: If the commit is not an annotation or an argument is invalid.
    """
    repo = _open_repo(repo_path)
    _validate_branch_name(feedback_branch)
    _validate_commit_id(annotation_commit_id)

    tip = _feedback_tip(repo, feedback_branch)
    if tip is None:
        raise RepositoryOperationError(f"Feedback branch '{feedback_branch}' not found.")

    try:
        original = repo.revparse_single(annotation_commit_id).peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError) as e:
        raise RepositoryOperationError(
            f"Original annotation commit '{annotation_commit_id}' not found on branch '{feedback_branch}': {e}"
        ) from e
    if original.id != tip.id and not repo.descendant_of(tip.id, original.id):
        raise RepositoryOperationError(
            f"Original annotation commit '{annotation_commit_id}' not found on branch '{feedback_branch}'."
        )

    body = _split_message(original.message)
    if body is None:
        raise AnnotationError(
            f"Commit {annotation_commit_id} is not in the expected annotation format (subject/body structure)."
        )
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as e:
        raise AnnotationError(f"Failed to parse YAML for original annotation '{annotation_commit_id}': {e}") from e
    if not isinstance(data, dict):
        raise AnnotationError(f"YAML body of commit {annotation_commit_id} is not a dictionary.")
    if not all(field in data for field in _REQUIRED_FIELDS):
        raise AnnotationError(f"Commit {annotation_commit_id} is missing required fields in its YAML body.")

    try:
        original_annotation = _build_annotation(
            data, str(original.id), str(original.id), None,
            AnnotationStatus(data.get("status", AnnotationStatus.NEW.value)),
        )
    except (ValueError, TypeError) as e:
        raise AnnotationError(f"Data format error for original annotation '{annotation_commit_id}': {e}") from e

    # Everything is carried over; only the status changes. The pointer is always the thread's
    # creation commit, even when a status commit was named.
    thread_id = data.get("original_annotation_id") or str(original.id)
    update_data = _annotation_data(original_annotation)
    update_data["status"] = new_status.value
    update_data["original_annotation_id"] = thread_id

    yaml_content = _dump_yaml(update_data, "status update data")
    subject = (f"Update status: {original_annotation.file_path} "
               f"(Annotation {thread_id[:7]}) to {new_status.value}")
    return _commit_on_feedback(repo, feedback_branch, f"{subject}\n\n{yaml_content}")
