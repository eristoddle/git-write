# Test comment to check write access.
import click
import pygit2 # pygit2 is still used by other commands
import os # os seems to be no longer used by CLI commands directly
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
    RemoteNotFoundError, # Added for sync
    BranchNotFoundError as CoreBranchNotFoundError, # Added for review command
    CommitNotFoundError, # Added for cherry-pick
    PandocError, # Added for EPUB export
    FileNotFoundInCommitError # Added for EPUB export
)
from gitwrite_core.versioning import get_commit_history, get_diff, revert_commit, save_changes, get_branch_review_commits, cherry_pick_commit # Added get_branch_review_commits and cherry_pick_commit
from gitwrite_core.export import export_to_epub
from gitwrite_core.export import export_to_pdf, export_to_docx # Added for EPUB export
from rich.table import Table # Ensure Table is imported for switch

@click.group()
@click.pass_context
def cli(ctx):
    """GitWrite: Version control for writers.
    
    GitWrite makes version control accessible to writers with intuitive commands.
    Think of it as "track changes" but much more powerful.
    
    Common workflows:
      gitwrite init "MyNovel"     # Start a new writing project
      gitwrite save "Chapter 1"   # Save your progress
      gitwrite explore ideas       # Try different approaches
      gitwrite switch main         # Return to your main work
      gitwrite history             # See your writing journey
    
    Get help for any command: gitwrite COMMAND --help
    """
    if ctx.obj is None:
        ctx.obj = {}

