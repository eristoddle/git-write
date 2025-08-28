# Configuration Management

GitWrite CLI provides comprehensive configuration management that allows users to customize their writing environment, set preferences, and manage credentials across multiple repositories and contexts. The configuration system balances ease-of-use with powerful customization options.

## Overview

The configuration system supports:
- **Global Configuration**: User-wide settings and preferences
- **Repository Configuration**: Project-specific settings
- **Profile Management**: Multiple configuration profiles for different contexts
- **Environment Variables**: System-level configuration overrides
- **Secure Credential Storage**: Safe storage of authentication tokens
- **Migration and Backup**: Easy configuration transfer between systems

```
Configuration Hierarchy
    │
    ├─ System Environment Variables
    │   ├─ GITWRITE_CONFIG_DIR
    │   ├─ GITWRITE_API_URL
    │   └─ GITWRITE_LOG_LEVEL
    │
    ├─ Global Configuration (~/.gitwrite/config.yaml)
    │   ├─ User Preferences
    │   ├─ Default Settings
    │   └─ Authentication Profiles
    │
    ├─ Repository Configuration (.gitwrite/config.yaml)
    │   ├─ Project Settings
    │   ├─ Collaboration Rules
    │   └─ Export Preferences
    │
    └─ Command-line Overrides
        ├─ --config flags
        ├─ --profile switches
        └─ Direct option overrides
```

## Configuration File Structure

### 1. Global Configuration

```yaml
# ~/.gitwrite/config.yaml
user:
  name: "Jane Writer"
  email: "jane@example.com"
  default_author: true

preferences:
  editor:
    default: "code"  # VS Code
    word_wrap: true
    line_numbers: true
    tab_size: 2

  writing:
    auto_save: true
    auto_save_interval: 30  # seconds
    spell_check: true
    language: "en-US"
    word_count_goal: 500  # daily

  collaboration:
    auto_pull: true
    conflict_resolution: "prompt"  # prompt, auto, manual
    notification_level: "important"  # all, important, none

api:
  base_url: "https://api.gitwrite.com"
  timeout: 30
  retry_attempts: 3

output:
  default_format: "markdown"
  export_directory: "~/Documents/GitWrite/exports"
  include_metadata: true

profiles:
  work:
    api:
      base_url: "https://api.company.com/gitwrite"
    user:
      name: "Jane Writer (Work)"
      email: "jane.writer@company.com"

  personal:
    api:
      base_url: "https://api.gitwrite.com"
    user:
      name: "Jane Writer"
      email: "jane@personal.com"

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "~/.gitwrite/logs/gitwrite.log"
  max_size: "10MB"
  backup_count: 5
```

### 2. Repository Configuration

```yaml
# .gitwrite/config.yaml (in repository root)
repository:
  name: "my-novel"
  description: "My first novel project"

collaboration:
  enabled: true
  auto_accept_invites: false
  roles:
    editors: ["editor@example.com"]
    beta_readers: ["reader1@example.com", "reader2@example.com"]

  permissions:
    editors:
      - read
      - write
      - comment
      - suggest
    beta_readers:
      - read
      - comment

writing:
  structure:
    chapters_directory: "chapters"
    notes_directory: "notes"
    research_directory: "research"

  naming_convention:
    chapters: "chapter-{number:02d}-{title}"
    scenes: "scene-{number}"

  word_count:
    target: 80000
    daily_goal: 500
    track_by_file: true

export:
  formats:
    - markdown
    - epub
    - pdf

  epub:
    cover_image: "assets/cover.jpg"
    metadata:
      title: "My Novel"
      author: "Jane Writer"
      publisher: "Self Published"
      language: "en"

  pdf:
    template: "manuscript"
    include_title_page: true
    double_space: true

automation:
  save_triggers:
    - word_count_milestone: 1000
    - time_interval: 300  # 5 minutes

  backup:
    enabled: true
    interval: "daily"
    keep_count: 30

notifications:
  email:
    enabled: true
    on_collaboration_invite: true
    on_feedback_received: true
    daily_summary: true

  desktop:
    enabled: true
    writing_reminders: true
    goal_achievements: true
```

## Configuration Management Commands

### 1. Basic Configuration Commands

