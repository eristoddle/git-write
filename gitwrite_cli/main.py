# Test comment to check write access.
import click
import pygit2 # pygit2 is still used by other commands
# import os # os seems to be no longer used by CLI commands directly
from pathlib import Path
# from pygit2 import Signature # Signature might not be needed if init was the only user. Let's check.
# Signature is used in 'save' and 'tag_add', so it should remain.
from pygit2 import Signature
from rich.console import Console
from rich.panel import Panel
from gitwrite_core.repository import initialize_repository, add_pattern_to_gitignore, list_gitignore_patterns # Added import
from gitwrite_core.tagging import create_tag
from gitwrite_core.repository import sync_repository # Added for sync
from gitwrite_core.versioning import get_commit_history, get_diff, revert_commit, save_changes # Added save_changes
from gitwrite_core.branching import ( # Updated for merge
    create_and_switch_branch,
    list_branches,
    switch_to_branch,
    merge_branch_into_current
)
from gitwrite_core.exceptions import (
    RepositoryNotFoundError,
    CommitNotFoundError,
    TagAlreadyExistsError,
    GitWriteError,
    NotEnoughHistoryError,
    RepositoryEmptyError,
    BranchAlreadyExistsError,
    BranchNotFoundError,
    MergeConflictError, # Added for merge
    NoChangesToSaveError, # Added for save_changes
    RevertConflictError, # Added for save_changes
    DetachedHeadError, # Added for sync
    FetchError, # Added for sync
    PushError, # Added for sync
    RemoteNotFoundError # Added for sync
)
from rich.table import Table # Ensure Table is imported for switch

@click.group()
def cli():
    """GitWrite: A CLI tool for writer-friendly Git repositories."""
    pass

@cli.command()
@click.argument("project_name", required=False)
def init(project_name):
    """Initializes a new GitWrite project or adds GitWrite structure to an existing Git repository."""
    # Determine the base path (current working directory)
    # The core function expects path_str to be the CWD from where CLI is called.
    base_path_str = str(Path.cwd())

    # Call the core function
    result = initialize_repository(base_path_str, project_name)

    # Print messages based on the result
    if result.get('status') == 'success':
        click.echo(result.get('message', 'Initialization successful.'))
        # Optionally, print the path if available and relevant:
        # if result.get('path'):
        # click.echo(f"Project path: {result.get('path')}")
    else: # 'error' or any other status
        click.echo(result.get('message', 'An unknown error occurred.'), err=True)
        # Consider if a non-zero exit code should be set here, e.g. ctx.exit(1)
        # For now, just printing to err=True is consistent with current style.

@cli.command()
@click.argument("message")
@click.option(
    "-i",
    "--include",
    "include_paths",
    type=click.Path(exists=False),
    multiple=True,
    help="Specify a file or directory to include in the save. Can be used multiple times. If not provided, all changes are saved.",
)
def save(message, include_paths):
    """Stages changes and creates a commit with the given message. Supports selective staging with --include."""
    try:
        repo_path_str = str(Path.cwd()) # Core function handles discovery from this path

        # Convert Click's tuple of include_paths to a list, or None if empty
        include_list = list(include_paths) if include_paths else None

        result = save_changes(repo_path_str, message, include_list)

        # Success output
        if result.get('status') == 'success':
            message_first_line = result.get('message', '').splitlines()[0] if result.get('message') else ""

            click.echo(
                f"[{result.get('branch_name', 'Unknown Branch')} {result.get('short_oid', 'N/A')}] {message_first_line}"
            )
            if result.get('is_merge_commit'):
                click.echo("Successfully completed merge operation.")
            if result.get('is_revert_commit'):
                click.echo("Successfully completed revert operation.")
        else:
            # This case should ideally not be reached if core function throws exceptions for errors
            click.echo(f"Save operation reported unhandled status: {result.get('status', 'unknown')}", err=True)

    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
    except RepositoryEmptyError as e:
        # The core function might raise this if attempting to commit to an empty repo
        # without it being an initial commit (though save_changes handles initial commit logic)
        # Or if other operations fail due to empty repo state where not expected.
        click.echo(f"Error: {e}", err=True)
        click.echo("Hint: If this is the first commit, 'gitwrite save \"Initial commit\"' should create it.", err=True)
    except NoChangesToSaveError as e:
        click.echo(str(e)) # E.g., "No changes to save..." or "No specified files had changes..."
    except (MergeConflictError, RevertConflictError) as e:
        click.echo(str(e), err=True)
        if hasattr(e, 'conflicting_files') and e.conflicting_files:
            click.echo("Conflicting files:", err=True)
            for f_path in sorted(e.conflicting_files): # Sort for consistent output
                click.echo(f"  {f_path}", err=True)
        if isinstance(e, MergeConflictError):
            click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge.", err=True)
        elif isinstance(e, RevertConflictError):
             click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the revert.", err=True)
    except GitWriteError as e: # Catch-all for other specific errors from core
        click.echo(f"Error during save: {e}", err=True)
    except Exception as e: # General catch-all for unexpected issues at CLI level
        click.echo(f"An unexpected error occurred during save: {e}", err=True)