@cli.command()
@click.argument("project_name", required=False)
def init(project_name):
    """Start a new writing project or set up version control in current folder.
    
    Examples:
      gitwrite init "MyNovel"      # Create a new project folder
      gitwrite init                 # Set up current folder for writing
    
    This creates:
    - A writing-friendly folder structure (drafts/, notes/)
    - Version control to track your changes
    - Metadata file for project information
    """
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
    help="Include specific files/folders. Use multiple times for multiple files.",
)
def save(message, include_paths):
    """Save your writing progress with a descriptive message.
    
    This is like "Save As" but creates a snapshot you can return to later.
    
    Examples:
      gitwrite save "Finished Chapter 3"           # Save all changes
      gitwrite save "Draft notes" -i notes/        # Save only notes folder
      gitwrite save "Character development" -i characters.md -i plot.md
    
    Tips:
      - Use clear, descriptive messages
      - Save frequently to track your progress
      - Each save creates a checkpoint in your writing journey
    """
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
@click.option("-n", "--number", "count", type=int, default=None, help="Number of saves to show (default: all).")
def history(count):
    """View your writing journey - all the saves you've made.
    
    Examples:
      gitwrite history              # Show all your progress
      gitwrite history -n 10        # Show last 10 saves
    
    This shows:
      - When you saved each version
      - What you were working on (your save messages)
      - Who made the changes (useful for collaboration)
    """
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
def status():
    """Show what's happening in your writing project right now.
    
    This tells you:
      - What version/exploration you're currently working on
      - What files have been changed since your last save
      - Whether you have unsaved work
      - Helpful next steps
    
    Think of this as your writing dashboard.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        import pygit2
        
        console = Console()
        
        # Discover repository
        repo_path_str = pygit2.discover_repository(str(Path.cwd()))
        if repo_path_str is None:
            console.print("❌ Not in a GitWrite project. Use 'gitwrite init' to start.", style="red")
            return
            
        repo = pygit2.Repository(repo_path_str)
        
        # Current branch/exploration
        current_branch = "main" if repo.head_is_unborn else repo.head.shorthand
        branch_display = "📝 Main work" if current_branch == "main" else f"🔍 Exploring: {current_branch}"
        
        # Check for changes
        status_flags = repo.status()
        
        changed_files = []
        new_files = []
        
        for file_path, flags in status_flags.items():
            if flags & (pygit2.GIT_STATUS_WT_MODIFIED | pygit2.GIT_STATUS_INDEX_MODIFIED):
                changed_files.append(file_path)
            elif flags & (pygit2.GIT_STATUS_WT_NEW | pygit2.GIT_STATUS_INDEX_NEW):
                new_files.append(file_path)
        
        # Create status display
        status_text = Text()
        status_text.append(branch_display + "\n\n", style="bold cyan")
        
        if not changed_files and not new_files:
            status_text.append("✅ All work saved!\n", style="green")
            status_text.append("Ready to continue writing.", style="dim")
        else:
            if new_files:
                status_text.append(f"📄 New files: {len(new_files)}\n", style="yellow")
                for f in new_files[:3]:  # Show first 3
                    status_text.append(f"   + {f}\n", style="green")
                if len(new_files) > 3:
                    status_text.append(f"   ... and {len(new_files) - 3} more\n", style="dim")
                status_text.append("\n")
                    
            if changed_files:
                status_text.append(f"✏️  Changed files: {len(changed_files)}\n", style="yellow")
                for f in changed_files[:3]:  # Show first 3
                    status_text.append(f"   ~ {f}\n", style="yellow")
                if len(changed_files) > 3:
                    status_text.append(f"   ... and {len(changed_files) - 3} more\n", style="dim")
                status_text.append("\n")
            
            status_text.append("💡 Next step: ", style="bold")
            status_text.append("gitwrite save \"Your message here\"", style="cyan")
        
        # Get last save info if available
        try:
            if not repo.head_is_unborn:
                last_commit = repo.head.peel()
                last_save_msg = last_commit.message.strip().split('\n')[0]
                status_text.append(f"\n\n📚 Last save: {last_save_msg}", style="dim")
        except:
            pass
            
        console.print(Panel(status_text, title="📊 Writing Project Status", expand=False))
        
    except ImportError:
        click.echo("Error: Rich library required for status display.")
    except Exception as e:
        click.echo(f"Error checking status: {e}", err=True)

@cli.command("help")
@click.argument("topic", required=False)
def help_command(topic):
    """Get help with GitWrite workflows and concepts.
    
    Examples:
      gitwrite help                    # General help and workflows
      gitwrite help getting-started    # New user guide
      gitwrite help collaboration      # Working with others
      gitwrite help concepts           # Understanding key concepts
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    
    console = Console()
    
    if topic is None:
        # General help
        help_text = Text()
        help_text.append("📚 GitWrite: Version Control for Writers\n\n", style="bold blue")
        help_text.append("Common Workflows:\n", style="bold")
        help_text.append("🚀 Getting Started:\n", style="green")
        help_text.append("  gitwrite init \"MyProject\"     # Start new project\n")
        help_text.append("  # Write content in your favorite editor\n")
        help_text.append("  gitwrite save \"First chapter\"  # Save progress\n\n")
        
        help_text.append("🔍 Daily Writing:\n", style="green")
        help_text.append("  gitwrite status                 # Check what's changed\n")
        help_text.append("  gitwrite save \"Chapter updates\" # Save your work\n")
        help_text.append("  gitwrite history                # See your progress\n\n")
        
        help_text.append("🎨 Trying New Ideas:\n", style="green")
        help_text.append("  gitwrite explore alternate-plot # Try something new\n")
        help_text.append("  # Make changes safely\n")
        help_text.append("  gitwrite save \"Experiment\"      # Save the experiment\n")
        help_text.append("  gitwrite switch main            # Return to main work\n\n")
        
        help_text.append("🔄 Comparing Versions:\n", style="green")
        help_text.append("  gitwrite compare                # See recent changes\n")
        help_text.append("  gitwrite compare main alternate-plot # Compare versions\n\n")
        
        help_text.append("For specific help: gitwrite help [topic]\n", style="dim")
        help_text.append("Topics: getting-started, collaboration, concepts", style="dim")
        
        console.print(Panel(help_text, title="🎨 GitWrite Help", expand=False))
        
    elif topic == "getting-started":
        help_text = Text()
        help_text.append("🚀 Getting Started with GitWrite\n\n", style="bold blue")
        help_text.append("1. Start a New Project:\n", style="bold")
        help_text.append("   gitwrite init \"MyNovel\"\n")
        help_text.append("   cd MyNovel\n\n")
        help_text.append("2. Understand the Structure:\n", style="bold")
        help_text.append("   drafts/    → Your main writing\n")
        help_text.append("   notes/     → Research and planning\n")
        help_text.append("   .gitignore → Files to ignore\n\n")
        help_text.append("3. Write and Save:\n", style="bold")
        help_text.append("   # Use any text editor to write\n")
        help_text.append("   gitwrite save \"First chapter draft\"\n\n")
        help_text.append("4. Check Your Progress:\n", style="bold")
        help_text.append("   gitwrite status    # What's changed?\n")
        help_text.append("   gitwrite history   # Your writing journey\n")
        
        console.print(Panel(help_text, title="📚 New Writer Guide", expand=False))
        
    elif topic == "collaboration":
        help_text = Text()
        help_text.append("🤝 Collaboration with GitWrite\n\n", style="bold blue")
        help_text.append("Working with Co-authors:\n", style="bold")
        help_text.append("  gitwrite sync                   # Get latest changes\n")
        help_text.append("  # Make your changes\n")
        help_text.append("  gitwrite save \"My contribution\" # Save your work\n")
        help_text.append("  gitwrite sync                   # Share with others\n\n")
        help_text.append("Review Process:\n", style="bold")
        help_text.append("  gitwrite review editor-feedback # See editor's changes\n")
        help_text.append("  gitwrite cherry-pick <commit>   # Apply specific changes\n\n")
        help_text.append("Handling Conflicts:\n", style="bold")
        help_text.append("  When sync shows conflicts:\n")
        help_text.append("  1. Open the conflicted files\n")
        help_text.append("  2. Choose which version to keep\n")
        help_text.append("  3. gitwrite save \"Resolved conflicts\"\n")
        
        console.print(Panel(help_text, title="📝 Collaboration Guide", expand=False))
        
    elif topic == "concepts":
        concepts = [
            ("Save", "Like \"Save As\" but creates a checkpoint you can return to"),
            ("Explore", "Try new ideas safely without affecting your main work"),
            ("Switch", "Move between different versions of your work"),
            ("History", "See all the saves you've made over time"),
            ("Compare", "See what changed between two versions"),
            ("Sync", "Share changes with collaborators or backup online"),
        ]
        
        concept_panels = []
        for name, desc in concepts:
            panel = Panel(desc, title=f"💡 {name}", width=25)
            concept_panels.append(panel)
        
        console.print("\n📚 Key GitWrite Concepts\n", style="bold blue")
        console.print(Columns(concept_panels[:3]))
        console.print(Columns(concept_panels[3:]))
        
    else:
        console.print(f"\n❌ Unknown help topic: {topic}", style="red")
        console.print("Available topics: getting-started, collaboration, concepts", style="dim")

