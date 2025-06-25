import pygit2
import pygit2.enums # Added for MergeFavor
# import pygit2.ops # ModuleNotFoundError with pygit2 1.18.0
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import re # For get_word_level_diff
import difflib # For get_word_level_diff

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
    # commits_processed = 0 # This variable was unused

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
        except (pygit2.GitError, KeyError, TypeError) as e:
            raise CommitNotFoundError(f"Reference '{ref1_str}' not found or not a commit: {e}")
        try:
            commit2_obj = repo.head.peel(pygit2.Commit)
        except (pygit2.GitError, KeyError) as e:
            raise CommitNotFoundError(f"Could not resolve HEAD: {e}")
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
    else:
        raise ValueError("Invalid reference combination for diff. Cannot specify ref2 without ref1 unless both are None.")

    if not commit1_obj or not commit2_obj:
        raise CommitNotFoundError("Could not resolve one or both references to commits.")

    tree1 = commit1_obj.tree
    tree2 = commit2_obj.tree
    diff_obj = repo.diff(tree1, tree2, context_lines=3, interhunk_lines=1)

    return {
        "ref1_oid": str(commit1_obj.id),
        "ref2_oid": str(commit2_obj.id),
        "ref1_display_name": ref1_resolved_name if ref1_resolved_name else str(commit1_obj.id),
        "ref2_display_name": ref2_resolved_name if ref2_resolved_name else str(commit2_obj.id),
        "patch_text": diff_obj.patch if diff_obj else ""
    }

def revert_commit(repo_path_str: str, commit_ish_to_revert: str) -> dict:
    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    try:
        commit_to_revert = repo.revparse_single(commit_ish_to_revert).peel(pygit2.Commit)
    except (pygit2.GitError, KeyError, TypeError) as e:
        raise CommitNotFoundError(f"Commit '{commit_ish_to_revert}' not found or not a commit: {e}")

    original_head_oid = None
    original_index_tree_oid = repo.index.write_tree() # Save current index state for potential full reset

    try:
        if not commit_to_revert.parents:
            raise GitWriteError(f"Cannot revert commit {commit_to_revert.short_id} as it has no parents (initial commit).")

        parent_to_revert_to = commit_to_revert.parents[0]
        ancestor_tree = commit_to_revert.tree
        current_head_commit = repo.head.peel(pygit2.Commit)
        our_tree = current_head_commit.tree
        their_tree = parent_to_revert_to.tree
        original_head_oid = repo.head.target
        index = repo.merge_trees(ancestor_tree, our_tree, their_tree)

        has_actual_conflicts = False
        if index.conflicts is not None:
            try:
                next(iter(index.conflicts))
                has_actual_conflicts = True
            except StopIteration:
                has_actual_conflicts = False

        if has_actual_conflicts:
            # On conflict, reset HEAD and working directory. Index is not yet written from 'index' object.
            repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
            # Restore original index
            original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
            if original_tree_obj_for_index_reset:
                repo.index.read_tree(original_tree_obj_for_index_reset)
            repo.index.write()
            raise MergeConflictError("Revert resulted in conflicts. The revert has been aborted and the working directory is clean.")

        repo.index.read_tree(index.write_tree())
        repo.index.write()
        repo.checkout_index(strategy=pygit2.GIT_CHECKOUT_FORCE)

    except MergeConflictError:
        raise
    except GitWriteError as e:
        if original_head_oid and str(original_head_oid) != str(repo.head.target):
             repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
             original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
             if original_tree_obj_for_index_reset:
                repo.index.read_tree(original_tree_obj_for_index_reset)
             repo.index.write()
        raise
    except pygit2.GitError as e:
        if original_head_oid and str(original_head_oid) != str(repo.head.target):
             repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
             original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
             if original_tree_obj_for_index_reset:
                repo.index.read_tree(original_tree_obj_for_index_reset)
             repo.index.write()
        raise GitWriteError(f"Error during revert operation: {e}. Working directory reset.")
    except Exception as e:
        if original_head_oid and str(original_head_oid) != str(repo.head.target):
            repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
            original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
            if original_tree_obj_for_index_reset:
               repo.index.read_tree(original_tree_obj_for_index_reset)
            repo.index.write()
        raise GitWriteError(f"An unexpected error occurred during revert: {e}. Working directory reset.")

    try:
        user_signature = repo.default_signature
        if not user_signature:
            user_signature = pygit2.Signature("GitWrite", "gitwrite@example.com")
        original_commit_summary = _get_commit_summary(commit_to_revert)
        revert_commit_message = f"Revert \"{original_commit_summary}\"\n\nThis reverts commit {commit_to_revert.id}."
        parents = [repo.head.target] if not repo.head_is_unborn else []
        new_commit_tree_oid = repo.index.write_tree()
        new_commit_oid_val = repo.create_commit(
            "HEAD", user_signature, user_signature, revert_commit_message, new_commit_tree_oid, parents
        )
        repo.state_cleanup()
        return {
            'status': 'success',
            'new_commit_oid': str(new_commit_oid_val),
            'message': 'Commit reverted successfully.'
        }
    except pygit2.GitError as e:
        # Attempt to reset to original_head_oid if commit creation fails
        repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
        original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
        if original_tree_obj_for_index_reset:
            repo.index.read_tree(original_tree_obj_for_index_reset)
        repo.index.write()
        raise GitWriteError(f"Failed to create revert commit after a clean revert: {e}. Working directory reset.")
    except Exception as e:
        repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
        original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
        if original_tree_obj_for_index_reset:
            repo.index.read_tree(original_tree_obj_for_index_reset)
        repo.index.write()
        raise GitWriteError(f"An unexpected error occurred while creating the revert commit: {e}. Working directory reset.")

