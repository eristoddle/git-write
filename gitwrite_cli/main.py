# Test comment to check write access.
import click
import pygit2
import os
from pathlib import Path
from pygit2 import Signature
from rich.console import Console
from rich.panel import Panel

@click.group()
def cli():
    """GitWrite: A CLI tool for writer-friendly Git repositories."""
    pass

@cli.command()
@click.argument("project_name", required=False)
def init(project_name):
    """Initializes a new GitWrite project or adds GitWrite structure to an existing Git repository."""
    if project_name:
        target_dir = Path(project_name)
        try:
            if target_dir.is_file():
                click.echo(f"Error: '{target_dir}' exists and is a file. Please specify a directory name.", err=True)
                return
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=False)
            elif any(target_dir.iterdir()) and not (target_dir / ".git").is_dir():
                click.echo(f"Error: Directory '{target_dir}' already exists, is not empty, and is not a Git repository.", err=True)
                return
        except Exception as e:
            click.echo(f"Error handling directory '{target_dir}': {e}", err=True)
            return
    else:
        target_dir = Path.cwd()
        if any(target_dir.iterdir()) and not (target_dir / ".git").is_dir():
            click.echo(f"Error: Current directory '{target_dir}' is not empty and not a Git repository. Please use an empty directory or an existing Git repository, or specify a project name.", err=True)
            return

    try:
        is_existing_repo = (target_dir / ".git").is_dir()
        if is_existing_repo:
            repo = pygit2.Repository(str(target_dir))
            click.echo(f"Opened existing Git repository in {target_dir.resolve()}")
        else:
            repo = pygit2.init_repository(str(target_dir))
            click.echo(f"Initialized empty Git repository in {target_dir.resolve()}")

        # Create writer-friendly structure and .gitkeep files
        drafts_dir = target_dir / "drafts"
        notes_dir = target_dir / "notes"
        drafts_dir.mkdir(exist_ok=True)
        notes_dir.mkdir(exist_ok=True)

        drafts_gitkeep = drafts_dir / ".gitkeep"
        notes_gitkeep = notes_dir / ".gitkeep"
        metadata_file = target_dir / "metadata.yml"
        gitignore_file = target_dir / ".gitignore"

        drafts_gitkeep.touch()
        notes_gitkeep.touch()
        metadata_file.touch()
        click.echo("Created/ensured GitWrite directory structure: drafts/, notes/, metadata.yml (with .gitkeep files)")

        # Manage .gitignore
        common_ignores = ["/.venv/", "/.idea/", "/.vscode/", "*.pyc", "__pycache__/"]
        existing_ignores = set()
        if gitignore_file.exists():
            with open(gitignore_file, "r") as f:
                for line in f:
                    existing_ignores.add(line.strip())

        needs_gitignore_update = False
        with open(gitignore_file, "a") as f:
            for item in common_ignores:
                if item not in existing_ignores:
                    f.write(f"{item}\n")
                    needs_gitignore_update = True

        # Stage items
        repo.index.read() # Load existing index if any (important for existing repos)

        items_to_stage = [
            str(Path("drafts") / ".gitkeep"),
            str(Path("notes") / ".gitkeep"),
            "metadata.yml"
        ]
        # Use gitignore_file.name for status_file, as it expects relative paths
        if needs_gitignore_update or not gitignore_file.exists() or not repo.status_file(gitignore_file.name):
            items_to_stage.append(".gitignore")

        staged_anything = False
        for item_path_str in items_to_stage:
            # Check if file exists before trying to add it
            full_item_path = target_dir / item_path_str
            if not full_item_path.exists():
                click.echo(f"Warning: File {full_item_path} not found for staging.", err=True)
                continue

            try:
                # For new repos, or if file is untracked, or modified
                status_flags = repo.status_file(item_path_str)
                if status_flags == pygit2.GIT_STATUS_WT_NEW or \
                   status_flags & pygit2.GIT_STATUS_WT_MODIFIED or \
                   status_flags & pygit2.GIT_STATUS_INDEX_NEW or \
                   is_existing_repo :
                    repo.index.add(item_path_str)
                    staged_anything = True
            except KeyError:
                repo.index.add(item_path_str)
                staged_anything = True
            except Exception as e:
                 click.echo(f"Warning: Could not stage {item_path_str}: {e}", err=True)


        if staged_anything:
            repo.index.write()
            click.echo(f"Staged GitWrite files: {', '.join(items_to_stage)}")
        else:
            click.echo("No new GitWrite structure elements to stage. Files might already be tracked and unchanged.")
            if not repo.head_is_unborn and repo.index.write_tree() == repo.head.peel(pygit2.Tree).id:
                 click.echo("And repository tree is identical to HEAD, no commit needed.")
                 click.echo(f"Successfully processed GitWrite initialization for {target_dir.resolve()}")
                 return


        # Create commit
        author = pygit2.Signature("GitWrite System", "system@gitwrite.io")
        committer = author

        parents = []
        if not repo.head_is_unborn:
            parents = [repo.head.target]

        tree = repo.index.write_tree()

        if repo.head_is_unborn or tree != repo.head.peel(pygit2.Tree).id:
            commit_message_for_init = f"Initialized GitWrite project structure in {target_dir.name}"
            if is_existing_repo and parents:
                commit_message_for_init = f"Added GitWrite structure to {target_dir.name}"

            repo.create_commit("HEAD", author, committer, commit_message_for_init, tree, parents)
            click.echo("Created GitWrite structure commit.")
        else:
            click.echo("No changes to commit. GitWrite structure may already be committed and identical.")

        click.echo(f"Successfully processed GitWrite initialization for {target_dir.resolve()}")

    except pygit2.GitError as e:
        click.echo(f"GitError during init: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during init: {e}", err=True)

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
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot save in a bare repository.", err=True)
            return

        # Determine if we are in a merge or revert state FIRST
        # These details need to be captured *before* any index manipulation by add_all
        # as index changes (like resolving conflicts by add_all) might clear these refs.
        initial_is_completing_operation = None
        initial_merge_head_target_oid = None
        initial_revert_head_details = None

        click.echo("DEBUG: Save command started.")

        # Check for MERGE_HEAD or REVERT_HEAD early, especially if --include is used.
        merge_head_exists = False
        revert_head_exists = False
        try:
            if repo.lookup_reference("MERGE_HEAD").target:
                merge_head_exists = True
                click.echo("DEBUG: MERGE_HEAD found.")
        except KeyError:
            click.echo("DEBUG: MERGE_HEAD not found.")
            pass

        try:
            revert_head_target = repo.lookup_reference("REVERT_HEAD").target
            if revert_head_target and repo.get(revert_head_target).type == pygit2.GIT_OBJECT_COMMIT:
                revert_head_exists = True
                click.echo("DEBUG: REVERT_HEAD found and points to a commit.")
            else:
                click.echo("DEBUG: REVERT_HEAD found but does not point to a valid commit.")
        except KeyError:
            click.echo("DEBUG: REVERT_HEAD not found.")
            pass

        if include_paths:
            if merge_head_exists or revert_head_exists:
                operation = "merge" if merge_head_exists else "revert"
                click.echo(
                    f"Error: Selective staging with --include is not allowed during an active {operation} operation. "
                    "Please resolve the operation first or use 'gitwrite save' without --include.",
                    err=True
                )
                return # Or ctx.fail() if in a context that supports it

            click.echo(f"DEBUG: Selective staging requested for: {include_paths}")
            staged_files_actually_changed = []
            warnings = []

            for path_str in include_paths:
                path_obj = Path(path_str) # Convert to Path object for easier manipulation if needed
                # repo.status_file() expects relative paths from repo root
                # Assuming path_str is already relative to repo root or is absolute
                # If absolute, pygit2 handles it. If relative to subdir, user must ensure it's correct
                # For simplicity, we'll assume path_str is usable by status_file directly.

                try:
                    status_flags = repo.status_file(path_str)
                    click.echo(f"DEBUG: Status for '{path_str}': {status_flags}")

                    if status_flags == pygit2.GIT_STATUS_CURRENT:
                        warnings.append(f"Warning: Path '{path_str}' has no changes to stage.")
                        continue
                    elif status_flags & pygit2.GIT_STATUS_IGNORED:
                        warnings.append(f"Warning: Path '{path_str}' is ignored.")
                        continue
                    elif status_flags == 0: # Should be caught by GIT_STATUS_CURRENT, but as a safeguard
                        warnings.append(f"Warning: Path '{path_str}' has no changes to stage (status is 0).")
                        continue

                    # Check for untracked files explicitly if not covered by other WT flags for addition
                    is_worktree_new = status_flags & pygit2.GIT_STATUS_WT_NEW
                    is_worktree_modified = status_flags & pygit2.GIT_STATUS_WT_MODIFIED
                    is_worktree_deleted = status_flags & pygit2.GIT_STATUS_WT_DELETED
                    is_worktree_renamed = status_flags & pygit2.GIT_STATUS_WT_RENAMED
                    is_worktree_typechange = status_flags & pygit2.GIT_STATUS_WT_TYPECHANGE

                    # Any relevant change in the working tree that can be staged
                    if is_worktree_new or is_worktree_modified or is_worktree_deleted or is_worktree_renamed or is_worktree_typechange:
                        click.echo(f"DEBUG: Staging '{path_str}'...")
                        repo.index.add(path_str)
                        staged_files_actually_changed.append(path_str)
                    else:
                        # This case might indicate a file that is in a state not typically "staged" directly by add,
                        # e.g. GIT_STATUS_INDEX_NEW, GIT_STATUS_INDEX_MODIFIED etc. if user includes something already staged.
                        # Or a more complex status. For now, we focus on WT changes.
                        warnings.append(f"Warning: Path '{path_str}' has status {status_flags} which was not explicitly handled for staging new changes.")
                        continue

                except KeyError:
                    warnings.append(f"Warning: Path '{path_str}' is not tracked by Git or does not exist.")
                    continue
                except Exception as e:
                    warnings.append(f"Warning: Error processing path '{path_str}': {e}")
                    continue

            for warning in warnings:
                click.echo(warning, err=True)

            if not staged_files_actually_changed:
                click.echo("No specified files had changes to stage.")
                click.echo("No changes to save.")
                return
            else:
                repo.index.write()
                click.echo(f"Staged specified files: {', '.join(staged_files_actually_changed)}")
                # Proceed to commit logic

        else: # Default (stage all) logic
            click.echo("DEBUG: No --include paths provided, proceeding with default staging logic.")
            # The original logic for determining merge/revert state for 'stage all'
            if merge_head_exists:
                initial_is_completing_operation = 'merge'
                initial_merge_head_target_oid = repo.lookup_reference("MERGE_HEAD").target
                click.echo(f"DEBUG: MERGE_HEAD confirmed. Target OID: {initial_merge_head_target_oid}")
                click.echo("Repository is in a merge state (MERGE_HEAD found).")

            if not initial_is_completing_operation and revert_head_exists:
                reverted_commit_oid = repo.lookup_reference("REVERT_HEAD").target # We know it's a commit from above
                reverted_commit = repo.get(reverted_commit_oid)
                initial_is_completing_operation = 'revert'
                initial_revert_head_details = {
                    "short_id": reverted_commit.short_id,
                    "id": str(reverted_commit.id),
                    "message_first_line": reverted_commit.message.splitlines()[0]
                }
                click.echo(f"DEBUG: REVERT_HEAD confirmed. Details: {initial_revert_head_details}")
                click.echo(f"Repository is in a revert state (REVERT_HEAD found for commit {initial_revert_head_details['short_id']}).")

            click.echo(f"DEBUG: Initial is_completing_operation (captured for stage-all): {initial_is_completing_operation}")

            if initial_is_completing_operation == 'revert':
            # Check for conflicts *before* staging for revert operations
            has_initial_revert_conflicts = False
            if repo.index.conflicts is not None:
                try:
                    next(iter(repo.index.conflicts))
                    has_initial_revert_conflicts = True
                except StopIteration:
                    pass # No conflicts

            if has_initial_revert_conflicts:
                click.echo("Error: Unresolved conflicts detected during revert.", err=True)
                click.echo("Please resolve them before saving.", err=True)
                conflicting_files_display = []
                if repo.index.conflicts is not None: # Re-check for safety, though it should be same as above
                    for conflict_item_tuple in repo.index.conflicts:
                        path_to_display = next((entry.path for entry in conflict_item_tuple if entry and entry.path), "unknown_path")
                        if path_to_display not in conflicting_files_display:
                            conflicting_files_display.append(path_to_display)
                if conflicting_files_display:
                    click.echo("Conflicting files: " + ", ".join(sorted(conflicting_files_display)), err=True)
                return # Abort save
        elif initial_is_completing_operation == 'merge':
            # Check for conflicts *before* staging, as staging might auto-resolve them from pygit2's perspective
            has_initial_conflicts = False
            if repo.index.conflicts is not None:
                try:
                    next(iter(repo.index.conflicts))
                    has_initial_conflicts = True
                except StopIteration:
                    pass # No conflicts

            if has_initial_conflicts:
                click.echo("Error: Unresolved conflicts detected during merge.", err=True)
                click.echo("Please resolve them before saving.", err=True)
                conflicting_files_display = []
                # This re-check of repo.index.conflicts is okay, it's cheap
                if repo.index.conflicts is not None:
                    for conflict_item_tuple in repo.index.conflicts:
                        path_to_display = next((entry.path for entry in conflict_item_tuple if entry and entry.path), "unknown_path")
                        if path_to_display not in conflicting_files_display:
                            conflicting_files_display.append(path_to_display)
                if conflicting_files_display:
                    click.echo("Conflicting files: " + ", ".join(sorted(conflicting_files_display)), err=True)
                return # Abort save

        # If in a merge or revert state, first try to stage everything.
        # This ensures user's manual resolutions in working dir are staged.
        if initial_is_completing_operation:
            click.echo(f"DEBUG: Actively staging changes from working directory to finalize {initial_is_completing_operation} operation...")
            repo.index.add_all()  # Stage all tracked/modified/new files
            repo.index.write()    # Write updated index to disk
            repo.index.read()     # Re-read index from disk for current repo instance

            # Check for conflicts AFTER staging resolutions
            has_index_conflicts_after_staging = False
            if repo.index.conflicts is not None:
                try:
                    next(iter(repo.index.conflicts))
                    has_index_conflicts_after_staging = True
                except StopIteration:
                    pass # No conflicts
            click.echo(f"DEBUG: Index re-read. Conflicts after staging: {list(repo.index.conflicts) if repo.index.conflicts and has_index_conflicts_after_staging else 'None'}")

            if has_index_conflicts_after_staging:
                if initial_is_completing_operation == 'merge':
                    click.echo("Error: Unresolved conflicts detected during merge.", err=True)
                elif initial_is_completing_operation == 'revert':
                    click.echo("Error: Unresolved conflicts detected during revert.", err=True)
                else:
                    # Fallback, though initial_is_completing_operation should be 'merge' or 'revert' here
                    click.echo(f"Error: Unresolved conflicts detected during {initial_is_completing_operation} operation.", err=True)
                click.echo("Please resolve them before saving.", err=True)
                conflicting_files_display = []
                if repo.index.conflicts is not None:
                    for conflict_item_tuple in repo.index.conflicts:
                        path_to_display = next((entry.path for entry in conflict_item_tuple if entry and entry.path), "unknown_path")
                        if path_to_display not in conflicting_files_display:
                            conflicting_files_display.append(path_to_display)
                if conflicting_files_display:
                    click.echo("Conflicting files: " + ", ".join(sorted(conflicting_files_display)), err=True)
                return # Abort save

        # Check overall repository status for any changes (working dir or staged)
        # This block is now part of the 'else' for 'not include_paths'
        if not include_paths:
            status = repo.status()
            if not initial_is_completing_operation and not status:
                click.echo("No changes to save (working directory and index are clean).")
                return

            # If not already staged by the block above (for merge/revert)
            if status and not initial_is_completing_operation:
                repo.index.add_all()
                repo.index.write()
                click.echo("Staged all changes.")
            elif initial_is_completing_operation and not status: # Merge/revert was resolved, no other changes
                 click.echo("No further working directory changes to stage. Proceeding with finalization of operation.")
            elif not status and not initial_is_completing_operation: # Should be caught by earlier check
                 click.echo("No changes to save.")
                 return

        # Commit logic (common for both selective and full staging, once index is prepared)
        try:
            author = repo.default_signature
        except pygit2.GitError:
            author_name = os.environ.get("GIT_AUTHOR_NAME", "Unknown Author")
            author_email = os.environ.get("GIT_AUTHOR_EMAIL", "author@example.com")
            author = pygit2.Signature(author_name, author_email)
        committer = author

        tree = repo.index.write_tree()
        parents = []
        final_message = message

        click.echo(f"DEBUG: Before parent/message logic: initial_is_completing_operation='{initial_is_completing_operation}'")
        if initial_merge_head_target_oid:
             click.echo(f"DEBUG: initial_merge_head_target_oid='{initial_merge_head_target_oid}'")
        if initial_revert_head_details:
             click.echo(f"DEBUG: initial_revert_head_details='{initial_revert_head_details}'")

        if initial_is_completing_operation == 'merge':
            parents = [repo.head.target, initial_merge_head_target_oid] # Use stored OID
            click.echo(f"DEBUG: Setting up MERGE commit. Parents: [{repo.head.target}, {initial_merge_head_target_oid}]")
        elif initial_is_completing_operation == 'revert' and initial_revert_head_details:
            click.echo(f"DEBUG: Setting up REVERT commit. Details: {initial_revert_head_details}")
            final_message = (
                f"Revert \"{initial_revert_head_details['message_first_line']}\"\n\n"
                f"This reverts commit {initial_revert_head_details['id']}.\n\n"
                f"{message}"
            )
            if not repo.is_empty and not repo.head_is_unborn:
                parents = [repo.head.target]
            else:
                click.echo("Error: Cannot finalize revert, HEAD is unborn.", err=True)
                return
        else:
            if not repo.is_empty and not repo.head_is_unborn:
                parents = [repo.head.target]

        commit_oid = repo.create_commit("HEAD", author, committer, final_message, tree, parents)

        if initial_is_completing_operation:
            click.echo(f"DEBUG: About to call repo.state_cleanup() for {initial_is_completing_operation}")
            if initial_is_completing_operation == 'revert' and initial_revert_head_details:
                click.echo(f"Finalizing revert of commit {initial_revert_head_details['short_id']}.")
            repo.state_cleanup()
            click.echo(f"Successfully completed {initial_is_completing_operation} operation.")

        short_hash = str(commit_oid)[:7]
        try:
            branch_name = repo.head.shorthand
        except pygit2.GitError:
            branch_name = "DETACHED HEAD"
            if repo.head_is_unborn:
                active_branch = next((b for b in repo.branches.local if b.is_head()), None)
                if active_branch:
                    branch_name = active_branch.branch_name
        click.echo(f"[{branch_name} {short_hash}] {message}")

    except pygit2.GitError as e:
        click.echo(f"GitError during save: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during save: {e}", err=True)

