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
        is_merge_commit = False

        try:
            # Check for MERGE_HEAD to determine if we are in the middle of a merge
            merge_head_ref = repo.lookup_reference("MERGE_HEAD") # pygit2.KeyError if not found
            if merge_head_ref and merge_head_ref.target:
                parents = [repo.head.target, merge_head_ref.target]
                is_merge_commit = True
                click.echo("Finalizing merge...")
            else: # Should not happen if MERGE_HEAD exists and is valid
                if not repo.is_empty and not repo.head_is_unborn:
                    parents.append(repo.head.target)
        except KeyError: # This means MERGE_HEAD does not exist (lookup_reference failed with KeyError)
            if not repo.is_empty and not repo.head_is_unborn:
                parents.append(repo.head.target)
        except Exception as e: # Catch any other errors during parent determination
            click.echo(f"Warning: Error determining parents, proceeding as normal commit. Error: {e}", err=True)
            if not repo.is_empty and not repo.head_is_unborn:
                parents.append(repo.head.target)

        # Create the commit
        commit_oid = repo.create_commit(
            "HEAD",       # Update the HEAD pointer
            author,
            committer,
            message,
            tree,
            parents
        )

        if is_merge_commit:
            repo.state_cleanup() # Clean up MERGE_HEAD and other merge state info

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


if __name__ == "__main__":
    cli()
