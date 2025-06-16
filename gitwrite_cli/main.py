# Test comment to check write access.
import click
import pygit2
import os
from pathlib import Path

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
        if needs_gitignore_update or not gitignore_file.exists() or not repo.status_file(str(gitignore_file)):
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
                status = repo.status_file(item_path_str)
                if status == pygit2.GIT_STATUS_WT_NEW or \
                   status & pygit2.GIT_STATUS_WT_MODIFIED or \
                   status & pygit2.GIT_STATUS_INDEX_NEW or \
                   is_existing_repo : # In existing repo, be more liberal with adding
                    repo.index.add(item_path_str)
                    staged_anything = True
            except KeyError: # File not in index, means it's new
                repo.index.add(item_path_str)
                staged_anything = True
            except Exception as e:
                 click.echo(f"Warning: Could not stage {item_path_str}: {e}", err=True)


        if staged_anything:
            repo.index.write()
            click.echo(f"Staged GitWrite files: {', '.join(items_to_stage)}")
        else:
            click.echo("No new GitWrite structure elements to stage. Files might already be tracked and unchanged.")
            # Check if tree is different anyway, e.g. due to mode changes or other index manipulations
            if not repo.head_is_unborn and repo.index.write_tree() == repo.head.peel(pygit2.Tree).id:
                 click.echo("And repository tree is identical to HEAD, no commit needed.")
                 click.echo(f"Successfully processed GitWrite initialization for {target_dir.resolve()}")
                 return # Nothing to commit


        # Create commit
        author = pygit2.Signature("GitWrite System", "system@gitwrite.io")
        committer = author

        parents = []
        if not repo.head_is_unborn:
            parents = [repo.head.target]

        tree = repo.index.write_tree()

        if repo.head_is_unborn or tree != repo.head.peel(pygit2.Tree).id:
            commit_message = f"Initialized GitWrite project structure in {target_dir.name}"
            if is_existing_repo and parents: # only modify message if it's truly an existing, non-empty repo
                commit_message = f"Added GitWrite structure to {target_dir.name}"

            repo.create_commit("HEAD", author, committer, commit_message, tree, parents)
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
def save(message):
    """Stages all changes and creates a commit with the given message."""
    try:
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return

        repo = pygit2.Repository(repo_path_str)

        if repo.is_bare:
            click.echo("Error: Cannot save in a bare repository.", err=True)
            return

        # Check repository status
        status = repo.status()
        if not status:
            # Check if there are staged changes waiting for commit, even if working dir is clean
            # This can happen if `git add` was run manually.
            # A more thorough check would involve comparing index to HEAD.
            # For simplicity, if `repo.status()` is empty, we assume no pending changes.
            # However, `pygit2.status()` returns a dict. An empty dict means no changes.
            click.echo("No changes to save (working directory and index are clean).")
            return

        # Stage all changes (untracked, modified, deleted)
        repo.index.add_all()
        repo.index.write()
        click.echo("Staged all changes.")

        # Retrieve author and committer details
        try:
            # Use default_signature which reads from .git/config
            author = repo.default_signature
        except pygit2.GitError:
            # Fallback if no user.name or user.email is set in Git config
            author_name = os.environ.get("GIT_AUTHOR_NAME", "Unknown Author")
            author_email = os.environ.get("GIT_AUTHOR_EMAIL", "author@example.com")
            author = pygit2.Signature(author_name, author_email)

        committer = author # Keep it simple: committer is the same as author

        # Get the current tree from the updated index
        tree = repo.index.write_tree()

        # Determine parent commit(s)
        parents = []
        final_message = message # User's provided message
        is_completing_operation = None # 'merge' or 'revert'

        # Check for MERGE_HEAD (completing a merge)
        try:
            merge_head_ref = repo.lookup_reference("MERGE_HEAD")
            if merge_head_ref and merge_head_ref.target:
                parents = [repo.head.target, merge_head_ref.target]
                is_completing_operation = 'merge'
                click.echo("Finalizing merge...")
                # Standard merge commit message is often auto-generated by Git,
                # but here we use the user's message.
                # We could choose to prepend a default merge message if user message is simple.
        except KeyError:
            pass # MERGE_HEAD doesn't exist, not a merge completion.
        except Exception as e:
            click.echo(f"Warning: Error checking MERGE_HEAD: {e}", err=True)

        # Check for REVERT_HEAD (completing a revert)
        if not is_completing_operation: # Only check if not already identified as merge
            try:
                revert_head_ref = repo.lookup_reference("REVERT_HEAD")
                if revert_head_ref and revert_head_ref.target:
                    reverted_commit_oid = revert_head_ref.target
                    reverted_commit = repo.get(reverted_commit_oid)
                    if reverted_commit:
                        is_completing_operation = 'revert'
                        click.echo(f"Finalizing revert of commit {reverted_commit.short_id}...")
                        original_msg_first_line = reverted_commit.message.splitlines()[0]
                        final_message = (
                            f"Revert \"{original_msg_first_line}\"\n\n"
                            f"This reverts commit {reverted_commit.id}.\n\n"
                            f"{message}"
                        )
                    else: # Should not happen if REVERT_HEAD is valid
                        click.echo(f"Warning: REVERT_HEAD found but commit {reverted_commit_oid} could not be read.", err=True)
                    # Parents for a completed revert are just the current HEAD
                    if not repo.is_empty and not repo.head_is_unborn:
                        parents = [repo.head.target]
                    else: # Should not be able to revert if HEAD is unborn
                        click.echo("Error: Cannot finalize revert, HEAD is unborn.", err=True)
                        return
            except KeyError:
                pass # REVERT_HEAD doesn't exist, not a revert completion.
            except Exception as e:
                click.echo(f"Warning: Error checking REVERT_HEAD: {e}", err=True)

        # If not completing a merge or revert, set parents for a normal commit
        if not is_completing_operation:
            if not repo.is_empty and not repo.head_is_unborn:
                parents = [repo.head.target]

        # Create the commit
        commit_oid = repo.create_commit(
            "HEAD",       # Update the HEAD pointer
            author,
            committer,
            final_message, # Use the potentially modified message
            tree,
            parents
        )

        if is_completing_operation: # 'merge' or 'revert'
            repo.state_cleanup() # Clean up MERGE_HEAD/REVERT_HEAD and other state info
            click.echo(f"Successfully completed {is_completing_operation} operation.")

        short_hash = str(commit_oid)[:7]
        try:
            branch_name = repo.head.shorthand
        except pygit2.GitError: # Detached HEAD or other issues
            branch_name = "DETACHED HEAD"
            # After the first commit, or if HEAD is somehow still unborn after a merge commit
            # (which shouldn't happen if 'HEAD' is passed to create_commit), try to get branch name.
            if repo.head_is_unborn:
                active_branch = next((b for b in repo.branches.local if b.is_head()), None)
                if active_branch:
                    branch_name = active_branch.branch_name
                elif branch_name == "DETACHED HEAD": # Still detached, maybe it's a tag?
                    # For simplicity, we'll stick to DETACHED HEAD if not an obvious local branch.
                    pass


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

        # walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE)
        # For newest first, GIT_SORT_TIME is usually enough. REVERSE would make it oldest first.
        walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME)

        for i, commit in enumerate(walker):
            if count is not None and i >= count:
                break

            short_hash = str(commit.id)[:7]
            author_name = commit.author.name

            # Convert commit time to a datetime object with timezone
            tzinfo = timezone(timedelta(minutes=commit.author.offset))
            commit_time_dt = datetime.fromtimestamp(commit.author.time, tzinfo)
            date_str = commit_time_dt.strftime("%Y-%m-%d %H:%M:%S %z")

            message = commit.message.splitlines()[0] if commit.message else ""

            table.add_row(short_hash, author_name, date_str, Text(message, overflow="ellipsis"))

        # After the loop, if the table still has no rows, then no commits were actually added.
        # This covers cases where the walker might be empty despite earlier checks,
        # or if all commits were filtered out by some logic (not currently the case here).
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

        commit = repo.head.peel(pygit2.Commit) # Ensure we are pointing to a commit object
        new_branch = repo.branches.local.create(branch_name, commit)

        # Construct the refname for checkout
        refname = f"refs/heads/{branch_name}"
        repo.checkout(refname, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(refname) # Update HEAD to point to the new branch ref

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
            # List branches
            if repo.is_empty or repo.head_is_unborn: # Check again, as listing branches on empty repo is trivial but good to be consistent
                click.echo("No explorations (branches) yet.")
                return

            from rich.table import Table
            from rich.console import Console

            table = Table(title="Available Explorations")
            table.add_column("Name", style="cyan")

            current_branch_ref = repo.head.name

            branches = list(repo.branches.local)
            if not branches:
                click.echo("No explorations (branches) found.")
                return

            for b_name in sorted(branches):
                ref_name_for_branch = f"refs/heads/{b_name}"
                if ref_name_for_branch == current_branch_ref:
                    table.add_row(f"* {b_name}")
                else:
                    table.add_row(f"  {b_name}")

            console = Console()
            console.print(table)
            return

        # Switch to a specific branch
        if repo.is_empty or repo.head_is_unborn: # Cannot switch if no commits/branches exist beyond default
             click.echo(f"Error: Repository is empty or HEAD is unborn. Cannot switch to '{branch_name}'.", err=True)
             return

        target_branch_ref = f"refs/heads/{branch_name}"
        branch_obj = repo.branches.get(branch_name) # Check local branches by short name

        if branch_obj is None : # Check remote branches if not found locally (though explore creates local)
            branch_obj = repo.branches.get(f"origin/{branch_name}") # Basic remote check
            if branch_obj:
                target_branch_ref = branch_obj.name # Use full remote ref name if found
            else:
                click.echo(f"Error: Exploration '{branch_name}' not found locally or on common remote 'origin'.", err=True)
                return
        else:
             target_branch_ref = branch_obj.name


        # Check if already on the target branch
        if repo.head.name == target_branch_ref:
            click.echo(f"Already on exploration: {branch_name}")
            return

        repo.checkout(target_branch_ref, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(target_branch_ref)

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

        # Ensure we are using the commit object for merge analysis and merge
        # target_commit = repo.lookup_commit(target_branch_obj.target) # Incorrect method
        target_commit = repo[target_branch_obj.target] # Correct way to get commit from OID

        # Perform merge analysis
        # Note: pygit2's merge_analysis expects the OID of the commit to merge from their perspective,
        # so it's repo.merge_analysis([target_commit.id]) typically.
        # However, the simpler form repo.merge_analysis(target_commit.id) is for merging 'their_head' into 'our_head'.
        # The merge_base is also useful: base = repo.merge_base(repo.head.target, target_commit.id)

        # We want to merge 'target_commit' (from branch_name) INTO current HEAD
        # The merge analysis is from the perspective of HEAD, checking what would happen if we merge `target_commit`.
        merge_result, _ = repo.merge_analysis(target_commit.id)

        if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
            click.echo(f"Already up-to-date with {branch_name}.")
            return

        elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
            click.echo(f"Attempting Fast-forward merge for {branch_name} into {current_branch_shorthand}...")
            current_branch_ref_name = repo.head.name # Full ref name e.g. refs/heads/master
            current_branch_ref = repo.lookup_reference(current_branch_ref_name)
            current_branch_ref.set_target(target_commit.id)
            repo.checkout(current_branch_ref_name, strategy=pygit2.GIT_CHECKOUT_FORCE) # Use FORCE for FF
            click.echo(f"Fast-forwarded {current_branch_shorthand} to {branch_name} (commit {str(target_commit.id)[:7]}).")
            return

        elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
            click.echo(f"Attempting Normal merge for {branch_name} into {current_branch_shorthand}...")
            repo.merge(target_commit.id) # This updates the index

            has_conflicts = False
            if repo.index.conflicts is not None:
                # Iterate to actually check if there's content.
                # An empty iterator means no conflicts were actually found by pygit2.
                # (Actually, pygit2.IndexConflictIterator is not None if there are conflicts)
                # So, just checking `if repo.index.conflicts:` should be enough.
                # For robustness, let's assume it's an iterator that might be empty.
                for _conflict_entry in repo.index.conflicts: # Try to iterate
                    has_conflicts = True
                    break

            if has_conflicts:
                click.echo("Automatic merge failed; fix conflicts and then commit the result using 'gitwrite save'.", err=True)
                click.echo("Conflicting files:")
                # repo.index.conflicts is an iterator. Each item is a tuple (ancestor_entry, our_entry, their_entry).
                # These IndexEntry objects can be None if that side doesn't exist (e.g. add/add conflict).
                for conflict_entries in repo.index.conflicts:
                    # We just need one path to identify the file. 'our_entry' is usually a good choice if it exists.
                    our_entry = conflict_entries[1]
                    their_entry = conflict_entries[2]
                    if our_entry:
                        click.echo(f"  {our_entry.path}")
                    elif their_entry: # Fallback if 'our' side was deleted but 'theirs' exists
                        click.echo(f"  {their_entry.path}")
                    # If both are None (e.g. delete/delete conflict on same file path), this might not print.
                    # However, git status usually shows D D conflicts. pygit2 might represent this differently.
                    # For MVP, showing one path is sufficient.
                return # Do not call repo.state_cleanup() here

            # No conflicts, create merge commit
            try:
                author = repo.default_signature
            except pygit2.GitError:
                author_name = os.environ.get("GIT_AUTHOR_NAME", "Unknown Author")
                author_email = os.environ.get("GIT_AUTHOR_EMAIL", "author@example.com")
                author = pygit2.Signature(author_name, author_email)
            committer = author

            tree = repo.index.write_tree()
            parents = [repo.head.target, target_commit.id]
            merge_commit_msg = f"Merge branch '{branch_name}' into {current_branch_shorthand}"

            repo.create_commit("HEAD", author, committer, merge_commit_msg, tree, parents)
            click.echo(f"Merged {branch_name} into {current_branch_shorthand}.")
            repo.state_cleanup() # Important after a successful merge or checkout
            return

        else:
            # This case handles GIT_MERGE_ANALYSIS_NONE or GIT_MERGE_ANALYSIS_UNBORN or other unexpected results
            click.echo(f"Merge not possible. Analysis result code: {merge_result}", err=True)
            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UNBORN:
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
    # Note: Current implementation focuses on commit-to-commit diff.
    # Working directory diff (ref1=None, ref2=None, or ref1=some_commit, ref2=None for diff against working dir)
    # is a more complex scenario involving repo.diff(commit.tree, None) or repo.diff(None, commit.tree).
    # The prompt implies commit-to-commit, so HEAD~1 vs HEAD, ref vs HEAD, ref1 vs ref2.

    from rich.console import Console
    from rich.text import Text
    import difflib # Ensure this is at the top of the file if not already

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
            # Allow compare if exactly one commit exists and comparing HEAD vs HEAD~1 (which will fail gracefully)
            # But if trying to compare specific refs, and repo is empty, it's an error.
             if ref1_str or ref2_str: # If specific refs are given, error out on empty/unborn.
                click.echo("Error: Repository is empty or HEAD is unborn. Cannot compare specific references.", err=True)
                return

        commit1_obj = None
        commit2_obj = None

        if ref1_str is None and ref2_str is None: # Compare HEAD with HEAD~1
            if repo.is_empty or repo.head_is_unborn:
                 click.echo("Error: Repository is empty or HEAD is unborn. Cannot perform default comparison (HEAD vs HEAD~1).", err=True)
                 return
            try:
                commit2_obj = repo.head.peel(pygit2.Commit)
                if not commit2_obj.parents:
                    click.echo("Error: HEAD has no parents to compare with (it's the initial commit).", err=True)
                    return
                commit1_obj = commit2_obj.parents[0] # HEAD~1
            except pygit2.GitError as e:
                click.echo(f"Error resolving default comparison (HEAD vs HEAD~1): {e}", err=True)
                return
            except IndexError: # No parents for HEAD
                click.echo("Error: HEAD has no parents to compare with (it's the initial commit).", err=True)
                return
            ref1_str, ref2_str = "HEAD~1", "HEAD" # For display purposes

        elif ref1_str is not None and ref2_str is None: # Compare ref1 with HEAD
            if repo.is_empty or repo.head_is_unborn:
                 click.echo("Error: Repository is empty or HEAD is unborn. Cannot compare with HEAD.", err=True)
                 return
            try:
                commit2_obj = repo.head.peel(pygit2.Commit)
                commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
            except (pygit2.GitError, KeyError, TypeError) as e: # Added KeyError, TypeError
                click.echo(f"Error: Could not resolve reference '{ref1_str}': {e}", err=True)
                return
            ref2_str = "HEAD" # For display purposes

        elif ref1_str is not None and ref2_str is not None: # Compare ref1 with ref2
            try:
                commit1_obj = repo.revparse_single(ref1_str).peel(pygit2.Commit)
                commit2_obj = repo.revparse_single(ref2_str).peel(pygit2.Commit)
            except (pygit2.GitError, KeyError, TypeError) as e: # Added KeyError, TypeError
                click.echo(f"Error: Could not resolve references ('{ref1_str}', '{ref2_str}'): {e}", err=True)
                return
        else: # ref1_str is None, ref2_str is not None -- invalid combination based on prompt, treat as error
            click.echo("Error: Invalid combination of references for comparison.", err=True)
            return

        if not commit1_obj or not commit2_obj: # Should be caught by specific errors above
            click.echo("Error: Could not resolve one or both references to commits.", err=True)
            return

        tree1 = commit1_obj.tree
        tree2 = commit2_obj.tree

        diff = repo.diff(tree1, tree2, context_lines=3, interhunk_lines=1)

        if not diff:
            click.echo(f"No differences found between {ref1_str} and {ref2_str}.")
            return

        console = Console()
        console.print(f"Diff between {ref1_str} (a) and {ref2_str} (b):")

        old_line_content_for_word_diff = None

        for patch in diff:
            console.print(f"--- a/{patch.delta.old_file.path}\n+++ b/{patch.delta.new_file.path}", style="bold yellow")
            for hunk in patch.hunks:
                console.print(hunk.header.strip(), style="cyan")

                # Process lines in pairs for word diff
                lines_in_hunk = list(hunk.lines) # Materialize lines for lookahead/pairing
                i = 0
                while i < len(lines_in_hunk):
                    line = lines_in_hunk[i]
                    content = line.content.rstrip('\r\n')

                    # Check if current line is '-' and next line is '+'
                    if line.origin == '-' and (i + 1 < len(lines_in_hunk)) and lines_in_hunk[i+1].origin == '+':
                        old_content = content
                        new_content = lines_in_hunk[i+1].content.rstrip('\r\n')

                        sm = difflib.SequenceMatcher(None, old_content.split(), new_content.split())
                        text_old = Text("-", style="red")
                        text_new = Text("+", style="green")
                        has_word_diff = any(tag != 'equal' for tag, _, _, _, _ in sm.get_opcodes())

                        if not has_word_diff: # If all words are equal (e.g. only whitespace change not split)
                             console.print(Text(f"-{old_content}", style="red"))
                             console.print(Text(f"+{new_content}", style="green"))
                        else:
                            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                                old_words_segment = old_content.split()[i1:i2]
                                new_words_segment = new_content.split()[j1:j2]

                                old_chunk = " ".join(old_words_segment)
                                new_chunk = " ".join(new_words_segment)

                                # Add trailing space if segment is not empty and not the last part of the line potentially
                                old_space = " " if old_chunk and i2 < len(old_content.split()) else ""
                                new_space = " " if new_chunk and j2 < len(new_content.split()) else ""

                                if tag == 'replace':
                                    text_old.append(old_chunk + old_space, style="black on red")
                                    text_new.append(new_chunk + new_space, style="black on green")
                                elif tag == 'delete':
                                    text_old.append(old_chunk + old_space, style="black on red")
                                elif tag == 'insert':
                                    text_new.append(new_chunk + new_space, style="black on green")
                                elif tag == 'equal':
                                    text_old.append(old_chunk + old_space)
                                    text_new.append(new_chunk + new_space)
                            console.print(text_old)
                            console.print(text_new)
                        i += 2 # Consumed two lines
                        continue

                    # Handle single lines (not part of a diff pair)
                    if line.origin == '-':
                        console.print(Text(f"-{content}", style="red"))
                    elif line.origin == '+':
                        console.print(Text(f"+{content}", style="green"))
                    elif line.origin == ' ':
                        console.print(f" {content}")
                    # Other origins like 'H' (hunk header), 'F' (file summary) could be handled.
                    i += 1

    # except pygit2.GitError as e: # This will be caught by the more specific ones above or the final Exception
    #     # Catch common revparse errors more specifically
    #     if "revspec" in str(e).lower() or "unknown revision" in str(e).lower() or "reference not found" in str(e).lower():
    #         click.echo(f"Error: Invalid reference provided for comparison - {e}", err=True)
    #     else:
    #         click.echo(f"GitError during compare: {e}", err=True)
    except IndexError: # For HEAD~1 on initial commit / empty parent list
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
            # Potentially allow fetch if remote exists and has branches, but pull/push would fail.
            # For MVP, require existing commit.
            return

        # Determine current branch if not specified
        if branch_name_opt:
            current_branch_ref_name = f"refs/heads/{branch_name_opt}"
            current_branch = repo.lookup_reference(current_branch_ref_name) # pygit2.KeyError if not found
            if not current_branch or not current_branch.is_branch():
                click.echo(f"Error: Branch '{branch_name_opt}' not found or is not a local branch.", err=True)
                return
        else:
            if repo.head_is_detached:
                click.echo("Error: HEAD is detached. Please switch to a branch to sync.", err=True)
                return
            current_branch = repo.head # This is a reference object e.g. refs/heads/main
            branch_name_opt = current_branch.shorthand # e.g. main

        click.echo(f"Syncing branch '{branch_name_opt}' with remote '{remote_name}'...")

        # --- Remote Handling & Fetch Logic (Step 3 & 4) ---
        try:
            remote = repo.remotes[remote_name]
        except KeyError:
            click.echo(f"Error: Remote '{remote_name}' not found.", err=True)
            return
        except Exception as e:
            click.echo(f"Error accessing remote '{remote_name}': {e}", err=True)
            return

        click.echo(f"Fetching from remote '{remote_name}'...")
        try:
            # You can add pygit2.RemoteCallbacks for progress, credentials, etc.
            # For now, keeping it simple.
            stats = remote.fetch() # stats object has info like total_objects, received_bytes etc.
            if hasattr(stats, 'received_objects') and hasattr(stats, 'total_objects'):
                 click.echo(f"Fetch complete. Received {stats.received_objects}/{stats.total_objects} objects.")
            else:
                 click.echo("Fetch complete. (No detailed stats available from fetch operation)")
        except pygit2.GitError as e:
            click.echo(f"Error during fetch: {e}", err=True)
            # Check for specific error messages if needed, e.g. authentication
            if "authentication required" in str(e).lower():
                click.echo("Hint: Ensure your SSH keys or credential manager are configured correctly.", err=True)
            return
        except Exception as e: # Catch other potential errors during fetch
            click.echo(f"An unexpected error occurred during fetch: {e}", err=True)
            return

        # --- Pull Logic (Step 5) ---
        click.echo("Attempting to integrate remote changes...")

        # Ensure current_branch is the reference to the local branch, not just HEAD's target OID
        # current_branch was already defined as repo.lookup_reference(current_branch_ref_name) or repo.head

        local_commit_oid = current_branch.target
        local_commit = repo.get(local_commit_oid) # Get the commit object

        remote_tracking_branch_name = f"{remote_name}/{branch_name_opt}"
        try:
            # Ensure we are looking for the branch in the correct namespace
            # pygit2 uses 'refs/remotes/origin/main' as the full name
            remote_branch_ref = repo.lookup_reference(f"refs/remotes/{remote_tracking_branch_name}")
            if not remote_branch_ref: # Should raise KeyError if not found, but double check
                 raise KeyError(f"Remote tracking branch '{remote_tracking_branch_name}' not found.")
            their_commit_oid = remote_branch_ref.target
            their_commit = repo.get(their_commit_oid)
        except KeyError:
            click.echo(f"Error: Remote tracking branch '{remote_tracking_branch_name}' not found. Has it been fetched?", err=True)
            return
        except Exception as e:
            click.echo(f"Error looking up remote tracking branch '{remote_tracking_branch_name}': {e}", err=True)
            return

        if local_commit_oid == their_commit_oid:
            click.echo("Local branch is already up-to-date with remote.")
        else:
            # Perform merge analysis
            # We want to merge 'their_commit' (remote) INTO 'local_commit' (our current HEAD of the branch)

            # Ensure HEAD is pointing to our local branch before merge_analysis if we rely on default for our_head
            if repo.head.target != local_commit_oid:
                 repo.set_head(current_branch.name) # current_branch.name is like 'refs/heads/main'

            merge_result, _ = repo.merge_analysis(their_commit_oid) # our_head defaults to repo.head.target
            # Old call: repo.merge_analysis(their_commit_oid, local_commit_oid)


            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                click.echo(f"Branch '{branch_name_opt}' is already up-to-date with '{remote_tracking_branch_name}'.")

            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                click.echo(f"Attempting Fast-forward for branch '{branch_name_opt}'...")
                try:
                    # Update the local branch reference to point to the remote commit
                    current_branch.set_target(their_commit_oid)

                    # Checkout the updated local branch to update HEAD, index, and working directory
                    # Using GIT_CHECKOUT_FORCE is generally safe for fast-forwards.
                    # It ensures the working directory matches the new commit.
                    repo.checkout(current_branch.name, strategy=pygit2.GIT_CHECKOUT_FORCE)

                    # No need to call repo.set_head() separately if checking out a branch reference directly,
                    # as checkout should handle updating HEAD to point to this branch.
                    click.echo(f"Fast-forwarded '{branch_name_opt}' to match '{remote_tracking_branch_name}'.")
                except pygit2.GitError as e:
                    click.echo(f"Error during fast-forward: {e}. Your branch may be in an inconsistent state.", err=True)
                    return

            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                click.echo(f"Attempting Normal merge of '{remote_tracking_branch_name}' into '{branch_name_opt}'...")
                try:
                    repo.merge(their_commit_oid) # This attempts to merge 'their' commit into the current HEAD (index)
                    repo.index.write() # Persist the index, especially if it now contains conflicts.

                    has_actual_conflicts = False
                    if repo.index.conflicts is not None:
                        for _conflict_entry in repo.index.conflicts: # Try to iterate
                            has_actual_conflicts = True
                            break

                    if has_actual_conflicts:
                        click.echo("Conflicts detected. Please resolve them manually and then run 'gitwrite save'.", err=True)
                        # List conflicting files
                        conflicting_files_display = []
                        # Re-iterate to get paths, since we broke out of the first loop
                        for conflict_item_tuple in repo.index.conflicts:
                            # Each conflict_item_tuple can be (ancestor, ours, theirs)
                            # We want the path, which should be consistent across them if they exist
                            path_to_display = "unknown_path"
                            if conflict_item_tuple[1] and conflict_item_tuple[1].path: # Our entry
                                path_to_display = conflict_item_tuple[1].path
                            elif conflict_item_tuple[2] and conflict_item_tuple[2].path: # Their entry
                                path_to_display = conflict_item_tuple[2].path
                            elif conflict_item_tuple[0] and conflict_item_tuple[0].path: # Ancestor entry
                                path_to_display = conflict_item_tuple[0].path
                            if path_to_display not in conflicting_files_display:
                                 conflicting_files_display.append(path_to_display)

                        if conflicting_files_display:
                             click.echo("Conflicting files: " + ", ".join(sorted(conflicting_files_display)), err=True)
                        # Do not proceed with push, user must resolve.
                        # repo.state_cleanup() # DO NOT cleanup state here, user needs to see it.
                        return
                    else:
                        # No conflicts, create merge commit
                        click.echo("No conflicts. Creating merge commit...")
                        try:
                            author = repo.default_signature
                            committer = repo.default_signature
                        except pygit2.GitError: # Fallback if not configured
                            author_name = os.environ.get("GIT_AUTHOR_NAME", "GitWrite User")
                            author_email = os.environ.get("GIT_AUTHOR_EMAIL", "user@gitwrite.io")
                            author = pygit2.Signature(author_name, author_email)
                            committer = author

                        tree = repo.index.write_tree()
                        # Parents for merge commit: current local commit and the commit from remote branch
                        parents = [local_commit_oid, their_commit_oid]
                        merge_commit_message = f"Merge remote-tracking branch '{remote_tracking_branch_name}' into {branch_name_opt}"

                        repo.create_commit(
                            current_branch.name, # Update the local branch reference
                            author,
                            committer,
                            merge_commit_message,
                            tree,
                            parents
                        )
                        repo.state_cleanup() # Clean up merge state (e.g., MERGE_HEAD)
                        click.echo("Successfully merged remote changes.")

                except pygit2.GitError as e:
                    click.echo(f"Error during merge process: {e}", err=True)
                    repo.state_cleanup() # Attempt to clean up state on error
                    return

            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_UNBORN:
                 click.echo(f"Merge not possible: '{branch_name_opt}' or '{remote_tracking_branch_name}' is an unborn branch.", err=True)
                 return
            else: # Other merge analysis results
                click.echo(f"Merge not possible. Analysis result: {merge_result}. Local and remote histories may have diverged significantly.", err=True)
                return

        # --- Push Logic (Step 6) ---
        # We should only push if the local branch was successfully updated (either FF or merge commit)
        # or if it was already up-to-date and potentially had local commits to push.

        # Check if the remote tracking branch is ahead of our current local branch AFTER potential merge/ff.
        # This check is more about whether there's anything TO push.
        # Re-fetch local_commit_oid as it might have changed after a merge commit.
        local_commit_oid_after_pull = repo.lookup_reference(current_branch.name).target

        # Get the new remote tracking branch's OID post-fetch (their_commit_oid should still be valid from fetch stage)
        # If local_commit_oid_after_pull is now equal to their_commit_oid, and there were no local changes prior to pull that
        # were not part_of_their_commit_oid, then push might not be needed or might be up-to-date.
        # However, a simpler model is: if we fetched and merged, the working assumption is to try to push the result.
        # A more robust check would be to see if current_branch.target is an ancestor of remote_branch_ref.target
        # If so, push is rejected (non-fast-forward) unless forced.
        # Or, if remote_branch_ref.target is an ancestor of current_branch.target, then push is fine.

        # For simplicity: Attempt push. Git server will reject non-fast-forwards if necessary.
        # More advanced: Check if local branch is ahead of its remote counterpart.
        # upstream_ref = repo.branches.get(f"{remote_name}/{branch_name_opt}", pygit2.GIT_BRANCH_REMOTE)
        upstream_ref = repo.lookup_reference(f"refs/remotes/{remote_name}/{branch_name_opt}") # Use the one from fetch

        if not upstream_ref:
            click.echo(f"Warning: Could not find remote tracking branch {remote_name}/{branch_name_opt} to compare for push eligibility. Proceeding with push attempt.", err=True)
        elif local_commit_oid_after_pull == upstream_ref.target:
            click.echo(f"Local branch '{branch_name_opt}' is aligned with '{remote_name}/{branch_name_opt}'. Nothing to push.")
            # This means fetch + pull resulted in local being same as remote, and there were no further local commits.
            # Or, local was already ahead, and pull did nothing or was FF, and now we want to push these local changes.
            # This specific check might be too simplistic.
            # A better check: Are there any local commits that are not on the remote tracking branch?
            # common_ancestor = repo.merge_base(local_commit_oid_after_pull, upstream_ref.target)
            # if common_ancestor == local_commit_oid_after_pull and local_commit_oid_after_pull != upstream_ref.target:
            #    click.echo(f"Remote '{remote_name}/{branch_name_opt}' is ahead. This should have been handled by pull. Won't push.")
            #    return
            # elif common_ancestor == upstream_ref.target and local_commit_oid_after_pull != upstream_ref.target:
            #    click.echo(f"Local branch '{branch_name_opt}' is ahead. Proceeding with push.")
            # else: # Diverged or up-to-date
            #    if local_commit_oid_after_pull == upstream_ref.target:
            #        click.echo(f"Local branch '{branch_name_opt}' is aligned with '{remote_name}/{branch_name_opt}'. Nothing to push.")
            #        return
            #    else: # Diverged
            #        click.echo(f"Local and remote branches have diverged. Merge should have handled this. Push might fail.", err=True)


        # The critical check is really if local HEAD is ahead of remote HEAD.
        # If after fetch & merge, local_commit_oid_after_pull is an ancestor of their_commit_oid, something is wrong.
        # It means we merged "backwards" or FF'd to an older state. This shouldn't happen with the previous logic.

        # If local_commit_oid (original local before pull) was different from local_commit_oid_after_pull (after merge/FF)
        # OR if there were local changes that were not part of the main fetch/merge cycle (e.g. user committed something else)
        # then a push is relevant.

        # The simplest strategy is to just try pushing the current local branch reference.
        # The remote will enforce fast-forward rules.
        click.echo(f"Attempting to push local changes from '{branch_name_opt}' to '{remote_name}/{branch_name_opt}'...")
        try:
            # Construct the refspec: refs/heads/local_branch:refs/heads/remote_branch
            refspec = f"refs/heads/{branch_name_opt}:refs/heads/{branch_name_opt}"
            remote.push([refspec]) # Add callbacks for status/errors if needed
            click.echo("Push successful.")
        except pygit2.GitError as e:
            click.echo(f"Error during push: {e}", err=True)
            if "non-fast-forward" in str(e).lower():
                click.echo("Hint: The remote has changes that were not integrated locally. Try running sync again or manually resolving.", err=True)
            elif "authentication required" in str(e).lower():
                click.echo("Hint: Ensure your SSH keys or credential manager are configured for push access.", err=True)
            # No return here, as sync might have partially succeeded (fetch/pull)
        except Exception as e:
            click.echo(f"An unexpected error occurred during push: {e}", err=True)
            # No return here

        click.echo(f"Sync process for branch '{branch_name_opt}' with remote '{remote_name}' completed.")

    except pygit2.GitError as e:
        click.echo(f"GitError during sync: {e}", err=True)
    except KeyError as e: # For cases like invalid branch name leading to lookup_reference failure
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during sync: {e}", err=True)


@cli.command()
@click.argument("commit_ref")
@click.option("-m", "--mainline", "mainline_option", type=int, default=None, help="For merge commits, the parent number (1-indexed) to revert towards.")
def revert(commit_ref, mainline_option):
    """Reverts a commit.

    <commit_ref> is the commit reference (e.g., commit hash, branch name, HEAD) to revert.
    For merge commits, use --mainline to specify the parent (e.g., 1 or 2).
    """
    try:
        # Discover repository path starting from current directory
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
            return
        repo = pygit2.Repository(repo_path_str)
    except pygit2.GitError as e:
        click.echo(f"Error initializing repository: {e}", err=True)
        return

    if repo.is_bare:
        click.echo("Error: Cannot revert in a bare repository.", err=True)
        return

    try:
        commit_to_revert = repo.revparse_single(commit_ref)
        if commit_to_revert.type != pygit2.GIT_OBJECT_COMMIT:
            click.echo(f"Error: '{commit_ref}' does not resolve to a commit.", err=True)
            return
        # Peel to commit object if it's a tag
        commit_to_revert = commit_to_revert.peel(pygit2.Commit)
        click.echo(f"Attempting to revert commit: {commit_to_revert.short_id} ('{commit_to_revert.message.strip().splitlines()[0]}')")

    except (KeyError, pygit2.GitError):
        click.echo(f"Error: Invalid or ambiguous commit reference '{commit_ref}'.", err=True)
        return
    except Exception as e: # Catch other potential errors during revparse e.g. if not a commit
        click.echo(f"Error resolving commit '{commit_ref}': {e}", err=True)
        return

    # 1. Check for Dirty Working Directory or Index
    status = repo.status()
    is_dirty = False
    for filepath, flags in status.items():
        if flags != pygit2.GIT_STATUS_CURRENT: # GIT_STATUS_CURRENT means clean
            # Ignore untracked files for "dirty" check in this context,
            # as revert primarily cares about changes to tracked files.
            if flags & pygit2.GIT_STATUS_WT_NEW and not (flags & pygit2.GIT_STATUS_INDEX_NEW):
                continue # Untracked file, not in index
            is_dirty = True
            break

    if is_dirty:
        click.echo("Error: Your working directory or index has uncommitted changes.", err=True)
        click.echo("Please commit or stash them before attempting to revert.", err=True)
        return

    # 2. Determine Mainline for Merge Commits
    is_merge_commit = len(commit_to_revert.parents) > 1
    mainline_to_use = 0  # Default for non-merge commits or if pygit2 handles it

    if is_merge_commit:
        if mainline_option is None:
            mainline_to_use = 1 # Default to the first parent for merge commits
            click.echo(f"Note: '{commit_to_revert.short_id}' is a merge commit. Reverting towards parent 1 (default).")
            click.echo("Use --mainline <parent_number> to specify a different parent.")
        elif mainline_option < 1 or mainline_option > len(commit_to_revert.parents):
            click.echo(f"Error: Invalid mainline number '{mainline_option}'. Must be between 1 and {len(commit_to_revert.parents)} for this merge commit.", err=True)
            return
        else:
            mainline_to_use = mainline_option
            click.echo(f"Reverting merge commit {commit_to_revert.short_id} towards parent {mainline_to_use}.")
    elif mainline_option is not None:
        click.echo(f"Warning: Commit {commit_to_revert.short_id} is not a merge commit. The --mainline option will be ignored.", fg="yellow")

    # 3. Perform the Revert
    try:
        # For non-merge commits, mainline_to_use will be 0.
        # For merge commits, it will be the user-specified or default (1).
        # pygit2's repo.revert() expects mainline to be 1-indexed for merge commits.
        # If the commit is not a merge, this mainline param is ignored by pygit2's C layer or handled appropriately.
        # So, we can pass mainline_to_use directly.
        # However, to be absolutely clear with pygit2's intent, we can pass it as keyword only if it's a merge.
        if is_merge_commit:
            repo.revert(commit_to_revert, mainline=mainline_to_use)
        else:
            repo.revert(commit_to_revert) # No mainline needed for non-merge

        click.echo(f"Index updated to reflect revert of commit {commit_to_revert.short_id}.")

    except pygit2.GitError as e:
        # This can happen for various reasons, e.g., revert not possible cleanly,
        # or sometimes if there are conflicts that pygit2 itself cannot stage as conflicted.
        click.echo(f"Error during revert operation: {e}", err=True)
        click.echo("This might be due to complex changes that cannot be automatically reverted or unresolved conflicts.", err=True)
        # Check if conflicts exist in the index, even if revert threw a generic error.
        # repo.index.conflicts is an iterator (or None).
        has_conflicts_after_error = False
        if repo.index.conflicts is not None:
            for _ in repo.index.conflicts:
                has_conflicts_after_error = True
                break
        if has_conflicts_after_error:
            click.echo("Conflicts were detected in the index. Please resolve them and then commit.", err=True)
        # It's good practice to clean up state if revert fails and leaves things in a weird state,
        # though pygit2's revert might not always set a specific state like MERGE_RR.
        # repo.state_cleanup() # Might be too aggressive here if user needs to see state.
        return
    except Exception as e: # Catch any other unexpected errors
        click.echo(f"An unexpected error occurred during revert: {e}", err=True)
        return

    # 1. Check for Conflicts Post-Revert
    has_conflicts = False
    if repo.index.conflicts is not None:
        for conflict in repo.index.conflicts:
            has_conflicts = True
            break # Found a conflict, no need to check further

    if has_conflicts:
        # Placeholder for full conflict handling logic (next subtask)
        click.echo("Conflicts detected after revert. Automatic commit aborted.", err=True)
        click.echo("Please resolve the conflicts manually and then commit the changes using 'gitwrite save'.", err=True)

        # List conflicting files for user convenience
        click.echo("Conflicting files:", err=True)
        # repo.index.conflicts is an iterator. Each item is a tuple (ancestor_entry, our_entry, their_entry).
        # These IndexEntry objects can be None if that side doesn't exist.
        for conflict_entries in repo.index.conflicts:
            our_entry = conflict_entries[1] # IndexEntry for 'ours'
            their_entry = conflict_entries[2] # IndexEntry for 'theirs'
            # A file path should be available from either our_entry or their_entry if they exist
            if our_entry:
                click.echo(f"  {our_entry.path}", err=True)
            elif their_entry: # Fallback if 'our' side was deleted but 'theirs' exists
                click.echo(f"  {their_entry.path}", err=True)
            # (If both are None, it's an unusual conflict, but one path should typically be present)

        # repo.state_cleanup() # DO NOT cleanup state here if there are conflicts, user needs it.
        return # Stop here, user needs to resolve.
    else:
        # 2. Create Revert Commit (No Conflicts)
        click.echo("No conflicts detected. Proceeding to create revert commit.")
        try:
            # Author and Committer
            try:
                author = repo.default_signature
                committer = repo.default_signature
            except pygit2.GitError: # Fallback if not configured
                author_name = os.environ.get("GIT_AUTHOR_NAME", "GitWrite User")
                author_email = os.environ.get("GIT_AUTHOR_EMAIL", "user@gitwrite.io")
                author = Signature(author_name, author_email)
                committer = author

            # Commit Message
            original_message_first_line = commit_to_revert.message.splitlines()[0]
            revert_message = f"Revert \"{original_message_first_line}\"\n\nThis reverts commit {commit_to_revert.id}."

            # Parents for the new commit (current HEAD)
            if repo.head_is_unborn:
                click.echo("Error: HEAD is unborn. Cannot create revert commit in an empty repository.", err=True)
                # This case should ideally be caught earlier, but as a safeguard.
                return
            parents = [repo.head.target]

            # Tree
            tree_oid = repo.index.write_tree()

            # Create Commit
            new_commit_oid = repo.create_commit(
                "HEAD",       # Update HEAD to point to this new commit
                author,
                committer,
                revert_message,
                tree_oid,
                parents
            )

            reverted_commit_short_id = commit_to_revert.short_id
            new_commit_short_id = str(new_commit_oid)[:7]

            # 3. Success Message
            click.echo(f"Successfully reverted commit {reverted_commit_short_id}. New commit: {new_commit_short_id}")

            # 4. State Cleanup
            repo.state_cleanup() # Clean up REVERT_HEAD, CHERRY_PICK_HEAD etc.

        except pygit2.GitError as e:
            click.echo(f"Error creating revert commit: {e}", err=True)
            click.echo("Your working directory might contain the reverted changes, but the commit failed.", err=True)
            click.echo("You may need to manually commit using 'gitwrite save'.", err=True)
        except Exception as e:
            click.echo(f"An unexpected error occurred during revert commit creation: {e}", err=True)


if __name__ == "__main__":
    cli()