@cli.command()
@click.option("-n", "--number", "count", type=int, default=None, help="Number of commits to show.")
def history(count):
    """Shows the commit history of the project."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot show history for a bare repository.", err=True)
            return

        if repo.is_empty or repo.head_is_unborn:
            click.echo("No history yet.")
            return

        from rich.table import Table
        from rich.text import Text
        from rich.console import Console
        from datetime import datetime, timezone, timedelta

        table = Table(title="Commit History")
        table.add_column("Commit", style="cyan", no_wrap=True)
        table.add_column("Author", style="magenta")
        table.add_column("Date", style="green")
        table.add_column("Message", style="white")

        walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME)

        for i, commit_obj in enumerate(walker):
            if count is not None and i >= count:
                break

            short_hash = str(commit_obj.id)[:7]
            author_name = commit_obj.author.name

            tzinfo = timezone(timedelta(minutes=commit_obj.author.offset))
            commit_time_dt = datetime.fromtimestamp(commit_obj.author.time, tzinfo)
            date_str = commit_time_dt.strftime("%Y-%m-%d %H:%M:%S %z")

            message_first_line = commit_obj.message.splitlines()[0] if commit_obj.message else ""

            table.add_row(short_hash, author_name, date_str, Text(message_first_line, overflow="ellipsis"))

        if not table.rows:
             click.echo("No commits found to display.")
             return

        console = Console()
        console.print(table)

    except pygit2.GitError as e:
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
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository.", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot explore in a bare repository.", err=True)
            return
        if repo.is_empty or repo.head_is_unborn:
            click.echo("Error: Cannot create an exploration in an empty repository. Please make some commits first.", err=True)
            return

        if branch_name in repo.branches.local:
            click.echo(f"Error: Exploration '{branch_name}' already exists.", err=True)
            return

        commit_obj_explore = repo.head.peel(pygit2.Commit)
        new_branch = repo.branches.local.create(branch_name, commit_obj_explore)
        refname = f"refs/heads/{branch_name}"
        repo.checkout(refname, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(refname)

        click.echo(f"Switched to a new exploration: {branch_name}")

    except pygit2.GitError as e:
        click.echo(f"GitError during explore: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during explore: {e}", err=True)


@cli.command()
@click.argument("branch_name", required=False)
def switch(branch_name):
    """Switches to an existing exploration (branch) or lists all explorations."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository.", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot switch branches in a bare repository.", err=True)
            return

        if branch_name is None:
            if repo.is_empty or repo.head_is_unborn:
                click.echo("No explorations (branches) yet.")
                return

            from rich.table import Table
            from rich.console import Console

            table = Table(title="Available Explorations")
            table.add_column("Name", style="cyan")

            current_branch_ref_name = repo.head.name

            branches_list = list(repo.branches.local)
            if not branches_list:
                click.echo("No explorations (branches) found.")
                return

            for b_name_iter in sorted(branches_list):
                ref_name_for_branch = f"refs/heads/{b_name_iter}"
                if ref_name_for_branch == current_branch_ref_name:
                    table.add_row(f"* {b_name_iter}")
                else:
                    table.add_row(f"  {b_name_iter}")

            console = Console()
            console.print(table)
            return

        if repo.is_empty or repo.head_is_unborn:
             click.echo(f"Error: Repository is empty or HEAD is unborn. Cannot switch to '{branch_name}'.", err=True)
             return

        target_branch_ref_name = f"refs/heads/{branch_name}"
        branch_obj = repo.branches.get(branch_name)

        if branch_obj is None :
            branch_obj = repo.branches.get(f"origin/{branch_name}")
            if branch_obj:
                target_branch_ref_name = branch_obj.name
            else:
                click.echo(f"Error: Exploration '{branch_name}' not found locally or on common remote 'origin'.", err=True)
                return
        else:
             target_branch_ref_name = branch_obj.name


        if repo.head.name == target_branch_ref_name:
            click.echo(f"Already on exploration: {branch_name}")
            return

        repo.checkout(target_branch_ref_name, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(target_branch_ref_name)

        click.echo(f"Switched to exploration: {branch_name}")

    except pygit2.GitError as e:
        click.echo(f"GitError during switch: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed for listing branches.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during switch: {e}", err=True)

@cli.command("merge")
@click.argument("branch_name")
def merge_command(branch_name):
    """Merges the specified exploration (branch) into the current one."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository.", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot merge in a bare repository.", err=True)
            return
        if repo.is_empty or repo.head_is_unborn:
            click.echo("Error: Repository is empty or HEAD is unborn. Cannot perform merge.", err=True)
            return

        current_branch_shorthand = repo.head.shorthand
        if current_branch_shorthand == branch_name:
            click.echo("Error: Cannot merge a branch into itself.", err=True)
            return

        target_branch_obj = repo.branches.get(branch_name)
        if not target_branch_obj:
            click.echo(f"Error: Exploration '{branch_name}' not found.", err=True)
            return

        target_commit_obj_merge = repo[target_branch_obj.target]

        merge_result_analysis, _ = repo.merge_analysis(target_commit_obj_merge.id)

        if merge_result_analysis & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
            click.echo(f"Already up-to-date with {branch_name}.")
            return

        elif merge_result_analysis & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
            click.echo(f"Attempting Fast-forward merge for {branch_name} into {current_branch_shorthand}...")
            current_branch_full_ref_name_merge = repo.head.name
            current_branch_ref = repo.lookup_reference(current_branch_full_ref_name_merge)
            current_branch_ref.set_target(target_commit_obj_merge.id)
            repo.checkout(current_branch_full_ref_name_merge, strategy=pygit2.GIT_CHECKOUT_FORCE)
            click.echo(f"Fast-forwarded {current_branch_shorthand} to {branch_name} (commit {str(target_commit_obj_merge.id)[:7]}).")
            return

        elif merge_result_analysis & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
            click.echo(f"Attempting Normal merge for {branch_name} into {current_branch_shorthand}...")
            repo.merge(target_commit_obj_merge.id)

            has_conflicts_merge = False
            if repo.index.conflicts is not None:
                for _conflict_entry_merge in repo.index.conflicts:
                    has_conflicts_merge = True
                    break

            if has_conflicts_merge:
                click.echo("Automatic merge failed; fix conflicts and then commit the result using 'gitwrite save'.", err=True)
                click.echo("Conflicting files:")
                if repo.index.conflicts:
                    for conflict_entries_tuple_merge in repo.index.conflicts:
                        our_entry = conflict_entries_tuple_merge[1]
                        their_entry = conflict_entries_tuple_merge[2]
                        path_to_print = (our_entry.path if our_entry else
                                         (their_entry.path if their_entry else "unknown_path"))
                        click.echo(f"  {path_to_print}")
                return

            try:
                author_sig = repo.default_signature
            except pygit2.GitError:
                author_name_env = os.environ.get("GIT_AUTHOR_NAME", "Unknown Author")
                author_email_env = os.environ.get("GIT_AUTHOR_EMAIL", "author@example.com")
                author_sig = pygit2.Signature(author_name_env, author_email_env)
            committer_sig = author_sig

            tree = repo.index.write_tree()
            parents = [repo.head.target, target_commit_obj_merge.id]
            merge_commit_msg_text = f"Merge branch '{branch_name}' into {current_branch_shorthand}"

            repo.create_commit("HEAD", author_sig, committer_sig, merge_commit_msg_text, tree, parents)
            click.echo(f"Merged {branch_name} into {current_branch_shorthand}.")
            repo.state_cleanup()
            return

        else:
            click.echo(f"Merge not possible. Analysis result code: {merge_result_analysis}", err=True)
            if merge_result_analysis & pygit2.GIT_MERGE_ANALYSIS_UNBORN:
                 click.echo("The HEAD of the repository is unborn; cannot merge.", err=True)


    except pygit2.GitError as e:
        click.echo(f"GitError during merge: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during merge: {e}", err=True)

@cli.command()
@click.argument("ref1_str", metavar="REF1", required=False, default=None)
@click.argument("ref2_str", metavar="REF2", required=False, default=None)
def compare(ref1_str, ref2_str):
    """Compares two references (commits, branches, tags) or shows changes in working directory."""
    from rich.console import Console
    from rich.text import Text
    import difflib

    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository.", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot compare in a bare repository.", err=True)
            return
        if repo.is_empty or repo.head_is_unborn:
             if ref1_str or ref2_str:
                click.echo("Error: Repository is empty or HEAD is unborn. Cannot compare specific references.", err=True)
                return

        commit1_obj = None
        commit2_obj = None

        if ref1_str is None and ref2_str is None:
            if repo.is_empty or repo.head_is_unborn:
                 click.echo("Error: Repository is empty or HEAD is unborn. Cannot perform default comparison (HEAD vs HEAD~1).", err=True)
                 return
            try:
                commit2_obj = repo.head.peel(pygit2.Commit)
                if not commit2_obj.parents:
                    click.echo("Error: HEAD has no parents to compare with (it's the initial commit).", err=True)
                    return
                commit1_obj = commit2_obj.parents[0]
            except pygit2.GitError as e:
                click.echo(f"Error resolving default comparison (HEAD vs HEAD~1): {e}", err=True)
                return
            except IndexError:
                click.echo("Error: HEAD has no parents to compare with (it's the initial commit).", err=True)
                return
            ref1_str, ref2_str = "HEAD~1", "HEAD"

        elif ref1_str is not None and ref2_str is None:
            if repo.is_empty or repo.head_is_unborn:
                 click.echo("Error: Repository is empty or HEAD is unborn. Cannot compare with HEAD.", err=True)
                 return
            try:
                commit2_obj = repo.head.peel(pygit2.Commit)
                commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
            except (pygit2.GitError, KeyError, TypeError) as e:
                click.echo(f"Error: Could not resolve reference '{ref1_str}': {e}", err=True)
                return
            ref2_str = "HEAD"

        elif ref1_str is not None and ref2_str is not None:
            try:
                commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
                commit2_obj = repo.revparse_single(ref2_str).peel(pygit2.Commit)
            except (pygit2.GitError, KeyError, TypeError) as e:
                click.echo(f"Error: Could not resolve references ('{ref1_str}', '{ref2_str}'): {e}", err=True)
                return
        else:
            click.echo("Error: Invalid combination of references for comparison.", err=True)
            return

        if not commit1_obj or not commit2_obj:
            click.echo("Error: Could not resolve one or both references to commits.", err=True)
            return

        tree1 = commit1_obj.tree
        tree2 = commit2_obj.tree

        diff_obj = repo.diff(tree1, tree2, context_lines=3, interhunk_lines=1)

        if not diff_obj:
            click.echo(f"No differences found between {ref1_str} and {ref2_str}.")
            return

        console = Console()
        console.print(f"Diff between {ref1_str} (a) and {ref2_str} (b):")

        for patch_obj in diff_obj:
            console.print(f"--- a/{patch_obj.delta.old_file.path}\n+++ b/{patch_obj.delta.new_file.path}", style="bold yellow")
            for hunk_obj in patch_obj.hunks:
                console.print(hunk_obj.header.strip(), style="cyan")
                lines_in_hunk = list(hunk_obj.lines)
                i = 0
                while i < len(lines_in_hunk):
                    line_obj = lines_in_hunk[i]
                    content = line_obj.content.rstrip('\r\n')

                    if line_obj.origin == '-' and (i + 1 < len(lines_in_hunk)) and lines_in_hunk[i+1].origin == '+':
                        old_content = content
                        new_content = lines_in_hunk[i+1].content.rstrip('\r\n')

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
                    if line_obj.origin == '-':
                        console.print(Text(f"-{content}", style="red"))
                    elif line_obj.origin == '+':
                        console.print(Text(f"+{content}", style="green"))
                    elif line_obj.origin == ' ':
                        console.print(f" {content}")
                    i += 1
    except IndexError:
         click.echo("Error: Not enough history to perform comparison (e.g., initial commit has no parent).", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is in pyproject.toml and installed.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during compare: {e}", err=True)


@cli.command()
@click.option("--remote", "remote_name", default="origin", help="The remote to sync with.")
@click.option("--branch", "branch_name_opt", default=None, help="The branch to sync. Defaults to the current branch.")
def sync(remote_name, branch_name_opt):
    """Fetches changes from a remote, integrates them, and pushes local changes."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot sync in a bare repository.", err=True)
            return

        if repo.is_empty or repo.head_is_unborn:
            click.echo("Error: Repository is empty or HEAD is unborn. Please make some commits first.", err=True)
            return

        current_branch_obj_sync = None
        if branch_name_opt:
            current_branch_full_ref_name_sync = f"refs/heads/{branch_name_opt}"
            try:
                current_branch_obj_sync = repo.lookup_reference(current_branch_full_ref_name_sync)
            except KeyError:
                click.echo(f"Error: Branch '{branch_name_opt}' not found.", err=True)
                return
            if not current_branch_obj_sync.is_branch():
                click.echo(f"Error: '{branch_name_opt}' is not a local branch.", err=True)
                return
        else:
            if repo.head_is_detached:
                click.echo("Error: HEAD is detached. Please switch to a branch to sync.", err=True)
                return
            current_branch_obj_sync = repo.head
            branch_name_opt = current_branch_obj_sync.shorthand
            # current_branch_full_ref_name_sync = current_branch_obj_sync.name # Already have this

        click.echo(f"Syncing branch '{branch_name_opt}' with remote '{remote_name}'...")
        try:
            remote_obj = repo.remotes[remote_name]
        except KeyError:
            click.echo(f"Error: Remote '{remote_name}' not found.", err=True)
            return
        except Exception as e:
            click.echo(f"Error accessing remote '{remote_name}': {e}", err=True)
            return

        click.echo(f"Fetching from remote '{remote_name}'...")
        try:
            stats = remote_obj.fetch()
            if hasattr(stats, 'received_objects') and hasattr(stats, 'total_objects'):
                 click.echo(f"Fetch complete. Received {stats.received_objects}/{stats.total_objects} objects.")
            else:
                 click.echo("Fetch complete. (No detailed stats available from fetch operation)")
        except pygit2.GitError as e:
            click.echo(f"Error during fetch: {e}", err=True)
            if "authentication required" in str(e).lower():
                click.echo("Hint: Ensure your SSH keys or credential manager are configured correctly.", err=True)
            return
        except Exception as e:
            click.echo(f"An unexpected error occurred during fetch: {e}", err=True)
            return

        click.echo("Attempting to integrate remote changes...")
        local_commit_oid_sync = current_branch_obj_sync.target
        remote_tracking_branch_full_name_sync = f"refs/remotes/{remote_name}/{branch_name_opt}"
        try:
            remote_branch_ref_sync = repo.lookup_reference(remote_tracking_branch_full_name_sync)
            their_commit_oid_sync = remote_branch_ref_sync.target
        except KeyError:
            click.echo(f"Error: Remote tracking branch '{remote_tracking_branch_full_name_sync}' not found. Has it been fetched?", err=True)
            return
        except Exception as e:
            click.echo(f"Error looking up remote tracking branch '{remote_tracking_branch_full_name_sync}': {e}", err=True)
            return

        if local_commit_oid_sync == their_commit_oid_sync:
            click.echo("Local branch is already up-to-date with remote.")
        else:
            if repo.head.target != local_commit_oid_sync:
                 repo.set_head(current_branch_obj_sync.name)

            merge_result_analysis_sync, _ = repo.merge_analysis(their_commit_oid_sync)

            if merge_result_analysis_sync & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                click.echo(f"Branch '{branch_name_opt}' is already up-to-date with '{remote_tracking_branch_full_name_sync}'.")
            elif merge_result_analysis_sync & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                click.echo(f"Attempting Fast-forward for branch '{branch_name_opt}'...")
                try:
                    current_branch_obj_sync.set_target(their_commit_oid_sync)
                    repo.checkout(current_branch_obj_sync.name, strategy=pygit2.GIT_CHECKOUT_FORCE)
                    click.echo(f"Fast-forwarded '{branch_name_opt}' to match '{remote_tracking_branch_full_name_sync}'.")
                except pygit2.GitError as e:
                    click.echo(f"Error during fast-forward: {e}. Your branch may be in an inconsistent state.", err=True)
                    return
            elif merge_result_analysis_sync & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                click.echo(f"Attempting Normal merge of '{remote_tracking_branch_full_name_sync}' into '{branch_name_opt}'...")
                try:
                    repo.merge(their_commit_oid_sync)
                    repo.index.write()

                    has_actual_conflicts_sync = False
                    if repo.index.conflicts is not None:
                        for _conflict_entry_sync in repo.index.conflicts:
                            has_actual_conflicts_sync = True
                            break
                    if has_actual_conflicts_sync:
                        click.echo("Conflicts detected. Please resolve them manually and then run 'gitwrite save'.", err=True)
                        conflicting_files_display = []
                        if repo.index.conflicts:
                            for conflict_item_tuple_sync in repo.index.conflicts:
                                path_to_display = next((entry.path for entry in conflict_item_tuple_sync if entry and entry.path), "unknown_path")
                                if path_to_display not in conflicting_files_display:
                                     conflicting_files_display.append(path_to_display)
                        if conflicting_files_display:
                             click.echo("Conflicting files: " + ", ".join(sorted(conflicting_files_display)), err=True)
                        return
                    else:
                        click.echo("No conflicts. Creating merge commit...")
                        try:
                            author_sig_sync = repo.default_signature
                            committer_sig_sync = repo.default_signature
                        except pygit2.GitError:
                            author_name_env_sync = os.environ.get("GIT_AUTHOR_NAME", "GitWrite User")
                            author_email_env_sync = os.environ.get("GIT_AUTHOR_EMAIL", "user@gitwrite.io")
                            author_sig_sync = pygit2.Signature(author_name_env_sync, author_email_env_sync)
                            committer_sig_sync = author_sig_sync
                        tree_sync = repo.index.write_tree()
                        parents_sync = [local_commit_oid_sync, their_commit_oid_sync]
                        merge_commit_message_text_sync = f"Merge remote-tracking branch '{remote_tracking_branch_full_name_sync}' into {branch_name_opt}"
                        repo.create_commit(current_branch_obj_sync.name, author_sig_sync, committer_sig_sync, merge_commit_message_text_sync, tree_sync, parents_sync)
                        repo.state_cleanup()
                        click.echo("Successfully merged remote changes.")
                except pygit2.GitError as e:
                    click.echo(f"Error during merge process: {e}", err=True)
                    repo.state_cleanup()
                    return
            elif merge_result_analysis_sync & pygit2.GIT_MERGE_ANALYSIS_UNBORN:
                 click.echo(f"Merge not possible: '{branch_name_opt}' or '{remote_tracking_branch_full_name_sync}' is an unborn branch.", err=True)
                 return
            else:
                click.echo(f"Merge not possible. Analysis result: {merge_result_analysis_sync}. Local and remote histories may have diverged significantly.", err=True)
                return

        click.echo(f"Attempting to push local changes from '{branch_name_opt}' to '{remote_name}/{branch_name_opt}'...")
        try:
            refspec_sync = f"refs/heads/{branch_name_opt}:refs/heads/{branch_name_opt}"
            remote_obj.push([refspec_sync])
            click.echo("Push successful.")
        except pygit2.GitError as e:
            click.echo(f"Error during push: {e}", err=True)
            if "non-fast-forward" in str(e).lower():
                click.echo("Hint: The remote has changes that were not integrated locally. Try running sync again or manually resolving.", err=True)
            elif "authentication required" in str(e).lower():
                click.echo("Hint: Ensure your SSH keys or credential manager are configured for push access.", err=True)
        except Exception as e:
            click.echo(f"An unexpected error occurred during push: {e}", err=True)

        click.echo(f"Sync process for branch '{branch_name_opt}' with remote '{remote_name}' completed.")

    except pygit2.GitError as e:
        click.echo(f"GitError during sync: {e}", err=True)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during sync: {e}", err=True)


