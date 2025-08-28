# Core Engine (Python Library)

The GitWrite Core Engine (`gitwrite_core`) is the heart of the GitWrite platform, containing all business logic and Git operation abstractions. This pure Python library encapsulates the domain knowledge of version control for writers, providing a clean interface that hides Git's complexity while preserving its power.

## Module Overview

The core engine is organized into focused modules, each handling a specific aspect of the writing workflow:

```
gitwrite_core/
├── repository.py      # Project initialization and management
├── versioning.py      # Change tracking and history
├── branching.py       # Exploration (branch) operations
├── annotations.py     # Feedback and comment system
├── export.py          # Document generation and formatting
├── tagging.py         # Version milestone management
└── exceptions.py      # Domain-specific error handling
```

## Design Principles

### 1. Domain-Driven Design
Each module represents a core concept in the writing domain:
- **Repository**: The writing project container
- **Versioning**: Tracking changes over time
- **Branching**: Exploring alternative approaches
- **Annotations**: Collecting and managing feedback
- **Export**: Publishing and sharing work
- **Tagging**: Marking important milestones

### 2. Pure Business Logic
The core engine contains no infrastructure concerns:
- No HTTP handling (that's the API layer's job)
- No user interface logic (that's the frontend's job)
- No command-line parsing (that's the CLI's job)
- Only domain operations and Git abstractions

### 3. Git Abstraction Layer
The core engine serves as an abstraction layer over Git operations:
- Wraps pygit2 operations in writer-friendly methods
- Translates Git concepts to writing terminology
- Handles Git errors and provides meaningful feedback
- Maintains full Git compatibility

## Core Concepts

### Writer-Centric Abstractions

The core engine transforms Git concepts into writer-friendly operations:

```python
# Git operations (what happens internally)
repo = pygit2.Repository(path)
index = repo.index
index.add_all()
index.write()
tree = index.write_tree()
commit_id = repo.create_commit('HEAD', signature, signature, message, tree, parents)

# Writer operations (what users see)
def save_changes(message: str, files: List[str] = None) -> SaveResult:
    """Save your work with a descriptive message"""
    return _perform_save_operation(message, files)
```

### Result Objects

All operations return structured result objects instead of throwing exceptions:

```python
@dataclass
class SaveResult:
    """Result of a save operation"""
    success: bool
    commit_id: Optional[str] = None
    message: str = ""
    files_saved: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class ExplorationResult:
    """Result of exploration (branch) operations"""
    success: bool
    exploration_name: Optional[str] = None
    current_exploration: Optional[str] = None
    available_explorations: List[str] = field(default_factory=list)
    error: Optional[str] = None
```

### Consistent Interface Pattern

All modules follow a consistent interface pattern:

```python
class ModuleInterface:
    """Consistent interface across all core modules"""

    def create(...) -> OperationResult:
        """Create new entities"""
        pass

    def get(...) -> DataResult:
        """Retrieve information"""
        pass

    def update(...) -> OperationResult:
        """Modify existing entities"""
        pass

    def delete(...) -> OperationResult:
        """Remove entities"""
        pass

    def list(...) -> ListResult:
        """List multiple entities"""
        pass
```

## Integration Patterns

### 1. Dependency Injection
Core modules are designed for easy testing and flexibility:

```python
class RepositoryManager:
    def __init__(self, git_backend: GitBackend = None):
        self.git_backend = git_backend or Pygit2Backend()

    def create_repository(self, path: str, config: RepoConfig) -> RepositoryResult:
        """Create repository using injected Git backend"""
        return self.git_backend.init_repository(path, config)

# Easy testing with mock backend
class MockGitBackend(GitBackend):
    def init_repository(self, path: str, config: RepoConfig) -> RepositoryResult:
        return RepositoryResult(success=True, path=path)

# Production usage
repo_manager = RepositoryManager()  # Uses real Git

# Test usage
test_repo_manager = RepositoryManager(MockGitBackend())
```

