import pygit2
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, NotEnoughHistoryError

def get_commit_history(repo_path_str: str, count: Optional[int] = None) -> List[Dict]:
    """
    Retrieves the commit history for a Git repository.

    Args:
        repo_path_str: Path to the repository.
        count: Optional number of commits to return.

    Returns:
        A list of dictionaries, where each dictionary contains details of a commit.

    Raises:
        RepositoryNotFoundError: If the repository is not found at the given path.
    """
    try:
        # Discover the repository path
        repo_path = pygit2.discover_repository(repo_path_str)
        if repo_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")

        repo = pygit2.Repository(repo_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        return []

    if repo.is_empty or repo.head_is_unborn:
        return []

    history = []
    commits_processed = 0

    walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME)

    for commit_obj in walker:
        if count is not None and commits_processed >= count:
            break

        author_tz = timezone(timedelta(minutes=commit_obj.author.offset))
        committer_tz = timezone(timedelta(minutes=commit_obj.committer.offset))

        history.append({
            "short_hash": str(commit_obj.id)[:7],
            "author_name": commit_obj.author.name,
            "author_email": commit_obj.author.email,
            "date": datetime.fromtimestamp(commit_obj.author.time, tz=author_tz).strftime('%Y-%m-%d %H:%M:%S %z'),
            "committer_name": commit_obj.committer.name,
            "committer_email": commit_obj.committer.email,
            "committer_date": datetime.fromtimestamp(commit_obj.committer.time, tz=committer_tz).strftime('%Y-%m-%d %H:%M:%S %z'),
            "message": commit_obj.message.strip(),
            "message_short": commit_obj.message.splitlines()[0].strip(),
            "oid": str(commit_obj.id),
        })
        commits_processed += 1

    return history

def get_diff(repo_path_str: str, ref1_str: Optional[str] = None, ref2_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Compares two references in a Git repository and returns the diff.

    Args:
        repo_path_str: Path to the repository.
        ref1_str: The first reference (e.g., commit hash, branch, tag). Defaults to HEAD~1.
        ref2_str: The second reference. Defaults to HEAD.

    Returns:
        A dictionary containing resolved OIDs, display names, and the patch text.
        {
            "ref1_oid": str,
            "ref2_oid": str,
            "ref1_display_name": str,
            "ref2_display_name": str,
            "patch_text": str
        }

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        CommitNotFoundError: If a specified reference cannot be resolved to a commit.
        NotEnoughHistoryError: If the comparison cannot be made due to lack of history (e.g., initial commit).
        ValueError: If an invalid combination of references is provided.
    """
    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    commit1_obj: Optional[pygit2.Commit] = None
    commit2_obj: Optional[pygit2.Commit] = None

    ref1_resolved_name = ref1_str
    ref2_resolved_name = ref2_str

    if ref1_str is None and ref2_str is None: # Default: HEAD~1 vs HEAD
        if repo.is_empty or repo.head_is_unborn:
            raise NotEnoughHistoryError("Repository is empty or HEAD is unborn.")
        try:
            commit2_obj = repo.head.peel(pygit2.Commit)
        except (pygit2.GitError, KeyError) as e:
            raise CommitNotFoundError(f"Could not resolve HEAD: {e}")

        if not commit2_obj.parents:
            raise NotEnoughHistoryError("HEAD is the initial commit and has no parent to compare with.")
        commit1_obj = commit2_obj.parents[0]

        ref1_resolved_name = f"{str(commit1_obj.id)[:7]} (HEAD~1)"
        ref2_resolved_name = f"{str(commit2_obj.id)[:7]} (HEAD)"

    elif ref1_str is not None and ref2_str is None: # Compare ref1_str vs HEAD
        if repo.is_empty or repo.head_is_unborn:
            raise NotEnoughHistoryError("Repository is empty or HEAD is unborn, cannot compare with HEAD.")
        try:
            commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
        except (pygit2.GitError, KeyError, TypeError) as e: # TypeError if peel is on wrong type
            raise CommitNotFoundError(f"Reference '{ref1_str}' not found or not a commit: {e}")
        try:
            commit2_obj = repo.head.peel(pygit2.Commit)
        except (pygit2.GitError, KeyError) as e:
            raise CommitNotFoundError(f"Could not resolve HEAD: {e}")

        # ref1_resolved_name is already ref1_str
        ref2_resolved_name = f"{str(commit2_obj.id)[:7]} (HEAD)"


    elif ref1_str is not None and ref2_str is not None: # Compare ref1_str vs ref2_str
        try:
            commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
        except (pygit2.GitError, KeyError, TypeError) as e:
            raise CommitNotFoundError(f"Reference '{ref1_str}' not found or not a commit: {e}")
        try:
            commit2_obj = repo.revparse_single(ref2_str).peel(pygit2.Commit)
        except (pygit2.GitError, KeyError, TypeError) as e:
            raise CommitNotFoundError(f"Reference '{ref2_str}' not found or not a commit: {e}")

        # ref1_resolved_name and ref2_resolved_name are already the input strings

    else: # ref1_str is None and ref2_str is not None -- invalid combination
        raise ValueError("Invalid reference combination for diff. Cannot specify ref2 without ref1 unless both are None.")

    if not commit1_obj or not commit2_obj:
        # This should ideally be caught by earlier checks, but as a safeguard:
        raise CommitNotFoundError("Could not resolve one or both references to commits.")

    tree1 = commit1_obj.tree
    tree2 = commit2_obj.tree

    diff_obj = repo.diff(tree1, tree2, context_lines=3, interhunk_lines=1)

    return {
        "ref1_oid": str(commit1_obj.id),
        "ref2_oid": str(commit2_obj.id),
        "ref1_display_name": ref1_resolved_name if ref1_resolved_name else str(commit1_obj.id), # Fallback if somehow None
        "ref2_display_name": ref2_resolved_name if ref2_resolved_name else str(commit2_obj.id), # Fallback if somehow None
        "patch_text": diff_obj.patch if diff_obj else ""
    }