@cli.command()
@click.argument("branch_name")
def explore(branch_name):
    """Start exploring new ideas without affecting your main work.
    
    Examples:
      gitwrite explore alternate-ending    # Try a different ending
      gitwrite explore character-backstory # Develop character ideas
      gitwrite explore experimental-style  # Try a new writing style
    
    What this does:
      - Creates a safe space to experiment
      - Your main work stays untouched
      - You can always return to your main work
      - Later, you can merge good ideas back
    
    Use 'gitwrite switch main' to return to your main work.
    """
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
    """Switch between different versions of your work or see all available versions.
    
    Examples:
      gitwrite switch                    # See all your work versions
      gitwrite switch main               # Return to main work
      gitwrite switch alternate-ending   # Switch to explore alternate ending
    
    Common workflow:
      1. 'gitwrite switch' to see what versions you have
      2. 'gitwrite switch [name]' to move to a specific version
      3. Work on that version, save progress
      4. 'gitwrite switch main' to return to main work
    """
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
    """Combine an exploration or collaboration branch with your current work.
    
    Examples:
      gitwrite merge alternate-ending    # Bring in your experimental work
      gitwrite merge co-author-edits     # Merge collaborator's changes
      gitwrite merge feature-additions   # Combine new features
    
    What this does:
      - Takes all changes from another branch
      - Combines them with your current work
      - Creates a new save that includes both sets of changes
    
    Common workflow:
      1. gitwrite switch main            # Go to your main work
      2. gitwrite merge alternate-ending # Bring in the good parts
      3. gitwrite save "Merged new ending"
    
    If there are conflicts:
      - GitWrite will tell you which files have conflicting changes
      - Open those files and choose which version to keep
      - Use 'gitwrite save "Resolved conflicts"' when done
    
    Great for:
      - Bringing successful experiments into main work
      - Incorporating feedback from collaborators
      - Combining different writing approaches
    """
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
@click.argument("ref1_str", metavar="VERSION1", required=False, default=None)
@click.argument("ref2_str", metavar="VERSION2", required=False, default=None)
def compare(ref1_str, ref2_str):
    """See what changed between different versions of your work.
    
    Examples:
      gitwrite compare                        # See recent changes
      gitwrite compare main alternate-ending  # Compare two versions
      gitwrite compare HEAD~2 HEAD           # Compare with 2 saves ago
      gitwrite compare v1.0 v2.0             # Compare tagged versions
    
    This shows:
      - Lines that were added (in green)
      - Lines that were removed (in red)  
      - Lines that changed (highlighted differences)
    
    Great for:
      - Reviewing what you changed in a writing session
      - Comparing different approaches to the same scene
      - Seeing how your work evolved over time
      - Understanding what changed between versions
    
    The comparison uses writer-friendly highlighting to show:
      - Word-level changes within lines
      - File-by-file differences
      - Clear before/after view
    """
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
            if not lines:
                continue

            # Attempt to parse file paths from the "diff --git a/path1 b/path2" line
            # Default file paths
            parsed_old_path_from_diff_line = "unknown_from_diff_a"
            parsed_new_path_from_diff_line = "unknown_from_diff_b"
            if lines[0].startswith("diff --git a/"):
                parts = lines[0].split(' ')
                if len(parts) >= 4: # Should be: diff --git a/path1 b/path2
                    parsed_old_path_from_diff_line = parts[2][2:] # Remove "a/"
                    parsed_new_path_from_diff_line = parts[3][2:] # Remove "b/"

            old_file_path_in_patch = parsed_old_path_from_diff_line
            new_file_path_in_patch = parsed_new_path_from_diff_line
            hunk_lines_for_processing = []

            # Process subsequent lines for ---, +++, @@, and hunk data
            for line_idx, line_content in enumerate(lines[1:]): # Start from second line
                if line_content.startswith("--- a/"):
                    old_file_path_in_patch = line_content[len("--- a/"):].strip()
                    # If new_file_path_in_patch was "unknown_new" or from diff --git,
                    # and old_file_path_in_patch is not /dev/null, it's likely the same file (modified/renamed from)
                    if old_file_path_in_patch != "/dev/null" and \
                       (new_file_path_in_patch == parsed_new_path_from_diff_line or new_file_path_in_patch == "unknown_new"):
                       new_file_path_in_patch = old_file_path_in_patch # Assume modification of same file unless +++ says otherwise
                elif line_content.startswith("+++ b/"):
                    new_file_path_in_patch = line_content[len("+++ b/"):].strip()
                    # If old_file_path_in_patch was "unknown_old" or from diff --git,
                    # and new_file_path_in_patch is not /dev/null, it's likely the same file (modified/renamed to)
                    if new_file_path_in_patch != "/dev/null" and \
                       (old_file_path_in_patch == parsed_old_path_from_diff_line or old_file_path_in_patch == "unknown_old"):
                        old_file_path_in_patch = new_file_path_in_patch


                    # Print file header once all path info is gathered for this delta
                    # This print should happen just before the first hunk (@@ line) or after +++ line if no --- line.
                    # We need to ensure it's printed only once per file_patch.
                    # Let's move the print to just before processing hunks or at end of file info lines.
                    # For now, this placement is problematic if --- a/ appears after +++ b/ (not typical)
                    # A better approach: collect all header info (---, +++) then print, then process hunks.
                    # This simplified loop assumes typical order.
                    # The actual printing of this header is done just before the first @@ line now.
                elif line_content.startswith("@@"):
                    # This is the first hunk header, print the file paths now.
                    if line_idx == 0 or not lines[line_idx-1].startswith("@@"): # Print only for the first hunk or if not already printed
                         # Ensure correct paths for add/delete cases
                        if old_file_path_in_patch == parsed_old_path_from_diff_line and new_file_path_in_patch == "/dev/null": # Deletion
                            pass # old_file_path_in_patch is already correct from diff --git
                        elif new_file_path_in_patch == parsed_new_path_from_diff_line and old_file_path_in_patch == "/dev/null": # Addition
                            pass # new_file_path_in_patch is already correct from diff --git

                        # If --- a/ was /dev/null, use the path from diff --git b/
                        if old_file_path_in_patch == "/dev/null" and new_file_path_in_patch != parsed_new_path_from_diff_line and parsed_new_path_from_diff_line != "unknown_from_diff_b":
                           pass # old_file_path_in_patch is /dev/null, new_file_path_in_patch is set from +++ b/
                        # If +++ b/ was /dev/null, use the path from diff --git a/
                        elif new_file_path_in_patch == "/dev/null" and old_file_path_in_patch != parsed_old_path_from_diff_line and parsed_old_path_from_diff_line != "unknown_from_diff_a":
                           pass # new_file_path_in_patch is /dev/null, old_file_path_in_patch is set from --- a/

                        console.print(f"--- a/{old_file_path_in_patch}\n+++ b/{new_file_path_in_patch}", style="bold yellow")

                    if hunk_lines_for_processing: # Process previous hunk's lines
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
@click.pass_context
def sync(ctx, remote_name, branch_name_opt, no_push_flag):
    """Share your work with collaborators and get their latest changes.
    
    Examples:
      gitwrite sync                    # Share your work and get updates
      gitwrite sync --no-push         # Get updates but don't share yours yet
      gitwrite sync --branch main     # Sync a specific branch
    
    What this does:
      1. Downloads the latest changes from your collaborators
      2. Combines them with your local work
      3. Uploads your changes for others to see
    
    Collaboration workflow:
      1. gitwrite sync                 # Get latest before starting
      2. Write and make changes
      3. gitwrite save "My changes"    # Save your work
      4. gitwrite sync                 # Share with team
    
    If there are conflicts:
      - GitWrite will show which files have conflicting changes
      - Open those files and choose which version to keep
      - Use 'gitwrite save "Resolved conflicts"' when done
    
    Great for:
      - Working with co-authors
      - Backing up your work to cloud services
      - Keeping multiple computers in sync
    """
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
        if ctx: ctx.exit(1)
    except KeyError as e: # Should be caught by specific exceptions like RemoteNotFoundError now
        click.echo(f"Error during sync setup (KeyError): {e}", err=True)
        if ctx: ctx.exit(1)
    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
        if ctx: ctx.exit(1)
    except RepositoryEmptyError as e:
        click.echo(f"Error: {e}", err=True) # Core message is usually good
        if ctx: ctx.exit(1)
    except DetachedHeadError as e:
        click.echo(f"Error: {e}. Please switch to a branch to sync or specify a branch name.", err=True)
        if ctx: ctx.exit(1)
    except RemoteNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        if ctx: ctx.exit(1)
    except BranchNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        if ctx: ctx.exit(1)
    except FetchError as e:
        click.echo(f"Error during fetch: {e}", err=True)
        if ctx: ctx.exit(1)
    except MergeConflictError as e: # This exception is raised by sync_repository if conflicts occur and are not resolved by it.
        click.echo(f"Error: {e}", err=True)
        if hasattr(e, 'conflicting_files') and e.conflicting_files:
            click.echo("Conflicting files:", err=True)
            for f_path in sorted(e.conflicting_files):
                click.echo(f"  {f_path}", err=True)
        click.echo("Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge.", err=True)
        if ctx: ctx.exit(1)
    except PushError as e:
        click.echo(f"Error during push: {e}", err=True)
        if ctx: ctx.exit(1)
    except GitWriteError as e: # Catch-all for other gitwrite core errors
        click.echo(f"Error during sync: {e}", err=True)
        if ctx: ctx.exit(1)
    except Exception as e: # General unexpected errors
        click.echo(f"An unexpected error occurred during sync: {e}", err=True)
        if ctx: ctx.exit(1)


