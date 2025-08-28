# Repository Management

The Repository Management module (`repository.py`) handles all aspects of GitWrite project lifecycle, from initialization through configuration and maintenance. It serves as the foundation for all other GitWrite operations by managing the underlying Git repository structure.

## Core Responsibilities

### 1. Project Initialization
- Create new GitWrite projects with proper structure
- Initialize Git repositories with writer-friendly defaults
- Set up project metadata and configuration
- Create initial files and directory structure

### 2. Repository Configuration
- Manage GitWrite-specific configuration
- Handle user preferences and project settings
- Configure Git settings for optimal writing workflows
- Maintain compatibility with standard Git repositories

### 3. Project Discovery and Access
- Locate and validate GitWrite projects
- Provide secure access to repository operations
- Handle multi-user permissions and access control
- Maintain project registry and metadata

### 4. Repository Maintenance
- Perform repository health checks
- Handle repository optimization and cleanup
- Manage repository size and performance
- Provide diagnostic and repair capabilities

## Implementation Details

### Repository Structure

When a GitWrite project is initialized, it creates a structured environment optimized for writing:

```
my-novel/                    # Project root directory
├── .git/                    # Standard Git repository
├── .gitwrite/              # GitWrite-specific configuration
│   ├── config.json         # Project configuration
│   ├── templates/          # Export templates
│   ├── metadata/           # Project metadata
│   └── collaborators.json  # Collaboration settings
├── manuscript/             # Main writing content
│   ├── chapters/           # Chapter organization
│   ├── characters/         # Character development
│   ├── notes/             # Research and notes
│   └── outline.md         # Story structure
├── .gitignore             # Ignore patterns for writers
├── README.md              # Project description
└── gitwrite.yaml          # Main configuration file
```

### Core Classes

#### GitWriteRepository

The main repository management class that provides all repository operations:

```python
from pathlib import Path
from typing import Optional, Dict, List
import pygit2
import json
from datetime import datetime

class GitWriteRepository:
    """
    Main repository management class for GitWrite projects.

    Handles repository initialization, configuration, and basic operations
    while maintaining full Git compatibility.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.git_path = self.path / '.git'
        self.gitwrite_path = self.path / '.gitwrite'
        self._pygit2_repo = None
        self._config = None

    @property
    def git_repo(self) -> pygit2.Repository:
        """Lazy-loaded pygit2 repository"""
        if self._pygit2_repo is None:
            if not self.git_path.exists():
                raise RepositoryError(f"No Git repository found at {self.path}")
            self._pygit2_repo = pygit2.Repository(str(self.path))
        return self._pygit2_repo

    @property
    def is_gitwrite_repo(self) -> bool:
        """Check if this is a valid GitWrite repository"""
        return (
            self.git_path.exists() and
            self.gitwrite_path.exists() and
            (self.path / 'gitwrite.yaml').exists()
        )

    @classmethod
    def initialize(
        cls,
        path: str,
        config: 'ProjectConfig'
    ) -> 'RepositoryResult':
        """
        Initialize a new GitWrite project.

        Args:
            path: Directory path for the new project
            config: Project configuration and metadata

        Returns:
            RepositoryResult with initialization status and details
        """
        try:
            project_path = Path(path)

            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)

            # Initialize Git repository
            git_repo = pygit2.init_repository(str(project_path))

            # Create GitWrite structure
            repo = cls(str(project_path))
            repo._create_gitwrite_structure(config)
            repo._create_initial_content(config)
            repo._configure_git_settings()

            # Initial commit
            repo._create_initial_commit(config)

            return RepositoryResult(
                success=True,
                path=str(project_path),
                message=f"Initialized GitWrite project '{config.name}'",
                repository=repo
            )

        except Exception as e:
            return RepositoryResult(
                success=False,
                error=f"Failed to initialize repository: {str(e)}",
                suggestions=[
                    "Check that the directory is writable",
                    "Ensure the path doesn't already contain a Git repository",
                    "Verify you have sufficient disk space"
                ]
            )

    def _create_gitwrite_structure(self, config: 'ProjectConfig'):
        """Create GitWrite-specific directory structure"""
        # Create .gitwrite directory
        self.gitwrite_path.mkdir(exist_ok=True)

        # Create subdirectories
        (self.gitwrite_path / 'templates').mkdir(exist_ok=True)
        (self.gitwrite_path / 'metadata').mkdir(exist_ok=True)

        # Create manuscript structure
        manuscript_path = self.path / 'manuscript'
        manuscript_path.mkdir(exist_ok=True)
        (manuscript_path / 'chapters').mkdir(exist_ok=True)
        (manuscript_path / 'characters').mkdir(exist_ok=True)
        (manuscript_path / 'notes').mkdir(exist_ok=True)

        # Create configuration files
        self._create_configuration_files(config)

    def _create_configuration_files(self, config: 'ProjectConfig'):
        """Create initial configuration files"""
        # Main GitWrite configuration
        gitwrite_config = {
            'version': '1.0',
            'project': {
                'name': config.name,
                'type': config.project_type,
                'created': datetime.utcnow().isoformat(),
                'author': config.author,
                'description': config.description
            },
            'settings': {
                'default_branch': 'main',
                'auto_save': config.auto_save,
                'export_formats': config.export_formats,
                'collaboration': {
                    'enabled': config.collaboration_enabled,
                    'default_permissions': 'reader'
                }
            }
        }

        with open(self.path / 'gitwrite.yaml', 'w') as f:
            yaml.dump(gitwrite_config, f, default_flow_style=False)

        # GitWrite-specific config
        internal_config = {
            'repository_id': str(uuid.uuid4()),
            'created_with_version': '1.0.0',
            'last_updated': datetime.utcnow().isoformat()
        }

        with open(self.gitwrite_path / 'config.json', 'w') as f:
            json.dump(internal_config, f, indent=2)

        # Create .gitignore for writers
        gitignore_content = self._get_writer_gitignore_template()
        with open(self.path / '.gitignore', 'w') as f:
            f.write(gitignore_content)

    def _get_writer_gitignore_template(self) -> str:
        """Get .gitignore template optimized for writers"""
        return """# GitWrite specific
.gitwrite/cache/
.gitwrite/temp/

# Common writing application files
*.tmp
*~
.DS_Store
Thumbs.db

# Word processing temporary files
~$*
*.backup
*.bak

# Scrivener files (if not using Scrivener as main tool)
*.scriv/

# Common IDE/Editor files
.vscode/
.idea/
*.swp
*.swo

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Compiled output (if using export features)
output/
exports/
build/
"""

    def _create_initial_content(self, config: 'ProjectConfig'):
        """Create initial content files"""
        # README file
        readme_content = f"""# {config.name}

{config.description}

## About This Project

This is a GitWrite project for collaborative writing. GitWrite provides version control specifically designed for writers, with features like:

- **Explorations**: Try different approaches safely (like Git branches, but writer-friendly)
- **Annotations**: Collect and manage feedback from editors and beta readers
- **History**: Track every change with the ability to revert to any previous version
- **Export**: Generate professional documents in multiple formats (EPUB, PDF, DOCX)

## Getting Started

- Write in the `manuscript/` directory
- Use `gitwrite save "description"` to save your progress
- Create explorations with `gitwrite explore create "name"`
- Export your work with `gitwrite export epub`

## Project Structure

- `manuscript/chapters/` - Main story content
- `manuscript/characters/` - Character development notes
- `manuscript/notes/` - Research and general notes
- `manuscript/outline.md` - Story structure and planning

Author: {config.author}
Created: {datetime.now().strftime('%Y-%m-%d')}
"""

        with open(self.path / 'README.md', 'w') as f:
            f.write(readme_content)

        # Initial outline
        outline_content = f"""# {config.name} - Story Outline

## Concept
[Describe the core concept of your story]

## Characters
### Main Characters
- **Protagonist**: [Name and brief description]
- **Antagonist**: [Name and brief description]

### Supporting Characters
- [Supporting character 1]
- [Supporting character 2]

## Plot Structure
### Act 1 - Setup
- [Opening hook]
- [Introduce characters]
- [Establish conflict]

### Act 2 - Confrontation
- [Rising action]
- [Midpoint twist]
- [Complications]

### Act 3 - Resolution
- [Climax]
- [Resolution]
- [Conclusion]

## Themes
- [Primary theme]
- [Secondary themes]

## Notes
[Any additional notes, research, or ideas]
"""

        with open(self.path / 'manuscript' / 'outline.md', 'w') as f:
            f.write(outline_content)

    def _configure_git_settings(self):
        """Configure Git settings optimized for writing"""
        config = self.git_repo.config

        # Set user information if not already set
        try:
            config['user.name']
        except KeyError:
            config['user.name'] = 'GitWrite User'

        try:
            config['user.email']
        except KeyError:
            config['user.email'] = 'user@gitwrite.local'

        # Configure Git for better writing experience
        config['core.autocrlf'] = 'true'  # Handle line endings
        config['core.ignorecase'] = 'false'  # Case sensitive file names
        config['pull.rebase'] = 'false'  # Use merge strategy
        config['init.defaultBranch'] = 'main'  # Modern default branch name

        # Configure merge strategy for text files
        config['merge.tool'] = 'gitwrite-merge'  # Custom merge tool

        # Performance optimizations for large text files
        config['core.preloadindex'] = 'true'
        config['core.fscache'] = 'true'
        config['gc.auto'] = '256'  # More frequent garbage collection

    def _create_initial_commit(self, config: 'ProjectConfig'):
        """Create the initial commit for the repository"""
        # Stage all files
        index = self.git_repo.index
        index.add_all()
        index.write()

        # Create signature
        signature = pygit2.Signature(
            config.author or 'GitWrite User',
            config.email or 'user@gitwrite.local'
        )

        # Create initial commit
        tree = index.write_tree()
        commit_message = f"Initial commit: {config.name}\n\nCreated with GitWrite"

        self.git_repo.create_commit(
            'HEAD',
            signature,
            signature,
            commit_message,
            tree,
            []  # No parents for initial commit
        )

    def get_status(self) -> 'RepositoryStatus':
        """
        Get current repository status.

        Returns:
            RepositoryStatus with information about the current state
        """
        try:
            repo = self.git_repo

            # Get current branch
            try:
                current_branch = repo.head.shorthand
            except pygit2.GitError:
                current_branch = None  # No commits yet

            # Get status of working directory
            status_flags = repo.status()

            # Categorize changes
            modified_files = []
            new_files = []
            deleted_files = []

            for file_path, flags in status_flags.items():
                if flags & pygit2.GIT_STATUS_WT_MODIFIED:
                    modified_files.append(file_path)
                elif flags & pygit2.GIT_STATUS_WT_NEW:
                    new_files.append(file_path)
                elif flags & pygit2.GIT_STATUS_WT_DELETED:
                    deleted_files.append(file_path)

            # Check if repository is clean
            is_clean = len(status_flags) == 0

            # Get commit count
            try:
                commit_count = len(list(repo.walk(repo.head.target)))
            except (pygit2.GitError, AttributeError):
                commit_count = 0

            return RepositoryStatus(
                is_clean=is_clean,
                current_branch=current_branch,
                modified_files=modified_files,
                new_files=new_files,
                deleted_files=deleted_files,
                commit_count=commit_count,
                last_commit=self._get_last_commit_info()
            )

        except Exception as e:
            raise RepositoryError(f"Failed to get repository status: {str(e)}")

    def _get_last_commit_info(self) -> Optional[Dict]:
        """Get information about the last commit"""
        try:
            last_commit = self.git_repo[self.git_repo.head.target]
            return {
                'id': str(last_commit.id),
                'short_id': str(last_commit.id)[:8],
                'message': last_commit.message.strip(),
                'author': last_commit.author.name,
                'timestamp': datetime.fromtimestamp(last_commit.commit_time)
            }
        except (pygit2.GitError, AttributeError):
            return None

    def get_configuration(self) -> 'ProjectConfig':
        """
        Get project configuration.

        Returns:
            ProjectConfig object with current settings
        """
        if self._config is None:
            self._config = self._load_configuration()
        return self._config

    def _load_configuration(self) -> 'ProjectConfig':
        """Load configuration from gitwrite.yaml"""
        config_path = self.path / 'gitwrite.yaml'

        if not config_path.exists():
            raise RepositoryError("GitWrite configuration file not found")

        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            return ProjectConfig.from_dict(config_data)

        except Exception as e:
            raise RepositoryError(f"Failed to load configuration: {str(e)}")

    def update_configuration(self, updates: Dict) -> 'OperationResult':
        """
        Update project configuration.

        Args:
            updates: Dictionary of configuration updates

        Returns:
            OperationResult indicating success or failure
        """
        try:
            config = self.get_configuration()
            config.update(updates)

            # Save updated configuration
            config_path = self.path / 'gitwrite.yaml'
            with open(config_path, 'w') as f:
                yaml.dump(config.to_dict(), f, default_flow_style=False)

            # Clear cached config
            self._config = None

            return OperationResult(
                success=True,
                message="Configuration updated successfully"
            )

        except Exception as e:
            return OperationResult(
                success=False,
                error=f"Failed to update configuration: {str(e)}"
            )
```

