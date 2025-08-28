# Extending CLI

GitWrite CLI is designed to be extensible and customizable, allowing writers and developers to add new commands, modify existing functionality, and integrate with external tools. This extensibility ensures that GitWrite can adapt to diverse writing workflows and environments.

## Overview

The extension system provides several mechanisms for customization:
- **Plugin System**: Add new commands and functionality through plugins
- **Custom Commands**: Create repository-specific or user-specific commands
- **Hooks**: Execute custom code at specific points in GitWrite operations
- **Templates**: Define reusable content and structure templates
- **Integrations**: Connect with external writing tools and services
- **Themes**: Customize CLI appearance and output formatting

```
Extension Architecture
    │
    ├─ Core CLI Framework
    │   ├─ Command Registry
    │   ├─ Plugin Manager
    │   └─ Hook System
    │
    ├─ Extension Points
    │   ├─ Command Extensions
    │   ├─ Operation Hooks
    │   ├─ Format Handlers
    │   └─ Integration Adapters
    │
    ├─ User Extensions
    │   ├─ Custom Commands
    │   ├─ Local Plugins
    │   └─ Configuration Scripts
    │
    └─ Third-party Extensions
        ├─ Community Plugins
        ├─ Tool Integrations
        └─ Service Connectors
```

## Plugin System

### 1. Plugin Architecture

```python
# gitwrite/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import click

class GitWritePlugin(ABC):
    """Base class for all GitWrite plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description."""
        pass

    @property
    def author(self) -> str:
        """Plugin author."""
        return "Unknown"

    @property
    def dependencies(self) -> List[str]:
        """List of required dependencies."""
        return []

    @abstractmethod
    def initialize(self, cli_context: Dict[str, Any]) -> None:
        """Initialize the plugin."""
        pass

    @abstractmethod
    def register_commands(self) -> List[click.Command]:
        """Return list of commands provided by this plugin."""
        pass

    def register_hooks(self) -> Dict[str, callable]:
        """Return dict of hook name -> function mappings."""
        return {}

    def cleanup(self) -> None:
        """Cleanup when plugin is unloaded."""
        pass

# Example plugin implementation
class WordCountPlugin(GitWritePlugin):
    """Plugin that provides advanced word counting features."""

    @property
    def name(self) -> str:
        return "word-count-extended"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Extended word counting and statistics"

    def initialize(self, cli_context: Dict[str, Any]) -> None:
        self.config = cli_context.get('config', {})
        click.echo(f"Initialized {self.name} plugin")

    def register_commands(self) -> List[click.Command]:
        return [
            self.word_frequency_command(),
            self.reading_time_command(),
            self.complexity_analysis_command()
        ]

    def word_frequency_command(self) -> click.Command:
        @click.command()
        @click.argument('file_path')
        @click.option('--top', default=10, help='Number of top words to show')
        @click.option('--min-length', default=3, help='Minimum word length')
        def word_frequency(file_path: str, top: int, min_length: int):
            """Analyze word frequency in a file."""
            # Implementation here
            pass

        return word_frequency

    def reading_time_command(self) -> click.Command:
        @click.command()
        @click.argument('file_path')
        @click.option('--wpm', default=200, help='Words per minute reading speed')
        def reading_time(file_path: str, wpm: int):
            """Calculate estimated reading time."""
            # Implementation here
            pass

        return reading_time

    def complexity_analysis_command(self) -> click.Command:
        @click.command()
        @click.argument('file_path')
        @click.option('--metrics', multiple=True,
                     default=['flesch', 'gunning_fog'],
                     help='Readability metrics to calculate')
        def complexity(file_path: str, metrics: List[str]):
            """Analyze text complexity and readability."""
            # Implementation here
            pass

        return complexity
```

### 2. Plugin Manager