@cli.command()
@click.argument("commit_ref")
@click.pass_context
@click.option("-m", "--mainline", "mainline_option", type=int, default=None, help="For merge commits, the parent number (1-indexed) to revert towards.")
def revert(ctx, commit_ref, mainline_option):
    """Reverts a commit.

    <commit_ref> is the commit reference (e.g., commit hash, branch name, HEAD) to revert.
    For merge commits, use --mainline to specify the parent (e.g., 1 or 2).
    """
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            ctx.fail("Error: Not a Git repository (or any of the parent directories).")
        repo = pygit2.Repository(repo_path_str)
    except pygit2.GitError as e:
        ctx.fail(f"Error initializing repository: {e}")

    if repo.is_bare:
        ctx.fail("Error: Cannot revert in a bare repository.")

    try:
        commit_to_revert_obj_revert = repo.revparse_single(commit_ref)
        if commit_to_revert_obj_revert.type != pygit2.GIT_OBJECT_COMMIT:
            ctx.fail(f"Error: '{commit_ref}' does not resolve to a commit.")
        commit_to_revert = commit_to_revert_obj_revert.peel(pygit2.Commit)
        click.echo(f"Attempting to revert commit: {commit_to_revert.short_id} ('{commit_to_revert.message.strip().splitlines()[0]}')")

    except (KeyError, pygit2.GitError):
        ctx.fail(f"Error: Invalid or ambiguous commit reference '{commit_ref}'.")
    except Exception as e:
        ctx.fail(f"Error resolving commit '{commit_ref}': {e}")

    status_revert = repo.status()
    is_dirty = False
    for _filepath_revert, flags_revert in status_revert.items():
        if flags_revert != pygit2.GIT_STATUS_CURRENT:
            if flags_revert & pygit2.GIT_STATUS_WT_NEW and not (flags_revert & pygit2.GIT_STATUS_INDEX_NEW):
                continue
            is_dirty = True
            break

    if is_dirty:
        ctx.fail("Error: Your working directory or index has uncommitted changes.\nPlease commit or stash them before attempting to revert.")

    is_merge_commit = len(commit_to_revert.parents) > 1

    if is_merge_commit:
        ctx.fail(
            f"Error: Commit '{commit_to_revert.short_id}' is a merge commit. "
            "Reverting merge commits with specific mainline parent selection to only update the "
            "working directory/index (before creating a commit) is not supported with the current "
            "underlying library (pygit2.Repository.revert()). "
            "Consider reverting using standard git commands or a different tool for this specific operation."
        )
    elif mainline_option is not None:
        click.echo(f"Warning: Commit {commit_to_revert.short_id} is not a merge commit. The --mainline option will be ignored.", fg="yellow")

    try:
        repo.revert(commit_to_revert)
        click.echo(f"Index updated to reflect revert of commit {commit_to_revert.short_id}.")

    except pygit2.GitError as e:
        error_message_detail = str(e)
        custom_error_message = (
            f"Error during revert operation: {error_message_detail}\nThis might be due to complex changes that "
            "cannot be automatically reverted or unresolved conflicts."
        )
        if "takes 1 positional argument but 2 were given" in error_message_detail or \
           "takes at most 1 positional argument" in error_message_detail or \
           "unexpected keyword argument" in error_message_detail:
            custom_error_message = (
                f"Error during revert operation: {error_message_detail}.\n"
                "This indicates an issue with how pygit2's Repository.revert() handles arguments for mainline parent selection (if at all for index-only reverts)."
            )

        has_conflicts_after_error_revert = False
        if repo.index.conflicts is not None:
            try:
                next(iter(repo.index.conflicts))
                has_conflicts_after_error_revert = True
            except StopIteration:
                pass
        if has_conflicts_after_error_revert:
            custom_error_message += "\nConflicts were detected in the index. Please resolve them and then commit."
        ctx.fail(custom_error_message)
    except Exception as e:
        ctx.fail(f"An unexpected error occurred during revert: {e}")

    has_conflicts_revert_check = False
    if repo.index.conflicts is not None:
        try:
            next(iter(repo.index.conflicts))
            has_conflicts_revert_check = True
        except StopIteration:
            pass

    if has_conflicts_revert_check:
        click.echo("Conflicts detected after revert. Automatic commit aborted.", err=True)
        click.echo("Please resolve the conflicts manually and then commit the changes using 'gitwrite save'.", err=True)
        click.echo("Conflicting files:", err=True)
        if repo.index.conflicts:
            for conflict_entries_tuple_iter_revert in repo.index.conflicts:
                our_entry_revert = conflict_entries_tuple_iter_revert[1]
                their_entry_revert = conflict_entries_tuple_iter_revert[2]
                path_to_print_revert = (our_entry_revert.path if our_entry_revert else
                                 (their_entry_revert.path if their_entry_revert else "unknown_path"))
                click.echo(f"  {path_to_print_revert}", err=True)
        return
    else:
        click.echo("No conflicts detected. Proceeding to create revert commit.")
        try:
            try:
                author_sig_revert = repo.default_signature
                committer_sig_revert = repo.default_signature
            except pygit2.GitError:
                author_name_env_revert = os.environ.get("GIT_AUTHOR_NAME", "GitWrite User")
                author_email_env_revert = os.environ.get("GIT_AUTHOR_EMAIL", "user@gitwrite.io")
                author_sig_revert = Signature(author_name_env_revert, author_email_env_revert)
                committer_sig_revert = author_sig_revert

            original_message_first_line_revert = commit_to_revert.message.splitlines()[0]
            revert_message_text = f"Revert \"{original_message_first_line_revert}\"\n\nThis reverts commit {commit_to_revert.id}."

            if repo.head_is_unborn:
                ctx.fail("Error: HEAD is unborn. Cannot create revert commit.")
            parents_revert = [repo.head.target]
            tree_oid_revert = repo.index.write_tree()
            new_commit_oid_revert = repo.create_commit("HEAD", author_sig_revert, committer_sig_revert, revert_message_text, tree_oid_revert, parents_revert)
            reverted_commit_short_id_display = commit_to_revert.short_id
            new_commit_short_id_display = str(new_commit_oid_revert)[:7]
            click.echo(f"Successfully reverted commit {reverted_commit_short_id_display}. New commit: {new_commit_short_id_display}")
            repo.state_cleanup()
        except pygit2.GitError as e:
            ctx.fail(f"Error creating revert commit: {e}\nYour working directory might contain the reverted changes, but the commit failed.\nYou may need to manually commit using 'gitwrite save'.")
        except Exception as e:
            ctx.fail(f"An unexpected error occurred during revert commit creation: {e}")


