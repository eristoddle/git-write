# CLI Tool (Python Click)

The GitWrite Command Line Interface (CLI) provides a powerful, writer-friendly terminal experience for all GitWrite operations. Built with Python Click, the CLI transforms complex Git operations into intuitive commands that writers can easily understand and use.

## Design Philosophy

### Writer-First Approach

The CLI is designed around how writers think and work, not how developers use Git:

**Traditional Git:**
```bash
git add .
git commit -m "Updated chapter 3"
git checkout -b alternative-ending
git merge main
```

**GitWrite CLI:**
```bash
gitwrite save "Updated chapter 3"
gitwrite explore create alternative-ending
gitwrite explore merge main
```

### Intuitive Command Structure

Commands follow natural language patterns that writers already understand:

```bash
# Project management
gitwrite init my-novel
gitwrite status
gitwrite history

# Writing workflow
gitwrite save "Added character development"
gitwrite explore create "different-ending"
gitwrite compare main different-ending

# Collaboration
gitwrite share --with editor@example.com
gitwrite annotations list
gitwrite review start

# Publishing
gitwrite export epub
gitwrite publish --platform kindle
```

## CLI Architecture

### Command Hierarchy

The CLI follows a hierarchical structure with logical groupings:

```
gitwrite
├── init                    # Project initialization
├── config                  # Configuration management
├── status                  # Current project status
├── save                    # Save changes (commit)
├── history                 # View project history
├── stats                   # Writing statistics
├── diff                    # Compare versions
├── explore/               # Exploration (branch) management
│   ├── create            # Create new exploration
│   ├── list              # List explorations
│   ├── switch            # Change exploration
│   ├── merge             # Merge explorations
│   └── delete            # Remove exploration
├── annotations/           # Feedback and comments
│   ├── add               # Add annotation
│   ├── list              # List annotations
│   ├── show              # Show annotation details
│   └── resolve           # Mark as resolved
├── export/                # Document generation
│   ├── epub              # Export to EPUB
│   ├── pdf               # Export to PDF
│   ├── docx              # Export to Word
│   └── html              # Export to HTML
├── collaborate/           # Collaboration features
│   ├── invite            # Invite collaborators
│   ├── share             # Share project
│   └── permissions       # Manage access
└── help                   # Context-sensitive help
```

### Click Framework Integration

The CLI leverages Click's powerful features for a polished user experience:

```python
import click
from gitwrite_core import repository, versioning, branching

@click.group()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--config', type=click.Path(), help='Custom config file')
@click.pass_context
def cli(ctx, verbose, config):
    """GitWrite - Version control for writers"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = config

@cli.command()
@click.argument('message')
@click.option('--files', multiple=True, help='Specific files to save')
@click.option('--tag', help='Tag this save as a milestone')
def save(message, files, tag):
    """Save your work with a descriptive message"""
    try:
        result = versioning.save_changes(
            message=message,
            files=list(files) if files else None,
            tag=tag
        )

        if result.success:
            click.echo(f"✓ Saved: {result.message}")
            if tag:
                click.echo(f"  Tagged as: {tag}")
        else:
            click.echo(f"✗ Error: {result.error}", err=True)

    except Exception as e:
        click.echo(f"✗ Unexpected error: {e}", err=True)
```

### Rich Output Formatting

The CLI provides rich, colorful output that's easy to scan and understand:

```python
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.syntax import Syntax

console = Console()

def show_status(status_info):
    """Display repository status with rich formatting"""
    if status_info.is_clean:
        console.print("✓ No changes to save", style="green")
    else:
        console.print(f"📝 {status_info.total_changes} files changed", style="yellow")

        if status_info.modified_files:
            console.print(f"  Modified: {len(status_info.modified_files)} files", style="blue")
        if status_info.new_files:
            console.print(f"  New: {len(status_info.new_files)} files", style="green")
        if status_info.deleted_files:
            console.print(f"  Deleted: {len(status_info.deleted_files)} files", style="red")

def show_history(commits):
    """Display commit history in a formatted table"""
    table = Table(title="Project History")
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Message", style="white")
    table.add_column("Author", style="green")
    table.add_column("Date", style="blue")

    for commit in commits[:10]:  # Show last 10 commits
        table.add_row(
            commit.short_id,
            commit.message[:50] + "..." if len(commit.message) > 50 else commit.message,
            commit.author,
            commit.timestamp.strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)
```

## Core Commands

### Project Management Commands

#### `gitwrite init`

Initialize a new GitWrite project with intelligent defaults:

