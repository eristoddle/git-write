import pygit2
from pathlib import Path
from typing import List, Dict, Any, Optional # Added Optional
from .exceptions import ( # Ensure all are imported, including BranchNotFoundError and MergeConflictError
    RepositoryNotFoundError,
    RepositoryEmptyError,
    BranchAlreadyExistsError,
    BranchNotFoundError, # Already added in a previous step, ensure it stays
    MergeConflictError, # Added for merge function
    GitWriteError
)

def create_and_switch_branch(repo_path_str: str, branch_name: str) -> Dict[str, Any]: # Updated return type
    """
    Creates a new branch from the current HEAD and switches to it.

    Args:
        repo_path_str: The path to the repository.
        branch_name: The name for the new branch.

    Returns:
        A dictionary with details of the created branch.
        e.g., {'status': 'success', 'branch_name': 'feature-branch', 'head_commit_oid': 'abcdef123...'}

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        RepositoryEmptyError: If the repository is empty or HEAD is unborn.
        BranchAlreadyExistsError: If the branch already exists.
        GitWriteError: For other git-related issues or if operating on a bare repository.
    """
    try:
        discovered_repo_path = pygit2.discover_repository(repo_path_str)
        if discovered_repo_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")

        repo = pygit2.Repository(discovered_repo_path)

        if repo.is_bare:
            raise GitWriteError("Operation not supported in bare repositories.")

        # Check if HEAD is unborn before trying to peel it.
        # repo.is_empty also implies HEAD is unborn for newly initialized repos.
        if repo.head_is_unborn: # Covers repo.is_empty for practical purposes of creating a branch from HEAD
            raise RepositoryEmptyError("Cannot create branch: HEAD is unborn. Commit changes first.")

        if branch_name in repo.branches.local:
            raise BranchAlreadyExistsError(f"Branch '{branch_name}' already exists.")

        # Get the commit object for HEAD
        # Ensure HEAD is valid and points to a commit.
        try:
            head_commit = repo.head.peel(pygit2.Commit)
        except pygit2.GitError as e:
            # This can happen if HEAD is detached or points to a non-commit object,
            # though head_is_unborn should catch most common cases.
            raise GitWriteError(f"Could not resolve HEAD to a commit: {e}")

        # Create the new branch
        new_branch = repo.branches.local.create(branch_name, head_commit)

        refname = new_branch.name # This is already the full refname, e.g., "refs/heads/mybranch"

        # Checkout the new branch
        repo.checkout(refname, strategy=pygit2.GIT_CHECKOUT_SAFE)

        # Set HEAD to the new branch reference
        repo.set_head(refname)

        return {
            'status': 'success',
            'branch_name': branch_name,
            'head_commit_oid': str(repo.head.target) # OID of the commit HEAD now points to
        }

    except pygit2.GitError as e:
        # Catch pygit2 errors that were not caught by more specific checks
        # This helps prevent leaking pygit2 specific exceptions
        raise GitWriteError(f"Git operation failed: {e}")
    # Custom exceptions (RepositoryNotFoundError, RepositoryEmptyError, BranchAlreadyExistsError, GitWriteError from checks)
    # will propagate up as they are already GitWriteError subclasses or GitWriteError itself.

def list_branches(repo_path_str: str) -> List[Dict[str, Any]]:
    """
    Lists all local branches in the repository.

    Args:
        repo_path_str: The path to the repository.

    Returns:
        A list of dictionaries, where each dictionary contains details of a branch
        (name, is_current, target_oid). Sorted by branch name.
        Returns an empty list if the repository is empty or has no branches.

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        GitWriteError: For other git-related issues like bare repo.
    """
    try:
        discovered_repo_path = pygit2.discover_repository(repo_path_str)
        if discovered_repo_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")

        repo = pygit2.Repository(discovered_repo_path)

        if repo.is_bare:
            raise GitWriteError("Operation not supported in bare repositories.")

        if repo.is_empty or repo.head_is_unborn:
            # If the repo is empty or HEAD is unborn, there are no branches to list in a meaningful way.
            # repo.branches.local would be empty or operations might be ill-defined.
            return []

        branches_data_list = []
        current_head_full_ref_name = None
        if not repo.head_is_detached:
            current_head_full_ref_name = repo.head.name # e.g., "refs/heads/main"

        for branch_name_str in repo.branches.local: # Assuming this iterates over string names now based on error
            # Convert shorthand name to full reference name for comparison
            full_ref_name_of_iterated_branch = f"refs/heads/{branch_name_str}"

            is_current = (current_head_full_ref_name is not None) and \
                         (full_ref_name_of_iterated_branch == current_head_full_ref_name)

            # To get the target OID, we need to look up the branch object by its string name
            branch_lookup = repo.branches.local.get(branch_name_str)
            target_oid = str(branch_lookup.target) if branch_lookup else None # Handle if lookup fails (should not happen in this loop)

            branches_data_list.append({
                'name': branch_name_str, # The string itself is the short name
                'is_current': is_current,
                'target_oid': target_oid
            })

        # Sort by branch name (which is the short name)
        return sorted(branches_data_list, key=lambda b: b['name'])

    except pygit2.GitError as e:
        # Catch specific pygit2 errors if necessary, or generalize
        raise GitWriteError(f"Git operation failed while listing branches: {e}")
    # Custom exceptions like RepositoryNotFoundError, GitWriteError from specific checks,
    # will propagate up.

