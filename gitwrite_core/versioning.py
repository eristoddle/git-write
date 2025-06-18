import pygit2
# import pygit2.ops # No longer attempting to use pygit2.ops
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, NotEnoughHistoryError, MergeConflictError, GitWriteError

def _get_commit_summary(commit: pygit2.Commit) -> str:
    """Helper function to get the first line of a commit message."""
    return commit.message.splitlines()[0]

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

def revert_commit(repo_path_str: str, commit_ish_to_revert: str) -> dict:
    """
    Reverts a specified commit.

    Args:
        repo_path_str: Path to the repository.
        commit_ish_to_revert: The commit reference (hash, branch, tag) to revert.

    Returns:
        A dictionary indicating success and the new commit OID if the revert was clean.
        {'status': 'success', 'new_commit_oid': str(new_commit_oid), 'message': 'Commit reverted successfully.'}

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        CommitNotFoundError: If the commit to revert is not found.
        MergeConflictError: If the revert results in conflicts.
        GitWriteError: For other Git-related errors.
    """
    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    try:
        commit_to_revert = repo.revparse_single(commit_ish_to_revert).peel(pygit2.Commit)
    except (pygit2.GitError, KeyError, TypeError) as e: # TypeError if peel on wrong type
        raise CommitNotFoundError(f"Commit '{commit_ish_to_revert}' not found or not a commit: {e}")

    try:
        # For reverting regular commits, mainline_index is typically 1.
        # pygit2's revert defaults to mainline 1 if not specified (mainline_opts=0).
        # which is usually correct for reverting a merge commit by
        # Manual revert logic using three-way merge.
        # The goal is to apply the inverse of 'commit_to_revert' onto the current HEAD.
        # This is equivalent to merging the parent of 'commit_to_revert' into HEAD,
        # using 'commit_to_revert' as the common ancestor.

        if not commit_to_revert.parents:
            raise GitWriteError(f"Cannot revert commit {commit_to_revert.short_id} as it has no parents (initial commit).")

        # For non-merge commits, there's one parent.
        # For merge commits, mainline_opts=0 (default for repo.revert) usually means reverting
        # the changes brought by the second parent. So, P1 is current HEAD's line, P2 is merged line.
        # Reverting a merge commit M(P1, P2) with mainline 1 (default) means applying changes from P1,
        # effectively undoing what P2 brought. So, "their_tree" should be P1's tree.
        # P1 is commit_to_revert.parents[0].
        parent_to_revert_to = commit_to_revert.parents[0] # This is "mainline 1"

        ancestor_tree = commit_to_revert.tree
        current_head_commit = repo.head.peel(pygit2.Commit)
        our_tree = current_head_commit.tree
        their_tree = parent_to_revert_to.tree

        # Store original HEAD in case of conflict and reset
        original_head_oid = repo.head.target

        # Perform the merge into a new index
        # This index will represent the state of the working directory after the revert.
        # The merge_trees function simulates merging 'their_tree' (parent of reverted commit)
        # onto 'our_tree' (current HEAD), using 'ancestor_tree' (the commit being reverted)
        # as the common base.
        index = repo.merge_trees(ancestor_tree, our_tree, their_tree)

        has_actual_conflicts = False # Initialize before checking
        if index.conflicts is not None:
            try:
                next(iter(index.conflicts)) # Try to get the first conflict entry
                has_actual_conflicts = True
            except StopIteration:
                has_actual_conflicts = False # Iterator was empty, so no conflicts

        if has_actual_conflicts:
            # Conflicts detected by merge_trees. Abort the revert.
            repo.index.clear() # Clear any staged changes from the conflicted merge index if it affected repo.index
            # Reset working directory and index to original HEAD
            repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
            raise MergeConflictError("Revert resulted in conflicts. The revert has been aborted and the working directory is clean.")

        # No conflicts, write this new index to the actual repository's index
        repo.index.read_tree(index.write_tree()) # Load the resolved tree into the main index
        repo.index.write()

        # Checkout the index to update the working directory
        repo.checkout_index(strategy=pygit2.GIT_CHECKOUT_FORCE)

    except MergeConflictError: # Specifically let MergeConflictError pass through
        raise
    except GitWriteError as e: # Catch our own specific errors first
        if original_head_oid and str(original_head_oid) != str(repo.head.target): # Avoid reset if HEAD didn't change or error is from reset itself
             repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
        raise # Re-raise GitWriteError
    except pygit2.GitError as e:
        # In case of other GitErrors during the manual revert process
        if original_head_oid and str(original_head_oid) != str(repo.head.target):
             repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
        raise GitWriteError(f"Error during revert operation: {e}. Working directory reset.")
    except Exception as e: # Catch any other unexpected error
        if original_head_oid and str(original_head_oid) != str(repo.head.target):
            repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
        raise GitWriteError(f"An unexpected error occurred during revert: {e}. Working directory reset.")


    # If we reach here, the index and working directory should reflect the reverted state.
    # Proceed to commit.

    try:
        user_signature = repo.default_signature
        if not user_signature:
            # Fallback if default signature is not set (e.g., in some CI environments)
            # pygit2 requires author and committer to be set.
            # Using a placeholder. Ideally, this should be configured in the git environment.
            user_signature = pygit2.Signature("GitWrite", "gitwrite@example.com")

        original_commit_summary = _get_commit_summary(commit_to_revert)
        revert_commit_message = f"Revert \"{original_commit_summary}\"\n\nThis reverts commit {commit_to_revert.id}."

        # Determine parents for the new commit
        parents = [repo.head.target] if not repo.head_is_unborn else []

        new_commit_oid = repo.index.write_tree()
        new_commit_oid = repo.create_commit(
            "HEAD",  # Update HEAD to point to the new commit
            user_signature,
            user_signature,
            revert_commit_message,
            new_commit_oid, # Tree OID
            parents
        )
        repo.state_cleanup() # Clean up repository state after commit

        return {
            'status': 'success',
            'new_commit_oid': str(new_commit_oid),
            'message': 'Commit reverted successfully.'
        }
    except pygit2.GitError as e:
        # If commit fails after a successful revert, try to clean up.
        # This situation is less common but good to handle.
        repo.reset(repo.head.target, pygit2.GIT_RESET_HARD) # Reset to pre-revert state if possible
        raise GitWriteError(f"Failed to create revert commit after a clean revert: {e}. Working directory reset.")
    except Exception as e: # Catch any other unexpected error during commit
        repo.reset(repo.head.target, pygit2.GIT_RESET_HARD)
        raise GitWriteError(f"An unexpected error occurred while creating the revert commit: {e}. Working directory reset.")