### Data Models

#### ProjectConfig

Configuration object for GitWrite projects:

```python
@dataclass
class ProjectConfig:
    """Configuration for a GitWrite project"""
    name: str
    author: str
    description: str = ""
    project_type: str = "novel"  # novel, article, screenplay, etc.
    email: str = ""
    auto_save: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["epub", "pdf"])
    collaboration_enabled: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectConfig':
        """Create ProjectConfig from dictionary"""
        project_data = data.get('project', {})
        settings_data = data.get('settings', {})

        return cls(
            name=project_data.get('name', ''),
            author=project_data.get('author', ''),
            description=project_data.get('description', ''),
            project_type=project_data.get('type', 'novel'),
            email=project_data.get('email', ''),
            auto_save=settings_data.get('auto_save', True),
            export_formats=settings_data.get('export_formats', ['epub', 'pdf']),
            collaboration_enabled=settings_data.get('collaboration', {}).get('enabled', False)
        )

    def to_dict(self) -> Dict:
        """Convert ProjectConfig to dictionary"""
        return {
            'version': '1.0',
            'project': {
                'name': self.name,
                'author': self.author,
                'description': self.description,
                'type': self.project_type,
                'email': self.email
            },
            'settings': {
                'auto_save': self.auto_save,
                'export_formats': self.export_formats,
                'collaboration': {
                    'enabled': self.collaboration_enabled
                }
            }
        }
```

