from pathlib import Path
import pygit2
import os
import time
from typing import Optional, Dict, List, Any

# Common ignore patterns for .gitignore
COMMON_GITIGNORE_PATTERNS = [
    "*.pyc",
    "__pycache__/",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*.swn",
    # Add other common patterns as needed
]

def initialize_repository(path_str: str, project_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Initializes a new GitWrite repository or adds GitWrite structure to an existing one.

    Args:
        path_str: The string representation of the base path (e.g., current working directory).
        project_name: Optional name of the project directory to be created within path_str.

    Returns:
        A dictionary with 'status', 'message', and 'path' (if successful).
    """
    try:
        base_path = Path(path_str)
        if project_name:
            target_dir = base_path / project_name
        else:
            target_dir = base_path

        # 1. Target Directory Determination & Validation
        if project_name:
            if target_dir.is_file():
                return {'status': 'error', 'message': f"Error: A file named '{project_name}' already exists at '{base_path}'.", 'path': str(target_dir.resolve())}
            if not target_dir.exists():
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return {'status': 'error', 'message': f"Error: Could not create directory '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
            elif target_dir.exists() and any(target_dir.iterdir()) and not (target_dir / ".git").exists():
                return {'status': 'error', 'message': f"Error: Directory '{target_dir.name}' already exists, is not empty, and is not a Git repository.", 'path': str(target_dir.resolve())}
        else: # No project_name, using path_str as target_dir
            if any(target_dir.iterdir()) and not (target_dir / ".git").exists():
                 # Check if CWD is empty or already a git repo
                if not target_dir.is_dir(): # Should not happen if path_str is CWD
                    return {'status': 'error', 'message': f"Error: Target path '{target_dir}' is not a directory.", 'path': str(target_dir.resolve())}
                return {'status': 'error', 'message': f"Error: Current directory '{target_dir.name}' is not empty and not a Git repository. Specify a project name or run in an empty directory/Git repository.", 'path': str(target_dir.resolve())}

        # 2. Repository Initialization
        is_existing_repo = (target_dir / ".git").exists()
        repo: pygit2.Repository
        if is_existing_repo:
            try:
                repo = pygit2.Repository(str(target_dir))
            except pygit2.GitError as e:
                return {'status': 'error', 'message': f"Error: Could not open existing Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
        else:
            try:
                repo = pygit2.init_repository(str(target_dir))
            except pygit2.GitError as e:
                return {'status': 'error', 'message': f"Error: Could not initialize Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 3. GitWrite Structure Creation
        drafts_dir = target_dir / "drafts"
        notes_dir = target_dir / "notes"
        metadata_file = target_dir / "metadata.yml"

        try:
            drafts_dir.mkdir(exist_ok=True)
            (drafts_dir / ".gitkeep").touch(exist_ok=True)
            notes_dir.mkdir(exist_ok=True)
            (notes_dir / ".gitkeep").touch(exist_ok=True)
            if not metadata_file.exists():
                 metadata_file.write_text("# GitWrite Metadata\n# Add project-specific metadata here in YAML format.\n")
        except OSError as e:
            return {'status': 'error', 'message': f"Error: Could not create GitWrite directory structure in '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 4. .gitignore Management
        gitignore_file = target_dir / ".gitignore"
        gitignore_modified_or_created = False
        existing_ignores: List[str] = []

        if gitignore_file.exists():
            try:
                existing_ignores = gitignore_file.read_text().splitlines()
            except IOError as e:
                 return {'status': 'error', 'message': f"Error: Could not read existing .gitignore file at '{gitignore_file}'. {e}", 'path': str(target_dir.resolve())}


        new_ignores_added = False
        with open(gitignore_file, "a+") as f: # Open in append+read mode, create if not exists
            f.seek(0) # Go to the beginning to read existing content if any (though already read)
            # Ensure there's a newline before adding new patterns if file is not empty and doesn't end with one
            if f.tell() > 0: # File is not empty
                f.seek(0, os.SEEK_END) # Go to the end
                f.seek(f.tell() -1, os.SEEK_SET) # Go to last char
                if f.read(1) != '\n':
                    f.write('\n')

            for pattern in COMMON_GITIGNORE_PATTERNS:
                if pattern not in existing_ignores:
                    f.write(pattern + "\n")
                    new_ignores_added = True
                    if not gitignore_modified_or_created: # Record modification only once
                        gitignore_modified_or_created = True

        if not gitignore_file.exists() and new_ignores_added: # File was created
            gitignore_modified_or_created = True


        # 5. Staging Files
        items_to_stage_relative: List[str] = []
        # Paths must be relative to the repository root (target_dir) for staging
        drafts_gitkeep_rel = Path("drafts") / ".gitkeep"
        notes_gitkeep_rel = Path("notes") / ".gitkeep"
        metadata_yml_rel = Path("metadata.yml")

        items_to_stage_relative.append(str(drafts_gitkeep_rel))
        items_to_stage_relative.append(str(notes_gitkeep_rel))
        items_to_stage_relative.append(str(metadata_yml_rel))

        gitignore_rel_path_str = ".gitignore"

        # Check .gitignore status
        if gitignore_modified_or_created:
            items_to_stage_relative.append(gitignore_rel_path_str)
        elif is_existing_repo: # Even if not modified by us, stage it if it's untracked
            try:
                status = repo.status_file(gitignore_rel_path_str)
                if status == pygit2.GIT_STATUS_WT_NEW or status == pygit2.GIT_STATUS_WT_MODIFIED:
                     items_to_stage_relative.append(gitignore_rel_path_str)
            except KeyError: # File is not in index and not in working dir (e.g. after a clean)
                 if gitignore_file.exists(): # if it exists on disk, it's new
                    items_to_stage_relative.append(gitignore_rel_path_str)
            except pygit2.GitError as e:
                # Could fail if target_dir is not a repo, but we checked this
                pass # Best effort to check status


        staged_anything = False
        try:
            repo.index.read() # Load existing index if any

            for item_rel_path_str in items_to_stage_relative:
                item_abs_path = target_dir / item_rel_path_str
                if not item_abs_path.exists():
                    # This might happen if e.g. .gitkeep was deleted manually before commit
                    # Or if .gitignore was meant to be staged but somehow failed creation/modification silently
                    # For now, we'll try to add and let pygit2 handle it, or skip.
                    # Consider logging a warning if a robust logging system were in place.
                    continue

                # Check status to decide if it needs staging (especially for existing repos)
                try:
                    status = repo.status_file(item_rel_path_str)
                except KeyError: # File is not in index and not in working dir (but we know it exists)
                    status = pygit2.GIT_STATUS_WT_NEW # Treat as new if status_file errors due to not being tracked
                except pygit2.GitError: # Other potential errors with status_file
                    status = pygit2.GIT_STATUS_WT_NEW # Default to staging if status check fails


                # Stage if new, modified, or specifically marked for staging (like .gitignore)
                # GIT_STATUS_CURRENT is 0, means it's tracked and unmodified.
                if item_rel_path_str == gitignore_rel_path_str and gitignore_modified_or_created:
                    repo.index.add(item_rel_path_str)
                    staged_anything = True
                elif status & (pygit2.GIT_STATUS_WT_NEW | pygit2.GIT_STATUS_WT_MODIFIED | \
                             pygit2.GIT_STATUS_INDEX_NEW | pygit2.GIT_STATUS_INDEX_MODIFIED ):
                    repo.index.add(item_rel_path_str)
                    staged_anything = True
                elif item_rel_path_str in [str(drafts_gitkeep_rel), str(notes_gitkeep_rel), str(metadata_yml_rel)] and \
                     (status == pygit2.GIT_STATUS_WT_NEW or \
                      (not repo.head_is_unborn and item_rel_path_str not in repo.head.peel(pygit2.Commit).tree) or \
                      repo.head_is_unborn): # If unborn, any new file should be added
                     # If it's WT_NEW or not in current HEAD tree (and HEAD exists), or if repo is unborn, add it.
                     repo.index.add(item_rel_path_str)
                     staged_anything = True


            if staged_anything:
                repo.index.write()
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Error: Could not stage files in Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 6. Commit Creation
        if staged_anything or (is_existing_repo and repo.head_is_unborn): # Commit if files were staged or if it's a new repo (head_is_unborn)
            try:
                # Define author/committer
                author_name = "GitWrite System"
                author_email = "gitwrite@example.com" # Placeholder email
                author = pygit2.Signature(author_name, author_email)
                committer = pygit2.Signature(author_name, author_email)

                # Determine parents
                parents = []
                if not repo.head_is_unborn:
                    parents.append(repo.head.target)

                tree = repo.index.write_tree()

                # Check if tree actually changed compared to HEAD, or if it's the very first commit
                if repo.head_is_unborn or (parents and repo.get(parents[0]).tree_id != tree) or not parents:
                    commit_message_action = "Initialized GitWrite project structure in" if not is_existing_repo or repo.head_is_unborn else "Added GitWrite structure to"
                    commit_message = f"{commit_message_action} {target_dir.name}"

                    repo.create_commit(
                        "HEAD",          # ref_name
                        author,          # author
                        committer,       # committer
                        commit_message,  # message
                        tree,            # tree
                        parents          # parents
                    )
                    action_summary = "Initialized empty Git repository.\n" if not is_existing_repo else ""
                    action_summary += "Created GitWrite directory structure.\n"
                    action_summary += "Staged GitWrite files.\n"
                    action_summary += "Created GitWrite structure commit."
                    return {'status': 'success', 'message': action_summary.replace(".\n", f" in {target_dir.name}.\n").strip(), 'path': str(target_dir.resolve())}
                else:
                    # No changes to commit, but structure is there.
                    action_summary = "GitWrite structure already present and up-to-date."
                    if not is_existing_repo : action_summary = "Initialized empty Git repository.\n" + action_summary
                    return {'status': 'success', 'message': action_summary.replace(".\n", f" in {target_dir.name}.\n").strip(), 'path': str(target_dir.resolve())}

            except pygit2.GitError as e:
                return {'status': 'error', 'message': f"Error: Could not create commit in Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
        else:
            # No files were staged, means structure likely already exists and is tracked.
            message = "GitWrite structure already present and tracked."
            if not is_existing_repo : message = f"Initialized empty Git repository in {target_dir.name}.\n{message}"

            return {'status': 'success', 'message': message, 'path': str(target_dir.resolve())}

    except Exception as e:
        # Catch-all for unexpected errors
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}", 'path': str(target_dir.resolve() if 'target_dir' in locals() else base_path.resolve() if 'base_path' in locals() else path_str)}


def add_pattern_to_gitignore(repo_path_str: str, pattern: str) -> Dict[str, str]:
    """
    Adds a pattern to the .gitignore file in the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.
        pattern: The ignore pattern string to add.

    Returns:
        A dictionary with 'status' and 'message'.
    """
    try:
        gitignore_file_path = Path(repo_path_str) / ".gitignore"
        pattern_to_add = pattern.strip()

        if not pattern_to_add:
            return {'status': 'error', 'message': 'Pattern cannot be empty.'}

        existing_patterns: set[str] = set()
        last_line_had_newline = True # Assume true for new/empty file

        if gitignore_file_path.exists():
            try:
                content_data = gitignore_file_path.read_text()
                if content_data:
                    lines_data = content_data.splitlines()
                    for line_iter_ignore in lines_data:
                        existing_patterns.add(line_iter_ignore.strip())
                    if content_data.endswith("\n") or content_data.endswith("\r"):
                        last_line_had_newline = True
                    else:
                        last_line_had_newline = False
                # If content_data is empty, last_line_had_newline remains True (correct for writing)
            except (IOError, OSError) as e:
                return {'status': 'error', 'message': f"Error reading .gitignore: {e}"}

        if pattern_to_add in existing_patterns:
            return {'status': 'exists', 'message': f"Pattern '{pattern_to_add}' already exists in .gitignore."}

        try:
            with open(gitignore_file_path, "a") as f:
                if not last_line_had_newline:
                    f.write("\n")
                f.write(f"{pattern_to_add}\n")
            return {'status': 'success', 'message': f"Pattern '{pattern_to_add}' added to .gitignore."}
        except (IOError, OSError) as e:
            return {'status': 'error', 'message': f"Error writing to .gitignore: {e}"}

    except Exception as e: # Catch-all for unexpected issues like invalid repo_path_str
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}"}


def list_gitignore_patterns(repo_path_str: str) -> Dict[str, Any]:
    """
    Lists all patterns in the .gitignore file of the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.

    Returns:
        A dictionary with 'status', 'patterns' (list), and 'message'.
    """
    try:
        gitignore_file_path = Path(repo_path_str) / ".gitignore"

        if not gitignore_file_path.exists():
            return {'status': 'not_found', 'patterns': [], 'message': '.gitignore file not found.'}

        try:
            content_data_list = gitignore_file_path.read_text()
        except (IOError, OSError) as e:
            return {'status': 'error', 'patterns': [], 'message': f"Error reading .gitignore: {e}"}

        if not content_data_list.strip(): # empty or whitespace-only
            return {'status': 'empty', 'patterns': [], 'message': '.gitignore is empty.'}

        patterns_list = [line.strip() for line in content_data_list.splitlines() if line.strip()]
        return {'status': 'success', 'patterns': patterns_list, 'message': 'Successfully retrieved patterns.'}

    except Exception as e: # Catch-all for unexpected issues
        return {'status': 'error', 'patterns': [], 'message': f"An unexpected error occurred: {e}"}


def get_conflicting_files(conflicts_iterator) -> List[str]: # Copied from versioning.py for now
    """Helper function to extract path names from conflicts iterator.
    Assumes conflicts_iterator yields tuples of (ancestor_entry, our_entry, their_entry).
    """
    conflicting_paths = set() # Use a set to store paths to ensure uniqueness
    if conflicts_iterator:
        for conflict_tuple in conflicts_iterator:
            # Each element of the tuple is an IndexEntry or None
            ancestor_entry, our_entry, their_entry = conflict_tuple

            if our_entry is not None:
                conflicting_paths.add(our_entry.path)
            elif their_entry is not None: # Use elif as the path is the same for a single conflict
                conflicting_paths.add(their_entry.path)
            elif ancestor_entry is not None:
                conflicting_paths.add(ancestor_entry.path)
    return list(conflicting_paths)


def sync_repository(repo_path_str: str, remote_name: str = "origin", branch_name_opt: Optional[str] = None, push: bool = True, allow_no_push: bool = False) -> dict:
    """
    Synchronizes a local repository branch with its remote counterpart.
    It fetches changes, integrates them (fast-forward or merge), and optionally pushes.
    """
    from .exceptions import ( # Local import to avoid issues if this file is imported elsewhere early
        RepositoryNotFoundError, RepositoryEmptyError, DetachedHeadError,
        RemoteNotFoundError, BranchNotFoundError, FetchError,
        MergeConflictError, PushError, GitWriteError
    )
    import time # For fallback signature

    # Initialize return dictionary structure
    result_summary = {
        "status": "pending",
        "branch_synced": None,
        "remote": remote_name,
        "fetch_status": {"message": "Not performed"},
        "local_update_status": {"type": "none", "message": "Not performed", "conflicting_files": []},
        "push_status": {"pushed": False, "message": "Not performed"}
    }

    try:
        repo_discovered_path = pygit2.discover_repository(repo_path_str)
        if repo_discovered_path is None:
            raise RepositoryNotFoundError(f"Repository not found at or above '{repo_path_str}'.")
        repo = pygit2.Repository(repo_discovered_path)
    except pygit2.GitError as e:
        raise RepositoryNotFoundError(f"Error discovering repository at '{repo_path_str}': {e}")

    if repo.is_bare:
        raise GitWriteError("Cannot sync a bare repository.")
    if repo.is_empty or repo.head_is_unborn:
        raise RepositoryEmptyError("Repository is empty or HEAD is unborn. Cannot sync.")

    # Determine target local branch and its reference
    local_branch_name: str
    local_branch_ref: pygit2.Reference
    if branch_name_opt:
        local_branch_name = branch_name_opt
        try:
            local_branch_ref = repo.branches.local[local_branch_name]
        except KeyError:
            raise BranchNotFoundError(f"Local branch '{local_branch_name}' not found.")
    else:
        if repo.head_is_detached:
            raise DetachedHeadError("HEAD is detached. Please specify a branch to sync or checkout a branch.")
        local_branch_name = repo.head.shorthand
        local_branch_ref = repo.head

    result_summary["branch_synced"] = local_branch_name

    # Get remote
    try:
        remote = repo.remotes[remote_name]
    except KeyError:
        raise RemoteNotFoundError(f"Remote '{remote_name}' not found.")

    # 1. Fetch
    try:
        stats = remote.fetch()
        result_summary["fetch_status"] = {
            "received_objects": stats.received_objects,
            "total_objects": stats.total_objects,
            "message": "Fetch complete."
        }
    except pygit2.GitError as e:
        result_summary["fetch_status"] = {"message": f"Fetch failed: {e}"}
        raise FetchError(f"Failed to fetch from remote '{remote_name}': {e}")

    # 2. Integrate Remote Changes
    local_commit_oid = local_branch_ref.target
    remote_tracking_branch_name = f"refs/remotes/{remote_name}/{local_branch_name}"

    try:
        remote_branch_ref = repo.lookup_reference(remote_tracking_branch_name)
        their_commit_oid = remote_branch_ref.target
    except KeyError:
        # Remote tracking branch doesn't exist. This means local branch is new or remote was deleted.
        # We can only push if local branch has commits.
        result_summary["local_update_status"]["type"] = "no_remote_branch"
        result_summary["local_update_status"]["message"] = f"Remote tracking branch '{remote_tracking_branch_name}' not found. Assuming new local branch to be pushed."
        # Proceed to push logic if applicable
        pass
    else: # Remote tracking branch exists, proceed with merge/ff logic
        if local_commit_oid == their_commit_oid:
            result_summary["local_update_status"]["type"] = "up_to_date"
            result_summary["local_update_status"]["message"] = "Local branch is already up-to-date with remote."
        else:
            # Ensure HEAD is pointing to the local branch being synced
            if repo.head.target != local_branch_ref.target :
                 repo.checkout(local_branch_ref.name, strategy=pygit2.GIT_CHECKOUT_FORCE) # Switch to the branch
                 repo.set_head(local_branch_ref.name) # Ensure HEAD reference is updated

            ahead, behind = repo.ahead_behind(local_commit_oid, their_commit_oid)

            if ahead > 0 and behind == 0: # Local is ahead
                result_summary["local_update_status"]["type"] = "local_ahead"
                result_summary["local_update_status"]["message"] = "Local branch is ahead of remote. Nothing to merge/ff."
            elif behind > 0 : # Remote has changes, need to integrate
                merge_analysis_result, _ = repo.merge_analysis(their_commit_oid, local_branch_ref.name)

                if merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                    try:
                        local_branch_ref.set_target(their_commit_oid)
                        repo.checkout(local_branch_ref.name, strategy=pygit2.GIT_CHECKOUT_FORCE) # Update workdir
                        repo.set_head(local_branch_ref.name) # Update HEAD ref
                        result_summary["local_update_status"]["type"] = "fast_forwarded"
                        result_summary["local_update_status"]["message"] = f"Fast-forwarded '{local_branch_name}' to remote commit {str(their_commit_oid)[:7]}."
                        result_summary["local_update_status"]["commit_oid"] = str(their_commit_oid)
                    except pygit2.GitError as e:
                        result_summary["local_update_status"]["type"] = "error"
                        result_summary["local_update_status"]["message"] = f"Error during fast-forward: {e}"
                        raise GitWriteError(f"Failed to fast-forward branch '{local_branch_name}': {e}")

                elif merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                    repo.merge(their_commit_oid) # This updates the index

                    if repo.index.conflicts:
                        conflicting_files = get_conflicting_files(repo.index.conflicts)
                        repo.state_cleanup() # Clean up MERGE_MSG etc., but leave conflicts
                        result_summary["local_update_status"]["type"] = "conflicts_detected"
                        result_summary["local_update_status"]["message"] = "Merge resulted in conflicts. Please resolve them."
                        result_summary["local_update_status"]["conflicting_files"] = conflicting_files
                        # Do not raise MergeConflictError here, let the summary carry the info.
                        # The CLI can decide to raise or instruct based on this summary.
                        # For direct core usage, caller should check summary.
                        # However, the subtask asks for MergeConflictError to be raised.
                        raise MergeConflictError(
                            "Merge resulted in conflicts. Please resolve them.",
                            conflicting_files=conflicting_files
                        )
                    else: # No conflicts, create merge commit
                        try:
                            repo.index.write() # Persist merged index
                            tree_oid = repo.index.write_tree()

                            try:
                                author = repo.default_signature
                                committer = repo.default_signature
                            except pygit2.GitError:
                                current_time = int(time.time())
                                offset = 0 # UTC
                                author = pygit2.Signature("GitWrite Sync", "sync@example.com", current_time, offset)
                                committer = author

                            merge_commit_message = f"Merge remote-tracking branch '{remote_tracking_branch_name}' into {local_branch_name}"
                            new_merge_commit_oid = repo.create_commit(
                                local_branch_ref.name, # Update the local branch ref
                                author, committer, merge_commit_message, tree_oid,
                                [local_commit_oid, their_commit_oid] # Parents
                            )
                            repo.state_cleanup()
                                # Explicitly checkout the branch after merge and cleanup to ensure workdir and state are pristine
                            repo.checkout(local_branch_ref.name, strategy=pygit2.GIT_CHECKOUT_FORCE)
                            result_summary["local_update_status"]["type"] = "merged_ok"
                            result_summary["local_update_status"]["message"] = f"Successfully merged remote changes into '{local_branch_name}'."
                            result_summary["local_update_status"]["commit_oid"] = str(new_merge_commit_oid)
                        except pygit2.GitError as e:
                            result_summary["local_update_status"]["type"] = "error"
                            result_summary["local_update_status"]["message"] = f"Error creating merge commit: {e}"
                            raise GitWriteError(f"Failed to create merge commit for '{local_branch_name}': {e}")
                elif merge_analysis_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE: # Should have been caught by direct OID comparison
                    result_summary["local_update_status"]["type"] = "up_to_date"
                    result_summary["local_update_status"]["message"] = "Local branch is already up-to-date with remote."
                else: # Unborn, or other non-actionable states
                    result_summary["local_update_status"]["type"] = "error"
                    result_summary["local_update_status"]["message"] = "Merge not possible. Histories may have diverged or remote branch is unborn."
                    raise GitWriteError(result_summary["local_update_status"]["message"])
            # If ahead > 0 and behind > 0 (diverged), merge_analysis_normal should handle it.
            # If local is up to date (ahead == 0 and behind == 0), already handled.


    # 3. Push (if enabled)
    if push:
        try:
            # Check again if local is ahead of remote after potential merge/ff
            # This is important because ff/merge updates local_commit_oid
            current_local_head_oid = repo.branches.local[local_branch_name].target # Get updated local head

            remote_tracking_exists_for_push = True
            try:
                remote_branch_ref_for_push = repo.lookup_reference(remote_tracking_branch_name)
                their_commit_oid_for_push = remote_branch_ref_for_push.target
            except KeyError:
                remote_tracking_exists_for_push = False
                their_commit_oid_for_push = None # No remote tracking branch

            needs_push = False
            if not remote_tracking_exists_for_push:
                needs_push = True # New branch to push
            else:
                if current_local_head_oid != their_commit_oid_for_push:
                    # This check is simplified; proper ahead_behind might be needed if remote could also change concurrently
                    # For typical workflow, after merge/ff, local should be same or ahead.
                    # If it's same, nothing to push. If ahead, push.
                    push_ahead, push_behind = repo.ahead_behind(current_local_head_oid, their_commit_oid_for_push)
                    if push_ahead > 0 : needs_push = True
                    # If push_behind > 0 here, something is wrong (fetch/merge didn't work or concurrent remote change)

            if needs_push:
                refspec = f"refs/heads/{local_branch_name}:refs/heads/{local_branch_name}"
                remote.push([refspec])
                result_summary["push_status"]["pushed"] = True
                result_summary["push_status"]["message"] = "Push successful."
            else:
                result_summary["push_status"]["pushed"] = False
                result_summary["push_status"]["message"] = "Nothing to push. Local branch is not ahead of remote or is up-to-date."

        except pygit2.GitError as e:
            result_summary["push_status"]["pushed"] = False
            result_summary["push_status"]["message"] = f"Push failed: {e}"
            # Provide hints for common push errors
            if "non-fast-forward" in str(e).lower():
                hint = " (Hint: Remote has changes not present locally. Try syncing again.)"
            elif "authentication required" in str(e).lower() or "credentials" in str(e).lower():
                hint = " (Hint: Authentication failed. Check credentials/SSH keys.)"
            else:
                hint = ""
            raise PushError(f"Failed to push branch '{local_branch_name}' to '{remote_name}': {e}{hint}")
    elif not allow_no_push: # push is False but allow_no_push is also False
        # This case implies an expectation that push should have happened.
        # For core function, if caller explicitly sets push=False, we assume they know.
        # So, this branch might not be strictly necessary for core, more for CLI logic.
        # For now, just report that push was skipped.
        result_summary["push_status"]["message"] = "Push explicitly disabled by caller."
        result_summary["push_status"]["pushed"] = False
    else: # push is False and allow_no_push is True
         result_summary["push_status"]["message"] = "Push skipped as per 'allow_no_push'."
         result_summary["push_status"]["pushed"] = False


    # Determine overall status
    if result_summary["local_update_status"]["type"] == "conflicts_detected":
        result_summary["status"] = "success_conflicts"
    elif result_summary["push_status"].get("pushed") or (not push and allow_no_push):
        if result_summary["local_update_status"]["type"] == "up_to_date" and not result_summary["push_status"].get("pushed", False) and result_summary["push_status"]["message"] == "Nothing to push. Local branch is not ahead of remote or is up-to-date.":
             result_summary["status"] = "success_up_to_date_nothing_to_push"
        elif result_summary["local_update_status"]["type"] == "local_ahead" and result_summary["push_status"].get("pushed"):
             result_summary["status"] = "success" # Pushed local changes
        elif result_summary["local_update_status"]["type"] == "no_remote_branch" and result_summary["push_status"].get("pushed"):
             result_summary["status"] = "success_pushed_new_branch"
        else:
            result_summary["status"] = "success"
    elif result_summary["push_status"]["message"] == "Nothing to push. Local branch is not ahead of remote or is up-to-date.":
        result_summary["status"] = "success_nothing_to_push"
    else: # Default to success if no specific error/conflict status, but push might have failed if not caught by exception
        if "failed" not in result_summary["fetch_status"]["message"].lower() and \
           result_summary["local_update_status"]["type"] != "error" and \
           "failed" not in result_summary["push_status"]["message"].lower():
            result_summary["status"] = "success" # General success if no specific sub-errors
        else:
            result_summary["status"] = "error_in_sub_operation" # Some part failed but didn't raise fully

    return result_summary


def list_branches(repo_path_str: str) -> Dict[str, Any]:
    """
    Lists all local branches in the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.

    Returns:
        A dictionary with 'status', 'branches' (list of branch names), and 'message'.
    """
    branches_list: List[str] = []
    try:
        # Attempt to discover the repository if repo_path_str is not the .git folder directly
        try:
            repo_path = pygit2.discover_repository(repo_path_str)
            if repo_path is None:
                return {'status': 'error', 'branches': [], 'message': f"No Git repository found at or above '{repo_path_str}'."}
            repo = pygit2.Repository(repo_path)
        except pygit2.GitError: # Fallback for cases where discover_repository might not be suitable e.g. bare repo
             repo = pygit2.Repository(repo_path_str)


        if repo.is_bare:
            # For bare repositories, branches are listed directly.
            # repo.branches.local might not work as expected or might be empty
            # We can list all references under refs/heads/
            for ref_name in repo.listall_references():
                if ref_name.startswith("refs/heads/"):
                    branches_list.append(ref_name.replace("refs/heads/", ""))
        else:
            branches_list = list(repo.branches.local)

        if not branches_list and repo.is_empty: # Check if repo is empty and has no branches
             return {'status': 'empty_repo', 'branches': [], 'message': 'Repository is empty and has no branches.'}

        return {'status': 'success', 'branches': sorted(branches_list), 'message': 'Successfully retrieved local branches.'}
    except pygit2.GitError as e:
        return {'status': 'error', 'branches': [], 'message': f"Git error: {e}"}
    except Exception as e:
        return {'status': 'error', 'branches': [], 'message': f"An unexpected error occurred: {e}"}


def list_tags(repo_path_str: str) -> Dict[str, Any]:
    """
    Lists all tags in the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.

    Returns:
        A dictionary with 'status', 'tags' (list of tag names), and 'message'.
    """
    tags_list: List[str] = []
    try:
        try:
            repo_path = pygit2.discover_repository(repo_path_str)
            if repo_path is None:
                return {'status': 'error', 'tags': [], 'message': f"No Git repository found at or above '{repo_path_str}'."}
            repo = pygit2.Repository(repo_path)
        except pygit2.GitError:
            repo = pygit2.Repository(repo_path_str)

        # repo.listall_tags() is deprecated, use repo.references.iterator with "refs/tags/"
        for ref in repo.references.iterator():
            if ref.name.startswith("refs/tags/"):
                tags_list.append(ref.shorthand) # shorthand gives the tag name directly

        if not tags_list and repo.is_empty:
            return {'status': 'empty_repo', 'tags': [], 'message': 'Repository is empty and has no tags.'}
        elif not tags_list:
            return {'status': 'no_tags', 'tags': [], 'message': 'No tags found in the repository.'}

        return {'status': 'success', 'tags': sorted(tags_list), 'message': 'Successfully retrieved tags.'}
    except pygit2.GitError as e:
        return {'status': 'error', 'tags': [], 'message': f"Git error: {e}"}
    except Exception as e:
        return {'status': 'error', 'tags': [], 'message': f"An unexpected error occurred: {e}"}


def list_commits(repo_path_str: str, branch_name: Optional[str] = None, max_count: Optional[int] = None) -> Dict[str, Any]:
    """
    Lists commits for a given branch, or the current branch if branch_name is not provided.

    Args:
        repo_path_str: String path to the root of the repository.
        branch_name: Optional name of the branch. Defaults to the current branch (HEAD).
        max_count: Optional maximum number of commits to return.

    Returns:
        A dictionary with 'status', 'commits' (list of commit details), and 'message'.
    """
    commits_data: List[Dict[str, Any]] = []
    try:
        try:
            repo_path = pygit2.discover_repository(repo_path_str)
            if repo_path is None:
                return {'status': 'error', 'commits': [], 'message': f"No Git repository found at or above '{repo_path_str}'."}
            repo = pygit2.Repository(repo_path)
        except pygit2.GitError:
            repo = pygit2.Repository(repo_path_str)

        if repo.is_empty or repo.head_is_unborn:
            target_commit_oid = None
            if not branch_name: # No branch specified and repo is empty/unborn
                 return {'status': 'empty_repo', 'commits': [], 'message': 'Repository is empty or HEAD is unborn, and no branch specified.'}
            # If branch_name is specified, we'll try to find it, it might exist even if HEAD is unborn (e.g. bare repo)
        else:
            target_commit_oid = repo.head.target


        if branch_name:
            try:
                branch = repo.branches.get(branch_name) or repo.branches.get(f"origin/{branch_name}")
                if not branch: # Check remote branches if local not found
                    # Fallback for branches that might not be in `repo.branches` (e.g. some remote branches not fetched directly)
                    ref_lookup_name = f"refs/heads/{branch_name}"
                    if not repo.lookup_reference(ref_lookup_name): # try local first
                        ref_lookup_name = f"refs/remotes/origin/{branch_name}" # then common remote name
                        if not repo.lookup_reference(ref_lookup_name):
                             return {'status': 'error', 'commits': [], 'message': f"Branch '{branch_name}' not found."}
                    branch_ref = repo.lookup_reference(ref_lookup_name)
                    target_commit_oid = branch_ref.target
                else:
                    target_commit_oid = branch.target

            except KeyError:
                 return {'status': 'error', 'commits': [], 'message': f"Branch '{branch_name}' not found."}
            except pygit2.GitError: # Could be other GitError, e.g. ref is not direct
                 return {'status': 'error', 'commits': [], 'message': f"Error accessing branch '{branch_name}'."}
        elif repo.head_is_detached:
            # HEAD is detached, use its target directly. list_commits on current (detached) HEAD.
            target_commit_oid = repo.head.target

        if not target_commit_oid: # If still no target_commit_oid (e.g. empty repo and specific branch not found)
            # This case implies branch_name was given but not found in an empty/unborn repo.
            return {'status': 'error', 'commits': [], 'message': f"Branch '{branch_name}' not found or repository is empty."}


        count = 0
        for commit in repo.walk(target_commit_oid, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
            if max_count is not None and count >= max_count:
                break

            author_sig = commit.author
            committer_sig = commit.committer

            commits_data.append({
                'sha': str(commit.id),
                'message': commit.message.strip(),
                'author_name': author_sig.name,
                'author_email': author_sig.email,
                'author_date': author_sig.time, # Unix timestamp
                'committer_name': committer_sig.name,
                'committer_email': committer_sig.email,
                'committer_date': committer_sig.time, # Unix timestamp
                'parents': [str(p) for p in commit.parent_ids]
            })
            count += 1

        if not commits_data and (repo.is_empty or (branch_name and not commits_data)):
            # If we found a branch but it has no commits (e.g. orphaned branch or just initialized)
             message = f"No commits found for branch '{branch_name}'." if branch_name else "No commits found."
             if repo.is_empty : message = "Repository is empty." # More specific message for empty repo
             return {'status': 'no_commits', 'commits': [], 'message': message}


        return {'status': 'success', 'commits': commits_data, 'message': f'Successfully retrieved {len(commits_data)} commits.'}
    except pygit2.GitError as e:
        # Specific check for unborn head if no branch is specified
        if "unborn HEAD" in str(e).lower() and not branch_name:
             return {'status': 'empty_repo', 'commits': [], 'message': "Repository HEAD is unborn. Specify a branch or make an initial commit."}
        return {'status': 'error', 'commits': [], 'message': f"Git error: {e}"}
    except Exception as e:
        return {'status': 'error', 'commits': [], 'message': f"An unexpected error occurred: {e}"}


def save_and_commit_file(repo_path_str: str, file_path: str, content: str, commit_message: str, author_name: Optional[str] = None, author_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Saves a file's content to the specified path within a repository and commits it.

    Args:
        repo_path_str: The string representation of the repository's root path.
        file_path: The relative path of the file within the repository.
        content: The string content to be written to the file.
        commit_message: The message for the commit.
        author_name: Optional name of the commit author.
        author_email: Optional email of the commit author.

    Returns:
        A dictionary with 'status', 'message', and 'commit_id' (if successful).
    """
    try:
        repo_path = Path(repo_path_str)
        absolute_file_path = repo_path / file_path

        # Ensure file_path is treated as relative and does not try to escape the repo
        # Resolve paths to compare them reliably
        resolved_repo_path = repo_path.resolve()
        resolved_file_path = absolute_file_path.resolve()

        if not resolved_file_path.is_relative_to(resolved_repo_path):
            # Check if the resolved file path starts with the resolved repo path,
            # This is a more robust check for containment.
            if not str(resolved_file_path).startswith(str(resolved_repo_path)):
                 return {'status': 'error', 'message': 'File path is outside the repository.', 'commit_id': None}
            # If it starts with, but is_relative_to is False, it might be the same path.
            # Allow if it's the same (e.g. repo_path is a file itself, though unlikely for a repo root)
            # However, typical usage is file_path is a file *within* repo_path directory.
            # The check `str(resolved_file_path).startswith(str(resolved_repo_path))` handles most cases.
            # A direct equality check for resolved paths can be added if files can be repos.
            # For now, if `is_relative_to` fails, we double check with startswith.

        # Create parent directories if they don't exist
        try:
            absolute_file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {'status': 'error', 'message': f"Error creating directories: {e}", 'commit_id': None}

        # Write the content to the file
        try:
            with open(absolute_file_path, "w") as f:
                f.write(content)
        except IOError as e:
            return {'status': 'error', 'message': f"Error writing file: {e}", 'commit_id': None}

        # Open the repository
        try:
            # Use resolved path for consistency, though pygit2 usually handles it.
            repo = pygit2.Repository(str(resolved_repo_path))
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Repository not found or invalid: {e}", 'commit_id': None}

        # Stage the file
        try:
            # file_path must be relative to the repository workdir for add()
            # os.path.relpath is safer for this.
            relative_file_path = os.path.relpath(str(resolved_file_path), repo.workdir)
            repo.index.add(relative_file_path)
            repo.index.write()
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Error staging file: {e}", 'commit_id': None}
        except Exception as e:
            return {'status': 'error', 'message': f"An unexpected error occurred during staging: {e}", 'commit_id': None}

        # Create the commit
        try:
            current_time = int(time.time())
            # Get local timezone offset in minutes
            # time.timezone gives offset in seconds WEST of UTC (negative for EAST)
            # pygit2.Signature expects offset in minutes EAST of UTC (positive for EAST)
            local_offset_seconds = -time.timezone if not time.daylight else -time.altzone
            tz_offset_minutes = local_offset_seconds // 60

            # Determine committer details
            try:
                committer_signature_obj = repo.default_signature
                # If default_signature exists, use its name, email, and time (but override time with current_time for consistency)
                # pygit2.Signature time is a combination of timestamp and offset.
                # We'll use current_time and the system's current tz_offset_minutes for the committer.
                # This ensures the committer timestamp is always "now".
                # The offset from default_signature is repo-configured, which is good to respect.
                committer_name = committer_signature_obj.name
                committer_email = committer_signature_obj.email
                # Use default_signature's offset if available, otherwise current system's
                committer_offset = committer_signature_obj.offset if hasattr(committer_signature_obj, 'offset') else tz_offset_minutes
                committer_signature = pygit2.Signature(committer_name, committer_email, current_time, committer_offset)
            except pygit2.GitError: # Default signature not set in git config
                committer_name = "GitWrite System"
                committer_email = "gitwrite@example.com"
                committer_signature = pygit2.Signature(committer_name, committer_email, current_time, tz_offset_minutes)

            # Determine author details
            if author_name and author_email:
                # Use provided author details with current time and system's current timezone offset
                author_signature = pygit2.Signature(author_name, author_email, current_time, tz_offset_minutes)
            else:
                # Fallback to committer details for author
                author_signature = committer_signature


            tree_id = repo.index.write_tree() # Get OID of tree from index
            parents = [] if repo.head_is_unborn else [repo.head.target]

            commit_oid = repo.create_commit(
                "HEAD",                    # Update the current branch (ref_name)
                author_signature,          # Author
                committer_signature,       # Committer
                commit_message,
                tree_id,                   # Tree OID
                parents
            )
            return {'status': 'success', 'message': 'File saved and committed successfully.', 'commit_id': str(commit_oid)}
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Error committing file: {e}", 'commit_id': None}
        except Exception as e:
            return {'status': 'error', 'message': f"An unexpected error occurred during commit: {e}", 'commit_id': None}

    except Exception as e:
        # Catch-all for unexpected errors at the function level
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}", 'commit_id': None}


