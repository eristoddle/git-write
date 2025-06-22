import pygit2
import pygit2.enums # Added for MergeFavor
# import pygit2.ops # ModuleNotFoundError with pygit2 1.18.0
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