def get_conflicting_files(conflicts_iterator):
    conflicting_paths = []
    if conflicts_iterator:
        for conflict_entry in conflicts_iterator:
            ancestor_meta, our_meta, their_meta = conflict_entry
            if our_meta:
                conflicting_paths.append(our_meta.path)
            elif their_meta:
                conflicting_paths.append(their_meta.path)
            elif ancestor_meta:
                conflicting_paths.append(ancestor_meta.path)
    return conflicting_paths

def save_changes(repo_path_str: str, message: str, include_paths: Optional[List[str]] = None) -> Dict:
    import time
    from .exceptions import NoChangesToSaveError, RevertConflictError, RepositoryEmptyError

    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error discovering or initializing repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        raise GitWriteError("Cannot save changes in a bare repository.")

    is_merge_commit = False
    is_revert_commit = False
    parents = []
    final_message = message

    try:
        author = repo.default_signature
        committer = repo.default_signature
    except pygit2.GitError:
        current_time = int(time.time())
        offset = 0
        try:
            local_tz = datetime.now(timezone.utc).astimezone().tzinfo
            if local_tz:
                offset_delta = local_tz.utcoffset(datetime.now())
                if offset_delta:
                    offset = int(offset_delta.total_seconds() / 60)
        except Exception:
            pass
        author = pygit2.Signature("GitWrite User", "user@example.com", current_time, offset)
        committer = pygit2.Signature("GitWrite User", "user@example.com", current_time, offset)

    try:
        merge_head_ref = repo.lookup_reference("MERGE_HEAD")
        if merge_head_ref and merge_head_ref.target:
            if include_paths:
                raise GitWriteError("Selective staging with --include is not allowed during an active merge operation.")
            merge_head_oid = merge_head_ref.target
            repo.index.read()
            if repo.index.conflicts:
                conflicting_files = get_conflicting_files(repo.index.conflicts)
                raise MergeConflictError(
                    "Unresolved conflicts detected during merge. Please resolve them before saving.",
                    conflicting_files=conflicting_files
                )
            repo.index.add_all()
            repo.index.write()
            if repo.head_is_unborn:
                raise GitWriteError("Repository HEAD is unborn during a merge operation, which is unexpected.")
            parents = [repo.head.target, merge_head_oid]
            is_merge_commit = True
    except KeyError:
        pass
    except pygit2.GitError as e:
        raise GitWriteError(f"Error checking for MERGE_HEAD: {e}")

    if not is_merge_commit:
        try:
            revert_head_ref = repo.lookup_reference("REVERT_HEAD")
            if revert_head_ref and revert_head_ref.target:
                if include_paths:
                    raise GitWriteError("Selective staging with --include is not allowed during an active revert operation.")
                revert_head_oid = revert_head_ref.target
                repo.index.read()
                repo.index.add_all()
                repo.index.write()
                if repo.index.conflicts:
                    conflicting_files = get_conflicting_files(repo.index.conflicts)
                    raise RevertConflictError(
                        "Unresolved conflicts detected during revert. Please resolve them before saving.",
                        conflicting_files=conflicting_files
                    )
                if repo.head_is_unborn:
                     raise GitWriteError("Repository HEAD is unborn during a revert operation, which is unexpected.")
                parents = [repo.head.target]
                try:
                    reverted_commit = repo.get(revert_head_oid)
                    if reverted_commit and reverted_commit.message:
                        first_line_of_reverted_msg = reverted_commit.message.splitlines()[0]
                        final_message = f"Revert \"{first_line_of_reverted_msg}\"\n\nThis reverts commit {revert_head_oid}.\n\n{message}"
                    else:
                        final_message = f"Revert commit {revert_head_oid}.\n\n{message}"
                except Exception:
                     final_message = f"Revert commit {revert_head_oid}.\n\n{message}"
                is_revert_commit = True
        except KeyError:
            pass
        except pygit2.GitError as e:
            raise GitWriteError(f"Error checking for REVERT_HEAD: {e}")

    if not is_merge_commit and not is_revert_commit:
        repo.index.read()
        if repo.head_is_unborn: # Initial commit
            if not include_paths:
                repo.index.add_all()
            else:
                for path_spec_item in include_paths:
                    if not path_spec_item.strip(): continue
                    path_obj = Path(repo.workdir) / path_spec_item
                    if not path_obj.exists():
                        print(f"Warning: Path '{path_spec_item}' (in initial commit) does not exist and was not added.")
                        continue
                    if path_obj.is_dir():
                        for item in path_obj.rglob('*'):
                            if item.is_file():
                                try:
                                    file_rel_path_str = str(item.relative_to(repo.workdir))
                                    status_flags = repo.status_file(file_rel_path_str)
                                    if status_flags & pygit2.GIT_STATUS_IGNORED:
                                        print(f"Warning: File '{file_rel_path_str}' in directory '{path_spec_item}' is ignored and was not added (in initial commit).")
                                    else:
                                        repo.index.add(file_rel_path_str)
                                except pygit2.GitError as e:
                                    print(f"Warning: Could not add file '{item}' from directory '{path_spec_item}' (in initial commit): {e}")
                    elif path_obj.is_file():
                        try:
                            status_flags = repo.status_file(path_spec_item)
                            if status_flags & pygit2.GIT_STATUS_IGNORED:
                                print(f"Warning: File '{path_spec_item}' is ignored and was not added (in initial commit).")
                            else:
                                repo.index.add(path_spec_item)
                        except pygit2.GitError as e:
                            print(f"Warning: Could not add file '{path_spec_item}' (in initial commit): {e}")
                    else:
                        print(f"Warning: Path '{path_spec_item}' (in initial commit) is not a file or directory and was not added.")
            repo.index.write()
            if not list(repo.index):
                raise NoChangesToSaveError(
                    "Cannot create an initial commit: no files were staged. "
                    "If include_paths were specified, they might be invalid or ignored."
                )
            parents = []
        else: # Regular commit
            if include_paths:
                for path_spec_item in include_paths:
                    if not path_spec_item.strip(): continue
                    path_obj = Path(repo.workdir) / path_spec_item
                    if not path_obj.exists():
                        print(f"Warning: Path '{path_spec_item}' does not exist and was not added.")
                        continue
                    if path_obj.is_dir():
                        for item in path_obj.rglob('*'):
                            if item.is_file():
                                try:
                                    file_rel_path_str = str(item.relative_to(repo.workdir))
                                    status_flags = repo.status_file(file_rel_path_str)
                                    if status_flags & pygit2.GIT_STATUS_IGNORED:
                                        print(f"Warning: File '{file_rel_path_str}' in directory '{path_spec_item}' is ignored and was not added.")
                                    else:
                                        repo.index.add(file_rel_path_str)
                                except pygit2.GitError as e:
                                    print(f"Warning: Could not add file '{item}' from directory '{path_spec_item}': {e}")
                    elif path_obj.is_file():
                        try:
                            status_flags = repo.status_file(path_spec_item)
                            if status_flags & pygit2.GIT_STATUS_IGNORED:
                                print(f"Warning: File '{path_spec_item}' is ignored and was not added.")
                            else:
                                repo.index.add(path_spec_item)
                        except pygit2.GitError as e:
                            print(f"Warning: Could not add file '{path_spec_item}': {e}")
                    else:
                        print(f"Warning: Path '{path_spec_item}' is not a file or directory and was not added.")
                repo.index.write()
                diff_to_head = repo.index.diff_to_tree(repo.head.peel(pygit2.Tree))
                if not diff_to_head:
                    raise NoChangesToSaveError(
                        "No specified files had changes to stage relative to HEAD. "
                        "Files might be unchanged, non-existent, or gitignored."
                    )
            else: # include_paths is None, stage all
                repo.index.add_all()
                repo.index.write()
                if not repo.head_is_unborn and not repo.index.diff_to_tree(repo.head.peel(pygit2.Tree)):
                    raise NoChangesToSaveError("No changes to save (working directory and index are clean or match HEAD).")
                elif repo.head_is_unborn and not list(repo.index):
                    raise NoChangesToSaveError("No changes to save for initial commit after add_all.")

            if repo.head_is_unborn: # Should be caught by initial commit logic already.
                 raise RepositoryEmptyError("Repository is empty and this is not an initial commit flow.")
            parents = [repo.head.target]

    try:
        tree_oid = repo.index.write_tree()
    except pygit2.GitError as e:
        if repo.head_is_unborn and not list(repo.index):
            raise NoChangesToSaveError("Cannot create an initial commit with no files staged. Index is empty before tree write.")
        raise GitWriteError(f"Failed to write index tree: {e}")

    if not repo.head_is_unborn and not parents:
        parents = [repo.head.target]

    try:
        commit_oid = repo.create_commit("HEAD", author, committer, final_message, tree_oid, parents)
    except pygit2.GitError as e:
        raise GitWriteError(f"Failed to create commit object: {e}")
    except ValueError as e:
        raise GitWriteError(f"Failed to create commit due to invalid value (e.g. empty message): {e}")

    if is_merge_commit or is_revert_commit:
        try:
            repo.state_cleanup()
        except pygit2.GitError as e:
            print(f"Warning: Commit was successful, but failed to cleanup repository state (e.g., MERGE_HEAD/REVERT_HEAD): {e}")
            pass

    branch_name = None
    if not repo.head_is_detached:
        try:
            branch_name = repo.head.shorthand
        except pygit2.GitError:
            branch_name = "UNKNOWN_BRANCH"
    else:
        branch_name = "DETACHED_HEAD"

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

    original_head_oid = repo.head.target
    original_index_tree_oid = repo.index.write_tree()

    try:
        if len(commit_to_pick.parents) > 1 and mainline is None:
            raise GitWriteError(
                f"Commit {commit_to_pick.short_id} is a merge commit. "
                "Please specify the 'mainline' parameter (e.g., 1 or 2) to choose which parent's changes to pick."
            )

        # Additional mainline validations specifically for when mainline IS provided
        if mainline is not None:
            if not (len(commit_to_pick.parents) > 1):
                raise GitWriteError(f"Mainline option specified, but commit {commit_to_pick.short_id} is not a merge commit.")
            if not (1 <= mainline <= len(commit_to_pick.parents)):
                 raise GitWriteError(f"Invalid mainline number {mainline} for merge commit {commit_to_pick.short_id} with {len(commit_to_pick.parents)} parents.")

        our_commit = repo.head.peel(pygit2.Commit)
        our_tree = our_commit.tree

        if len(commit_to_pick.parents) > 1:
            if mainline is None:
                 raise GitWriteError(f"Internal error: Mainline must be specified for cherry-picking a merge commit ({commit_to_pick.short_id}) at this stage.")
            mainline_parent_index = mainline - 1
            ancestor_tree = commit_to_pick.parents[mainline_parent_index].tree
        else:
            if not commit_to_pick.parents:
                ancestor_tree = None
            else:
                ancestor_tree = commit_to_pick.parents[0].tree

        their_tree = commit_to_pick.tree
        index = repo.merge_trees(ancestor_tree, our_tree, their_tree)

        if index.conflicts:
            conflicting_files = get_conflicting_files(index.conflicts)
            if conflicting_files:
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                original_tree_obj_for_index_reset = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
                if original_tree_obj_for_index_reset:
                    repo.index.read_tree(original_tree_obj_for_index_reset)
                repo.index.write()
                repo.state_cleanup()
                raise MergeConflictError(
                    f"Cherry-pick of commit {commit_to_pick.short_id} resulted in conflicts.",
                    conflicting_files=conflicting_files
                )

        repo.index.read_tree(index.write_tree())
        repo.index.write()
        repo.checkout_index(strategy=pygit2.GIT_CHECKOUT_FORCE)

        author = pygit2.Signature(
            commit_to_pick.author.name, commit_to_pick.author.email,
            time=commit_to_pick.author.time, offset=commit_to_pick.author.offset
        )
        committer = repo.default_signature
        if not committer:
             current_time = int(datetime.now(timezone.utc).timestamp())
             offset_minutes = 0
             try:
                local_tz = datetime.now(timezone.utc).astimezone().tzinfo
                if local_tz:
                    offset_delta = local_tz.utcoffset(datetime.now())
                    if offset_delta:
                        offset_minutes = int(offset_delta.total_seconds() / 60)
             except Exception:
                offset_minutes = 0
             committer = pygit2.Signature("GitWrite System", "gitwrite@example.com", time=current_time, offset=offset_minutes)
        else:
            current_time = int(datetime.now(timezone.utc).timestamp())
            committer = pygit2.Signature(committer.name, committer.email, time=current_time, offset=committer.offset)

        commit_message = commit_to_pick.message
        new_tree_oid = repo.index.write_tree()
        # The parent of the new commit is the commit HEAD was pointing to before this operation.
        # This 'original_head_oid' was captured before any cherry-pick logic.
        parents = [original_head_oid]
        new_commit_oid_val = repo.create_commit(
            "HEAD", author, committer, commit_message, new_tree_oid, parents
        )
        repo.state_cleanup()
        return {
            'status': 'success',
            'new_commit_oid': str(new_commit_oid_val),
            'message': f"Commit '{commit_to_pick.short_id}' cherry-picked successfully as '{str(new_commit_oid_val)[:7]}'."
        }
    except MergeConflictError:
        raise
    except pygit2.GitError as e:
        current_head = repo.head.target if not repo.head_is_unborn else None
        if current_head != original_head_oid :
            try:
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                original_tree = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
                if original_tree:
                    repo.index.read_tree(original_tree)
                repo.index.write()
            except Exception as reset_e:
                raise GitWriteError(f"Error during cherry-pick: {e}. Additionally, failed to reset repository: {reset_e}")
        repo.state_cleanup()
        raise GitWriteError(f"Error during cherry-pick operation for commit '{commit_oid_to_pick}': {e}")
    except Exception as e:
        current_head = repo.head.target if not repo.head_is_unborn else None
        if current_head != original_head_oid:
            try:
                repo.reset(original_head_oid, pygit2.GIT_RESET_HARD)
                original_tree = repo.get(original_index_tree_oid, pygit2.GIT_OBJECT_TREE)
                if original_tree:
                    repo.index.read_tree(original_tree)
                repo.index.write()
            except Exception as reset_e:
                raise GitWriteError(f"An unexpected error occurred during cherry-pick: {e}. Additionally, failed to reset repository: {reset_e}")
        repo.state_cleanup()
        raise GitWriteError(f"An unexpected error occurred during cherry-pick for commit '{commit_oid_to_pick}': {e}")