#### RepositoryStatus

Status information for a GitWrite repository:

```python
@dataclass
class RepositoryStatus:
    """Current status of a GitWrite repository"""
    is_clean: bool
    current_branch: Optional[str]
    modified_files: List[str]
    new_files: List[str]
    deleted_files: List[str]
    commit_count: int
    last_commit: Optional[Dict]

    @property
    def has_changes(self) -> bool:
        """Check if repository has any changes"""
        return len(self.modified_files) > 0 or len(self.new_files) > 0 or len(self.deleted_files) > 0

    @property
    def total_changes(self) -> int:
        """Total number of changed files"""
        return len(self.modified_files) + len(self.new_files) + len(self.deleted_files)

    def get_summary(self) -> str:
        """Get human-readable status summary"""
        if self.is_clean:
            return "No changes to save"

        changes = []
        if self.modified_files:
            changes.append(f"{len(self.modified_files)} modified")
        if self.new_files:
            changes.append(f"{len(self.new_files)} new")
        if self.deleted_files:
            changes.append(f"{len(self.deleted_files)} deleted")

        return f"{', '.join(changes)} files"
```

## Usage Examples

### Basic Repository Operations

```python
from gitwrite_core.repository import GitWriteRepository, ProjectConfig

# Initialize a new project
config = ProjectConfig(
    name="My Great Novel",
    author="Jane Writer",
    description="A thrilling story of adventure and discovery",
    project_type="novel"
)

result = GitWriteRepository.initialize("/path/to/my-novel", config)
if result.success:
    print(f"Created project: {result.message}")
    repo = result.repository
else:
    print(f"Failed: {result.error}")

# Open existing repository
repo = GitWriteRepository("/path/to/existing-project")

# Check repository status
status = repo.get_status()
print(f"Current branch: {status.current_branch}")
print(f"Changes: {status.get_summary()}")

# Update configuration
repo.update_configuration({
    'settings': {
        'auto_save': False,
        'export_formats': ['epub', 'pdf', 'docx']
    }
})
```

### Repository Discovery

```python
def find_gitwrite_repositories(search_path: str) -> List[GitWriteRepository]:
    """Find all GitWrite repositories in a directory tree"""
    repositories = []

    for root, dirs, files in os.walk(search_path):
        if '.git' in dirs and '.gitwrite' in dirs:
            try:
                repo = GitWriteRepository(root)
                if repo.is_gitwrite_repo:
                    repositories.append(repo)
            except RepositoryError:
                continue  # Skip invalid repositories

    return repositories
```

---

*Repository Management provides the foundation for all GitWrite operations, ensuring that projects are properly initialized, configured, and maintained while preserving full Git compatibility and providing a writer-friendly experience.*