def save_and_commit_multiple_files(repo_path_str: str, files_to_commit: Dict[str, str], commit_message: str, author_name: Optional[str] = None, author_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Saves multiple files to the repository and creates a single commit with all changes.

    Args:
        repo_path_str: The string representation of the repository's root path.
        files_to_commit: A dictionary where keys are relative paths within the repository
                         (e.g., "drafts/chapter1.txt") and values are absolute paths
                         to the temporary uploaded files on the server.
        commit_message: The message for the commit.
        author_name: Optional name of the commit author.
        author_email: Optional email of the commit author.

    Returns:
        A dictionary with 'status', 'message', and 'commit_id' (if successful).
    """
    import shutil # For shutil.copyfile
    import os # For path normalization and checking

    try:
        repo_path = Path(repo_path_str)
        resolved_repo_path = repo_path.resolve()

        try:
            repo = pygit2.Repository(str(resolved_repo_path))
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Repository not found or invalid: {e}", 'commit_id': None}

        if repo.is_bare:
            return {'status': 'error', 'message': "Operation not supported on bare repositories.", 'commit_id': None}

        # Ensure index is fresh before starting operations
        repo.index.read()

        for relative_repo_file_path_str, temp_file_abs_path_str in files_to_commit.items():
            # Ensure relative_repo_file_path_str is indeed relative and safe
            if Path(relative_repo_file_path_str).is_absolute() or ".." in relative_repo_file_path_str:
                return {'status': 'error', 'message': f"Invalid relative file path: {relative_repo_file_path_str}", 'commit_id': None}

            absolute_target_path = resolved_repo_path / relative_repo_file_path_str

            # Path safety check: Ensure the target path is within the repository boundaries.
            # Normalizing paths helps in comparing them reliably.
            normalized_repo_path = os.path.normpath(str(resolved_repo_path))
            normalized_target_path = os.path.normpath(str(absolute_target_path))

            # Check if the normalized target path starts with the normalized repo path.
            # Add os.sep to ensure it's a subdirectory match, not just a prefix match (e.g. /repo vs /repo-something)
            # However, if relative_repo_file_path_str can be just a filename at root, direct startswith is fine.
            # For robustness with subdirectories:
            if not normalized_target_path.startswith(normalized_repo_path + os.sep) and normalized_target_path != normalized_repo_path:
                # If relative_repo_file_path_str can be empty or ".", target could be same as repo path.
                # This case needs to be handled if files can be written to the root itself directly by an empty relative path.
                # Assuming relative_repo_file_path_str will always point to a file *name*,
                # so `normalized_target_path` will always be longer or different if escaping.
                # A more direct check:
                # common_path = os.path.commonpath([normalized_target_path, normalized_repo_path])
                # if common_path != normalized_repo_path:
                # A simpler and often effective check is direct prefix after normalization.
                # If target is exactly repo path (e.g. trying to overwrite repo dir with a file), it's also an issue.
                # Path.is_relative_to (Python 3.9+) would be ideal here.
                # For now, combining startswith with a check against direct equality for the repo path itself.
                if not normalized_target_path.startswith(normalized_repo_path): # General check
                    return {'status': 'error', 'message': f"File path '{relative_repo_file_path_str}' escapes repository.", 'commit_id': None}
                # If it starts with, but is not a sub-path (e.g. /foo/bar vs /foo/barista), commonpath is better.
                # Let's use commonpath for clarity.
                common_base = os.path.commonpath([normalized_target_path, normalized_repo_path])
                if common_base != normalized_repo_path:
                    return {'status': 'error', 'message': f"File path '{relative_repo_file_path_str}' escapes repository boundaries.", 'commit_id': None}
                # Prevent writing directly to the .git directory or other sensitive paths.
                # This part could be expanded with more checks if needed.
                if ".git" in Path(relative_repo_file_path_str).parts:
                     return {'status': 'error', 'message': f"File path '{relative_repo_file_path_str}' targets a restricted directory.", 'commit_id': None}


            # Create parent directories if they don't exist
            try:
                absolute_target_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return {'status': 'error', 'message': f"Error creating directories for '{relative_repo_file_path_str}': {e}", 'commit_id': None}

            # Copy the temporary file to the target path
            try:
                shutil.copyfile(temp_file_abs_path_str, absolute_target_path)
            except IOError as e:
                return {'status': 'error', 'message': f"Error copying file '{temp_file_abs_path_str}' to '{absolute_target_path}': {e}", 'commit_id': None}

            # Stage the file
            try:
                # Path for add() must be relative to the repository workdir
                repo.index.add(relative_repo_file_path_str)
            except pygit2.GitError as e:
                return {'status': 'error', 'message': f"Error staging file '{relative_repo_file_path_str}': {e}", 'commit_id': None}
            except Exception as e: # Catch other potential errors like invalid path for index
                return {'status': 'error', 'message': f"An unexpected error occurred staging '{relative_repo_file_path_str}': {e}", 'commit_id': None}

        # Write the index after all files are added
        try:
            repo.index.write()
        except pygit2.GitError as e:
            return {'status': 'error', 'message': f"Error writing index: {e}", 'commit_id': None}

        # Create the commit
        try:
            current_time = int(time.time())
            local_offset_seconds = -time.timezone if not time.daylight else -time.altzone
            tz_offset_minutes = local_offset_seconds // 60

            try:
                default_sig = repo.default_signature
                committer_name = default_sig.name
                committer_email = default_sig.email
                committer_offset = default_sig.offset
                committer_signature = pygit2.Signature(committer_name, committer_email, current_time, committer_offset)
            except pygit2.GitError: # Default signature not set
                committer_name = "GitWrite System"
                committer_email = "gitwrite@example.com"
                committer_signature = pygit2.Signature(committer_name, committer_email, current_time, tz_offset_minutes)

            if author_name and author_email:
                author_signature = pygit2.Signature(author_name, author_email, current_time, tz_offset_minutes)
            else:
                author_signature = committer_signature # Fallback to committer details

            tree_id = repo.index.write_tree()
            parents = [] if repo.head_is_unborn else [repo.head.target]

            # Check if there are actual changes to commit
            if not parents: # First commit
                pass # Always commit if it's the first one
            else:
                # Compare new tree with HEAD's tree
                head_commit = repo.get(parents[0])
                if head_commit and head_commit.tree_id == tree_id:
                    # Check if the index is dirty (e.g. new files added, mode changes, etc.)
                    # even if the tree content hash is the same (unlikely for new files but good to check).
                    # A simple way is to check if there are any changes between HEAD tree and index tree.
                    # repo.diff_tree_to_index(head_commit.tree, repo.index) will show changes.
                    # For simplicity, if tree_id is same, assume no content changes relevant for commit unless index was modified.
                    # The act of `repo.index.add()` and `repo.index.write()` should make it "dirty" enough
                    # if new files were added or existing tracked files changed.
                    # If only untracked files were "added" that were already gitignored, tree might not change.
                    # But our loop explicitly adds files, so they should be in the index.
                    # A more robust check:
                    if not repo.status(): # If status is empty, no changes
                        return {'status': 'no_changes', 'message': 'No changes to commit.', 'commit_id': None}

            commit_oid = repo.create_commit(
                "HEAD",
                author_signature,
                committer_signature,
                commit_message,
                tree_id,
                parents
            )
            return {'status': 'success', 'message': 'Files committed successfully.', 'commit_id': str(commit_oid)}
        except pygit2.GitError as e:
            # It's possible to get an error here if the tree is identical to HEAD and no changes were staged
            # pygit2.GitError: 'failed to create commit: current tip is not the first parent' if parents is not empty
            # and tree is identical. Let's refine the "no_changes" check.
            if "nothing to commit" in str(e).lower() or (repo.head and not repo.head_is_unborn and repo.head.peel(pygit2.Commit).tree_id == tree_id):
                 return {'status': 'no_changes', 'message': 'No changes to commit.', 'commit_id': None}
            return {'status': 'error', 'message': f"Error committing files: {e}", 'commit_id': None}
        except Exception as e:
            return {'status': 'error', 'message': f"An unexpected error occurred during commit: {e}", 'commit_id': None}

    except Exception as e:
        # Catch-all for unexpected errors at the function level
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}", 'commit_id': None}