```python
@cli.command()
@click.argument('project_name', required=False)
@click.option('--author', prompt=True, help='Project author name')
@click.option('--description', help='Project description')
@click.option('--type', 'project_type',
              type=click.Choice(['novel', 'short-story', 'article', 'screenplay', 'academic']),
              default='novel', help='Type of writing project')
@click.option('--template', help='Custom project template')
@click.option('--interactive', is_flag=True, help='Interactive setup mode')
def init(project_name, author, description, project_type, template, interactive):
    """Initialize a new GitWrite project"""

    if interactive:
        # Interactive setup with prompts and validation
        project_name = project_name or click.prompt('Project name')
        description = description or click.prompt('Project description', default='')
        project_type = click.prompt(
            'Project type',
            type=click.Choice(['novel', 'short-story', 'article', 'screenplay', 'academic']),
            default=project_type
        )

    # Create project configuration
    config = ProjectConfig(
        name=project_name,
        author=author,
        description=description,
        project_type=project_type,
        template=template
    )

    # Initialize repository
    try:
        result = repository.GitWriteRepository.initialize(
            path=Path.cwd() / project_name if project_name else Path.cwd(),
            config=config
        )

        if result.success:
            console.print(f"✓ Created GitWrite project: {project_name}", style="green")
            console.print(f"  📁 Location: {result.path}")
            console.print(f"  📝 Type: {project_type}")
            console.print(f"  👤 Author: {author}")

            # Show next steps
            console.print("\n🚀 Next steps:", style="bold blue")
            console.print("  1. cd into your project directory")
            console.print("  2. Start writing in the manuscript/ folder")
            console.print("  3. Save your work with 'gitwrite save \"your message\"'")

        else:
            console.print(f"✗ Failed to create project: {result.error}", style="red")
            if result.suggestions:
                console.print("💡 Suggestions:", style="yellow")
                for suggestion in result.suggestions:
                    console.print(f"  • {suggestion}")

    except Exception as e:
        console.print(f"✗ Unexpected error: {e}", style="red")
        raise click.ClickException(str(e))
```

#### `gitwrite status`

Show the current state of the project in writer-friendly terms:

```python
@cli.command()
@click.option('--detailed', is_flag=True, help='Show detailed file status')
@click.option('--stats', is_flag=True, help='Include writing statistics')
def status(detailed, stats):
    """Show current project status"""
    try:
        repo = get_current_repository()
        status_info = repo.get_status()

        # Header with project info
        config = repo.get_configuration()
        console.print(f"📖 {config.name}", style="bold blue")
        console.print(f"👤 {config.author}")

        if status_info.current_branch != 'main':
            console.print(f"🔬 Working in exploration: {status_info.current_branch}", style="yellow")

        # Status overview
        show_status(status_info)

        # Detailed file listing
        if detailed and status_info.has_changes:
            console.print("\n📋 Changed files:", style="bold")

            for file_path in status_info.modified_files:
                console.print(f"  📝 {file_path} (modified)", style="blue")
            for file_path in status_info.new_files:
                console.print(f"  ✨ {file_path} (new)", style="green")
            for file_path in status_info.deleted_files:
                console.print(f"  🗑️  {file_path} (deleted)", style="red")

        # Writing statistics
        if stats:
            stats_info = get_writing_statistics()
            console.print(f"\n📊 Writing Stats:", style="bold")
            console.print(f"  Words today: {stats_info.words_today}")
            console.print(f"  Total words: {stats_info.total_words}")
            console.print(f"  Files: {stats_info.file_count}")

    except RepositoryError as e:
        console.print(f"✗ Not a GitWrite project: {e}", style="red")
        console.print("💡 Run 'gitwrite init' to create a new project")
        raise click.ClickException(str(e))
```

### Writing Workflow Commands

#### `gitwrite save`

Save changes with meaningful descriptions:

```python
@cli.command()
@click.argument('message')
@click.option('--files', multiple=True, help='Specific files to save')
@click.option('--tag', help='Tag this save as a milestone')
@click.option('--interactive', is_flag=True, help='Review changes before saving')
def save(message, files, tag, interactive):
    """Save your work with a descriptive message"""

    try:
        repo = get_current_repository()

        # Interactive mode - show changes before saving
        if interactive:
            status_info = repo.get_status()
            if status_info.has_changes:
                console.print("📋 Changes to be saved:", style="bold")
                show_status(status_info)

                if not click.confirm("Save these changes?"):
                    console.print("Save cancelled", style="yellow")
                    return

        # Perform the save
        result = versioning.save_changes(
            message=message,
            files=list(files) if files else None
        )

        if result.success:
            console.print(f"✓ Saved: {message}", style="green")
            console.print(f"  🆔 Save ID: {result.commit_id[:8]}")

            if files:
                console.print(f"  📄 Files: {', '.join(files)}")
            else:
                console.print(f"  📄 Files: all changes")

            # Add tag if requested
            if tag:
                tag_result = tagging.create_tag(tag, f"Milestone: {message}")
                if tag_result.success:
                    console.print(f"  🏷️  Tagged as: {tag}", style="blue")

            # Show writing statistics
            stats = get_session_statistics()
            if stats.words_added > 0:
                console.print(f"  ➕ Words added: {stats.words_added}", style="green")

        else:
            console.print(f"✗ Save failed: {result.error}", style="red")
            if result.suggestions:
                console.print("💡 Try:", style="yellow")
                for suggestion in result.suggestions:
                    console.print(f"  • {suggestion}")

    except Exception as e:
        console.print(f"✗ Unexpected error: {e}", style="red")
        raise click.ClickException(str(e))
```

#### `gitwrite explore`

Exploration management with subcommands:

```python
@cli.group()
def explore():
    """Manage explorations (alternative versions of your work)"""
    pass

@explore.command('create')
@click.argument('name')
@click.option('--description', help='Description of what you\'re exploring')
@click.option('--from-commit', help='Start exploration from specific save point')
def explore_create(name, description, from_commit):
    """Create a new exploration to try different approaches"""
    try:
        result = branching.create_exploration(
            name=name,
            description=description,
            from_commit=from_commit
        )

        if result.success:
            console.print(f"🔬 Created exploration: {name}", style="green")
            if description:
                console.print(f"  📝 {description}")
            console.print(f"  🚀 You can now safely experiment with different approaches")
            console.print(f"  🔄 Switch back with: gitwrite explore switch main")

        else:
            console.print(f"✗ Failed to create exploration: {result.error}", style="red")

    except Exception as e:
        console.print(f"✗ Unexpected error: {e}", style="red")
        raise click.ClickException(str(e))

@explore.command('list')
@click.option('--detailed', is_flag=True, help='Show detailed information')
def explore_list(detailed):
    """List all explorations"""
    try:
        explorations = branching.list_explorations()
        current = branching.get_current_exploration()

        if not explorations:
            console.print("📋 No explorations yet", style="yellow")
            console.print("💡 Create one with: gitwrite explore create <name>")
            return

        console.print("🔬 Explorations:", style="bold blue")

        for exploration in explorations:
            prefix = "→" if exploration.name == current else " "
            style = "bold green" if exploration.name == current else "white"

            console.print(f"{prefix} {exploration.name}", style=style)

            if detailed:
                console.print(f"    📝 {exploration.description or 'No description'}")
                console.print(f"    📅 Created: {exploration.created_at}")
                console.print(f"    💾 Last save: {exploration.last_commit}")

    except Exception as e:
        console.print(f"✗ Error listing explorations: {e}", style="red")
        raise click.ClickException(str(e))
```

### Export Commands

#### `gitwrite export`

Document generation with multiple format support:

```python
@cli.group()
def export():
    """Export your work to various formats"""
    pass

@export.command('epub')
@click.option('--title', help='Book title (default: project name)')
@click.option('--author', help='Author name (default: project author)')
@click.option('--cover', type=click.Path(exists=True), help='Cover image file')
@click.option('--output', type=click.Path(), help='Output file path')
@click.option('--template', help='Export template to use')
@click.option('--metadata', type=click.Path(exists=True), help='Metadata file')
def export_epub(title, author, cover, output, template, metadata):
    """Export to EPUB format for e-readers"""

    try:
        repo = get_current_repository()
        config = repo.get_configuration()

        # Use defaults from project config
        title = title or config.name
        author = author or config.author
        output = output or f"{title.replace(' ', '-').lower()}.epub"

        console.print(f"📚 Exporting '{title}' to EPUB...", style="blue")

        # Show progress
        with Progress() as progress:
            task = progress.add_task("Generating EPUB...", total=100)

            export_config = ExportConfig(
                format='epub',
                title=title,
                author=author,
                cover_image=cover,
                template=template,
                metadata_file=metadata,
                output_path=output
            )

            progress.update(task, advance=30)

            result = export.export_document(export_config)

            progress.update(task, advance=70)

        if result.success:
            console.print(f"✓ EPUB created: {output}", style="green")
            console.print(f"  📖 Title: {title}")
            console.print(f"  👤 Author: {author}")
            console.print(f"  📦 Size: {result.file_size}")

            if click.confirm("Open the EPUB file?"):
                click.launch(output)

        else:
            console.print(f"✗ Export failed: {result.error}", style="red")
            if result.suggestions:
                for suggestion in result.suggestions:
                    console.print(f"💡 {suggestion}", style="yellow")

    except Exception as e:
        console.print(f"✗ Unexpected error: {e}", style="red")
        raise click.ClickException(str(e))
```