def get_branch_review_commits(repo_path_str: str, branch_name_to_review: str, limit: Optional[int] = None) -> List[Dict]:
    """
    Retrieves commits present on branch_name_to_review but not on the current HEAD.

    Args:
        repo_path_str: Path to the repository.
        branch_name_to_review: The name of the branch to review.
        limit: Optional maximum number of commits to return.

    Returns:
        A list of dictionaries, where each dictionary contains details of a commit,
        ordered from oldest to newest among the unique commits.

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        BranchNotFoundError: If the branch_name_to_review is not found.
        GitWriteError: For other Git-related errors.
    """
    from .exceptions import BranchNotFoundError # Local import to avoid circular dependency issues at module load
    import difflib # For get_word_level_diff
    import re # For get_word_level_diff

    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"No repository found at or above '{repo_path_str}'")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error opening repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        raise GitWriteError("Cannot review branches in a bare repository.")
    if repo.head_is_unborn:
        raise GitWriteError("Cannot review branches when HEAD is unborn. Please make an initial commit.")

    try:
        branch_to_review_obj = repo.branches.get(branch_name_to_review)
        if not branch_to_review_obj:
            # Try remote branch if local not found
            remote_branch_name = f"origin/{branch_name_to_review}" # Common convention
            branch_to_review_obj = repo.branches.get(remote_branch_name)
            if not branch_to_review_obj:
                 raise BranchNotFoundError(f"Branch '{branch_name_to_review}' not found locally or as 'origin/{branch_name_to_review}'.")
        branch_oid = branch_to_review_obj.target
    except pygit2.GitError:
        raise BranchNotFoundError(f"Branch '{branch_name_to_review}' not found.")
    except KeyError: # For branches.get() if it doesn't find the branch
        raise BranchNotFoundError(f"Branch '{branch_name_to_review}' not found.")


    head_commit_oid = repo.head.target
    if branch_oid == head_commit_oid:
        return [] # The branch is the same as HEAD, no unique commits

    commits_data = []
    try:
        # Walk commits on branch_to_review, hide commits reachable from current HEAD
        # GIT_SORT_TOPOLOGICAL | GIT_SORT_REVERSE gives oldest first among the selection
        walker = repo.walk(branch_oid, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE, hide=head_commit_oid)
        for commit_obj in walker:
            author_tz = timezone(timedelta(minutes=commit_obj.author.offset))
            commits_data.append({
                "short_hash": str(commit_obj.id)[:7],
                "author_name": commit_obj.author.name,
                "date": datetime.fromtimestamp(commit_obj.author.time, tz=author_tz).strftime('%Y-%m-%d %H:%M:%S %z'),
                "message_short": commit_obj.message.splitlines()[0].strip(),
                "oid": str(commit_obj.id),
            })
            if limit is not None and len(commits_data) >= limit:
                break
    except pygit2.GitError as e:
        raise GitWriteError(f"Error walking commit history for branch '{branch_name_to_review}': {e}")

    return commits_data