```python
# gitwrite/cli/config.py
import click
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional

@click.group()
def config():
    """Configuration management commands."""
    pass

@config.command()
@click.option('--global', 'is_global', is_flag=True, help='Show global configuration')
@click.option('--repository', is_flag=True, help='Show repository configuration')
@click.option('--profile', help='Show specific profile configuration')
def show(is_global: bool, repository: bool, profile: Optional[str]):
    """Display current configuration."""

    if is_global or (not repository and not profile):
        click.echo("Global Configuration:")
        click.echo("=" * 50)
        global_config = load_global_config()
        click.echo(yaml.dump(global_config, default_flow_style=False))

    if repository:
        click.echo("\nRepository Configuration:")
        click.echo("=" * 50)
        repo_config = load_repository_config()
        if repo_config:
            click.echo(yaml.dump(repo_config, default_flow_style=False))
        else:
            click.echo("No repository configuration found.")

    if profile:
        click.echo(f"\nProfile '{profile}' Configuration:")
        click.echo("=" * 50)
        profile_config = load_profile_config(profile)
        if profile_config:
            click.echo(yaml.dump(profile_config, default_flow_style=False))
        else:
            click.echo(f"Profile '{profile}' not found.")

@config.command()
@click.argument('key')
@click.argument('value')
@click.option('--global', 'is_global', is_flag=True, help='Set global configuration')
@click.option('--repository', is_flag=True, help='Set repository configuration')
@click.option('--profile', help='Set configuration for specific profile')
def set(key: str, value: str, is_global: bool, repository: bool, profile: Optional[str]):
    """Set a configuration value."""

    # Parse value (try to detect type)
    parsed_value = parse_config_value(value)

    if profile:
        set_profile_config(profile, key, parsed_value)
        click.echo(f"Set {key} = {parsed_value} for profile '{profile}'")
    elif repository:
        set_repository_config(key, parsed_value)
        click.echo(f"Set {key} = {parsed_value} for repository")
    else:
        set_global_config(key, parsed_value)
        click.echo(f"Set {key} = {parsed_value} globally")

@config.command()
@click.argument('key')
@click.option('--global', 'is_global', is_flag=True, help='Get global configuration')
@click.option('--repository', is_flag=True, help='Get repository configuration')
@click.option('--profile', help='Get configuration from specific profile')
def get(key: str, is_global: bool, repository: bool, profile: Optional[str]):
    """Get a configuration value."""

    if profile:
        config_dict = load_profile_config(profile)
        source = f"profile '{profile}'"
    elif repository:
        config_dict = load_repository_config()
        source = "repository"
    else:
        config_dict = load_global_config()
        source = "global"

    value = get_nested_value(config_dict, key)

    if value is not None:
        click.echo(f"{key} = {value} (from {source})")
    else:
        click.echo(f"Configuration key '{key}' not found in {source} configuration.")

@config.command()
@click.argument('key')
@click.option('--global', 'is_global', is_flag=True, help='Unset global configuration')
@click.option('--repository', is_flag=True, help='Unset repository configuration')
@click.option('--profile', help='Unset configuration from specific profile')
def unset(key: str, is_global: bool, repository: bool, profile: Optional[str]):
    """Remove a configuration value."""

    if profile:
        unset_profile_config(profile, key)
        click.echo(f"Unset {key} from profile '{profile}'")
    elif repository:
        unset_repository_config(key)
        click.echo(f"Unset {key} from repository")
    else:
        unset_global_config(key)
        click.echo(f"Unset {key} from global configuration")

def parse_config_value(value: str) -> Any:
    """Parse string value to appropriate type."""

    # Try boolean
    if value.lower() in ('true', 'yes', 'on', '1'):
        return True
    if value.lower() in ('false', 'no', 'off', '0'):
        return False

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try JSON/YAML for complex structures
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError:
        pass

    # Return as string
    return value

def get_nested_value(config_dict: Dict[str, Any], key: str) -> Any:
    """Get nested configuration value using dot notation."""

    parts = key.split('.')
    current = config_dict

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current

def set_nested_value(config_dict: Dict[str, Any], key: str, value: Any) -> None:
    """Set nested configuration value using dot notation."""

    parts = key.split('.')
    current = config_dict

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value
```

### 2. Profile Management