# ... (rest of the file remains unchanged) ...
@cli.command()
@click.option("-n", "--number", "count", type=int, default=None, help="Number of commits to show.")
def history(count):
    """Shows the commit history of the project."""
    try:
        # Discover repository path first
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        # Call the core function
        commits = get_commit_history(repo_path_str, count)

        if not commits:
            click.echo("No history yet.") # Covers bare, empty, unborn HEAD, or no commits found by core function
            return

        from rich.table import Table
        from rich.text import Text
        from rich.console import Console
        # datetime, timezone, timedelta are no longer needed here as date is pre-formatted

        table = Table(title="Commit History")
        table.add_column("Commit", style="cyan", no_wrap=True)
        table.add_column("Author", style="magenta")
        table.add_column("Date", style="green")
        table.add_column("Message", style="white")

        for commit_data in commits:
            # Extract data directly from the dictionary
            short_hash = commit_data["short_hash"]
            author_name = commit_data["author_name"]
            date_str = commit_data["date"] # Already formatted
            message_short = commit_data["message_short"] # Already the first line

            table.add_row(short_hash, author_name, date_str, Text(message_short, overflow="ellipsis"))

        if not table.rows: # Should ideally be caught by `if not commits:` but good as a failsafe
             click.echo("No commits found to display.")
             return

        console = Console()
        console.print(table)

    except RepositoryNotFoundError: # Raised by get_commit_history
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
    except pygit2.GitError as e: # For discover_repository or other unexpected pygit2 errors
        click.echo(f"GitError during history: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is in pyproject.toml and installed.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during history: {e}", err=True)

@cli.command()
@click.argument("branch_name")
def explore(branch_name):
    """Creates and switches to a new exploration (branch)."""
    try:
        current_path_str = str(Path.cwd())
        result = create_and_switch_branch(current_path_str, branch_name)
        # Success message uses the branch name from the result for consistency
        click.echo(f"Switched to a new exploration: {result['branch_name']}")

    except RepositoryNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except RepositoryEmptyError as e:
        # Custom message to be more user-friendly for CLI context
        click.echo(f"Error: {e}", err=True)
    except BranchAlreadyExistsError as e:
        click.echo(f"Error: {e}", err=True)
    except GitWriteError as e: # Catches other specific errors from core like bare repo
        click.echo(f"Error: {e}", err=True)
    except Exception as e: # General catch-all for unexpected issues
        click.echo(f"An unexpected error occurred during explore: {e}", err=True)