def switch_to_branch(repo_path_str: str, branch_name: str) -> Dict[str, Any]:
    """
    Switches to an existing local or remote-tracking branch.
    If switching to a remote-tracking branch, HEAD will be detached at the commit.

    Args:
        repo_path_str: The path to the repository.
        branch_name: The name of the branch to switch to. Can be a short name
                     (e.g., "myfeature") or a full remote branch name if not ambiguous
                     (e.g., "origin/myfeature").

    Returns:
        A dictionary with status and details.
        e.g., {'status': 'success', 'branch_name': 'main', ...}
              {'status': 'already_on_branch', 'branch_name': 'main', ...}

    Raises:
        RepositoryNotFoundError: If the repository is not found.
        BranchNotFoundError: If the specified branch cannot be found.
        RepositoryEmptyError: If trying to switch in a repo that's empty and HEAD is unborn (relevant for some initial state checks).
        GitWriteError: For other git-related issues like bare repo or checkout failures.
    """
    try:
        discovered_repo_path = pygit2.discover_repository(repo_path_str)
        if discovered_repo_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")

        repo = pygit2.Repository(discovered_repo_path)

        if repo.is_bare:
            raise GitWriteError("Operation not supported in bare repositories.")

        # Capture previous state before any operation
        previous_branch_name = None
        is_initially_detached = repo.head_is_detached
        initial_head_oid = None
        if not repo.head_is_unborn:
            initial_head_oid = str(repo.head.target)
            if not is_initially_detached:
                previous_branch_name = repo.head.shorthand
        elif repo.is_empty: # If repo is empty, head is also unborn.
             # No previous branch, and cannot switch FROM an empty/unborn state if target also doesn't exist.
             # This specific check might be redundant if branch resolution fails gracefully.
             # However, if branch_name *is* the current unborn HEAD's ref (unlikely for user input), it's "already on branch".
             pass


        target_branch_obj = None
        is_local_branch_target = False

        # Try local branches first
        local_candidate = repo.branches.local.get(branch_name)
        if local_candidate:
            target_branch_obj = local_candidate
            is_local_branch_target = True
        else: # Not a local branch
            # Try remote-tracking branches
            # 1. Try the name as given (e.g. "origin/foo", "downstream/foo")
            target_branch_obj = repo.branches.remote.get(branch_name)

            # 2. If not found, and name was "origin/foo", try "origin/origin/foo"
            #    This handles the specific case in tests where remote branch is named "origin/branch"
            #    which becomes "origin/origin/branch" as a pygit2 remote-tracking branch.
            if not target_branch_obj and branch_name.startswith("origin/"):
                doubled_origin_name = f"origin/{branch_name}" # Creates "origin/origin/foo"
                target_branch_obj = repo.branches.remote.get(doubled_origin_name)

            # 3. If still not found, and it was a short name (e.g. "foo"), try "origin/foo"
            if not target_branch_obj and '/' not in branch_name:
                target_branch_obj = repo.branches.remote.get(f"origin/{branch_name}")

        if not target_branch_obj:
            # If still not found, and repo is empty/unborn, it's a clearer error.
            if repo.is_empty or repo.head_is_unborn:
                 raise RepositoryEmptyError(f"Cannot switch branch in an empty repository to non-existent branch '{branch_name}'.")
            raise BranchNotFoundError(f"Branch '{branch_name}' not found locally or on common remotes.")

        target_refname = target_branch_obj.name # Full refname (e.g., "refs/heads/main" or "refs/remotes/origin/main")

        # Check if already on the target branch (only if target is local and HEAD is not detached)
        if is_local_branch_target and not is_initially_detached and not repo.head_is_unborn and repo.head.name == target_refname:
            return {
                'status': 'already_on_branch',
                'branch_name': target_branch_obj.branch_name, # Use resolved short name
                'head_commit_oid': initial_head_oid
            }

        # Perform the checkout
        try:
            repo.checkout(target_refname, strategy=pygit2.GIT_CHECKOUT_SAFE)
        except pygit2.GitError as e:
            # More specific error if checkout fails due to working directory changes
            if "workdir contains unstaged changes" in str(e).lower() or "local changes overwrite" in str(e).lower():
                 raise GitWriteError(f"Checkout failed: Your local changes to tracked files would be overwritten by checkout of '{target_branch_obj.branch_name}'. Please commit your changes or stash them.")
            raise GitWriteError(f"Checkout operation failed for '{target_branch_obj.branch_name}': {e}")

        # Post-checkout state
        current_head_is_detached = repo.head_is_detached

        # If we checked out a local branch ref, ensure HEAD points to the symbolic ref.
        if is_local_branch_target:
            repo.set_head(target_refname) # Update symbolic HEAD to point to the local branch
            # After set_head, it should not be detached if target_refname was a local branch.
            current_head_is_detached = repo.head_is_detached
                                     # (should be False, unless target_refname was somehow not a proper local branch ref string)

        # Determine the name to return in the result.
        # If it was a local branch, target_branch_obj.branch_name is its short name (e.g. "main").
        # If it was a remote branch, we want to return the name the user used to find it
        # (e.g., "feature" that resolved to "origin/feature", or "origin/special-feature" that resolved
        # to "origin/origin/special-feature").
        # Consistently return the actual resolved branch name from the target object.
        returned_branch_name = target_branch_obj.branch_name

        return {
            'status': 'success',
            'branch_name': returned_branch_name, # This is now always target_branch_obj.branch_name
            'previous_branch_name': previous_branch_name,
            'head_commit_oid': str(repo.head.target),
            'is_detached': current_head_is_detached
        }

    except pygit2.GitError as e:
        # General pygit2 errors not caught by specific handlers above
        raise GitWriteError(f"Git operation failed during switch to branch '{branch_name}': {e}")
    # Custom exceptions (RepositoryNotFoundError, BranchNotFoundError, etc.) will propagate.