def get_word_level_diff(patch_text: str) -> List[Dict[str, Any]]:
    """
    Processes a standard diff patch string and returns a structured
    representation with word-level differences.

    Args:
        patch_text: A string containing the diff output (e.g., from `git diff`).

    Returns:
        A list of dictionaries, where each dictionary represents a file diff.
        Each file diff contains a list of hunks, and each hunk contains a list
        of lines. Lines are marked as 'context', 'deletion', or 'addition'.
        Deletion and addition lines will have a 'words' key containing a list
        of word segment dictionaries (e.g., {'type': 'removed', 'content': 'word'}).
    """
    if not patch_text:
        return []

    file_diffs: List[Dict[str, Any]] = []
    file_patches = re.split(r'(?=^diff --git a/)', patch_text, flags=re.MULTILINE)

    for file_patch in file_patches:
        if not file_patch.strip():
            continue

        lines = file_patch.splitlines()
        if not lines:
            continue

        file_info: Dict[str, Any] = {"hunks": []}
        current_hunk_lines: List[Tuple[str, str]] = []
        in_hunk_body = False

        # Initialize paths from the 'diff --git' line
        # These might be updated by 'rename from/to' or '---'/'+++' lines later
        path_a_from_diff_git = "unknown_a"
        path_b_from_diff_git = "unknown_b"

        if lines[0].startswith("diff --git a/"):
            parts = lines[0].split(' ', 3) # split into 4 parts: diff, --git, a/path, b/path
            if len(parts) == 4:
                path_a_from_diff_git = parts[2][2:].strip() # remove "a/" and strip
                path_b_from_diff_git = parts[3][2:].strip() # remove "b/" and strip

        # Set initial file_path and change_type. These are defaults and might be overridden.
        file_info["file_path"] = path_b_from_diff_git
        file_info["change_type"] = "modified" # Default, will be updated

        # Tentative old/new paths for renames/copies
        # These will be populated if rename/copy lines are found
        # or if --- a/ and +++ b/ lines differ significantly
        tentative_old_path = path_a_from_diff_git
        tentative_new_path = path_b_from_diff_git


        for line_content in lines[1:]: # Start from the second line
            if line_content.startswith("--- a/"):
                in_hunk_body = False
                path = line_content[len("--- a/"):].strip()
                tentative_old_path = path
                if path == "/dev/null":
                    file_info["change_type"] = "added"
            elif line_content.startswith("+++ b/"):
                in_hunk_body = False
                path = line_content[len("+++ b/"):].strip()
                tentative_new_path = path
                if path == "/dev/null":
                    file_info["change_type"] = "deleted"
                # The path from +++ b/ is generally the one to display
                file_info["file_path"] = path if path != "/dev/null" else tentative_old_path

            elif line_content.startswith("new file mode"):
                in_hunk_body = False
                file_info["change_type"] = "added"
            elif line_content.startswith("deleted file mode"):
                in_hunk_body = False
                file_info["change_type"] = "deleted"
                # If it's a deletion, the file_path should be the old path
                file_info["file_path"] = tentative_old_path

            elif line_content.startswith("rename from "):
                in_hunk_body = False
                file_info["change_type"] = "renamed"
                file_info["old_file_path"] = line_content[len("rename from "):].strip()
                tentative_old_path = file_info["old_file_path"]
            elif line_content.startswith("rename to "):
                in_hunk_body = False
                file_info["change_type"] = "renamed" # Should already be set by "rename from"
                file_info["new_file_path"] = line_content[len("rename to "):].strip()
                tentative_new_path = file_info["new_file_path"]
                file_info["file_path"] = file_info["new_file_path"] # For renames, new_file_path is the primary

            elif line_content.startswith("copy from "): # Handle copy as well, though tests don't explicitly cover it
                in_hunk_body = False
                file_info["change_type"] = "copied"
                file_info["old_file_path"] = line_content[len("copy from "):].strip()
                tentative_old_path = file_info["old_file_path"]
            elif line_content.startswith("copy to "):
                in_hunk_body = False
                file_info["change_type"] = "copied"
                file_info["new_file_path"] = line_content[len("copy to "):].strip()
                tentative_new_path = file_info["new_file_path"]
                file_info["file_path"] = file_info["new_file_path"]

            elif line_content.startswith("index ") or line_content.startswith("similarity index"):
                in_hunk_body = False
            elif line_content.startswith("Binary files") and "differ" in line_content:
                in_hunk_body = False
                file_info["is_binary"] = True
                file_info["hunks"] = [] # No hunks for binary files
                current_hunk_lines = [] # Clear any pending lines
                break # Stop processing lines for this file patch
            elif line_content.startswith("@@"):
                # Process lines accumulated for the *previous* hunk (if any)
                if current_hunk_lines:
                    processed_lines = _process_hunk_lines_for_structured_diff(current_hunk_lines)
                    if file_info["hunks"]:
                        file_info["hunks"][-1]["lines"].extend(processed_lines)
                    else:
                        file_info["hunks"].append({"lines": processed_lines})
                    current_hunk_lines = []

                # Start a new hunk
                file_info["hunks"].append({"lines": []})
                in_hunk_body = True
            elif line_content.startswith("\\ No newline at end of file"):
                if in_hunk_body and file_info["hunks"]:
                    # Process any pending +/-/space lines for the current hunk first
                    if current_hunk_lines:
                        processed_lines = _process_hunk_lines_for_structured_diff(current_hunk_lines)
                        file_info["hunks"][-1]["lines"].extend(processed_lines)
                        current_hunk_lines = []
                    # Add the "no newline" message to the current hunk
                    file_info["hunks"][-1]["lines"].append({"type": "no_newline", "content": line_content})
            elif in_hunk_body and (line_content.startswith(("+", "-", " "))):
                current_hunk_lines.append((line_content[0], line_content[1:]))

        # Process any remaining hunk lines for the last hunk after loop finishes
        if current_hunk_lines and file_info["hunks"]:
            processed_lines = _process_hunk_lines_for_structured_diff(current_hunk_lines)
            file_info["hunks"][-1]["lines"].extend(processed_lines)
        elif current_hunk_lines and not file_info["hunks"]:
             processed_lines = _process_hunk_lines_for_structured_diff(current_hunk_lines)
             if processed_lines:
                file_info["hunks"].append({"lines": processed_lines})

        current_change_type = file_info.get("change_type", "modified")
        hunks = file_info.get("hunks", [])
        is_binary = file_info.get("is_binary", False)

        _file_path = None
        _old_file_path = None
        _new_file_path = None

        if current_change_type == "added":
            _file_path = tentative_new_path if tentative_new_path != "/dev/null" else path_b_from_diff_git
        elif current_change_type == "deleted":
            _file_path = tentative_old_path if tentative_old_path != "/dev/null" else path_a_from_diff_git
        elif current_change_type == "modified":
            _file_path = path_a_from_diff_git
            if _file_path in ["unknown_a", "unknown_b", "/dev/null"]:
                 _file_path = path_b_from_diff_git
        elif current_change_type in ["renamed", "copied"]:
            _old_file_path = file_info.get("old_file_path")
            _new_file_path = file_info.get("new_file_path")

            if not _old_file_path and tentative_old_path != "/dev/null":
                _old_file_path = tentative_old_path
            if not _new_file_path and tentative_new_path != "/dev/null":
                _new_file_path = tentative_new_path

            _file_path = _new_file_path

        if _file_path == "/dev/null":
            if current_change_type == "added" and path_b_from_diff_git != "/dev/null":
                _file_path = path_b_from_diff_git
            elif current_change_type == "deleted" and path_a_from_diff_git != "/dev/null":
                _file_path = path_a_from_diff_git
        if _file_path in ["unknown_a", "unknown_b"]:
            if path_b_from_diff_git not in ["unknown_b", "/dev/null"]:
                _file_path = path_b_from_diff_git
            elif path_a_from_diff_git not in ["unknown_a", "/dev/null"]:
                _file_path = path_a_from_diff_git

        item_to_append = {}
        if current_change_type in ["renamed", "copied"]:
            item_to_append["old_file_path"] = _old_file_path
            item_to_append["new_file_path"] = _new_file_path
            item_to_append["file_path"] = _file_path
            item_to_append["change_type"] = current_change_type
        else:
            item_to_append["file_path"] = _file_path
            item_to_append["change_type"] = current_change_type

        item_to_append["hunks"] = hunks
        if is_binary:
            item_to_append["is_binary"] = True
            item_to_append["hunks"] = []

        if item_to_append.get("hunks") or item_to_append.get("is_binary"):
            file_diffs.append(item_to_append)

    return file_diffs