```python
@config.group()
def profile():
    """Profile management commands."""
    pass

@profile.command()
def list():
    """List all available profiles."""

    global_config = load_global_config()
    profiles = global_config.get('profiles', {})

    if not profiles:
        click.echo("No profiles configured.")
        return

    click.echo("Available profiles:")
    click.echo("-" * 20)

    for profile_name, profile_config in profiles.items():
        description = profile_config.get('description', 'No description')
        api_url = profile_config.get('api', {}).get('base_url', 'Default API')
        user_name = profile_config.get('user', {}).get('name', 'Unknown user')

        click.echo(f"• {profile_name}")
        click.echo(f"  Description: {description}")
        click.echo(f"  API: {api_url}")
        click.echo(f"  User: {user_name}")
        click.echo()

@profile.command()
@click.argument('name')
@click.option('--description', help='Profile description')
@click.option('--api-url', help='API base URL for this profile')
@click.option('--user-name', help='User name for this profile')
@click.option('--user-email', help='User email for this profile')
def create(name: str, description: str, api_url: str, user_name: str, user_email: str):
    """Create a new configuration profile."""

    global_config = load_global_config()

    if 'profiles' not in global_config:
        global_config['profiles'] = {}

    if name in global_config['profiles']:
        if not click.confirm(f"Profile '{name}' already exists. Overwrite?"):
            return

    profile_config = {}

    if description:
        profile_config['description'] = description

    if api_url:
        profile_config['api'] = {'base_url': api_url}

    if user_name or user_email:
        profile_config['user'] = {}
        if user_name:
            profile_config['user']['name'] = user_name
        if user_email:
            profile_config['user']['email'] = user_email

    global_config['profiles'][name] = profile_config
    save_global_config(global_config)

    click.echo(f"Created profile '{name}'")

@profile.command()
@click.argument('name')
def delete(name: str):
    """Delete a configuration profile."""

    global_config = load_global_config()
    profiles = global_config.get('profiles', {})

    if name not in profiles:
        click.echo(f"Profile '{name}' not found.")
        return

    if click.confirm(f"Delete profile '{name}'?"):
        del profiles[name]
        save_global_config(global_config)
        click.echo(f"Deleted profile '{name}'")

@profile.command()
@click.argument('name')
def use(name: str):
    """Switch to a different profile."""

    global_config = load_global_config()
    profiles = global_config.get('profiles', {})

    if name not in profiles:
        click.echo(f"Profile '{name}' not found.")
        return

    # Set current profile
    global_config['current_profile'] = name
    save_global_config(global_config)

    click.echo(f"Switched to profile '{name}'")
```

### 3. Configuration Validation

```python
# gitwrite/config/validator.py
from typing import Dict, Any, List
import jsonschema
from pathlib import Path

class ConfigValidator:
    """Validates GitWrite configuration files."""

    def __init__(self):
        self.schema = self._load_schema()

    def validate_global_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate global configuration."""
        errors = []

        try:
            jsonschema.validate(config, self.schema['global'])
        except jsonschema.ValidationError as e:
            errors.append(f"Global config validation error: {e.message}")

        # Custom validation rules
        errors.extend(self._validate_user_config(config.get('user', {})))
        errors.extend(self._validate_api_config(config.get('api', {})))

        return errors

    def validate_repository_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate repository configuration."""
        errors = []

        try:
            jsonschema.validate(config, self.schema['repository'])
        except jsonschema.ValidationError as e:
            errors.append(f"Repository config validation error: {e.message}")

        # Custom validation rules
        errors.extend(self._validate_export_config(config.get('export', {})))
        errors.extend(self._validate_collaboration_config(config.get('collaboration', {})))

        return errors

    def _validate_user_config(self, user_config: Dict[str, Any]) -> List[str]:
        """Validate user configuration section."""
        errors = []

        if 'email' in user_config:
            email = user_config['email']
            if '@' not in email or '.' not in email:
                errors.append("Invalid email format")

        return errors

    def _validate_api_config(self, api_config: Dict[str, Any]) -> List[str]:
        """Validate API configuration section."""
        errors = []

        if 'base_url' in api_config:
            url = api_config['base_url']
            if not url.startswith(('http://', 'https://')):
                errors.append("API base_url must start with http:// or https://")

        if 'timeout' in api_config:
            timeout = api_config['timeout']
            if not isinstance(timeout, int) or timeout <= 0:
                errors.append("API timeout must be a positive integer")

        return errors

    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema for configuration validation."""
        schema_path = Path(__file__).parent / 'schemas'

        with open(schema_path / 'global_config.json') as f:
            global_schema = json.load(f)

        with open(schema_path / 'repository_config.json') as f:
            repository_schema = json.load(f)

        return {
            'global': global_schema,
            'repository': repository_schema
        }

@config.command()
@click.option('--global', 'validate_global', is_flag=True, help='Validate global configuration')
@click.option('--repository', is_flag=True, help='Validate repository configuration')
def validate(validate_global: bool, repository: bool):
    """Validate configuration files."""

    validator = ConfigValidator()

    if validate_global or (not repository):
        click.echo("Validating global configuration...")
        global_config = load_global_config()
        errors = validator.validate_global_config(global_config)

        if errors:
            click.echo("Global configuration errors:")
            for error in errors:
                click.echo(f"  • {error}")
        else:
            click.echo("✓ Global configuration is valid")

    if repository:
        click.echo("Validating repository configuration...")
        repo_config = load_repository_config()

        if repo_config:
            errors = validator.validate_repository_config(repo_config)

            if errors:
                click.echo("Repository configuration errors:")
                for error in errors:
                    click.echo(f"  • {error}")
            else:
                click.echo("✓ Repository configuration is valid")
        else:
            click.echo("No repository configuration found")
```

