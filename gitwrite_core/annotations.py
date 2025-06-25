# Core Annotation Handling Logic
# This module will contain functions for creating, listing, and managing annotations.

from typing import List, Dict, Optional
import yaml # For storing annotation data in commit bodies
import os
from pathlib import Path

# Assuming git library like 'gitpython' might be used, or direct CLI calls.
# For now, we'll conceptualize with direct CLI calls or a helper.
# from git import Repo, GitCommandError # Example if GitPython is available

from gitwrite_api.models import Annotation, AnnotationStatus
import subprocess
from .exceptions import AnnotationError, RepositoryOperationError


# Helper function to run git commands
def _run_git_command(repo_path: str, command: List[str], expect_stdout: bool = True) -> str:
    """
    Runs a git command in the specified repository path.
    Raises RepositoryOperationError for command failures.
    """
    try:
        process = subprocess.run(
            ['git', '-C', repo_path] + command,  # Use -C to specify repository path
            capture_output=True,
            text=True,
            check=True
        )
        return process.stdout.strip() if expect_stdout else ""
    except subprocess.CalledProcessError as e:
        error_message = f"Git command failed: {' '.join(command)}\nError: {e.stderr.strip()}"
        # Try to get current branch to add to error context
        try:
            current_branch_process = subprocess.run(
                ['git', '-C', repo_path, 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, check=False
            )
            current_branch = current_branch_process.stdout.strip() if current_branch_process.returncode == 0 else "unknown"
            error_message += f"\nCurrent branch: {current_branch}"
        except Exception:
            pass # Ignore if getting branch fails
        raise RepositoryOperationError(error_message) from e
    except FileNotFoundError:
        raise AnnotationError("Git command not found. Is Git installed and in PATH?")


def create_annotation_commit(repo_path: str, feedback_branch: str, annotation_data: Annotation) -> str:
    """
    Creates a new commit on the feedback_branch with the annotation data.

    Args:
        repo_path: The path to the Git repository.
        feedback_branch: The name of the branch to commit the annotation to.
        annotation_data: An Annotation Pydantic model instance.

    Returns:
        The SHA of the newly created annotation commit.

    Raises:
        RepositoryOperationError: If any Git command fails.
        AnnotationError: For issues specific to annotation processing.
    """
    if not os.path.isdir(os.path.join(repo_path, '.git')):
        raise RepositoryOperationError(f"'{repo_path}' is not a valid Git repository.")

    # Ensure the feedback branch exists and switch to it
    try:
        # Check if branch exists locally
        _run_git_command(repo_path, ['rev-parse', '--verify', feedback_branch], expect_stdout=False)
        _run_git_command(repo_path, ['checkout', feedback_branch], expect_stdout=False)
    except RepositoryOperationError:
        # Branch does not exist, create it from HEAD
        # Check if there are any commits in the repo. If not, git checkout -b will fail.
        try:
            # Check if HEAD exists. If not, repo is empty or on an unborn branch.
            _run_git_command(repo_path, ['rev-parse', '--verify', 'HEAD'], expect_stdout=False)
            # If HEAD exists, create the branch from it.
            _run_git_command(repo_path, ['checkout', '-b', feedback_branch], expect_stdout=False)
        except RepositoryOperationError as e_head_check: # True if HEAD doesn't exist or other issue verifying it.
            # This path is taken if repo is empty or current branch is unborn.
            # The test `test_create_annotation_on_empty_repo_branch_creation` expects this error.
            # We do not attempt to create an orphan branch automatically here.
            # The user should ensure the repo has at least one commit.
            raise RepositoryOperationError(
                f"Failed to create feedback branch '{feedback_branch}'. "
                f"Ensure the repository is initialized and has at least one commit. Error checking HEAD: {e_head_check}"
            ) from e_head_check


    # Prepare annotation content for commit body
    # We only want to store the core data, not internal fields like 'id' or 'commit_id' yet
    commit_data = {
        "file_path": annotation_data.file_path,
        "highlighted_text": annotation_data.highlighted_text,
        "start_line": annotation_data.start_line,
        "end_line": annotation_data.end_line,
        "comment": annotation_data.comment,
        "author": annotation_data.author,
        "status": annotation_data.status.value, # Store the enum value
        # original_annotation_id is not set for new annotations
    }
    try:
        yaml_content = yaml.dump(commit_data, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise AnnotationError(f"Failed to serialize annotation data to YAML: {e}") from e

    commit_subject = f"Annotation: {annotation_data.file_path} (Lines {annotation_data.start_line}-{annotation_data.end_line})"
    commit_message = f"{commit_subject}\n\n{yaml_content}"

    # Create the commit
    # Git commit via plumbing is safer to handle messages with special characters
    # Using commit-tree is more robust but complex. For now, use high-level command with temp file for message.

    # To avoid issues with command line length or special characters in messages,
    # it's best to pass the commit message via a temporary file or stdin.
    # `git commit -F -` reads message from stdin.
    # `git commit --allow-empty -m "{subject}" -m "{body}"` could also work if body is not too large.

    # Using a temporary file for the commit message
    tmp_commit_msg_file = Path(repo_path) / ".git" / "ANNOTATION_COMMIT_MSG.tmp"
    try:
        with open(tmp_commit_msg_file, 'w', encoding='utf-8') as f:
            f.write(commit_message)

        # We need to stage something for a commit to be made, unless --allow-empty is used.
        # Annotations are metadata, so they don't necessarily change files in the working tree.
        # Using --allow-empty is appropriate here.
        _run_git_command(repo_path, ['commit', '--allow-empty', '-F', str(tmp_commit_msg_file)], expect_stdout=False)
    finally:
        if tmp_commit_msg_file.exists():
            tmp_commit_msg_file.unlink()

    # Get the SHA of the new commit
    new_commit_sha = _run_git_command(repo_path, ['rev-parse', 'HEAD'])

    # Update the annotation_data object with the commit ID (useful for the caller)
    # The Pydantic model passed is mutable by default.
    annotation_data.id = new_commit_sha
    annotation_data.commit_id = new_commit_sha

    return new_commit_sha


def list_annotations(repo_path: str, feedback_branch: str) -> List[Annotation]:
    """
    Lists all annotations from the history of the feedback_branch.

    Args:
        repo_path: The path to the Git repository.
        feedback_branch: The name of the branch to list annotations from.

    Returns:
        A list of Annotation objects.

    Raises:
        RepositoryOperationError: If any Git command fails or the branch doesn't exist.
        AnnotationError: For issues specific to annotation processing like parsing.
    """
    if not os.path.isdir(os.path.join(repo_path, '.git')):
        raise RepositoryOperationError(f"'{repo_path}' is not a valid Git repository.")

    annotations: List[Annotation] = []

    # Verify the branch exists before trying to log from it
    try:
        _run_git_command(repo_path, ['rev-parse', '--verify', feedback_branch], expect_stdout=False)
    except RepositoryOperationError as e:
        # If branch doesn't exist, it means no annotations, return empty list.
        # Or, we could raise an error. Plan implies listing, so empty list is fine.
        # However, the error from _run_git_command is generic. Let's make it more specific.
        # A common case is branch not found.
        # Git error messages can vary. Common ones for non-existent branches/refs:
        # "unknown revision or path not in the working tree"
        # "fatal: ambiguous argument '" + feedback_branch + "': unknown revision or path not in the working tree."
        # "fatal: Needed a single revision" (e.g. if branch name is valid but points to nothing or is ambiguous somehow)
        error_str = str(e).lower() # Normalize for easier checking
        if "unknown revision or path not in the working tree" in error_str or \
            "fatal: ambiguous argument" in error_str or \
            "fatal: needed a single revision" in error_str:
            # This indicates the branch likely doesn't exist or is invalid for log.
            # Depending on desired behavior: could return [] or raise a specific BranchNotFoundError.
            # For listing, returning [] if branch is empty or non-existent seems reasonable.
            return []
        raise RepositoryOperationError(f"Failed to verify feedback branch '{feedback_branch}': {e}") from e


    # Using a custom format for git log: %H for commit hash, %B for raw body (full message)
    # We'll use a unique delimiter that's unlikely to appear in commit messages.
    log_format = "%H%x00%B%x01" # Null byte to separate hash and body, SOH to separate entries
    try:
        log_output = _run_git_command(repo_path, ['log', feedback_branch, f'--pretty=format:{log_format}'])
    except RepositoryOperationError as e:
        # This can happen if the branch exists but has no commits.
        if "does not have any commits yet" in str(e) or "unknown revision" in str(e): # check for messages indicating no commits
            return [] # No commits, so no annotations
        raise RepositoryOperationError(f"Failed to get log for branch '{feedback_branch}': {e}") from e

    if not log_output:
        return []

    commit_entries = log_output.split('\x01') # Split by SOH

    for entry in commit_entries:
        entry = entry.strip() # Remove leading/trailing whitespace, including newlines from SOH
        if not entry:
            continue

        parts = entry.split('\x00', 1) # Split by null byte into hash and full message
        if len(parts) != 2:
            # Log a warning or skip malformed entry
            # print(f"Warning: Skipping malformed log entry: {entry[:100]}") # For debugging
            continue

        commit_sha, full_message = parts

        # The YAML content is expected after the first line (subject) and a blank line.
        message_lines = full_message.split('\n', 2)
        if len(message_lines) < 3 or message_lines[1].strip() != "":
            # Not a standard annotation commit format (missing blank line or body)
            # print(f"Skipping commit {commit_sha[:7]} - not an annotation (format error).")
            continue

        yaml_body = message_lines[2]

        try:
            data = yaml.safe_load(yaml_body)
            if not isinstance(data, dict):
                # print(f"Skipping commit {commit_sha[:7]} - YAML body is not a dictionary.")
                continue

            # Basic check for expected fields (can be more comprehensive)
            required_fields = ["file_path", "highlighted_text", "start_line", "end_line", "comment", "author", "status"]
            if not all(field in data for field in required_fields):
                # print(f"Skipping commit {commit_sha[:7]} - missing required fields in YAML.")
                continue

            # Validate status enum if possible
            try:
                status_enum = AnnotationStatus(data["status"])
            except ValueError:
                # print(f"Skipping commit {commit_sha[:7]} - invalid status value '{data['status']}'.")
                continue

            annotation = Annotation(
                id=commit_sha, # The commit SHA is the ID of this version of the annotation
                commit_id=commit_sha,
                file_path=data["file_path"],
                highlighted_text=data["highlighted_text"],
                start_line=data["start_line"],
                end_line=data["end_line"],
                comment=data["comment"],
                author=data["author"],
                status=status_enum,
                # original_annotation_id will be handled by update_annotation_status logic later
            )
            annotations.append(annotation)
        except yaml.YAMLError as e:
            # Not a valid YAML body, or not an annotation commit we recognize. Skip it.
            # print(f"Skipping commit {commit_sha[:7]} - YAML parsing error: {e}")
            continue
        except Exception as e: # Catch other potential errors during Annotation creation
            # print(f"Skipping commit {commit_sha[:7]} - Error creating annotation object: {e}")
            continue

    # At this stage, annotations are in reverse chronological order (newest first).
    # Depending on requirements, might need to reverse it if chronological order is desired.
    # The plan doesn't specify order, so newest first (Git log default) is fine.
    # This old version is now superseded by the refined one below.
    # return annotations

    # Refined list_annotations to handle status updates
    processed_annotations: Dict[str, Annotation] = {} # Key: original_annotation_id, Value: Annotation object at latest status
    # Stores the commit SHA of the latest update processed for an original_annotation_id, to ensure we only take the newest.
    # Not strictly needed if git log is guaranteed newest first and we process updates first for an ID.
    # Simpler: just use a set of original_ids that have been finalized.

    finalized_original_ids: set[str] = set()


    for entry in reversed(commit_entries): # Process oldest first to build up state
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split('\x00', 1)
        if len(parts) != 2:
            continue

        commit_sha, full_message = parts
        message_lines = full_message.split('\n', 2)
        if len(message_lines) < 3 or message_lines[1].strip() != "":
            continue
        yaml_body = message_lines[2]

        try:
            data = yaml.safe_load(yaml_body)
            if not isinstance(data, dict):
                continue

            required_fields = ["file_path", "highlighted_text", "start_line", "end_line", "comment", "author", "status"]
            if not all(field in data for field in required_fields):
                continue

            status_enum = AnnotationStatus(data["status"])

            original_id_from_yaml = data.get("original_annotation_id")

            if original_id_from_yaml:
                # This is a status update commit
                # It updates the annotation identified by original_id_from_yaml
                # Its own commit_id is commit_sha
                # Its id (as an Annotation object) should be original_id_from_yaml
                if original_id_from_yaml in processed_annotations:
                    # Update existing annotation's status and its commit_id to this newer one
                    ann = processed_annotations[original_id_from_yaml]
                    ann.status = status_enum
                    ann.commit_id = commit_sha # This commit defines the current state
                    # Carry over other fields from the update commit's YAML if they can change.
                    # For now, assuming only status changes. If other fields (e.g. comment) can be
                    # updated by a status update commit, they should be updated here too.
                    # The current `update_annotation_status` copies all fields.
                    ann.file_path = data["file_path"]
                    ann.highlighted_text = data["highlighted_text"]
                    ann.start_line = data["start_line"]
                    ann.end_line = data["end_line"]
                    ann.comment = data["comment"]
                    ann.author = data["author"]
                    ann.original_annotation_id = original_id_from_yaml # Ensure this is set
                else:
                    # This case should ideally not happen if original annotations are always created first.
                    # However, if it can, we might need to create a new entry.
                    # Or, it implies an update to a non-existent/deleted annotation.
                    # For now, let's assume valid update refers to an existing original_id.
                    # If the original annotation commit hasn't been processed yet (because we are going oldest to newest)
                    # this update might be processed before its base. This is fine.
                     processed_annotations[original_id_from_yaml] = Annotation(
                        id=original_id_from_yaml, # ID of the annotation thread
                        commit_id=commit_sha,     # SHA of this specific update commit
                        file_path=data["file_path"],
                        highlighted_text=data["highlighted_text"],
                        start_line=data["start_line"],
                        end_line=data["end_line"],
                        comment=data["comment"],
                        author=data["author"],
                        status=status_enum,
                        original_annotation_id=original_id_from_yaml
                    )
            else:
                # This is an original annotation commit
                # Its id is commit_sha
                if commit_sha not in processed_annotations: # If no updates have been processed for it yet
                    processed_annotations[commit_sha] = Annotation(
                        id=commit_sha,
                        commit_id=commit_sha,
                        file_path=data["file_path"],
                        highlighted_text=data["highlighted_text"],
                        start_line=data["start_line"],
                        end_line=data["end_line"],
                        comment=data["comment"],
                        author=data["author"],
                        status=status_enum,
                        original_annotation_id=None # Original annotations don't point to others
                    )
                # If commit_sha IS in processed_annotations, it means an update was processed earlier (which is good)
                # and has already established the entry for this annotation thread. We don't overwrite
                # the Annotation object, as it already reflects a newer status from an update.
                # We just ensure its base data (like original comment, author, etc.) is from this original commit
                # if the update didn't explicitly override it.
                # Current update_annotation_status *does* copy all data, so this may not be strictly necessary
                # if updates are comprehensive.
                # Let's re-verify: if an update for 'A' was processed, processed_annotations['A'] exists.
                # Now we process 'A' (original). We should NOT overwrite processed_annotations['A'] with older status.
                # The logic of `if commit_sha not in processed_annotations:` handles this correctly.

        except (yaml.YAMLError, ValueError, KeyError) as e: # Catches Pydantic validation errors too if strict
            # print(f"Skipping commit {commit_sha[:7]} - data processing error: {e}") # For debugging
            continue

    return list(processed_annotations.values())


def update_annotation_status(repo_path: str, feedback_branch: str, annotation_commit_id: str, new_status: AnnotationStatus) -> str:
    """
    Updates the status of an existing annotation by creating a new commit.

    Args:
        repo_path: The path to the Git repository.
        feedback_branch: The name of the feedback branch.
        annotation_commit_id: The commit SHA of the original annotation to update.
        new_status: The new status for the annotation.

    Returns:
        The SHA of the new commit that records the status update.

    Raises:
        RepositoryOperationError: If Git commands fail or the original annotation is not found.
        AnnotationError: For issues specific to annotation processing.
    """
    if not os.path.isdir(os.path.join(repo_path, '.git')):
        raise RepositoryOperationError(f"'{repo_path}' is not a valid Git repository.")

    # 0. Ensure feedback branch exists and check it out
    try:
        _run_git_command(repo_path, ['rev-parse', '--verify', feedback_branch], expect_stdout=False)
        _run_git_command(repo_path, ['checkout', feedback_branch], expect_stdout=False)
    except RepositoryOperationError as e:
        # If branch doesn't exist, cannot update an annotation on it.
        raise RepositoryOperationError(f"Feedback branch '{feedback_branch}' not found or could not be checked out: {e}") from e

    # 1. Retrieve the original annotation data.
    # We need this to carry over details like file_path, author, etc., into the new status commit.
    # This reuses part of the logic from list_annotations to get a specific commit's annotation data.
    original_annotation_data: Optional[Annotation] = None
    try:
        # %B gives the raw body, including subject, blank line, and message body
        commit_full_message = _run_git_command(repo_path, ['show', '-s', '--format=%B', annotation_commit_id])

        message_lines = commit_full_message.split('\n', 2)
        if len(message_lines) < 3 or message_lines[1].strip() != "":
            raise AnnotationError(f"Commit {annotation_commit_id} is not in the expected annotation format (subject/body structure).")

        yaml_body = message_lines[2]
        data = yaml.safe_load(yaml_body)
        if not isinstance(data, dict):
            raise AnnotationError(f"YAML body of commit {annotation_commit_id} is not a dictionary.")

        # Basic validation
        required_fields = ["file_path", "highlighted_text", "start_line", "end_line", "comment", "author"]
        if not all(field in data for field in required_fields):
            raise AnnotationError(f"Commit {annotation_commit_id} is missing required fields in its YAML body.")

        original_annotation_data = Annotation(
            id=annotation_commit_id, # Original commit ID
            commit_id=annotation_commit_id,
            file_path=data["file_path"],
            highlighted_text=data["highlighted_text"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            comment=data["comment"],
            author=data["author"],
            status=AnnotationStatus(data.get("status", AnnotationStatus.NEW.value)), # Use original status if present
             # original_annotation_id is None for the first commit of an annotation
        )

    except RepositoryOperationError as e:
        raise RepositoryOperationError(f"Original annotation commit '{annotation_commit_id}' not found on branch '{feedback_branch}': {e}") from e
    except yaml.YAMLError as e:
        raise AnnotationError(f"Failed to parse YAML for original annotation '{annotation_commit_id}': {e}") from e
    except (ValueError, KeyError) as e: # For AnnotationStatus conversion or missing keys
        raise AnnotationError(f"Data format error for original annotation '{annotation_commit_id}': {e}") from e

    if not original_annotation_data:
        # Should have been caught by exceptions above, but as a safeguard.
        raise AnnotationError(f"Could not retrieve data for original annotation commit '{annotation_commit_id}'.")

    # 2. Prepare data for the new status update commit.
    # This commit will carry over all data from the original, but with the new status,
    # and a pointer to the original annotation.
    update_commit_data = {
        "file_path": original_annotation_data.file_path,
        "highlighted_text": original_annotation_data.highlighted_text,
        "start_line": original_annotation_data.start_line,
        "end_line": original_annotation_data.end_line,
        "comment": original_annotation_data.comment, # Keep original comment
        "author": original_annotation_data.author,   # Keep original author
        "status": new_status.value,
        "original_annotation_id": annotation_commit_id # Link back to the original annotation
    }
    try:
        yaml_content = yaml.dump(update_commit_data, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise AnnotationError(f"Failed to serialize status update data to YAML: {e}") from e

    commit_subject = f"Update status: {original_annotation_data.file_path} (Annotation {annotation_commit_id[:7]}) to {new_status.value}"
    commit_message = f"{commit_subject}\n\n{yaml_content}"

    # 3. Create the new commit for the status update.
    tmp_commit_msg_file = Path(repo_path) / ".git" / "ANNOTATION_STATUS_UPDATE_COMMIT_MSG.tmp"
    try:
        with open(tmp_commit_msg_file, 'w', encoding='utf-8') as f:
            f.write(commit_message)

        _run_git_command(repo_path, ['commit', '--allow-empty', '-F', str(tmp_commit_msg_file)], expect_stdout=False)
    finally:
        if tmp_commit_msg_file.exists():
            tmp_commit_msg_file.unlink()

    # 4. Get the SHA of the new status update commit.
    status_update_commit_sha = _run_git_command(repo_path, ['rev-parse', 'HEAD'])

    return status_update_commit_sha

# End of placeholder content
# Actual implementations will follow in subsequent steps.