def _process_hunk_lines_for_structured_diff(hunk_lines: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    Helper function to process lines within a hunk for word-level diffs
    and return a structured list.
    """
    processed_lines: List[Dict[str, Any]] = []
    i = 0
    while i < len(hunk_lines):
        origin, content = hunk_lines[i]

        if origin == '-' and (i + 1 < len(hunk_lines)) and hunk_lines[i+1][0] == '+':
            old_content_str = content
            new_content_str = hunk_lines[i+1][1]
            old_words_list = old_content_str.split()
            new_words_list = new_content_str.split()
            old_words_set = set(old_words_list)
            new_words_set = set(new_words_list)

            sm = difflib.SequenceMatcher(None, old_content_str, new_content_str)
            similarity_ratio = sm.ratio()

            # If lines are too dissimilar, or no common words at word level, treat as whole line changes
            if similarity_ratio < 0.6 or not old_words_set.intersection(new_words_set):
                del_words = [{"type": "removed", "content": old_content_str.strip()}] if old_content_str.strip() else []
                add_words = [{"type": "added", "content": new_content_str.strip()}] if new_content_str.strip() else []
                processed_lines.append({"type": "deletion", "content": old_content_str, "words": del_words})
                processed_lines.append({"type": "addition", "content": new_content_str, "words": add_words})
            else:
                sm_word = difflib.SequenceMatcher(None, old_words_list, new_words_list)

                temp_deleted_words_structured: List[Dict[str, str]] = []
                temp_added_words_structured: List[Dict[str, str]] = []

                for tag_op, i1, i2, j1, j2 in sm_word.get_opcodes():
                    old_segment_list = old_words_list[i1:i2]
                    new_segment_list = new_words_list[j1:j2]
                    old_chunk = " ".join(old_segment_list)
                    new_chunk = " ".join(new_segment_list)

                    if tag_op == 'replace':
                        if old_chunk: temp_deleted_words_structured.append({"type": "removed", "content": old_chunk})
                        if new_chunk: temp_added_words_structured.append({"type": "added", "content": new_chunk})
                    elif tag_op == 'delete':
                        if old_chunk: temp_deleted_words_structured.append({"type": "removed", "content": old_chunk})
                    elif tag_op == 'insert':
                        if new_chunk: temp_added_words_structured.append({"type": "added", "content": new_chunk})
                    elif tag_op == 'equal':
                        if old_chunk: temp_deleted_words_structured.append({"type": "context", "content": old_chunk})
                        if new_chunk: temp_added_words_structured.append({"type": "context", "content": new_chunk})

                final_deleted_words = _condense_word_segments(temp_deleted_words_structured, old_words_list)
                final_added_words = _condense_word_segments(temp_added_words_structured, new_words_list)

                processed_lines.append({"type": "deletion", "content": old_content_str, "words": final_deleted_words})
                processed_lines.append({"type": "addition", "content": new_content_str, "words": final_added_words})

            i += 2
            continue

        if origin == '-':
            word_list = [{"type": "removed", "content": content.strip()}] if content.strip() else []
            processed_lines.append({"type": "deletion", "content": content, "words": word_list})
        elif origin == '+':
            word_list = [{"type": "added", "content": content.strip()}] if content.strip() else []
            processed_lines.append({"type": "addition", "content": content, "words": word_list})
        elif origin == ' ':
            processed_lines.append({"type": "context", "content": content})

        i += 1

    return processed_lines


def _condense_word_segments(segments: List[Dict[str, str]], original_words: List[str]) -> List[Dict[str, str]]:
    """
    Condenses adjacent word segments of the same type and ensures correct spacing.
    This is a simplified version and might need more robust space handling based on original text.
    """
    if not segments:
        return []

    condensed: List[Dict[str, str]] = []
    current_segment_content: List[str] = []
    current_segment_type = ""

    original_word_idx = 0

    for i, segment in enumerate(segments):
        num_words_in_segment = len(segment["content"].split())

        if not current_segment_type or segment["type"] != current_segment_type:
            if current_segment_content:
                condensed.append({"type": current_segment_type, "content": " ".join(current_segment_content)})
            current_segment_content = [segment["content"]]
            current_segment_type = segment["type"]
        else:
            current_segment_content.append(segment["content"])

        original_word_idx += num_words_in_segment

    if current_segment_type and current_segment_content:
        condensed.append({"type": current_segment_type, "content": " ".join(current_segment_content)})

    for seg in condensed:
        seg["content"] = seg["content"].strip()

    return [s for s in condensed if s["content"]]