```python
# gitwrite/plugins/manager.py
import importlib
import os
from pathlib import Path
from typing import Dict, List, Optional
import pkg_resources

class PluginManager:
    """Manages GitWrite plugins."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.plugins_dir = config_dir / 'plugins'
        self.plugins_dir.mkdir(exist_ok=True)

        self.loaded_plugins: Dict[str, GitWritePlugin] = {}
        self.plugin_commands: Dict[str, click.Command] = {}
        self.plugin_hooks: Dict[str, List[callable]] = {}

    def discover_plugins(self) -> List[str]:
        """Discover available plugins."""
        plugin_names = []

        # Discover built-in plugins
        builtin_plugins = self._discover_builtin_plugins()
        plugin_names.extend(builtin_plugins)

        # Discover installed plugins via entry points
        entry_point_plugins = self._discover_entry_point_plugins()
        plugin_names.extend(entry_point_plugins)

        # Discover local plugins
        local_plugins = self._discover_local_plugins()
        plugin_names.extend(local_plugins)

        return plugin_names

    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin."""
        try:
            # Try to import the plugin
            plugin_module = self._import_plugin(plugin_name)

            # Find plugin class
            plugin_class = self._find_plugin_class(plugin_module)

            # Instantiate and initialize
            plugin = plugin_class()
            plugin.initialize({'config': self._get_plugin_config(plugin_name)})

            # Register commands
            commands = plugin.register_commands()
            for command in commands:
                self.plugin_commands[command.name] = command

            # Register hooks
            hooks = plugin.register_hooks()
            for hook_name, hook_func in hooks.items():
                if hook_name not in self.plugin_hooks:
                    self.plugin_hooks[hook_name] = []
                self.plugin_hooks[hook_name].append(hook_func)

            self.loaded_plugins[plugin_name] = plugin
            return True

        except Exception as e:
            click.echo(f"Failed to load plugin '{plugin_name}': {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin."""
        if plugin_name not in self.loaded_plugins:
            return False

        plugin = self.loaded_plugins[plugin_name]

        # Remove commands
        commands = plugin.register_commands()
        for command in commands:
            if command.name in self.plugin_commands:
                del self.plugin_commands[command.name]

        # Remove hooks
        hooks = plugin.register_hooks()
        for hook_name in hooks.keys():
            if hook_name in self.plugin_hooks:
                self.plugin_hooks[hook_name] = [
                    h for h in self.plugin_hooks[hook_name]
                    if h != hooks[hook_name]
                ]

        # Cleanup
        plugin.cleanup()
        del self.loaded_plugins[plugin_name]

        return True

    def get_plugin_command(self, command_name: str) -> Optional[click.Command]:
        """Get plugin command by name."""
        return self.plugin_commands.get(command_name)

    def execute_hooks(self, hook_name: str, context: Dict[str, Any]) -> None:
        """Execute all hooks for a given hook point."""
        if hook_name in self.plugin_hooks:
            for hook_func in self.plugin_hooks[hook_name]:
                try:
                    hook_func(context)
                except Exception as e:
                    click.echo(f"Hook '{hook_name}' failed: {e}")

    def _discover_builtin_plugins(self) -> List[str]:
        """Discover built-in plugins."""
        builtin_dir = Path(__file__).parent / 'builtin'
        plugins = []

        if builtin_dir.exists():
            for plugin_file in builtin_dir.glob('*.py'):
                if plugin_file.stem != '__init__':
                    plugins.append(f"builtin.{plugin_file.stem}")

        return plugins

    def _discover_entry_point_plugins(self) -> List[str]:
        """Discover plugins via setuptools entry points."""
        plugins = []

        for entry_point in pkg_resources.iter_entry_points('gitwrite.plugins'):
            plugins.append(entry_point.name)

        return plugins

    def _discover_local_plugins(self) -> List[str]:
        """Discover local user plugins."""
        plugins = []

        for plugin_file in self.plugins_dir.glob('*.py'):
            if plugin_file.stem != '__init__':
                plugins.append(f"local.{plugin_file.stem}")

        return plugins
```

### 3. Creating Custom Commands