def merge_branch_into_current(repo_path_str: str, branch_to_merge_name: str) -> Dict[str, Any]:
    """
    Merges the specified branch into the current branch.

    Args:
        repo_path_str: Path to the repository.
        branch_to_merge_name: Name of the branch to merge.

    Returns:
        A dictionary describing the outcome (up_to_date, fast_forwarded, merged_ok).

    Raises:
        RepositoryNotFoundError: If the repository path is not found or not a git repo.
        BranchNotFoundError: If the branch_to_merge_name cannot be found.
        RepositoryEmptyError: If the repository is empty or HEAD is unborn.
        MergeConflictError: If the merge results in conflicts.
        GitWriteError: For other issues (e.g., bare repo, detached HEAD, user not configured).
    """
    try:
        discovered_repo_path = pygit2.discover_repository(repo_path_str)
        if discovered_repo_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")

        repo = pygit2.Repository(discovered_repo_path)

        if repo.is_bare:
            raise GitWriteError("Cannot merge in a bare repository.")
        if repo.is_empty or repo.head_is_unborn: # Check before accessing repo.head
            raise RepositoryEmptyError("Repository is empty or HEAD is unborn. Cannot perform merge.")
        if repo.head_is_detached:
            raise GitWriteError("HEAD is detached. Please switch to a branch to perform a merge.")

        current_branch_shorthand = repo.head.shorthand # Safe now due to above checks

        if current_branch_shorthand == branch_to_merge_name:
            raise GitWriteError("Cannot merge a branch into itself.")

        # Resolve branch_to_merge_name to a commit object
        target_branch_obj = repo.branches.local.get(branch_to_merge_name)
        if not target_branch_obj:
            remote_ref_name = f"origin/{branch_to_merge_name}"
            target_branch_obj = repo.branches.remote.get(remote_ref_name)
            if not target_branch_obj:
                if '/' in branch_to_merge_name and repo.branches.remote.get(branch_to_merge_name):
                    target_branch_obj = repo.branches.remote.get(branch_to_merge_name)
                else:
                    raise BranchNotFoundError(f"Branch '{branch_to_merge_name}' not found locally or as 'origin/{branch_to_merge_name}'.")

        # Ensure we have a commit object to merge
        target_commit_obj_merge = repo.get(target_branch_obj.target).peel(pygit2.Commit)

        # Perform merge analysis
        merge_analysis_result, _ = repo.merge_analysis(target_commit_obj_merge.id)

        if merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
            return {'status': 'up_to_date', 'branch_name': branch_to_merge_name, 'current_branch': current_branch_shorthand}

        elif merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
            current_branch_ref = repo.lookup_reference(repo.head.name)
            current_branch_ref.set_target(target_commit_obj_merge.id)
            repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE)
            return {
                'status': 'fast_forwarded',
                'branch_name': branch_to_merge_name,
                'current_branch': current_branch_shorthand,
                'commit_oid': str(target_commit_obj_merge.id)
            }

        elif merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
            repo.merge(target_commit_obj_merge.id) # This sets MERGE_HEAD

            conflicting_files_paths: List[str] = []
            if repo.index.conflicts is not None:
                for conflict_entry_tuple in repo.index.conflicts:
                    path = next((entry.path for entry in conflict_entry_tuple if entry and entry.path), None)
                    if path and path not in conflicting_files_paths:
                        conflicting_files_paths.append(path)

            if conflicting_files_paths:
                raise MergeConflictError(
                    message=f"Automatic merge of '{target_branch_obj.branch_name}' into '{current_branch_shorthand}' failed due to conflicts.",
                    conflicting_files=sorted(conflicting_files_paths)
                )

            # No conflicts, proceed to create merge commit
            try:
                author_sig = repo.default_signature
                committer_sig = repo.default_signature
            except ValueError as e: # Primarily for empty name/email from local config
                if "failed to parse signature" in str(e).lower():
                    raise GitWriteError("User signature (user.name and user.email) not configured in Git.")
                else:
                    # If ValueError is for something else, re-raise or wrap differently if needed
                    raise GitWriteError(f"Unexpected signature issue: {e}")
            except pygit2.GitError as e: # Catch other pygit2 errors, e.g. if config truly not found
                 # Check if it's a "not found" error for user.name or user.email
                if "config value 'user.name' was not found" in str(e).lower() or \
                   "config value 'user.email' was not found" in str(e).lower():
                    raise GitWriteError("User signature (user.name and user.email) not configured in Git.")
                raise GitWriteError(f"Git operation failed while obtaining signature: {e}") # General GitError


            tree = repo.index.write_tree()
            parents = [repo.head.target, target_commit_obj_merge.id]
            # Use resolved short name of merged branch for message clarity if it was remote
            resolved_merged_branch_name = target_branch_obj.branch_name
            merge_commit_msg_text = f"Merge branch '{resolved_merged_branch_name}' into {current_branch_shorthand}"

            new_commit_oid = repo.create_commit(
                "HEAD", author_sig, committer_sig,
                merge_commit_msg_text, tree, parents
            )
            repo.index.write() # Ensure index reflects the merge commit
            repo.index.read()  # Explicitly reload the index
            repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE)
            repo.state_cleanup()
            return {
                'status': 'merged_ok',
                'branch_name': resolved_merged_branch_name, # Name of the branch that was merged
                'current_branch': current_branch_shorthand, # Branch that was merged into
                'commit_oid': str(new_commit_oid)
            }
        else:
            if merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_UNBORN:
                 raise GitWriteError(f"Merge not possible: HEAD or '{target_branch_obj.branch_name}' is an unborn branch.")
            raise GitWriteError(f"Merge not possible for '{target_branch_obj.branch_name}' into '{current_branch_shorthand}'. Analysis result code: {merge_analysis_result}")

    except pygit2.GitError as e:
        raise GitWriteError(f"Git operation failed during merge of '{branch_to_merge_name}': {e}")
    # Custom exceptions like RepositoryNotFoundError, BranchNotFoundError etc. will propagate.