@cli.group()
def tag():
    """Manages tags."""
    pass


@tag.command("add")
@click.argument("tag_name")
@click.argument("commit_ref", required=False, default="HEAD")
@click.option("-m", "--message", "message_opt_tag", help="Annotation message for the tag.")
def tag_add(tag_name, commit_ref, message_opt_tag):
    """Creates a new tag.

    If -m/--message is provided, an annotated tag is created.
    Otherwise, a lightweight tag is created.
    The tag points to COMMIT_REF, which defaults to HEAD.
    """
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot create tags in a bare repository.", err=True)
            return

        if repo.is_empty or repo.head_is_unborn:
            click.echo("Error: Repository is empty or HEAD is unborn. Cannot create tag.", err=True)
            return

        try:
            target_commit_obj_tag = repo.revparse_single(commit_ref).peel(pygit2.Commit)
        except (KeyError, pygit2.GitError):
            click.echo(f"Error: Commit reference '{commit_ref}' not found or invalid.", err=True)
            return

        tag_ref_name_tag = f"refs/tags/{tag_name}"

        if tag_ref_name_tag in repo.references:
             click.echo(f"Error: Tag '{tag_name}' already exists.", err=True)
             return
        try:
            repo.revparse_single(tag_name)
            click.echo(f"Error: Tag '{tag_name}' already exists (possibly as an annotated tag object not listed directly in refs/tags/).", err=True)
            return
        except (pygit2.GitError, KeyError):
            pass


        if message_opt_tag:
            try:
                tagger_sig = repo.default_signature
            except pygit2.GitError:
                tagger_name_env = os.environ.get("GIT_TAGGER_NAME", "Unknown Tagger")
                tagger_email_env = os.environ.get("GIT_TAGGER_EMAIL", "tagger@example.com")
                tagger_sig = pygit2.Signature(tagger_name_env, tagger_email_env)

            try:
                repo.create_tag(
                    tag_name,
                    target_commit_obj_tag.id,
                    pygit2.GIT_OBJECT_COMMIT,
                    tagger_sig,
                    message_opt_tag
                )
                click.echo(f"Annotated tag '{tag_name}' created successfully, pointing to {target_commit_obj_tag.short_id}.")
            except pygit2.GitError as e:
                if "exists" in str(e).lower() or "already exists" in str(e).lower():
                     click.echo(f"Error: Tag '{tag_name}' already exists (detected by create_tag).", err=True)
                else:
                    click.echo(f"Error creating annotated tag '{tag_name}': {e}", err=True)
                return
        else:
            try:
                repo.references.create(tag_ref_name_tag, target_commit_obj_tag.id)
                click.echo(f"Lightweight tag '{tag_name}' created successfully, pointing to {target_commit_obj_tag.short_id}.")
            except pygit2.GitError as e:
                if "exists" in str(e).lower() or "already exists" in str(e).lower():
                     click.echo(f"Error: Tag '{tag_name}' already exists (detected by references.create).", err=True)
                else:
                    click.echo(f"Error creating lightweight tag '{tag_name}': {e}", err=True)
                return

    except pygit2.GitError as e:
        click.echo(f"GitError during tag creation: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during tag creation: {e}", err=True)