### 4. Configuration Migration

```python
@config.command()
@click.option('--from-version', help='Source configuration version')
@click.option('--to-version', help='Target configuration version')
@click.option('--backup', is_flag=True, help='Create backup before migration')
def migrate(from_version: str, to_version: str, backup: bool):
    """Migrate configuration between versions."""

    migrator = ConfigMigrator()

    if backup:
        click.echo("Creating configuration backup...")
        backup_path = migrator.create_backup()
        click.echo(f"Backup created at: {backup_path}")

    try:
        migrator.migrate(from_version, to_version)
        click.echo(f"Successfully migrated configuration from {from_version} to {to_version}")
    except Exception as e:
        click.echo(f"Migration failed: {e}")
        if backup:
            click.echo(f"Restore from backup: {backup_path}")

@config.command()
@click.argument('backup_file', type=click.Path(exists=True))
def restore(backup_file: str):
    """Restore configuration from backup."""

    if click.confirm(f"This will overwrite current configuration. Continue?"):
        migrator = ConfigMigrator()
        migrator.restore_from_backup(backup_file)
        click.echo("Configuration restored from backup")

@config.command()
@click.option('--include-profiles', is_flag=True, help='Include all profiles')
@click.option('--output', help='Output file path')
def backup(include_profiles: bool, output: str):
    """Create configuration backup."""

    migrator = ConfigMigrator()
    backup_path = migrator.create_backup(
        include_profiles=include_profiles,
        output_path=output
    )

    click.echo(f"Configuration backup created: {backup_path}")
```

## Environment Variables

### Supported Variables

```bash
# Core configuration
export GITWRITE_CONFIG_DIR="$HOME/.gitwrite"
export GITWRITE_API_URL="https://api.gitwrite.com"
export GITWRITE_API_TOKEN="your-api-token"

# Logging
export GITWRITE_LOG_LEVEL="INFO"
export GITWRITE_LOG_FILE="$HOME/.gitwrite/logs/gitwrite.log"

# Editor preferences
export GITWRITE_EDITOR="code"
export GITWRITE_AUTO_SAVE="true"

# Profile management
export GITWRITE_PROFILE="work"

# Development/debugging
export GITWRITE_DEBUG="true"
export GITWRITE_DEV_MODE="true"
```

### Environment Variable Priority

```python
def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value with proper precedence."""

    # 1. Environment variable (highest priority)
    env_key = f"GITWRITE_{key.upper().replace('.', '_')}"
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return parse_config_value(env_value)

    # 2. Command-line profile override
    current_profile = get_current_profile()
    if current_profile:
        profile_config = load_profile_config(current_profile)
        profile_value = get_nested_value(profile_config, key)
        if profile_value is not None:
            return profile_value

    # 3. Repository configuration
    repo_config = load_repository_config()
    if repo_config:
        repo_value = get_nested_value(repo_config, key)
        if repo_value is not None:
            return repo_value

    # 4. Global configuration
    global_config = load_global_config()
    global_value = get_nested_value(global_config, key)
    if global_value is not None:
        return global_value

    # 5. Default value (lowest priority)
    return default
```

## Configuration Templates

### Quick Setup Templates

```python
@config.command()
@click.option('--template', type=click.Choice(['writer', 'editor', 'team', 'minimal']),
              default='writer', help='Configuration template to use')
@click.option('--name', prompt='Your name', help='Your full name')
@click.option('--email', prompt='Your email', help='Your email address')
def init(template: str, name: str, email: str):
    """Initialize GitWrite configuration with a template."""

    templates = {
        'writer': create_writer_template(name, email),
        'editor': create_editor_template(name, email),
        'team': create_team_template(name, email),
        'minimal': create_minimal_template(name, email)
    }

    config = templates[template]
    save_global_config(config)

    click.echo(f"Initialized GitWrite configuration with '{template}' template")
    click.echo("Run 'gitwrite config show' to view your configuration")

def create_writer_template(name: str, email: str) -> Dict[str, Any]:
    """Create configuration template for individual writers."""
    return {
        'user': {
            'name': name,
            'email': email,
            'default_author': True
        },
        'preferences': {
            'writing': {
                'auto_save': True,
                'auto_save_interval': 30,
                'spell_check': True,
                'word_count_goal': 500
            },
            'editor': {
                'word_wrap': True,
                'line_numbers': False,
                'tab_size': 2
            }
        },
        'output': {
            'default_format': 'markdown',
            'include_metadata': True
        }
    }
```

---

*GitWrite's configuration management system provides flexible, hierarchical configuration that adapts to different writing workflows while maintaining simplicity for basic use cases and power for advanced scenarios.*