```python
# Example: ~/.gitwrite/plugins/manuscript_tools.py
from gitwrite.plugins.base import GitWritePlugin
import click
import re
from pathlib import Path

class ManuscriptToolsPlugin(GitWritePlugin):
    """Tools for manuscript formatting and preparation."""

    @property
    def name(self) -> str:
        return "manuscript-tools"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Manuscript formatting and preparation tools"

    def initialize(self, cli_context):
        self.config = cli_context.get('config', {})

    def register_commands(self):
        return [
            self.format_manuscript_command(),
            self.create_toc_command(),
            self.validate_structure_command()
        ]

    def format_manuscript_command(self):
        @click.command()
        @click.argument('input_file')
        @click.option('--output', help='Output file path')
        @click.option('--style', default='standard',
                     type=click.Choice(['standard', 'novel', 'screenplay']),
                     help='Manuscript formatting style')
        @click.option('--double-space', is_flag=True, help='Use double spacing')
        def format_manuscript(input_file, output, style, double_space):
            """Format a manuscript according to publishing standards."""

            input_path = Path(input_file)
            output_path = Path(output) if output else input_path.with_suffix('.formatted.md')

            with open(input_path, 'r') as f:
                content = f.read()

            # Apply formatting rules based on style
            if style == 'standard':
                content = self.apply_standard_formatting(content, double_space)
            elif style == 'novel':
                content = self.apply_novel_formatting(content, double_space)
            elif style == 'screenplay':
                content = self.apply_screenplay_formatting(content)

            with open(output_path, 'w') as f:
                f.write(content)

            click.echo(f"Formatted manuscript saved to: {output_path}")

        return format_manuscript

    def create_toc_command(self):
        @click.command()
        @click.argument('directory', default='.')
        @click.option('--pattern', default='chapter-*.md', help='File pattern to include')
        @click.option('--output', default='table-of-contents.md', help='Output file')
        @click.option('--levels', default=2, help='Heading levels to include')
        def create_toc(directory, pattern, output, levels):
            """Generate table of contents from manuscript files."""

            dir_path = Path(directory)
            files = list(dir_path.glob(pattern))
            files.sort()

            toc_lines = ["# Table of Contents", ""]

            for file_path in files:
                with open(file_path, 'r') as f:
                    content = f.read()

                # Extract headings
                headings = re.findall(r'^(#{1,' + str(levels) + r'})\s+(.+)$',
                                    content, re.MULTILINE)

                if headings:
                    toc_lines.append(f"## {file_path.stem.replace('-', ' ').title()}")

                    for level, title in headings:
                        indent = "  " * (len(level) - 1)
                        toc_lines.append(f"{indent}- {title}")

                    toc_lines.append("")

            output_path = Path(output)
            with open(output_path, 'w') as f:
                f.write('\n'.join(toc_lines))

            click.echo(f"Table of contents saved to: {output_path}")

        return create_toc

    def apply_standard_formatting(self, content, double_space):
        """Apply standard manuscript formatting."""

        # Remove extra whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Ensure proper paragraph spacing
        if double_space:
            content = re.sub(r'\n\n', '\n\n\n', content)

        # Format dialogue
        content = re.sub(r'^"([^"]+)"$', r'    "\1"', content, flags=re.MULTILINE)

        # Format chapter headings
        content = re.sub(r'^# (.+)$', r'# \1\n', content, flags=re.MULTILINE)

        return content
```

## Hook System

### 1. Available Hook Points

```python
# gitwrite/hooks/registry.py
from typing import Dict, Any, Callable, List

class HookRegistry:
    """Registry for GitWrite hooks."""

    # Define available hook points
    HOOKS = {
        # Repository operations
        'pre_repository_create': 'Before creating a new repository',
        'post_repository_create': 'After creating a new repository',
        'pre_save': 'Before saving changes',
        'post_save': 'After saving changes',

        # File operations
        'pre_file_create': 'Before creating a new file',
        'post_file_create': 'After creating a new file',
        'pre_file_edit': 'Before editing a file',
        'post_file_edit': 'After editing a file',

        # Export operations
        'pre_export': 'Before exporting content',
        'post_export': 'After exporting content',

        # Collaboration
        'pre_collaboration_invite': 'Before sending collaboration invite',
        'post_collaboration_accept': 'After accepting collaboration invite',

        # Session management
        'session_start': 'When writing session starts',
        'session_end': 'When writing session ends',

        # Milestone events
        'milestone_achieved': 'When a milestone is reached',
        'goal_completed': 'When a writing goal is completed',
    }

    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {hook: [] for hook in self.HOOKS}

    def register_hook(self, hook_name: str, callback: Callable):
        """Register a hook callback."""
        if hook_name in self.hooks:
            self.hooks[hook_name].append(callback)

    def execute_hooks(self, hook_name: str, context: Dict[str, Any]):
        """Execute all registered hooks for a hook point."""
        if hook_name in self.hooks:
            for callback in self.hooks[hook_name]:
                try:
                    callback(context)
                except Exception as e:
                    click.echo(f"Hook '{hook_name}' failed: {e}")

# Example hook usage
def word_count_milestone_hook(context: Dict[str, Any]):
    """Hook that celebrates word count milestones."""
    word_count = context.get('word_count', 0)
    milestones = [1000, 5000, 10000, 25000, 50000, 100000]

    for milestone in milestones:
        if word_count >= milestone and not context.get(f'milestone_{milestone}_celebrated'):
            click.echo(f"🎉 Congratulations! You've reached {milestone:,} words!")
            context[f'milestone_{milestone}_celebrated'] = True
            break

# Register the hook
hook_registry.register_hook('post_save', word_count_milestone_hook)
```