@cli.command()
@click.argument("branch_name", required=False)
def switch(branch_name):
    """Switches to an existing exploration (branch) or lists all explorations."""
    try:
        current_path_str = str(Path.cwd())

        if branch_name is None:
            # List branches
            branches_data = list_branches(current_path_str)
            if not branches_data:
                click.echo("No explorations (branches) yet.")
                return

            # Console is already imported at the top level if other commands use it,
            # or this will rely on the general ImportError.
            # Table is now explicitly imported at the top for this command.
            table = Table(title="Available Explorations")
            table.add_column("Name", style="cyan") # Keep existing style
            for b_data in branches_data: # Assumes branches_data is sorted by name from core function
                prefix = "* " if b_data.get('is_current', False) else "  "
                table.add_row(f"{prefix}{b_data['name']}")

            console = Console() # Create console instance to print table
            console.print(table)
        else:
            # Switch branch
            result = switch_to_branch(current_path_str, branch_name)

            status = result.get('status')
            returned_branch_name = result.get('branch_name', branch_name) # Fallback to input if not in result

            if status == 'success':
                click.echo(f"Switched to exploration: {returned_branch_name}")
                if result.get('is_detached'):
                    click.echo(click.style("Note: HEAD is now in a detached state. You are not on a local branch.", fg="yellow"))
            elif status == 'already_on_branch':
                click.echo(f"Already on exploration: {returned_branch_name}")
            else:
                # Should not happen if core function adheres to defined return statuses
                click.echo(f"Unknown status from switch operation: {status}", err=True)

    except RepositoryNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except BranchNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except RepositoryEmptyError as e:
        click.echo(f"Error: {e}", err=True)
    except GitWriteError as e:
        click.echo(f"Error: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is installed to list branches.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during switch: {e}", err=True)

@cli.command("merge")
@click.argument("branch_name")
def merge_command(branch_name):
    """Merges the specified exploration (branch) into the current one."""
    try:
        current_path_str = str(Path.cwd())
        result = merge_branch_into_current(current_path_str, branch_name)

        status = result.get('status')
        merged_branch = result.get('branch_name', branch_name) # Branch that was merged
        current_branch = result.get('current_branch', 'current branch') # Branch merged into
        commit_oid = result.get('commit_oid')

        if status == 'up_to_date':
            click.echo(f"'{current_branch}' is already up-to-date with '{merged_branch}'.")
        elif status == 'fast_forwarded':
            click.echo(f"Fast-forwarded '{current_branch}' to '{merged_branch}' (commit {commit_oid[:7]}).")
        elif status == 'merged_ok':
            click.echo(f"Merged '{merged_branch}' into '{current_branch}'. New commit: {commit_oid[:7]}.")
        else:
            click.echo(f"Merge operation completed with unhandled status: {status}", err=True)

    except MergeConflictError as e:
        # str(e) or e.message will give the main error message from core
        click.echo(str(e), err=True)
        if hasattr(e, 'conflicting_files') and e.conflicting_files:
            click.echo("Conflicting files:", err=True)
            for f_path in e.conflicting_files:
                click.echo(f"  {f_path}", err=True)
        click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge.", err=True)
    except RepositoryNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except BranchNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except RepositoryEmptyError as e:
        click.echo(f"Error: {e}", err=True)
    except GitWriteError as e: # Catches other core errors like detached HEAD, no signature, etc.
        click.echo(f"Error: {e}", err=True)
    except Exception as e: # General catch-all for unexpected issues
        click.echo(f"An unexpected error occurred during merge: {e}", err=True)

