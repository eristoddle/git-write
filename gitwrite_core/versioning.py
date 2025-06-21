import pygit2
# import pygit2.ops # No longer attempting to use pygit2.ops
from pathlib import Path
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

    # Use GIT_SORT_TOPOLOGICAL in combination with GIT_SORT_REVERSE for oldest-first order
    sort_mode = pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE
    walker = repo.walk(repo.head.target, sort_mode)

    history_data = []
    for commit_obj in walker:
        author_tz = timezone(timedelta(minutes=commit_obj.author.offset))
        committer_tz = timezone(timedelta(minutes=commit_obj.committer.offset))
        history_data.append({
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

    # history_data is now oldest-first
    if count is not None:
        # Return the first 'count' elements, which are the oldest 'count' commits
        return history_data[:count]
    else:
        # Return all commits, oldest-first
        return history_data

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

    original_head_oid = None # Initialize before try block
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


def get_conflicting_files(conflicts_iterator):
    """Helper function to extract path names from conflicts iterator."""
    conflicting_paths = []
    if conflicts_iterator:
        for conflict_entry in conflicts_iterator:
            # Each conflict_entry can have ancestor, our, their.
            # We need to pick one path that represents the conflict.
            # The iterator yields (ancestor_meta, our_meta, their_meta) tuples.
            ancestor_meta, our_meta, their_meta = conflict_entry
            if our_meta:
                conflicting_paths.append(our_meta.path)
            elif their_meta:
                conflicting_paths.append(their_meta.path)
            elif ancestor_meta: # Fallback if both 'our' and 'their' are not present
                conflicting_paths.append(ancestor_meta.path)
    return conflicting_paths


def save_changes(repo_path_str: str, message: str, include_paths: Optional[List[str]] = None) -> Dict:
    """
    Saves changes in the repository by creating a new commit.

    Args:
        repo_path_str: Path to the repository.
        message: The commit message.
        include_paths: Optional list of file/directory paths to stage.
                       If None, all changes in the working directory are staged.

    Returns:
        A dictionary with commit details on success.
        Example: {'status': 'success', 'oid': '...', 'short_oid': '...', ...}

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        RepositoryEmptyError: If trying to save in an empty repository without an initial commit
                              (unless this is the initial commit itself).
        NoChangesToSaveError: If no changes are detected to be staged (either overall or in
                              specified `include_paths`).
        MergeConflictError: If MERGE_HEAD exists and there are unresolved conflicts in the index.
        RevertConflictError: If REVERT_HEAD exists and there are unresolved conflicts in the index.
        GitWriteError: For other general Git-related errors during the save process.
    """
    import time # Import time for fallback signature
    from .exceptions import NoChangesToSaveError, RevertConflictError, RepositoryEmptyError # Ensure these are available

    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        # Catching generic GitError during discovery/init and re-raising
        raise RepositoryNotFoundError(f"Error discovering or initializing repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        raise GitWriteError("Cannot save changes in a bare repository.")

    is_merge_commit = False
    is_revert_commit = False
    parents = []
    final_message = message # Default to user-provided message

    try:
        author = repo.default_signature
        committer = repo.default_signature
    except pygit2.GitError: # Fallback if .gitconfig has no user.name/user.email
        current_time = int(time.time())
        # Offset is 0 for UTC, but pygit2.Signature expects it in minutes.
        # Using local time offset might be better if available, but 0 (UTC) is a safe default.
        offset = 0
        try:
            # Try to get local timezone offset
            local_tz = datetime.now(timezone.utc).astimezone().tzinfo
            if local_tz:
                offset_delta = local_tz.utcoffset(datetime.now())
                if offset_delta:
                    offset = int(offset_delta.total_seconds() / 60)
        except Exception: # pragma: no cover
            pass # Stick to UTC if local timezone fails
        author = pygit2.Signature("GitWrite User", "user@example.com", current_time, offset)
        committer = pygit2.Signature("GitWrite User", "user@example.com", current_time, offset)


    # 1. Handle special states: Merge/Revert
    # These states mean an operation (merge or revert) was started and needs finalizing.
    # In these cases, `include_paths` is usually ignored, and all changes related to
    # resolving the merge/revert are committed.

    try:
        # Check for MERGE_HEAD
        merge_head_ref = repo.lookup_reference("MERGE_HEAD")
        if merge_head_ref and merge_head_ref.target:
            if include_paths:
                raise GitWriteError("Selective staging with --include is not allowed during an active merge operation.")

            merge_head_oid = merge_head_ref.target
            repo.index.read() # Ensure index is up-to-date

            # Check for conflicts *before* attempting to stage all
            if repo.index.conflicts:
                conflicting_files = get_conflicting_files(repo.index.conflicts)
                raise MergeConflictError(
                    "Unresolved conflicts detected during merge. Please resolve them before saving.",
                    conflicting_files=conflicting_files
                )

            # If no conflicts, then proceed to stage and write
            repo.index.add_all() # Stage all changes to finalize the merge
            repo.index.write()   # Persist staged changes to the index file
            # Re-check for conflicts just in case add_all introduced any (should not happen if WD is clean)
            # This second check might be redundant if the first one is robust.
            # However, keeping it for safety or removing it if deemed unnecessary.
            # For now, let's assume the first check is the critical one for this bug.

            if repo.head_is_unborn: # Should not happen during a merge
                raise GitWriteError("Repository HEAD is unborn during a merge operation, which is unexpected.")
            parents = [repo.head.target, merge_head_oid]
            is_merge_commit = True
            # `final_message` will be the user-provided message.
            # Standard merge commits often have messages like "Merge branch 'X' into 'Y'".
            # Users of this function are expected to provide such a message if desired.

    except KeyError: # MERGE_HEAD not found, so not a merge (lookup_reference raises built-in KeyError)
        pass
    except pygit2.GitError as e: # Other git errors during merge head lookup
        raise GitWriteError(f"Error checking for MERGE_HEAD: {e}")


    if not is_merge_commit: # Only check for REVERT_HEAD if not already handling a merge
        try:
            revert_head_ref = repo.lookup_reference("REVERT_HEAD")
            if revert_head_ref and revert_head_ref.target:
                if include_paths:
                    raise GitWriteError("Selective staging with --include is not allowed during an active revert operation.")

                revert_head_oid = revert_head_ref.target
                repo.index.read() # Ensure index is up-to-date
                repo.index.add_all() # Stage all changes to finalize the revert
                repo.index.write()   # Persist staged changes

                if repo.index.conflicts:
                    conflicting_files = get_conflicting_files(repo.index.conflicts)
                    raise RevertConflictError(
                        "Unresolved conflicts detected during revert. Please resolve them before saving.",
                        conflicting_files=conflicting_files
                    )

                if repo.head_is_unborn: # Should not happen during a revert
                     raise GitWriteError("Repository HEAD is unborn during a revert operation, which is unexpected.")
                parents = [repo.head.target] # A revert commit typically has one parent (current HEAD)

                # Construct standard revert message format
                try:
                    reverted_commit = repo.get(revert_head_oid)
                    if reverted_commit and reverted_commit.message:
                        first_line_of_reverted_msg = reverted_commit.message.splitlines()[0]
                        final_message = f"Revert \"{first_line_of_reverted_msg}\"\n\nThis reverts commit {revert_head_oid}.\n\n{message}"
                    else: # pragma: no cover
                        final_message = f"Revert commit {revert_head_oid}.\n\n{message}" # Fallback if reverted commit message is weird
                except Exception: # pragma: no cover
                     final_message = f"Revert commit {revert_head_oid}.\n\n{message}" # General fallback

                is_revert_commit = True

        except KeyError: # REVERT_HEAD not found (lookup_reference raises built-in KeyError)
            pass # Not a revert
        except pygit2.GitError as e: # Other git errors
            raise GitWriteError(f"Error checking for REVERT_HEAD: {e}")

    # 2. Handle Normal Save (No Merge/Revert in Progress)
    if not is_merge_commit and not is_revert_commit:
        repo.index.read() # Load current index state

        if repo.head_is_unborn: # This is going to be the initial commit
            if not include_paths: # Stage all if no specific paths given
                repo.index.add_all()
            else: # Stage only specified paths
                for path_str in include_paths:
                    if not path_str.strip():
                        continue # Skip empty/whitespace-only paths
                    path_obj = Path(repo.workdir) / path_str
                    if not path_obj.exists():
                        print(f"Warning: Path '{path_str}' (in initial commit) does not exist and was not added.")
                        continue
                    if path_obj.is_dir():
                        # Add all files under the directory
                        # Convert to relative path for add_all's pathspec
                        relative_dir_path = path_obj.relative_to(repo.workdir)
                        # Using add_all with a pathspec like "dir_a/*" might be an option,
                        # but pygit2's add_all pathspecs can be tricky.
                        # A more robust way for directories is to walk them and add files.
                        # However, index.add() itself should handle pathspecs correctly if they are files.
                        # The issue is that index.add("somedir") fails.
                        # Let's iterate and add files explicitly.
                        for item in path_obj.rglob('*'):
                            if item.is_file():
                                try:
                                    # Need path relative to repo.workdir for index.add
                                    file_rel_path = item.relative_to(repo.workdir)
                                    status_flags = repo.status_file(str(file_rel_path))
                                    if status_flags & pygit2.GIT_STATUS_IGNORED:
                                        print(f"Warning: File '{file_rel_path}' in directory '{path_str}' is ignored and was not added (in initial commit).")
                                    else:
                                        repo.index.add(file_rel_path)
                                except pygit2.GitError as e:
                                    print(f"Warning: Could not add file '{item}' from directory '{path_str}' (in initial commit): {e}")
                    elif path_obj.is_file():
                        try:
                            # path_str is already relative to repo root for include_paths
                            status_flags = repo.status_file(path_str)
                            if status_flags & pygit2.GIT_STATUS_IGNORED:
                                print(f"Warning: File '{path_str}' is ignored and was not added (in initial commit).")
                            else:
                                repo.index.add(path_str)
                        except pygit2.GitError as e:
                            print(f"Warning: Could not add file '{path_str}' (in initial commit): {e}")
                    else:
                        print(f"Warning: Path '{path_str}' (in initial commit) is not a file or directory and was not added.")
            repo.index.write()
            if not list(repo.index): # Check if anything was actually staged
                raise NoChangesToSaveError(
                    "Cannot create an initial commit: no files were staged. "
                    "If include_paths were specified, they might be invalid or ignored."
                )
            parents = [] # Initial commit has no parents

        else: # Not an initial commit, regular commit
            # ---- NEW LOGIC FOR include_paths AND add_all ----
            if include_paths:
                for path_str in include_paths:
                    if not path_str.strip():
                        continue # Skip empty/whitespace-only paths
                    path_obj = Path(repo.workdir) / path_str
                    if not path_obj.exists():
                        print(f"Warning: Path '{path_str}' does not exist and was not added.")
                        continue
                    if path_obj.is_dir():
                        for item in path_obj.rglob('*'):
                            if item.is_file():
                                try:
                                    file_rel_path = item.relative_to(repo.workdir)
                                    status_flags = repo.status_file(str(file_rel_path))
                                    if status_flags & pygit2.GIT_STATUS_IGNORED:
                                        print(f"Warning: File '{file_rel_path}' in directory '{path_str}' is ignored and was not added.")
                                    else:
                                        repo.index.add(file_rel_path)
                                except pygit2.GitError as e:
                                    print(f"Warning: Could not add file '{item}' from directory '{path_str}': {e}")
                    elif path_obj.is_file():
                        try:
                            # path_str is already relative to repo root for include_paths
                            status_flags = repo.status_file(path_str)
                            if status_flags & pygit2.GIT_STATUS_IGNORED:
                                print(f"Warning: File '{path_str}' is ignored and was not added.")
                            else:
                                repo.index.add(path_str)
                        except pygit2.GitError as e:
                            print(f"Warning: Could not add file '{path_str}': {e}")
                    else:
                        print(f"Warning: Path '{path_str}' is not a file or directory and was not added.")
                repo.index.write() # Persist the changes to the index from add() operations

                # Now, check if the updated index has any changes compared to HEAD tree
                diff_to_head = repo.index.diff_to_tree(repo.head.peel(pygit2.Tree))
                if not diff_to_head:
                    raise NoChangesToSaveError(
                        "No specified files had changes to stage relative to HEAD. "
                        "Files might be unchanged, non-existent, or gitignored."
                    )
            else: # include_paths is None, stage all
                repo.index.add_all()
                repo.index.write() # Persist add_all changes

                # This check is specifically for the case where include_paths is None (staging all)
                # and it's not an initial commit.
                # It should come after repo.index.add_all() and repo.index.write()
                if not repo.head_is_unborn and not repo.index.diff_to_tree(repo.head.peel(pygit2.Tree)):
                    raise NoChangesToSaveError("No changes to save (working directory and index are clean or match HEAD).")
                # The initial commit case for include_paths=None is handled by the general initial commit logic
                # that checks `if not list(repo.index):` before this `else` block for regular commits.
                # However, if it's an initial commit and include_paths is None, add_all() runs.
                # We still need to ensure that *something* was staged for an initial commit.
                elif repo.head_is_unborn and not list(repo.index): # Check if anything was staged for initial commit
                    raise NoChangesToSaveError("No changes to save for initial commit after add_all.")
            # ---- END OF NEW LOGIC ----

            if repo.head_is_unborn: # Should be caught by initial commit logic already.
                # This case indicates an issue if reached here, as 'initial commit' path should handle it.
                 raise RepositoryEmptyError("Repository is empty and this is not an initial commit flow.")
            parents = [repo.head.target]


    # 3. Create Commit object
    try:
        # The index must have been written by this point by one of the branches above.
        tree_oid = repo.index.write_tree()
    except pygit2.GitError as e:
        # This can happen if the index is empty (e.g., initial commit with no files)
        # or somehow corrupted. The checks above should prevent an empty index here.
        if repo.head_is_unborn and not list(repo.index): # list(repo.index) checks current in-memory index
            raise NoChangesToSaveError("Cannot create an initial commit with no files staged. Index is empty before tree write.")
        raise GitWriteError(f"Failed to write index tree: {e}")

    # Ensure parents list is correctly set for non-initial commits
    if not repo.head_is_unborn and not parents:
        # This implies a non-initial commit is about to be made without parents.
        # This shouldn't happen if logic above is correct (merge, revert, or normal commit paths).
        # It might indicate HEAD is detached and points to a non-existent commit,
        # or some other inconsistent repository state.
        # For safety, re-fetch HEAD target if parents list is empty for a non-unborn HEAD.
        # However, pygit2.Repository.create_commit will likely fail if parents are incorrect.
        # The parent calculation logic in each branch (initial, merge, revert, normal)
        # should correctly set `parents`. This is a safeguard or indicates a logic flaw if hit.
        # Defaulting to current HEAD if it was missed:
        parents = [repo.head.target]


    try:
        commit_oid = repo.create_commit(
            "HEAD",          # Update HEAD to point to the new commit
            author,
            committer,
            final_message,   # Use the potentially modified message (e.g., for reverts)
            tree_oid,
            parents
        )
    except pygit2.GitError as e:
        # Example: empty message if git config disallows it, or bad parent OIDs.
        raise GitWriteError(f"Failed to create commit object: {e}")
    except ValueError as e: # E.g. if message is empty and not allowed
        raise GitWriteError(f"Failed to create commit due to invalid value (e.g. empty message): {e}")


    # 4. Post-Commit Actions
    if is_merge_commit or is_revert_commit:
        try:
            repo.state_cleanup() # Remove MERGE_HEAD, REVERT_HEAD, etc.
        except pygit2.GitError as e: # pragma: no cover
            # This is not ideal, but the commit was made. Log or notify about cleanup failure.
            print(f"Warning: Commit was successful, but failed to cleanup repository state (e.g., MERGE_HEAD/REVERT_HEAD): {e}")
            pass # Continue to return success as commit is made.

    # Determine current branch name
    branch_name = None
    if not repo.head_is_detached:
        try:
            branch_name = repo.head.shorthand
        except pygit2.GitError: # pragma: no cover
            branch_name = "UNKNOWN_BRANCH" # Should be rare if not detached
    else: # head_is_detached is True
        branch_name = "DETACHED_HEAD"
        # Could try to find branches pointing to this commit_oid for more info if needed

    # 5. Return Success
    return {
        'status': 'success',
        'oid': str(commit_oid),
        'short_oid': str(commit_oid)[:7],
        'branch_name': branch_name,
        'message': final_message,
        'is_merge_commit': is_merge_commit,
        'is_revert_commit': is_revert_commit,
    }


def cherry_pick_commit(repo_path_str: str, commit_oid_to_pick: str, mainline: Optional[int] = None) -> Dict[str, Any]:
    """
    Applies the changes introduced by a specific commit to the current branch.

    Args:
        repo_path_str: Path to the repository.
        commit_oid_to_pick: The OID of the commit to cherry-pick.
        mainline: Optional. If the commit to pick is a merge commit, this specifies
                  which parent (1-indexed) to consider as the mainline.

    Returns:
        A dictionary indicating success and the new commit OID if the cherry-pick was clean and committed.
        Example: {'status': 'success', 'new_commit_oid': '...', 'message': 'Commit cherry-picked successfully.'}
        If conflicts occur, a MergeConflictError is raised.

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        CommitNotFoundError: If the commit to pick is not found.
        MergeConflictError: If the cherry-pick results in conflicts.
        GitWriteError: For other Git-related errors.
    """
    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        raise GitWriteError("Cannot cherry-pick in a bare repository.")
    if repo.head_is_unborn:
        raise GitWriteError("Cannot cherry-pick onto an unborn HEAD. Please make an initial commit.")

    try:
        commit_to_pick = repo.revparse_single(commit_oid_to_pick).peel(pygit2.Commit)
    except (pygit2.GitError, KeyError, TypeError) as e:
        raise CommitNotFoundError(f"Commit '{commit_oid_to_pick}' not found or not a commit: {e}")

    # Store original HEAD in case of conflict or error to reset
    original_head_oid = repo.head.target
    original_index_tree_oid = repo.index.write_tree() # Save current index state

    try:
        # Check for mainline requirement if it's a merge commit
        if len(commit_to_pick.parents) > 1 and mainline is None:
            raise GitWriteError(
                f"Commit {commit_to_pick.short_id} is a merge commit. "
                "Please specify the 'mainline' parameter (e.g., 1 or 2) to choose which parent's changes to pick."
            )

        # Determine cherrypick_options
        opts = pygit2.CherryPickOptions() # Use PascalCase for CherryPickOptions
        if mainline is not None: # mainline is not None here implies it's for a merge or user explicitly set it
            if not commit_to_pick.parents or len(commit_to_pick.parents) < 2:
                # This case should ideally be caught if mainline is specified for a non-merge.
                # However, if mainline is None for non-merge, the above check is skipped.
                # If mainline is not None for non-merge, this check is important.
                raise GitWriteError(f"Mainline option specified, but commit {commit_to_pick.short_id} is not a merge commit.")
            if mainline <= 0 or mainline > len(commit_to_pick.parents):
                raise GitWriteError(f"Invalid mainline number {mainline} for merge commit {commit_to_pick.short_id} with {len(commit_to_pick.parents)} parents.")
            opts.mainline = mainline
        # If it's not a merge commit, opts.mainline remains 0, which is correct.

        # Perform the cherry-pick operation. This updates the working directory and index.
        # pygit2.Repository.cherrypick does NOT create a commit.
        repo.cherrypick(commit_to_pick.id, opts=opts)

        # Check for conflicts after cherrypick
        # The index is updated by repo.cherrypick(). If there are conflicts, repo.index.conflicts will be populated.
        if repo.index.conflicts is not None:
            conflicting_files = get_conflicting_files(repo.index.conflicts) # Use existing helper
            if conflicting_files:
                # Cherry-pick resulted in conflicts. The index is in a conflicted state.
                # The working directory contains conflict markers.
                # We should not proceed to commit.
                # The state is left for the user to resolve. REVERT_HEAD or CHERRY_PICK_HEAD might be set by libgit2.
                # pygit2.Repository.state_cleanup() would typically clean these, but we want to leave them
                # if user needs to resolve. However, for a programmatic API, it's better to
                # either complete the operation or fully abort and reset.
                # For now, we raise, and the repo is left in a conflicted state.
                # A more robust solution might involve `repo.reset()` if we don't want to leave it conflicted.
                # Let's reset to original state before raising.
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                repo.index.read_tree(original_index_tree_oid) # Restore original index
                repo.index.write()
                repo.state_cleanup() # Clean up CHERRY_PICK_HEAD etc.

                raise MergeConflictError(
                    f"Cherry-pick of commit {commit_to_pick.short_id} resulted in conflicts.",
                    conflicting_files=conflicting_files
                )

        # If no conflicts, the index reflects the cherry-picked changes.
        # Proceed to create a commit.

        # Use the original commit's message, author, and committer.
        # The commit time will be new.
        author = pygit2.Signature(
            commit_to_pick.author.name,
            commit_to_pick.author.email,
            time=commit_to_pick.author.time,
            offset=commit_to_pick.author.offset
        )
        committer = repo.default_signature # Use current user/time as committer
        if not committer: # Fallback
             # Create a new signature for committer with current time
             current_time = int(datetime.now(timezone.utc).timestamp())
             # Attempt to get local timezone offset, default to 0 (UTC)
             try:
                local_tz = datetime.now(timezone.utc).astimezone().tzinfo
                offset_minutes = 0
                if local_tz:
                    offset_delta = local_tz.utcoffset(datetime.now())
                    if offset_delta:
                        offset_minutes = int(offset_delta.total_seconds() / 60)
             except Exception:
                offset_minutes = 0
             committer = pygit2.Signature("GitWrite System", "gitwrite@example.com", time=current_time, offset=offset_minutes)
        else:
            # If default signature exists, use its name/email but update time to now
            current_time = int(datetime.now(timezone.utc).timestamp())
            committer = pygit2.Signature(committer.name, committer.email, time=current_time, offset=committer.offset)

        commit_message = commit_to_pick.message

        # Create the commit
        new_tree_oid = repo.index.write_tree()
        parents = [repo.head.target]

        new_commit_oid = repo.create_commit(
            "HEAD",             # Update HEAD to point to the new commit
            author,             # Author from original commit
            committer,          # Committer is the current user
            commit_message,     # Message from original commit
            new_tree_oid,       # Tree from the updated index
            parents             # Parent is the current HEAD
        )

        repo.state_cleanup() # Clean up CHERRY_PICK_HEAD if it was set

        return {
            'status': 'success',
            'new_commit_oid': str(new_commit_oid),
            'message': f"Commit '{commit_to_pick.short_id}' cherry-picked successfully as '{str(new_commit_oid)[:7]}'."
        }

    except MergeConflictError: # Re-raise if it's already our specific error
        raise
    except pygit2.GitError as e:
        # Attempt to reset repository to original state on error
        current_head = repo.head.target if not repo.head_is_unborn else None
        if current_head != original_head_oid : # Only reset if HEAD changed
            try:
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                # Also try to restore the index to its pre-cherrypick state
                # This might not be perfect if write_tree() failed or index was corrupted
                # but it's a best effort.
                original_tree = repo.get(original_index_tree_oid, pygit2.GIT_OBJ_TREE)
                if original_tree:
                    repo.index.read_tree(original_tree)
                repo.index.write()
            except Exception as reset_e: # pragma: no cover
                # If reset fails, append to original error or log it
                raise GitWriteError(f"Error during cherry-pick: {e}. Additionally, failed to reset repository: {reset_e}")

        repo.state_cleanup() # Ensure CHERRY_PICK_HEAD etc. are cleaned up on error
        raise GitWriteError(f"Error during cherry-pick operation for commit '{commit_oid_to_pick}': {e}")
    except Exception as e: # Catch any other unexpected error
        # Attempt to reset repository to original state
        current_head = repo.head.target if not repo.head_is_unborn else None
        if current_head != original_head_oid: # Only reset if HEAD changed
            try:
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                original_tree = repo.get(original_index_tree_oid, pygit2.GIT_OBJ_TREE)
                if original_tree:
                    repo.index.read_tree(original_tree)
                repo.index.write()
            except Exception as reset_e: # pragma: no cover
                raise GitWriteError(f"An unexpected error occurred during cherry-pick: {e}. Additionally, failed to reset repository: {reset_e}")

        repo.state_cleanup()
        raise GitWriteError(f"An unexpected error occurred during cherry-pick for commit '{commit_oid_to_pick}': {e}")