### 2. Event System
Core operations emit events for integration with other components:

```python
from typing import Callable, List

class EventEmitter:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, callback: Callable):
        """Register event listener"""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def emit(self, event: str, data: Dict):
        """Emit event to all listeners"""
        for callback in self._listeners.get(event, []):
            callback(data)

class VersioningSystem(EventEmitter):
    def save_changes(self, message: str) -> SaveResult:
        """Save changes and emit events"""
        result = self._perform_save(message)

        if result.success:
            self.emit('changes_saved', {
                'commit_id': result.commit_id,
                'message': message,
                'timestamp': datetime.utcnow()
            })

        return result
```

### 3. Plugin Architecture
Core modules support extensibility through plugins:

```python
class ExportPlugin:
    """Base class for export plugins"""

    def get_format_name(self) -> str:
        """Return format name (e.g., 'epub', 'pdf')"""
        raise NotImplementedError

    def export(self, content: str, metadata: Dict) -> bytes:
        """Generate document in this format"""
        raise NotImplementedError

class ExportSystem:
    def __init__(self):
        self._plugins: Dict[str, ExportPlugin] = {}

    def register_plugin(self, plugin: ExportPlugin):
        """Register export format plugin"""
        self._plugins[plugin.get_format_name()] = plugin

    def export_document(self, format_name: str, content: str, metadata: Dict) -> bytes:
        """Export using registered plugin"""
        plugin = self._plugins.get(format_name)
        if not plugin:
            raise ValueError(f"Unknown export format: {format_name}")
        return plugin.export(content, metadata)

# Built-in plugins
export_system = ExportSystem()
export_system.register_plugin(EPUBExportPlugin())
export_system.register_plugin(PDFExportPlugin())
export_system.register_plugin(DOCXExportPlugin())
```

## Error Handling Strategy

### Domain-Specific Exceptions

The core engine defines meaningful exceptions for different error conditions:

```python
class GitWriteError(Exception):
    """Base exception for all GitWrite operations"""
    def __init__(self, message: str, suggestions: List[str] = None):
        super().__init__(message)
        self.suggestions = suggestions or []

class RepositoryError(GitWriteError):
    """Repository-related errors"""
    pass

class VersioningError(GitWriteError):
    """Versioning operation errors"""
    pass

class MergeConflictError(VersioningError):
    """Merge conflict requiring user resolution"""
    def __init__(self, conflicted_files: List[str]):
        super().__init__(
            "Changes conflict with existing work",
            suggestions=[
                "Review the conflicted sections",
                "Choose which version to keep",
                "Or combine both versions creatively"
            ]
        )
        self.conflicted_files = conflicted_files

class PermissionError(GitWriteError):
    """Insufficient permissions for operation"""
    pass
```

### Graceful Error Recovery

Operations attempt to recover gracefully from errors:

```python
def save_changes(message: str, files: List[str] = None) -> SaveResult:
    """Save changes with automatic error recovery"""
    try:
        # Attempt normal save operation
        return _perform_save(message, files)

    except MergeConflictError as e:
        # Provide conflict resolution guidance
        return SaveResult(
            success=False,
            error="Your changes conflict with someone else's work",
            suggestions=e.suggestions,
            conflicted_files=e.conflicted_files
        )

    except pygit2.GitError as e:
        # Translate Git errors to user-friendly messages
        return SaveResult(
            success=False,
            error=translate_git_error(e),
            suggestions=get_recovery_suggestions(e)
        )

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in save_changes: {e}", exc_info=True)
        return SaveResult(
            success=False,
            error="An unexpected error occurred while saving",
            suggestions=["Please try again or contact support"]
        )
```

## Performance Considerations

### 1. Lazy Loading
Git operations are expensive, so the core engine uses lazy loading:

```python
class Repository:
    def __init__(self, path: str):
        self.path = path
        self._pygit2_repo = None  # Lazy-loaded
        self._commit_cache = {}   # Cache expensive operations

    @property
    def git_repo(self) -> pygit2.Repository:
        """Lazy-load pygit2 repository"""
        if self._pygit2_repo is None:
            self._pygit2_repo = pygit2.Repository(self.path)
        return self._pygit2_repo

    def get_commit(self, commit_id: str) -> Commit:
        """Get commit with caching"""
        if commit_id not in self._commit_cache:
            git_commit = self.git_repo[commit_id]
            self._commit_cache[commit_id] = Commit.from_pygit2(git_commit)
        return self._commit_cache[commit_id]
```

### 2. Batch Operations
Multiple operations are batched when possible:

```python
def save_multiple_files(changes: List[FileChange]) -> SaveResult:
    """Save multiple file changes in a single commit"""
    try:
        repo = get_current_repository()
        index = repo.git_repo.index

        # Batch all file operations
        for change in changes:
            if change.operation == 'add':
                index.add(change.file_path)
            elif change.operation == 'remove':
                index.remove(change.file_path)

        # Single commit for all changes
        index.write()
        tree = index.write_tree()

        commit_id = repo.git_repo.create_commit(
            'HEAD',
            get_signature(),
            get_signature(),
            f"Updated {len(changes)} files",
            tree,
            [repo.git_repo.head.target]
        )

        return SaveResult(
            success=True,
            commit_id=str(commit_id),
            files_saved=[change.file_path for change in changes]
        )

    except Exception as e:
        return SaveResult(success=False, error=str(e))
```

### 3. Memory Management
Large repositories are handled efficiently:

```python
def get_large_file_content(file_path: str, max_size: int = 10_000_000) -> str:
    """Get file content with size limits"""
    try:
        repo = get_current_repository()
        blob = repo.git_repo.head.tree[file_path]

        if blob.size > max_size:
            raise ValueError(f"File too large ({blob.size} bytes, max {max_size})")

        return blob.data.decode('utf-8')

    except UnicodeDecodeError:
        raise ValueError("File contains binary data and cannot be displayed as text")
```

## Testing Strategy

### Unit Testing
Each module is thoroughly unit tested:

```python
class TestVersioningSystem:
    def test_save_changes_success(self):
        """Test successful save operation"""
        versioning = VersioningSystem(MockGitBackend())
        result = versioning.save_changes("Added character development")

        assert result.success is True
        assert "character development" in result.message
        assert result.commit_id is not None

    def test_save_changes_with_conflict(self):
        """Test save operation with merge conflict"""
        versioning = VersioningSystem(ConflictGitBackend())
        result = versioning.save_changes("Conflicting changes")

        assert result.success is False
        assert "conflict" in result.error.lower()
        assert len(result.suggestions) > 0

class TestRepositoryManager:
    def test_create_repository_success(self):
        """Test repository creation"""
        manager = RepositoryManager(MockGitBackend())
        result = manager.create_repository("/tmp/test", RepoConfig())

        assert result.success is True
        assert result.path == "/tmp/test"
```

### Integration Testing
Integration tests verify module interactions:

```python
class TestCoreIntegration:
    def test_full_workflow(self):
        """Test complete writing workflow"""
        # Create repository
        repo_result = repository.create_repository("test-novel")
        assert repo_result.success

        # Save initial content
        save_result = versioning.save_changes("Initial chapter")
        assert save_result.success

        # Create exploration
        exp_result = branching.create_exploration("alternative-ending")
        assert exp_result.success

        # Add annotations
        ann_result = annotations.add_annotation("Consider different tone", line=42)
        assert ann_result.success

        # Export document
        export_result = export.export_document("epub", {"title": "Test Novel"})
        assert export_result.success
```

---

*The Core Engine provides a solid foundation for GitWrite's functionality, abstracting Git complexity while maintaining full compatibility and providing a writer-friendly interface that scales from simple operations to complex collaborative workflows.*