@cli.command()
@click.argument("ref1_str", metavar="REF1", required=False, default=None)
@click.argument("ref2_str", metavar="REF2", required=False, default=None)
def compare(ref1_str, ref2_str):
    """Compares two references (commits, branches, tags) or shows changes in working directory."""
    from rich.console import Console
    from rich.text import Text
    import difflib # difflib is still needed for word-level diff
    import re # For parsing patch text

    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository.", err=True)
            return

        # The explicit bare check can be removed as get_diff handles repository states.
        # repo_obj_for_bare_check = pygit2.Repository(repo_path_str)
        # if repo_obj_for_bare_check.is_bare:
        #     click.echo("Error: Cannot compare in a bare repository.", err=True)
        #     return

        diff_data = get_diff(repo_path_str, ref1_str, ref2_str)

        patch_text = diff_data["patch_text"]
        display_ref1 = diff_data["ref1_display_name"]
        display_ref2 = diff_data["ref2_display_name"]

        if not patch_text:
            click.echo(f"No differences found between {display_ref1} and {display_ref2}.")
            return

        console = Console()
        console.print(f"Diff between {display_ref1} (a) and {display_ref2} (b):")

        # Parse the patch text for display
        file_patches = re.split(r'(?=^diff --git )', patch_text, flags=re.MULTILINE)

        for file_patch in file_patches:
            if not file_patch.strip():
                continue

            lines = file_patch.splitlines()

            old_file_path_in_patch = "unknown_old"
            new_file_path_in_patch = "unknown_new"
            hunk_lines_for_processing = []

            for line_idx, line_content in enumerate(lines):
                if line_content.startswith("--- a/"):
                    old_file_path_in_patch = line_content[len("--- a/"):].strip()
                    if new_file_path_in_patch == "unknown_new": new_file_path_in_patch = old_file_path_in_patch
                elif line_content.startswith("+++ b/"):
                    new_file_path_in_patch = line_content[len("+++ b/"):].strip()
                    console.print(f"--- a/{old_file_path_in_patch}\n+++ b/{new_file_path_in_patch}", style="bold yellow")
                elif line_content.startswith("@@"):
                    if hunk_lines_for_processing:
                        process_hunk_lines_for_word_diff(hunk_lines_for_processing, console)
                        hunk_lines_for_processing = []
                    console.print(line_content, style="cyan")
                elif line_content.startswith("-") or line_content.startswith("+") or line_content.startswith(" "):
                    hunk_lines_for_processing.append((line_content[0], line_content[1:]))
                elif line_content.startswith("\\ No newline at end of file"):
                    # Process any pending hunk lines before printing this message
                    if hunk_lines_for_processing:
                        process_hunk_lines_for_word_diff(hunk_lines_for_processing, console)
                        hunk_lines_for_processing = []
                    console.print(line_content, style="dim")

            if hunk_lines_for_processing:
                process_hunk_lines_for_word_diff(hunk_lines_for_processing, console)

    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository.", err=True)
    except CommitNotFoundError as e:
        click.echo(f"Error: Could not resolve reference: {e}", err=True)
    except NotEnoughHistoryError as e:
        click.echo(f"Error: Not enough history to perform comparison: {e}", err=True)
    except ValueError as e:
        click.echo(f"Error: Invalid reference combination: {e}", err=True)
    except pygit2.GitError as e:
        click.echo(f"GitError during compare: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is in pyproject.toml and installed.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during compare: {e}", err=True)

# Helper function for word-level diff processing, adapted from original logic
def process_hunk_lines_for_word_diff(hunk_lines: list, console: Console):
    import difflib
    from rich.text import Text

    i = 0
    while i < len(hunk_lines):
        origin, content = hunk_lines[i]

        if origin == '-' and (i + 1 < len(hunk_lines)) and hunk_lines[i+1][0] == '+':
            old_content = content
            new_content = hunk_lines[i+1][1]

            sm = difflib.SequenceMatcher(None, old_content.split(), new_content.split())
            text_old = Text("-", style="red")
            text_new = Text("+", style="green")
            has_word_diff = any(tag != 'equal' for tag, _, _, _, _ in sm.get_opcodes())

            if not has_word_diff:
                console.print(Text(f"-{old_content}", style="red"))
                console.print(Text(f"+{new_content}", style="green"))
            else:
                for tag_op, i1, i2, j1, j2 in sm.get_opcodes():
                    old_words_segment = old_content.split()[i1:i2]
                    new_words_segment = new_content.split()[j1:j2]
                    old_chunk = " ".join(old_words_segment)
                    new_chunk = " ".join(new_words_segment)
                    old_space = " " if old_chunk and i2 < len(old_content.split()) else ""
                    new_space = " " if new_chunk and j2 < len(new_content.split()) else ""

                    if tag_op == 'replace':
                        text_old.append(old_chunk + old_space, style="black on red")
                        text_new.append(new_chunk + new_space, style="black on green")
                    elif tag_op == 'delete':
                        text_old.append(old_chunk + old_space, style="black on red")
                    elif tag_op == 'insert':
                        text_new.append(new_chunk + new_space, style="black on green")
                    elif tag_op == 'equal':
                        text_old.append(old_chunk + old_space)
                        text_new.append(new_chunk + new_space)
                console.print(text_old)
                console.print(text_new)
            i += 2
            continue

        if origin == '-':
            console.print(Text(f"-{content}", style="red"))
        elif origin == '+':
            console.print(Text(f"+{content}", style="green"))
        elif origin == ' ':
            console.print(f" {content}")
        i += 1