## Advanced CLI Features

### Context-Sensitive Help

The CLI provides intelligent help based on context:

```python
@cli.command()
@click.argument('command', required=False)
def help(command):
    """Get help for GitWrite commands"""

    if not command:
        # Check project state and provide relevant help
        try:
            repo = get_current_repository()
            status_info = repo.get_status()

            console.print("🆘 GitWrite Help", style="bold blue")

            if status_info.has_changes:
                console.print("\n📝 You have unsaved changes:", style="yellow")
                console.print("  gitwrite save \"description of changes\"")

            console.print("\n🔧 Common commands:")
            console.print("  gitwrite status           # Check project status")
            console.print("  gitwrite save \"message\"    # Save your work")
            console.print("  gitwrite history          # View project history")
            console.print("  gitwrite explore create   # Try different approaches")
            console.print("  gitwrite export epub      # Generate e-book")

        except RepositoryError:
            console.print("🆘 GitWrite Help", style="bold blue")
            console.print("\n💡 Not in a GitWrite project:")
            console.print("  gitwrite init my-project  # Create new project")
            console.print("  cd existing-project       # Enter existing project")

    else:
        # Show help for specific command
        try:
            cmd = cli.get_command(None, command)
            if cmd:
                console.print(cmd.get_help(click.Context(cmd)))
            else:
                console.print(f"Unknown command: {command}", style="red")
                console.print("Run 'gitwrite help' for available commands")
        except Exception:
            console.print(f"No help available for: {command}", style="red")
```

### Auto-completion

GitWrite provides shell auto-completion for better usability:

```python
# Enable completion for bash/zsh/fish
def enable_completion():
    """Enable shell completion for GitWrite commands"""

    # Add to shell rc file
    completion_script = '''
# GitWrite completion
eval "$(_GITWRITE_COMPLETE=source_bash gitwrite)"  # bash
eval "$(_GITWRITE_COMPLETE=source_zsh gitwrite)"   # zsh
eval (env _GITWRITE_COMPLETE=source_fish gitwrite | psub)  # fish
'''

    # Custom completion for project-specific items
    def complete_exploration_names(ctx, param, incomplete):
        """Complete exploration names"""
        try:
            explorations = branching.list_explorations()
            return [exp.name for exp in explorations if exp.name.startswith(incomplete)]
        except:
            return []

    def complete_file_names(ctx, param, incomplete):
        """Complete file names in project"""
        try:
            repo = get_current_repository()
            status = repo.get_status()
            all_files = status.modified_files + status.new_files
            return [f for f in all_files if f.startswith(incomplete)]
        except:
            return []
```

### Configuration Management

Comprehensive configuration system:

```python
@cli.group()
def config():
    """Manage GitWrite configuration"""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
@click.option('--global', 'is_global', is_flag=True, help='Set global configuration')
def config_set(key, value, is_global):
    """Set configuration value"""
    try:
        if is_global:
            result = set_global_config(key, value)
        else:
            result = set_project_config(key, value)

        if result.success:
            scope = "global" if is_global else "project"
            console.print(f"✓ Set {scope} config: {key} = {value}", style="green")
        else:
            console.print(f"✗ Failed to set config: {result.error}", style="red")

    except Exception as e:
        console.print(f"✗ Configuration error: {e}", style="red")

@config.command('list')
@click.option('--global', 'show_global', is_flag=True, help='Show global configuration')
def config_list(show_global):
    """List current configuration"""
    try:
        if show_global:
            config_data = get_global_config()
            console.print("🌍 Global Configuration:", style="bold blue")
        else:
            config_data = get_project_config()
            console.print("📁 Project Configuration:", style="bold blue")

        table = Table()
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Description", style="dim")

        for key, value in config_data.items():
            description = get_config_description(key)
            table.add_row(key, str(value), description)

        console.print(table)

    except Exception as e:
        console.print(f"✗ Error reading configuration: {e}", style="red")
```

---

*The GitWrite CLI provides a comprehensive, writer-friendly interface that makes version control accessible while preserving the full power of Git underneath. Its design focuses on natural language patterns and helpful feedback to guide writers through their workflow.*