### 2. Custom Hook Creation

```python
# ~/.gitwrite/hooks/custom_hooks.py
from gitwrite.hooks.registry import HookRegistry
import subprocess
import json
from datetime import datetime

def setup_custom_hooks(hook_registry: HookRegistry):
    """Set up custom hooks for this user."""

    # Auto-backup hook
    def auto_backup_hook(context):
        """Automatically backup after every save."""
        if context.get('save_successful'):
            backup_dir = Path.home() / '.gitwrite' / 'backups'
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f"backup_{timestamp}.tar.gz"

            subprocess.run([
                'tar', '-czf', str(backup_file),
                '-C', context['repository_path'], '.'
            ])

    # Writing session tracking
    def session_tracker_hook(context):
        """Track writing session statistics."""
        session_file = Path.home() / '.gitwrite' / 'session_log.json'

        session_data = {
            'timestamp': datetime.now().isoformat(),
            'action': context.get('action'),
            'word_count': context.get('word_count', 0),
            'files_modified': context.get('files_modified', [])
        }

        # Append to session log
        if session_file.exists():
            with open(session_file, 'r') as f:
                sessions = json.load(f)
        else:
            sessions = []

        sessions.append(session_data)

        with open(session_file, 'w') as f:
            json.dump(sessions, f, indent=2)

    # Register hooks
    hook_registry.register_hook('post_save', auto_backup_hook)
    hook_registry.register_hook('session_start', session_tracker_hook)
    hook_registry.register_hook('session_end', session_tracker_hook)
```

## Template System

### 1. Custom Templates

```python
# ~/.gitwrite/templates/novel_chapter.py
from gitwrite.templates.base import Template

class NovelChapterTemplate(Template):
    """Template for novel chapters."""

    @property
    def name(self):
        return "novel-chapter"

    @property
    def description(self):
        return "Standard novel chapter template"

    def generate(self, context):
        chapter_number = context.get('chapter_number', 1)
        chapter_title = context.get('chapter_title', f'Chapter {chapter_number}')
        author = context.get('author', 'Author Name')

        return f"""# {chapter_title}

## Opening

[Begin with a compelling hook that draws the reader in]

## Development

[Develop the scene, advance the plot, and reveal character]

## Transition

[End with a transition to the next chapter or a cliffhanger]

---

**Chapter {chapter_number} Notes:**
- Word count goal: 2,500-3,000 words
- Key plot points to cover:
  - [ ]
  - [ ]
  - [ ]
- Character development focus:
  - [ ]
  - [ ]

**Revision checklist:**
- [ ] Strong opening hook
- [ ] Clear conflict/tension
- [ ] Character growth shown
- [ ] Smooth transitions
- [ ] Engaging dialogue
- [ ] Vivid scene setting

*Draft started: {{{{date}}}}*
*Author: {author}*
"""
```

### 2. Template Manager

```python
# gitwrite/templates/manager.py
class TemplateManager:
    """Manages GitWrite templates."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.templates_dir = config_dir / 'templates'
        self.templates_dir.mkdir(exist_ok=True)

        self.templates = {}
        self._load_builtin_templates()
        self._load_user_templates()

    def create_from_template(self, template_name: str, output_path: Path,
                           context: Dict[str, Any]) -> bool:
        """Create file from template."""

        if template_name not in self.templates:
            click.echo(f"Template '{template_name}' not found")
            return False

        template = self.templates[template_name]
        content = template.generate(context)

        # Process template variables
        content = self._process_template_variables(content, context)

        with open(output_path, 'w') as f:
            f.write(content)

        return True

    def list_templates(self) -> List[str]:
        """List available templates."""
        return list(self.templates.keys())

    def _process_template_variables(self, content: str, context: Dict[str, Any]) -> str:
        """Process template variables like {{date}}, {{author}}, etc."""
        import re
        from datetime import datetime

        # Built-in variables
        variables = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'year': str(datetime.now().year),
            'month': datetime.now().strftime('%B'),
            'day': str(datetime.now().day),
        }

        # Add context variables
        variables.update(context)

        # Replace variables in content
        def replace_var(match):
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))

        return re.sub(r'\{\{(\w+)\}\}', replace_var, content)
```

## Integration Framework

### 1. External Tool Integration