@cli.command()
@click.argument("commit_ish")
@click.pass_context
def revert(ctx, commit_ish):
    """Undo a specific change by creating a new save that cancels it out.
    
    Examples:
      gitwrite revert abc123           # Undo that specific change
      gitwrite revert HEAD~1           # Undo the last save
      gitwrite revert main~3           # Undo a change from 3 saves ago
    
    What this does:
      - Creates a new save that undoes the specified change
      - Doesn't delete the original - just cancels it out
      - Safe way to fix mistakes without losing history
    
    Important notes:
      - This creates a NEW save that undoes the change
      - The original change stays in your history
      - Your working directory must be clean (no unsaved changes)
    
    When to use:
      - You made a change that introduced a bug
      - You want to undo something without losing other work
      - You need to "cancel out" a specific save
    
    Alternative: If you want to go back to an earlier version entirely,
    use 'gitwrite switch <tag-or-commit>' instead.
    
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
    """Create bookmarks for important versions of your work.
    
    Tags are like bookmarks that mark special moments in your writing:
    - "first-draft" when you complete your initial draft
    - "v1.0" for your first published version
    - "beta-reader-version" for the version you sent to readers
    
    Unlike branches, tags don't change - they permanently mark
    that specific version of your work.
    """
    pass


@tag.command("add")
@click.pass_context # Add pass_context to access ctx.obj
@click.argument("name") # Renamed from tag_name to name
@click.option("-m", "--message", "message", default=None, help="Annotation message for the tag.") # Renamed message_opt_tag
@click.option("--force", is_flag=True, help="Overwrite an existing tag.")
@click.option("-c", "--commit", "commit_ish", default="HEAD", help="Commit to tag. Defaults to HEAD.") # Added commit option
def add(ctx, name, message, force, commit_ish): # Function signature updated
    """Create a bookmark for an important version of your work.
    
    Examples:
      gitwrite tag add "first-draft"                    # Simple bookmark
      gitwrite tag add "v1.0" -m "First published version"  # With description
      gitwrite tag add "beta" --commit abc123             # Tag specific version
      gitwrite tag add "final" --force                   # Replace existing tag
    
    What this does:
      - Creates a permanent marker for this version
      - Like putting a bookmark in a physical book
      - You can always return to this exact version later
    
    Great for marking:
      - first-draft, second-draft, final-draft
      - v1.0, v2.0 (version numbers)
      - submitted-version, published-version
      - before-major-changes, after-editor-feedback
    
    If -m/--message is provided, an annotated tag is created.
    Otherwise, a lightweight tag is created.
    The tag points to COMMIT_ISH (commit reference), which defaults to HEAD.
    """
    try:
        repo_path = pygit2.discover_repository(str(Path.cwd()))
        if repo_path is None:
            raise RepositoryNotFoundError("Not a git repository (or any of the parent directories).")

        # Set up a fallback signature from environment variables if repo default is missing
        tagger = None
        if message: # Annotated tags require a signature
            try:
                repo = pygit2.Repository(repo_path)
                tagger = repo.default_signature
            except (pygit2.GitError, KeyError):
                name_env = os.environ.get("GIT_TAGGER_NAME", "GitWrite User") # Renamed to avoid conflict with 'name' argument
                email_env = os.environ.get("GIT_TAGGER_EMAIL", "user@gitwrite.com") # Renamed to avoid conflict
                tagger = pygit2.Signature(name_env, email_env)

        tag_details = create_tag(
            repo_path_str=repo_path,
            tag_name=name,
            target_commit_ish=commit_ish,
            message=message,
            force=force,
            tagger=tagger  # Pass the signature to the core function
        )

        click.echo(f"Successfully created {tag_details['type']} tag '{tag_details['name']}' pointing to {tag_details['target'][:7]}.")

    except (RepositoryNotFoundError, CommitNotFoundError, TagAlreadyExistsError, GitWriteError) as e:
        click.echo(f"Error: {e}", err=True)
        if ctx: ctx.exit(1) # Ensure non-zero exit for these handled errors
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        if ctx: ctx.exit(1)


@tag.command("list") # original name was tag_list, but Click uses function name, so it becomes 'list'
@click.pass_context # To potentially access repo_path if needed, though list_tags handles it
def list_cmd(ctx): # Renamed to avoid conflict if we had a variable named list
    """See all your bookmarked versions.
    
    This shows all the tags (bookmarks) you've created for your project.
    
    You'll see:
      - Tag names (like "first-draft", "v1.0")
      - What version each tag points to
      - Messages you added to annotated tags
    
    Use this to:
      - Remember what versions you've marked as important
      - Find version numbers for references
      - See your project's milestone history
    
    To return to a tagged version: gitwrite switch <tag-name>
    """
    # The list_tags function from core is intended to be used by the CLI's list command.
    # It needs to be imported.
    from gitwrite_core.tagging import list_tags as core_list_tags # This line is correct as per instructions

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
        # if ctx: ctx.exit(1) # Removed as per request
    except GitWriteError as e: # Catching base GitWriteError for other core errors
        click.echo(click.style(f"Error listing tags: {e}", fg='red'), err=True)
        # if ctx: ctx.exit(1) # Removed as per request
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

@cli.command()
@click.argument("branch_name")
@click.option("-n", "--number", "count", type=int, default=None, help="Number of changes to show (default: all).")
def review(branch_name, count):
    """Review changes from a collaborator or exploration branch.
    
    Examples:
      gitwrite review editor-feedback    # See what your editor changed
      gitwrite review alternate-ending   # Review your experimental branch
      gitwrite review co-author -n 5     # See last 5 changes from co-author
    
    This shows:
      - Changes that exist in the other version but not in your current work
      - Perfect for reviewing feedback or experimental branches
      - Use 'gitwrite cherry-pick <commit>' to apply specific changes
    
    Collaboration workflow:
      1. gitwrite review editor-feedback
      2. gitwrite cherry-pick <good-change>
      3. gitwrite save \"Applied editor suggestions\"
    """
    try:
        repo_path_str = str(Path.cwd()) # Core function handles discovery from this path
        commits = get_branch_review_commits(repo_path_str, branch_name, limit=count)

        if not commits:
            click.echo(f"No unique commits found on branch '{branch_name}' compared to HEAD.")
            return

        console = Console()
        table = Table(title=f"Review: Commits on '{branch_name}' not in HEAD")
        table.add_column("Commit", style="cyan", no_wrap=True)
        table.add_column("Author", style="magenta")
        table.add_column("Date", style="green")
        table.add_column("Message", style="white")

        for commit_data in commits:
            table.add_row(
                commit_data["short_hash"],
                commit_data["author_name"],
                commit_data["date"],
                commit_data["message_short"]
            )

        if not table.rows: # Should be caught by `if not commits:`
            click.echo(f"No unique commits to display for branch '{branch_name}'.")
            return

        console.print(table)

    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
    except CoreBranchNotFoundError as e: # Renamed to avoid clash with pygit2.BranchNotFoundError if used locally
        click.echo(f"Error: {e}", err=True)
    except GitWriteError as e:
        click.echo(f"Error during review: {e}", err=True)
    except ImportError:
        click.echo("Error: Rich library is not installed. Please ensure it is installed.", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred during review: {e}", err=True)

@cli.command("cherry-pick")
@click.argument("commit_id")
@click.option("--mainline", type=int, default=None, help="Parent number (1-based) to consider as the mainline, for merge commits.")
def cherry_pick_cmd(commit_id, mainline):
    """Apply a specific change from another version to your current work.
    
    Examples:
      gitwrite cherry-pick abc123          # Apply that specific change
      gitwrite cherry-pick main~2          # Apply a change from 2 saves ago
      gitwrite review alternate-ending     # First, see what changes are available
      gitwrite cherry-pick def456          # Then apply a specific good change
    
    What this does:
      - Takes a specific change (save/commit) from anywhere in your project
      - Applies just that change to your current work
      - Creates a new save with that change
    
    Great for:
      - Applying a bug fix from one version to another
      - Moving a good idea from an experiment to your main work
      - Selectively applying changes without merging everything
      - Incorporating feedback from collaborators piece by piece
    
    Tip: Use 'gitwrite review <branch>' first to see available changes.
    """
    try:
        repo_path_str = str(Path.cwd())
        result = cherry_pick_commit(repo_path_str, commit_id, mainline=mainline)

        if result.get('status') == 'success':
            click.echo(click.style(result.get('message', 'Cherry-pick successful.'), fg='green'))
            click.echo(f"New commit: {result.get('new_commit_oid')[:7]}")
        else:
            # This case should ideally not be reached if core function throws exceptions for errors
            click.echo(f"Cherry-pick operation reported unhandled status: {result.get('status', 'unknown')}", err=True)

    except RepositoryNotFoundError:
        click.echo("Error: Not a Git repository (or any of the parent directories).", err=True)
    except CommitNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
    except MergeConflictError as e:
        click.echo(click.style(f"Error: Cherry-pick of commit '{commit_id}' resulted in conflicts.", fg='red'))
        click.echo(str(e), err=True) # Core message often includes "working directory reset" or similar
        if hasattr(e, 'conflicting_files') and e.conflicting_files:
            click.echo("Conflicting files:", err=True)
            for f_path in sorted(e.conflicting_files):
                click.echo(f"  {f_path}", err=True)
        # Unlike merge/revert, cherry-pick in core currently aborts on conflict.
        # So, no instructions to "resolve and save" are typically needed here.
    except GitWriteError as e: # Catch-all for other specific errors from core (e.g., mainline issues)
        click.echo(f"Error during cherry-pick: {e}", err=True)
    except Exception as e: # General catch-all for unexpected issues
        click.echo(f"An unexpected error occurred during cherry-pick: {e}", err=True)

@ignore.command("add")
@click.argument("pattern")
def ignore_add(pattern):
    """Tell GitWrite to ignore specific files or patterns.
    
    Examples:
      gitwrite ignore add "*.tmp"          # Ignore all temporary files
      gitwrite ignore add "notes/private/" # Ignore private notes folder
      gitwrite ignore add ".DS_Store"      # Ignore system files (Mac)
      gitwrite ignore add "*.backup"       # Ignore backup files
    
    Common patterns:
      *.tmp, *.temp    → Temporary files
      .DS_Store        → Mac system files
      Thumbs.db        → Windows thumbnail files
      notes/private/   → Private folders
      *.bak, *.backup  → Backup files
    
    What this does:
      - Adds the pattern to your .gitignore file
      - Future saves won't include matching files
      - Keeps your project clean and focused
    """
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
    """See what files GitWrite is currently ignoring.
    
    This shows all the patterns in your .gitignore file.
    
    Use this to:
      - Check what's being ignored
      - Understand why certain files aren't being saved
      - Review your ignore patterns
    
    If you want to stop ignoring something:
      1. Note the pattern from this list
      2. Edit your .gitignore file to remove it
      3. Use 'gitwrite save' to start tracking those files
    """
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

@cli.group()
def export():
    """Create finished documents from your writing project.
    
    Transform your writing into professional formats for sharing,
    publishing, or archiving. Choose from multiple output formats
    depending on your needs.
    """
    pass

@export.command("epub")
@click.option("-o", "--output-path", "output_path_str", type=click.Path(dir_okay=False, writable=True), required=True, help="Path to save the EPUB file (e.g., my-book.epub).")
@click.option("-c", "--commit", "commit_ish", default="HEAD", help="Commit-ish (commit, branch, tag) to export from. Defaults to HEAD.")
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True))
@click.argument("files", nargs=-1, type=click.Path(exists=False, dir_okay=False), required=True) # Using exists=False as files are from repo, not local FS necessarily
@click.pass_context
def export_epub(ctx, output_path_str: str, commit_ish: str, repo_path: str, files: tuple[str, ...]):
    """Create an EPUB e-book from your markdown files.
    
    Examples:
      gitwrite export epub -o MyNovel.epub . chapter1.md chapter2.md
      gitwrite export epub -o MyBook.epub --commit final . drafts/*.md
    
    What this creates:
      - Professional EPUB file readable on most e-readers
      - Properly formatted with chapters and navigation
      - Compatible with Kindle, Apple Books, Adobe Digital Editions
    
    Requirements:
      - Pandoc must be installed on your system
      - Files should be in Markdown format
      - Files are combined in the order you specify
    
    Perfect for:
      - Creating e-books from your writing
      - Sharing long-form content with readers
      - Professional manuscript submission
      - Self-publishing preparation
    
    FILES arguments are paths to markdown files relative to the repository root.
    """
    if not files:
        click.echo("Error: At least one markdown file must be specified for export.", err=True)
        ctx.exit(1)
        return

    file_list = list(files)
    # repo_path_cli = str(Path.cwd()) # No longer using cwd, using the repo_path argument

    try:
        # Ensure output directory exists if path includes directories
        output_path_obj = Path(output_path_str)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        result = export_to_epub(
            repo_path_str=repo_path, # Use the repo_path argument
            commit_ish_str=commit_ish,
            file_list=file_list,
            output_epub_path_str=output_path_str # Core function expects full path
        )
        # Core function returns: {"status": "success", "message": "..."}
        if result["status"] == "success":
            click.echo(click.style(result["message"], fg="green"))
        else:
            # This case should ideally not be reached if core function throws exceptions for errors
            click.echo(f"EPUB export failed: {result.get('message', 'Unknown core error')}", err=True)
            ctx.exit(1)

    except RepositoryNotFoundError as e:
        click.echo(f"Error: Not a Git repository (or any of the parent directories): {e}", err=True)
        ctx.exit(1)
    except CommitNotFoundError as e:
        click.echo(f"Error: Commit '{commit_ish}' not found: {e}", err=True)
        ctx.exit(1)
    except FileNotFoundInCommitError as e:
        click.echo(f"Error: File not found in commit '{commit_ish}': {e}", err=True)
        ctx.exit(1)
    except PandocError as e:
        click.echo(f"Error during EPUB generation: {e}", err=True)
        if "Pandoc not found" in str(e):
            click.echo("Hint: Please ensure Pandoc is installed and accessible in your system's PATH.", err=True)
        ctx.exit(1)
    except GitWriteError as e: # Catch-all for other specific errors from core export
        # e.g., empty file list (already checked), non-UTF-8 content, empty content, output dir creation issues (partially handled)
        click.echo(f"Error during export: {e}", err=True)
        ctx.exit(1)
    except OSError as e: # For issues like creating output_path_obj.parent
        click.echo(f"Error creating output directory for '{output_path_str}': {e}", err=True)
        ctx.exit(1)
    except Exception as e: # Fallback for truly unexpected errors
        click.echo(f"An unexpected error occurred during EPUB export: {e}", err=True)
        ctx.exit(1)


@export.command("pdf")
@click.option("-o", "--output-path", "output_path_str", type=click.Path(dir_okay=False, writable=True), required=True, help="Path to save the PDF file (e.g., my-document.pdf).")
@click.option("-c", "--commit", "commit_ish", default="HEAD", help="Commit-ish (commit, branch, tag) to export from. Defaults to HEAD.")
@click.option("--pdf-engine", default="pdflatex", help="PDF engine to use (pdflatex, xelatex, lualatex). Defaults to pdflatex.")
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True))
@click.argument("files", nargs=-1, type=click.Path(exists=False, dir_okay=False), required=True)
@click.pass_context
def export_pdf(ctx, output_path_str: str, commit_ish: str, pdf_engine: str, repo_path: str, files: tuple[str, ...]):
    """Create a professional PDF document from your markdown files.
    
    Examples:
      gitwrite export pdf -o MyNovel.pdf . chapter1.md chapter2.md
      gitwrite export pdf -o MyBook.pdf --pdf-engine xelatex . drafts/*.md
      gitwrite export pdf -o Report.pdf --commit final . report.md
    
    What this creates:
      - Professional PDF document with proper formatting
      - Print-ready output suitable for physical publishing
      - Configurable PDF engine for different typography needs
    
    Requirements:
      - Pandoc must be installed on your system
      - LaTeX distribution (e.g., TeX Live, MiKTeX) for PDF generation
      - Files should be in Markdown format
      - Files are combined in the order you specify
    
    PDF Engines:
      - pdflatex: Standard LaTeX engine (default)
      - xelatex: Better Unicode and font support
      - lualatex: Most modern LaTeX engine
    
    Perfect for:
      - Print manuscripts for traditional publishing
      - Professional reports and documentation
      - Academic papers and theses
      - High-quality archival copies
    
    FILES arguments are paths to markdown files relative to the repository root.
    """
    if not files:
        click.echo("Error: At least one markdown file must be specified for export.", err=True)
        ctx.exit(1)
        return

    file_list = list(files)
    
    try:
        # Ensure output directory exists if path includes directories
        output_path_obj = Path(output_path_str)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        from gitwrite_core.export import export_to_pdf
        
        # Set up PDF engine options
        pandoc_options = {}
        if pdf_engine:
            pandoc_options['extra_args'] = ['--standalone', f'--pdf-engine={pdf_engine}']
        
        result = export_to_pdf(
            repo_path_str=repo_path,
            commit_ish_str=commit_ish,
            file_list=file_list,
            output_pdf_path_str=output_path_str,
            **pandoc_options
        )
        
        if result["status"] == "success":
            click.echo(click.style(result["message"], fg="green"))
        else:
            click.echo(f"PDF export failed: {result.get('message', 'Unknown core error')}", err=True)
            ctx.exit(1)

    except RepositoryNotFoundError as e:
        click.echo(f"Error: Not a Git repository (or any of the parent directories): {e}", err=True)
        ctx.exit(1)
    except CommitNotFoundError as e:
        click.echo(f"Error: Commit '{commit_ish}' not found: {e}", err=True)
        ctx.exit(1)
    except FileNotFoundInCommitError as e:
        click.echo(f"Error: File not found in commit '{commit_ish}': {e}", err=True)
        ctx.exit(1)
    except PandocError as e:
        click.echo(f"Error during PDF generation: {e}", err=True)
        if "Pandoc not found" in str(e):
            click.echo("Hint: Please ensure Pandoc is installed and accessible in your system's PATH.", err=True)
        elif "pdflatex not found" in str(e) or "LaTeX" in str(e):
            click.echo(f"Hint: Please ensure a LaTeX distribution is installed for the '{pdf_engine}' engine.", err=True)
        ctx.exit(1)
    except GitWriteError as e:
        click.echo(f"Error during export: {e}", err=True)
        ctx.exit(1)
    except OSError as e:
        click.echo(f"Error creating output directory for '{output_path_str}': {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during PDF export: {e}", err=True)
        ctx.exit(1)


@export.command("docx")
@click.option("-o", "--output-path", "output_path_str", type=click.Path(dir_okay=False, writable=True), required=True, help="Path to save the DOCX file (e.g., my-document.docx).")
@click.option("-c", "--commit", "commit_ish", default="HEAD", help="Commit-ish (commit, branch, tag) to export from. Defaults to HEAD.")
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True))
@click.argument("files", nargs=-1, type=click.Path(exists=False, dir_okay=False), required=True)
@click.pass_context
def export_docx(ctx, output_path_str: str, commit_ish: str, repo_path: str, files: tuple[str, ...]):
    """Create a Microsoft Word document from your markdown files.
    
    Examples:
      gitwrite export docx -o MyNovel.docx . chapter1.md chapter2.md
      gitwrite export docx -o MyBook.docx --commit final . drafts/*.md
      gitwrite export docx -o Manuscript.docx . novel/*.md
    
    What this creates:
      - Microsoft Word (.docx) document with proper formatting
      - Compatible with Word, Google Docs, LibreOffice, and other editors
      - Editable format perfect for collaborative editing
      - Preserves structure, headings, and basic formatting
    
    Requirements:
      - Pandoc must be installed on your system
      - Files should be in Markdown format
      - Files are combined in the order you specify
    
    Perfect for:
      - Sharing drafts with editors who prefer Word
      - Collaborative editing in traditional office environments
      - Manuscripts for publishers who require Word format
      - Converting from Markdown to mainstream word processing
    
    The resulting DOCX file will:
      - Maintain your chapter structure and headings
      - Preserve formatting like bold, italic, and lists
      - Be immediately editable in Microsoft Word
      - Include proper page breaks between sections
    
    FILES arguments are paths to markdown files relative to the repository root.
    """
    if not files:
        click.echo("Error: At least one markdown file must be specified for export.", err=True)
        ctx.exit(1)
        return

    file_list = list(files)
    
    try:
        # Ensure output directory exists if path includes directories
        output_path_obj = Path(output_path_str)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        from gitwrite_core.export import export_to_docx
        
        result = export_to_docx(
            repo_path_str=repo_path,
            commit_ish_str=commit_ish,
            file_list=file_list,
            output_docx_path_str=output_path_str
        )
        
        if result["status"] == "success":
            click.echo(click.style(result["message"], fg="green"))
        else:
            click.echo(f"DOCX export failed: {result.get('message', 'Unknown core error')}", err=True)
            ctx.exit(1)

    except RepositoryNotFoundError as e:
        click.echo(f"Error: Not a Git repository (or any of the parent directories): {e}", err=True)
        ctx.exit(1)
    except CommitNotFoundError as e:
        click.echo(f"Error: Commit '{commit_ish}' not found: {e}", err=True)
        ctx.exit(1)
    except FileNotFoundInCommitError as e:
        click.echo(f"Error: File not found in commit '{commit_ish}': {e}", err=True)
        ctx.exit(1)
    except PandocError as e:
        click.echo(f"Error during DOCX generation: {e}", err=True)
        if "Pandoc not found" in str(e):
            click.echo("Hint: Please ensure Pandoc is installed and accessible in your system's PATH.", err=True)
        ctx.exit(1)
    except GitWriteError as e:
        click.echo(f"Error during export: {e}", err=True)
        ctx.exit(1)
    except OSError as e:
        click.echo(f"Error creating output directory for '{output_path_str}': {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during DOCX export: {e}", err=True)
        ctx.exit(1)


if __name__ == "__main__":
    cli()