@tag.command("list")
def tag_list():
    """Lists all tags in the repository."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return
        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot list tags in a bare repository.", err=True)
            return

        tag_names_list = repo.listall_tags()

        if not tag_names_list:
            click.echo("No tags found in the repository.")
            return

        from rich.table import Table
        from rich.console import Console

        table = Table(title="Repository Tags")
        table.add_column("Tag Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Target Commit", style="green")
        table.add_column("Message (Annotated Only)", style="white", overflow="ellipsis")

        for tag_name_iter_list in sorted(tag_names_list):
            tag_type_display = "Unknown"
            target_commit_short_id_display = "N/A"
            message_summary_display = "-"

            try:
                obj_tag = repo.revparse_single(tag_name_iter_list)

                if obj_tag.type == pygit2.GIT_OBJECT_TAG:
                    if hasattr(obj_tag, 'message') and hasattr(obj_tag, 'tagger') and hasattr(obj_tag, 'target'):
                        tag_type_display = "Annotated"
                        annotated_tag_object_item = obj_tag
                        try:
                            if annotated_tag_object_item.message:
                                message_summary_display = annotated_tag_object_item.message.splitlines()[0]
                            else:
                                message_summary_display = "-"
                        except Exception:
                            message_summary_display = "ERR_MSG_PROCESSING"

                        try:
                            target_oid_tag = annotated_tag_object_item.target
                            target_pointed_to_obj_tag = repo.get(target_oid_tag)
                            if target_pointed_to_obj_tag:
                               try:
                                   commit_obj_tag_target = target_pointed_to_obj_tag.peel(pygit2.Commit)
                                   target_commit_short_id_display = commit_obj_tag_target.short_id
                               except (KeyError, TypeError, pygit2.GitError):
                                   target_commit_short_id_display = f"ERR_PEEL:{str(target_oid_tag)[:7]}"
                            else:
                                target_commit_short_id_display = "ERR_TARGET_OBJ_NOT_FOUND"
                        except Exception as e_target:
                            target_commit_short_id_display = f"ERR_TARGET_PROCESSING:{type(e_target).__name__}"
                            if hasattr(annotated_tag_object_item, 'target'):
                                raw_target_val = getattr(annotated_tag_object_item, 'target', 'NO_TARGET_ATTR')
                                target_commit_short_id_display += f" (target_val:{str(raw_target_val)[:7]})"
                            if target_commit_short_id_display == "N/A":
                                target_commit_short_id_display = f"ERR_TARGET_UNCAUGHT:{type(e_target).__name__}"
                    else:
                        tag_type_display = "Annotated (No Attrs)"
                        message_summary_display = "Tag object lacks expected attrs."
                elif obj_tag.type == pygit2.GIT_OBJECT_COMMIT:
                    tag_type_display = "Lightweight"
                    commit_obj_lw_tag = obj_tag.peel(pygit2.Commit)
                    target_commit_short_id_display = commit_obj_lw_tag.short_id
                else:
                    tag_type_display = "Lightweight"
                    target_commit_short_id_display = f"{obj_tag.short_id} ({obj_tag.type_name})"
            except (KeyError, pygit2.GitError) as e:
                message_summary_display = f"Error resolving: {e}"
            except Exception as e:
                message_summary_display = f"Unexpected error: {e}"

            table.add_row(
                str(tag_name_iter_list),
                str(tag_type_display),
                str(target_commit_short_id_display),
                str(message_summary_display)
            )

        if not table.rows:
            click.echo("No tags to display.")
            return

        console = Console()
        console.print(table)

    except pygit2.GitError as e:
        click.echo(f"GitError during tag listing: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is in pyproject.toml and installed.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during tag listing: {e}", err=True)


@cli.group()
def ignore():
    """Manages .gitignore entries."""
    pass

@ignore.command("add")
@click.argument("pattern")
def ignore_add(pattern):
    """Adds a pattern to the .gitignore file."""
    gitignore_file_path = Path.cwd() / ".gitignore"
    pattern_to_add = pattern.strip()

    if not pattern_to_add:
        click.echo("Error: Pattern cannot be empty.", err=True)
        return

    existing_patterns = set()
    last_line_had_newline = True
    try:
        if gitignore_file_path.exists():
            with open(gitignore_file_path, "r") as f:
                content_data = f.read()
                if content_data:
                    lines_data = content_data.splitlines()
                    for line_iter_ignore in lines_data:
                        existing_patterns.add(line_iter_ignore.strip())
                    if content_data.endswith("\n") or content_data.endswith("\r"):
                        last_line_had_newline = True
                    else:
                        last_line_had_newline = False
                else:
                    last_line_had_newline = True
        else:
            last_line_had_newline = True

    except (IOError, OSError) as e:
        click.echo(f"Error reading .gitignore: {e}", err=True)
        return

    if pattern_to_add in existing_patterns:
        click.echo(f"Pattern '{pattern_to_add}' already exists in .gitignore.")
        return

    try:
        with open(gitignore_file_path, "a") as f:
            if not last_line_had_newline:
                f.write("\n")
            f.write(f"{pattern_to_add}\n")
        click.echo(f"Pattern '{pattern_to_add}' added to .gitignore.")
    except (IOError, OSError) as e:
        click.echo(f"Error writing to .gitignore: {e}", err=True)

@ignore.command(name="list")
def list_patterns():
    """Lists all patterns in the .gitignore file."""
    gitignore_file_path_list = Path.cwd() / ".gitignore"
    console = Console()

    try:
        if not gitignore_file_path_list.exists():
            click.echo(".gitignore file not found.")
            return

        with open(gitignore_file_path_list, "r") as f:
            content_data_list = f.read()

        if not content_data_list.strip():
            click.echo(".gitignore is empty.")
            return

        patterns_list_ignore = [line.strip() for line in content_data_list.splitlines() if line.strip()]

        if not patterns_list_ignore:
            click.echo(".gitignore is effectively empty (contains only whitespace).")
            return

        panel_content_data = "\n".join(patterns_list_ignore)
        console.print(Panel(panel_content_data, title="[bold green].gitignore Contents[/bold green]", expand=False))

    except (IOError, OSError) as e:
        click.echo(f"Error reading .gitignore: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library not found. Cannot display .gitignore contents with formatting.", err=True)
        if 'content_data_list' in locals():
            click.echo("\n.gitignore Contents (basic view):")
            for line_iter_basic_ignore in content_data_list.splitlines():
                if line_iter_basic_ignore.strip():
                    click.echo(line_iter_basic_ignore.strip())


if __name__ == "__main__":
    cli()