@cli.command()
@click.option("--remote", "remote_name", default="origin", help="The remote to sync with.")
@click.option("--branch", "branch_name_opt", default=None, help="The branch to sync. Defaults to the current branch.")
@click.option("--no-push", "no_push_flag", is_flag=True, default=False, help="Do not push changes to the remote.")
def sync(remote_name, branch_name_opt, no_push_flag):
    """Fetches changes from a remote, integrates them, and pushes local changes."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        # Call the core sync_repository function
        # The core function's `push` parameter means "do a push"
        # The CLI flag `--no-push` means "do NOT do a push"
        # So, push_action = not no_push_flag
        # The core function's `allow_no_push` parameter should be True if CLI's --no-push is used.
        sync_result = sync_repository(
            repo_path_str,
            remote_name=remote_name,
            branch_name_opt=branch_name_opt,
            push=not no_push_flag,
            allow_no_push=no_push_flag # If --no-push is specified, allow it.
        )

        # Report based on sync_result dictionary
        fetch_status_message = sync_result.get("fetch_status", {}).get("message", "Fetch status unknown.")
        is_fetch_error = "failed" in fetch_status_message.lower() or "error" in fetch_status_message.lower()
        click.echo(fetch_status_message, err=is_fetch_error)

        local_update_msg = sync_result.get("local_update_status", {}).get("message", "Local update status unknown.")
        if sync_result.get("local_update_status", {}).get("type") == "error" or \
           sync_result.get("local_update_status", {}).get("type") == "conflicts_detected":
            click.echo(local_update_msg, err=True)
            if sync_result.get("local_update_status", {}).get("conflicting_files"):
                click.echo("Conflicting files: " + ", ".join(sync_result["local_update_status"]["conflicting_files"]), err=True)
                click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge.", err=True)
        else:
            click.echo(local_update_msg)


        push_msg = sync_result.get("push_status", {}).get("message", "Push status unknown.")
        push_failed = "failed" in push_msg.lower() or \
                      ("pushed" in sync_result.get("push_status", {}) and not sync_result["push_status"]["pushed"] and not no_push_flag)

        if no_push_flag:
            click.echo("Push skipped (--no-push specified).")
        elif push_failed:
            click.echo(push_msg, err=True)
        else:
            click.echo(push_msg)

        if sync_result.get("status", "").startswith("success"):
            click.echo(f"Sync process for branch '{sync_result.get('branch_synced', branch_name_opt)}' with remote '{remote_name}' completed.")
        elif sync_result.get("status") == "error_in_sub_operation":
             click.echo(f"Sync process for branch '{sync_result.get('branch_synced', branch_name_opt)}' with remote '{remote_name}' completed with errors in some steps.", err=True)
        # Other error cases are typically raised as exceptions by the core function

    except pygit2.GitError as e: # Should be caught by more specific exceptions from core
        click.echo(f"GitError during sync: {e}", err=True)
    except KeyError as e: # Should be caught by specific exceptions like RemoteNotFoundError now
        click.echo(f"Error during sync setup (KeyError): {e}", err=True)
    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
    except RepositoryEmptyError as e:
        click.echo(f"Error: {e}", err=True) # Core message is usually good
    except DetachedHeadError as e:
        click.echo(f"Error: {e}. Please switch to a branch to sync or specify a branch name.", err=True)
    except RemoteNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except BranchNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except FetchError as e:
        click.echo(f"Error during fetch: {e}", err=True)
    except MergeConflictError as e: # This exception is raised by sync_repository if conflicts occur and are not resolved by it.
        click.echo(f"Error: {e}", err=True)
        if hasattr(e, 'conflicting_files') and e.conflicting_files:
            click.echo("Conflicting files:", err=True)
            for f_path in sorted(e.conflicting_files):
                click.echo(f"  {f_path}", err=True)
        click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge.", err=True)
    except PushError as e:
        click.echo(f"Error during push: {e}", err=True)
    except GitWriteError as e: # Catch-all for other gitwrite core errors
        click.echo(f"Error during sync: {e}", err=True)
    except Exception as e: # General unexpected errors
        click.echo(f"An unexpected error occurred during sync: {e}", err=True)


@cli.command()
@click.argument("commit_ish")
@click.pass_context
def revert(ctx, commit_ish):
    """Reverts a specified commit.

    <commit_ish> is the commit reference (e.g., commit hash, branch name, HEAD) to revert.
    If the revert results in conflicts, the operation is aborted, and the working directory
    is kept clean.
    """
    try:
        repo_path_str_cli = str(Path.cwd())

        # Explicitly check discovery before Repository() constructor
        discovered_path_cli = pygit2.discover_repository(repo_path_str_cli)
        if discovered_path_cli is None:
            click.secho("Error: Current directory is not a Git repository or no repository found.", fg="red")
            ctx.exit(1)
            return # Should not be reached due to ctx.exit(1)

        # Now that we know a repo path was discovered, proceed with checks
        repo_for_checks_cli = pygit2.Repository(discovered_path_cli)

        if repo_for_checks_cli.is_bare:
            click.secho("Error: Cannot revert in a bare repository.", fg="red")
            ctx.exit(1)
            return

        status_flags_check = repo_for_checks_cli.status()
        is_dirty = False
        for _filepath, flags in status_flags_check.items():
            # Check for any uncommitted changes in worktree or index, excluding untracked files
            # (as revert itself doesn't typically care about untracked files unless they conflict)
            if (flags != pygit2.GIT_STATUS_CURRENT and
                not (flags & pygit2.GIT_STATUS_WT_NEW and not (flags & pygit2.GIT_STATUS_INDEX_NEW))): # Exclude untracked files that are not in index
                is_dirty = True
                break
        if is_dirty:
            click.secho("Error: Your working directory or index has uncommitted changes.", fg="red")
            click.secho("Please commit or stash them before attempting to revert.", fg="yellow")
            ctx.exit(1)
            return
        del repo_for_checks_cli # clean up temporary repo object

        # Call the core function using the initially determined repo_path_str_cli,
        # as core function also does its own discovery.
        result = revert_commit(repo_path_str=repo_path_str_cli, commit_ish_to_revert=commit_ish)

        click.echo(click.style(f"{result['message']} (Original: '{commit_ish}')", fg="green"))
        click.echo(f"New commit: {result['new_commit_oid']}")

    except RepositoryNotFoundError: # This will be caught if core function fails discovery
        click.secho("Error: Current directory is not a Git repository or no repository found.", fg="red")
        ctx.exit(1)
    except CommitNotFoundError: # From core function
        click.secho(f"Error: Commit '{commit_ish}' not found or is not a valid commit reference.", fg="red")
        ctx.exit(1)
    except MergeConflictError as e:
        # The core function's error message for MergeConflictError is:
        # "Revert resulted in conflicts. The revert has been aborted and the working directory is clean."
        click.secho(f"Error: Reverting commit '{commit_ish}' resulted in conflicts.", fg="red")
        click.secho(str(e), fg="red") # This will print the detailed message from the core function.
        # No need for further instructions to resolve manually if the core function aborted.
        ctx.exit(1)
    except GitWriteError as e: # Catch other specific errors from gitwrite_core
        click.secho(f"Error during revert: {e}", fg="red")
        ctx.exit(1)
    except pygit2.GitError as e: # Catch pygit2 errors that might occur before core logic (e.g. status check)
        click.secho(f"A Git operation failed: {e}", fg="red")
        ctx.exit(1)
    except Exception as e: # Generic catch-all for unexpected issues
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        ctx.exit(1)

@cli.group()
def tag():
    """Manages tags."""
    pass


@tag.command("add")
@click.pass_context # Add pass_context to access ctx.obj
@click.argument("name") # Renamed from tag_name to name
@click.option("-m", "--message", "message", default=None, help="Annotation message for the tag.") # Renamed message_opt_tag
@click.option("--force", is_flag=True, help="Overwrite an existing tag.")
@click.option("-c", "--commit", "commit_ish", default="HEAD", help="Commit to tag. Defaults to HEAD.") # Added commit option
def add(ctx, name, message, force, commit_ish): # Function signature updated
    """Creates a new tag.

    If -m/--message is provided, an annotated tag is created.
    Otherwise, a lightweight tag is created.
    The tag points to COMMIT_ISH (commit reference), which defaults to HEAD.
    """
    try:
        # Assuming REPO_PATH is set up in a global context object, e.g., by the main cli group
        # If not, discover it: repo_path = pygit2.discover_repository(str(Path.cwd()))
        # For now, let's assume ctx.obj['REPO_PATH'] is available.
        # If your CLI structure doesn't pass REPO_PATH this way, you'll need to adjust.
        # A common pattern is to set ctx.obj['REPO_PATH'] = pygit2.discover_repository(str(Path.cwd()))
        # in the main `cli` function or a callback.
        # For robustness, let's try to discover if not present.

        repo_path = None
        if ctx.obj and 'REPO_PATH' in ctx.obj:
            repo_path = ctx.obj['REPO_PATH']

        if repo_path is None:
            # Fallback to discovering the repository if not in context
            discovered_path = pygit2.discover_repository(str(Path.cwd()))
            if discovered_path is None:
                click.echo(click.style("Error: Not a git repository (or any of the parent directories).", fg='red'), err=True)
                ctx.exit(1) # Exit with error code
            repo_path = discovered_path

        # Store it back for potential future use in the same command chain (though not typical for simple commands)
        if ctx.obj is None: ctx.obj = {}
        ctx.obj['REPO_PATH'] = repo_path


        tag_details = create_tag(
            repo_path_str=repo_path,
            tag_name=name,
            target_commit_ish=commit_ish,
            message=message,
            force=force
        )

        if tag_details['type'] == 'annotated':
            click.echo(click.style(f"Created annotated tag '{tag_details['name']}' pointing to {tag_details['target'][:7]}.", fg='green'))
        else: # lightweight
            click.echo(click.style(f"Created lightweight tag '{tag_details['name']}' pointing to {tag_details['target'][:7]}.", fg='green'))

    except RepositoryNotFoundError:
        click.echo(click.style("Error: Not a git repository.", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except CommitNotFoundError:
        click.echo(click.style(f"Error: Commit '{commit_ish}' not found.", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except TagAlreadyExistsError:
        click.echo(click.style(f"Error: Tag '{name}' already exists. Use --force to overwrite.", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except GitWriteError as e: # Catching the base GitWriteError for other core errors
        click.echo(click.style(f"Error creating tag: {e}", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except Exception as e: # Catch-all for unexpected errors
        click.echo(click.style(f"An unexpected error occurred: {e}", fg='red'), err=True)
        if ctx: ctx.exit(1)


@tag.command("list") # original name was tag_list, but Click uses function name, so it becomes 'list'
@click.pass_context # To potentially access repo_path if needed, though list_tags handles it
def list_cmd(ctx): # Renamed to avoid conflict if we had a variable named list
    """Lists all tags in the repository."""
    # The list_tags function from core is intended to be used by the CLI's list command.
    # It needs to be imported.
    from gitwrite_core.tagging import list_tags as core_list_tags

    repo_path = None
    if ctx.obj and 'REPO_PATH' in ctx.obj:
        repo_path = ctx.obj['REPO_PATH']

    if repo_path is None:
        discovered_path = pygit2.discover_repository(str(Path.cwd()))
        if discovered_path is None:
            click.echo(click.style("Error: Not a git repository (or any of the parent directories).", fg='red'), err=True)
            ctx.exit(1)
        repo_path = discovered_path

    if ctx.obj is None: ctx.obj = {} # Ensure ctx.obj exists
    ctx.obj['REPO_PATH'] = repo_path

    try:
        tags = core_list_tags(repo_path_str=repo_path)

        if not tags:
            click.echo("No tags found in the repository.")
            return

        from rich.table import Table
        from rich.console import Console # Ensure Console is imported if not already at top level

        table = Table(title="Repository Tags")
        table.add_column("Tag Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Target Commit", style="green")
        table.add_column("Message (Annotated Only)", style="white", overflow="ellipsis")

        for tag_data in sorted(tags, key=lambda t: t['name']):
            message_display = tag_data.get('message', '-') if tag_data['type'] == 'annotated' else '-'
            table.add_row(
                tag_data['name'],
                tag_data['type'],
                tag_data['target'][:7] if tag_data.get('target') else 'N/A', # Show short hash
                message_display
            )

        if not table.rows: # Should be redundant if `if not tags:` check is done
             click.echo("No tags to display.")
             return

        console = Console()
        console.print(table)

    except RepositoryNotFoundError:
        click.echo(click.style("Error: Not a git repository.", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except GitWriteError as e: # Catching base GitWriteError for other core errors
        click.echo(click.style(f"Error listing tags: {e}", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except ImportError: # For Rich
        click.echo(click.style("Error: Rich library is not installed. Please ensure it is in pyproject.toml and installed.", fg='red'), err=True)
        if ctx: ctx.exit(1)
    except Exception as e: # Catch-all for unexpected errors
        click.echo(click.style(f"An unexpected error occurred: {e}", fg='red'), err=True)
        if ctx: ctx.exit(1)


@cli.group()
def ignore():
    """Manages .gitignore entries."""
    pass

@ignore.command("add")
@click.argument("pattern")
def ignore_add(pattern):
    """Adds a pattern to the .gitignore file."""
    repo_path_str = str(Path.cwd()) # .gitignore is typically in CWD for this command

    result = add_pattern_to_gitignore(repo_path_str, pattern)

    if result['status'] == 'success':
        click.echo(result['message'])
    elif result['status'] == 'exists':
        click.echo(result['message']) # Info message, not an error
    elif result['status'] == 'error':
        click.echo(result['message'], err=True)
    else: # Should not happen
        click.echo("An unexpected issue occurred while adding pattern.", err=True)

@ignore.command(name="list")
def list_patterns():
    """Lists all patterns in the .gitignore file."""
    repo_path_str = str(Path.cwd()) # .gitignore is typically in CWD

    result = list_gitignore_patterns(repo_path_str)

    if result['status'] == 'success':
        patterns_list = result['patterns']
        # Retain Rich Panel formatting
        panel_content_data = "\n".join(patterns_list)
        console = Console()
        console.print(Panel(panel_content_data, title="[bold green].gitignore Contents[/bold green]", expand=False))
    elif result['status'] == 'not_found':
        click.echo(result['message'])
    elif result['status'] == 'empty':
        click.echo(result['message'])
    elif result['status'] == 'error':
        click.echo(result['message'], err=True)
    else: # Should not happen
        click.echo("An unexpected issue occurred while listing patterns.", err=True)


if __name__ == "__main__":
    cli()