```python
# gitwrite/integrations/base.py
from abc import ABC, abstractmethod

class ExternalIntegration(ABC):
    """Base class for external tool integrations."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def supported_operations(self) -> List[str]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if external tool is available."""
        pass

    @abstractmethod
    def import_content(self, source_path: str, target_path: str) -> bool:
        """Import content from external tool."""
        pass

    @abstractmethod
    def export_content(self, source_path: str, target_path: str) -> bool:
        """Export content to external tool."""
        pass

# Example: Scrivener integration
class ScrivenerIntegration(ExternalIntegration):
    """Integration with Scrivener writing software."""

    @property
    def name(self) -> str:
        return "scrivener"

    @property
    def supported_operations(self) -> List[str]:
        return ["import", "export", "sync"]

    def is_available(self) -> bool:
        """Check if Scrivener is installed."""
        return shutil.which("scrivener") is not None

    def import_content(self, source_path: str, target_path: str) -> bool:
        """Import from Scrivener project."""
        # Implementation to extract text from .scriv files
        pass

    def export_content(self, source_path: str, target_path: str) -> bool:
        """Export to Scrivener project."""
        # Implementation to create .scriv compatible files
        pass
```

## Configuration and Management

### 1. Extension Management Commands

```python
@click.group()
def extensions():
    """Manage GitWrite extensions."""
    pass

@extensions.command()
def list():
    """List all available extensions."""
    plugin_manager = get_plugin_manager()
    plugins = plugin_manager.discover_plugins()

    click.echo("Available Extensions:")
    click.echo("-" * 50)

    for plugin_name in plugins:
        status = "✓ Loaded" if plugin_name in plugin_manager.loaded_plugins else "○ Available"
        click.echo(f"{status} {plugin_name}")

@extensions.command()
@click.argument('extension_name')
def install(extension_name):
    """Install an extension."""
    # Implementation for installing extensions
    pass

@extensions.command()
@click.argument('extension_name')
def enable(extension_name):
    """Enable an extension."""
    plugin_manager = get_plugin_manager()
    if plugin_manager.load_plugin(extension_name):
        click.echo(f"Enabled extension: {extension_name}")
    else:
        click.echo(f"Failed to enable extension: {extension_name}")

@extensions.command()
@click.argument('extension_name')
def disable(extension_name):
    """Disable an extension."""
    plugin_manager = get_plugin_manager()
    if plugin_manager.unload_plugin(extension_name):
        click.echo(f"Disabled extension: {extension_name}")
    else:
        click.echo(f"Extension not loaded: {extension_name}")
```

### 2. Development Tools

```python
@extensions.command()
@click.argument('plugin_name')
@click.option('--template', default='basic', help='Plugin template to use')
def scaffold(plugin_name, template):
    """Create a new plugin scaffold."""

    plugin_dir = Path.home() / '.gitwrite' / 'plugins' / plugin_name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Create plugin files from template
    create_plugin_scaffold(plugin_dir, plugin_name, template)

    click.echo(f"Created plugin scaffold at: {plugin_dir}")
    click.echo("Edit the plugin files and run 'gitwrite extensions enable' to test.")

def create_plugin_scaffold(plugin_dir: Path, plugin_name: str, template: str):
    """Create plugin scaffold files."""

    # Main plugin file
    plugin_content = f'''from gitwrite.plugins.base import GitWritePlugin
import click

class {plugin_name.title()}Plugin(GitWritePlugin):
    @property
    def name(self):
        return "{plugin_name}"

    @property
    def version(self):
        return "1.0.0"

    @property
    def description(self):
        return "Description of {plugin_name} plugin"

    def initialize(self, cli_context):
        pass

    def register_commands(self):
        return [self.example_command()]

    def example_command(self):
        @click.command()
        @click.argument('arg')
        def example(arg):
            """Example command."""
            click.echo(f"Hello from {plugin_name}: {{arg}}")

        return example
'''

    with open(plugin_dir / '__init__.py', 'w') as f:
        f.write(plugin_content)

    # Configuration file
    config_content = f'''# Configuration for {plugin_name} plugin
version: "1.0.0"
dependencies: []
hooks: []
'''

    with open(plugin_dir / 'plugin.yaml', 'w') as f:
        f.write(config_content)
```

---

*GitWrite's extension system provides powerful customization capabilities while maintaining simplicity for basic use cases. Writers can extend the CLI to match their specific workflows, integrate with preferred tools, and automate repetitive tasks, making GitWrite truly adaptable to any writing process.*