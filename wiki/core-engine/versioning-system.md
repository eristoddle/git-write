# Versioning System

GitWrite's versioning system provides comprehensive change tracking and history management for writing projects. Built on Git's robust foundation, it abstracts complex version control operations into writer-friendly concepts while maintaining full Git compatibility.

## Overview

The versioning system is the core of GitWrite's value proposition, transforming Git's developer-centric version control into an intuitive writing tool. It tracks every change, maintains complete history, and provides powerful comparison and recovery capabilities.

```
┌─────────────────────────────────────────────┐
│            Writer Interface                 │
│  ┌─────────────────────────────────────────┐ │
│  │  Save Changes    View History           │ │
│  │  Compare Versions    Restore Previous   │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           Versioning Engine                 │
│  ┌─────────────────────────────────────────┐ │
│  │  Change Tracking    History Management  │ │
│  │  Diff Generation    Recovery System     │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              Git Core                       │
│  ┌─────────────────────────────────────────┐ │
│  │  Commit Objects    Tree Objects         │ │
│  │  Blob Storage      Index Management     │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Core Concepts

### 1. Save Operations (Commits)

GitWrite transforms Git commits into "save" operations that feel natural to writers.

```python
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import pygit2

@dataclass
class SaveResult:
    """Result of a save operation"""
    success: bool
    save_id: str  # Git commit hash
    message: str
    files_saved: List[str]
    word_count_change: int
    timestamp: datetime
    error: Optional[str] = None

class VersioningSystem:
    """Core versioning functionality for GitWrite"""

    def __init__(self, repository_path: str):
        self.repo = pygit2.Repository(repository_path)
        self.signature = self._get_default_signature()

    def save_changes(
        self,
        message: str,
        files: Optional[List[str]] = None,
        auto_stage: bool = True
    ) -> SaveResult:
        """
        Save changes to the project (Git commit)

        Args:
            message: Descriptive message about the changes
            files: Specific files to save (None for all changes)
            auto_stage: Automatically stage files before saving
        """
        try:
            start_time = datetime.utcnow()

            # Stage files if requested
            if auto_stage:
                staged_files = self._stage_files(files)
            else:
                staged_files = self._get_staged_files()

            if not staged_files:
                return SaveResult(
                    success=False,
                    save_id="",
                    message=message,
                    files_saved=[],
                    word_count_change=0,
                    timestamp=start_time,
                    error="No changes to save"
                )

            # Calculate word count change
            word_count_change = self._calculate_word_count_change(staged_files)

            # Create commit
            tree = self.repo.index.write_tree()
            parent_commits = [self.repo.head.target] if not self.repo.head_is_unborn else []

            commit_id = self.repo.create_commit(
                'HEAD',
                self.signature,
                self.signature,
                message,
                tree,
                parent_commits
            )

            return SaveResult(
                success=True,
                save_id=str(commit_id),
                message=message,
                files_saved=staged_files,
                word_count_change=word_count_change,
                timestamp=start_time
            )

        except Exception as e:
            return SaveResult(
                success=False,
                save_id="",
                message=message,
                files_saved=[],
                word_count_change=0,
                timestamp=datetime.utcnow(),
                error=str(e)
            )

    def _stage_files(self, files: Optional[List[str]]) -> List[str]:
        """Stage files for commit"""
        if files is None:
            # Stage all modified files
            status = self.repo.status()
            files_to_stage = [
                path for path, flags in status.items()
                if flags & (pygit2.GIT_STATUS_WT_MODIFIED |
                           pygit2.GIT_STATUS_WT_NEW |
                           pygit2.GIT_STATUS_WT_DELETED)
            ]
        else:
            files_to_stage = files

        for file_path in files_to_stage:
            self.repo.index.add(file_path)

        self.repo.index.write()
        return files_to_stage
```

### 2. History Management

```python
@dataclass
class HistoryEntry:
    """Represents a point in project history"""
    save_id: str
    short_id: str
    message: str
    author: str
    timestamp: datetime
    files_changed: List[str]
    word_count: int
    word_count_change: int
    tags: List[str]

class HistoryManager:
    """Manages project history and timeline"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def get_history(
        self,
        limit: int = 50,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> List[HistoryEntry]:
        """
        Retrieve project history with filtering options
        """
        walker = self.repo.walk(self.repo.head.target)

        # Apply time filters
        if since:
            walker = walker.filter(since=since.timestamp())
        if until:
            walker = walker.filter(until=until.timestamp())

        entries = []
        for commit in walker:
            # Apply author filter
            if author and author.lower() not in commit.author.name.lower():
                continue

            # Apply file filter
            if file_path and not self._commit_affects_file(commit, file_path):
                continue

            entry = self._create_history_entry(commit)
            entries.append(entry)

            if len(entries) >= limit:
                break

        return entries

    def _create_history_entry(self, commit: pygit2.Commit) -> HistoryEntry:
        """Create history entry from Git commit"""
        return HistoryEntry(
            save_id=str(commit.id),
            short_id=str(commit.id)[:8],
            message=commit.message.strip(),
            author=commit.author.name,
            timestamp=datetime.fromtimestamp(commit.commit_time),
            files_changed=self._get_changed_files(commit),
            word_count=self._calculate_word_count_at_commit(commit),
            word_count_change=self._calculate_word_count_change_for_commit(commit),
            tags=self._get_tags_for_commit(commit)
        )

    def _get_changed_files(self, commit: pygit2.Commit) -> List[str]:
        """Get list of files changed in a commit"""
        if not commit.parents:
            # Initial commit - all files are new
            return [item.name for item in commit.tree]

        parent = commit.parents[0]
        diff = self.repo.diff(parent.tree, commit.tree)

        return [delta.new_file.path for delta in diff.deltas]
```

### 3. Change Comparison

```python
from enum import Enum

class DiffFormat(Enum):
    UNIFIED = "unified"
    SIDE_BY_SIDE = "side_by_side"
    WORD_LEVEL = "word_level"
    SEMANTIC = "semantic"

@dataclass
class ComparisonResult:
    """Result of comparing two versions"""
    from_version: str
    to_version: str
    files_changed: List[str]
    additions: int
    deletions: int
    word_additions: int
    word_deletions: int
    diff_content: str
    format: DiffFormat

class ComparisonEngine:
    """Advanced comparison between versions"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def compare_versions(
        self,
        from_version: str,
        to_version: str,
        format: DiffFormat = DiffFormat.UNIFIED,
        files: Optional[List[str]] = None
    ) -> ComparisonResult:
        """
        Compare two versions of the project
        """
        # Resolve version identifiers to commits
        from_commit = self._resolve_version(from_version)
        to_commit = self._resolve_version(to_version)

        # Generate diff
        diff = self.repo.diff(from_commit.tree, to_commit.tree)

        # Filter files if specified
        if files:
            diff = self._filter_diff_by_files(diff, files)

        # Generate comparison result based on format
        if format == DiffFormat.WORD_LEVEL:
            return self._generate_word_level_diff(from_commit, to_commit, diff)
        elif format == DiffFormat.SEMANTIC:
            return self._generate_semantic_diff(from_commit, to_commit, diff)
        else:
            return self._generate_standard_diff(from_commit, to_commit, diff, format)

    def _generate_word_level_diff(
        self,
        from_commit: pygit2.Commit,
        to_commit: pygit2.Commit,
        diff: pygit2.Diff
    ) -> ComparisonResult:
        """Generate word-level comparison for writers"""

        word_additions = 0
        word_deletions = 0
        diff_content_parts = []

        for delta in diff.deltas:
            if delta.new_file.path.endswith(('.md', '.txt', '.rst')):
                # Get file content at both versions
                from_content = self._get_file_content(from_commit, delta.old_file.path)
                to_content = self._get_file_content(to_commit, delta.new_file.path)

                # Perform word-level diff
                word_diff = self._word_level_diff(from_content, to_content)
                diff_content_parts.append(f"--- {delta.old_file.path}")
                diff_content_parts.append(f"+++ {delta.new_file.path}")
                diff_content_parts.append(word_diff.content)

                word_additions += word_diff.additions
                word_deletions += word_diff.deletions

        return ComparisonResult(
            from_version=str(from_commit.id)[:8],
            to_version=str(to_commit.id)[:8],
            files_changed=[delta.new_file.path for delta in diff.deltas],
            additions=diff.stats.insertions,
            deletions=diff.stats.deletions,
            word_additions=word_additions,
            word_deletions=word_deletions,
            diff_content="\n".join(diff_content_parts),
            format=DiffFormat.WORD_LEVEL
        )

    def _word_level_diff(self, from_text: str, to_text: str):
        """Perform word-level diff for better writer feedback"""
        import difflib

        from_words = from_text.split()
        to_words = to_text.split()

        diff = difflib.unified_diff(
            from_words,
            to_words,
            lineterm=""
        )

        additions = 0
        deletions = 0
        content_lines = []

        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                additions += len(line[1:].split())
                content_lines.append(f"Added: {line[1:]}")
            elif line.startswith('-') and not line.startswith('---'):
                deletions += len(line[1:].split())
                content_lines.append(f"Removed: {line[1:]}")
            elif not line.startswith(('+++', '---', '@@')):
                content_lines.append(line)

        return type('WordDiff', (), {
            'additions': additions,
            'deletions': deletions,
            'content': '\n'.join(content_lines)
        })()
```

### 4. Recovery System

```python
class RecoverySystem:
    """System for recovering previous versions and undoing changes"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def undo_last_save(self, create_backup: bool = True) -> SaveResult:
        """
        Undo the last save operation
        """
        if self.repo.head_is_unborn:
            return SaveResult(
                success=False,
                save_id="",
                message="",
                files_saved=[],
                word_count_change=0,
                timestamp=datetime.utcnow(),
                error="No saves to undo"
            )

        current_commit = self.repo[self.repo.head.target]

        if not current_commit.parents:
            return SaveResult(
                success=False,
                save_id="",
                message="",
                files_saved=[],
                word_count_change=0,
                timestamp=datetime.utcnow(),
                error="Cannot undo initial save"
            )

        parent_commit = current_commit.parents[0]

        if create_backup:
            # Create backup branch
            backup_name = f"backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            self.repo.branches.local.create(backup_name, current_commit)

        # Reset to parent commit
        self.repo.reset(parent_commit.id, pygit2.GIT_RESET_HARD)

        return SaveResult(
            success=True,
            save_id=str(parent_commit.id),
            message=f"Undid: {current_commit.message}",
            files_saved=self._get_changed_files_between_commits(parent_commit, current_commit),
            word_count_change=self._calculate_word_count_change_for_undo(current_commit, parent_commit),
            timestamp=datetime.utcnow()
        )

    def restore_version(
        self,
        version_id: str,
        files: Optional[List[str]] = None,
        create_exploration: bool = True
    ) -> SaveResult:
        """
        Restore specific files or entire project to a previous version
        """
        target_commit = self._resolve_version(version_id)

        if create_exploration:
            # Create exploration for the restoration
            exploration_name = f"restore-{version_id[:8]}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            current_commit = self.repo[self.repo.head.target]
            self.repo.branches.local.create(exploration_name, current_commit)

        if files:
            # Restore specific files
            restored_files = self._restore_specific_files(target_commit, files)
        else:
            # Restore entire project
            self.repo.reset(target_commit.id, pygit2.GIT_RESET_HARD)
            restored_files = [item.name for item in target_commit.tree]

        return SaveResult(
            success=True,
            save_id=str(target_commit.id),
            message=f"Restored from version {version_id[:8]}",
            files_saved=restored_files,
            word_count_change=0,  # Calculate if needed
            timestamp=datetime.utcnow()
        )

    def _restore_specific_files(
        self,
        target_commit: pygit2.Commit,
        files: List[str]
    ) -> List[str]:
        """Restore specific files from a commit"""
        restored_files = []

        for file_path in files:
            try:
                # Get file content from target commit
                tree_entry = target_commit.tree[file_path]
                blob = self.repo[tree_entry.id]

                # Write to working directory
                full_path = self.repo.workdir + file_path
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                with open(full_path, 'wb') as f:
                    f.write(blob.data)

                # Stage the restored file
                self.repo.index.add(file_path)
                restored_files.append(file_path)

            except KeyError:
                # File doesn't exist in target commit
                continue

        self.repo.index.write()
        return restored_files
```

### 5. Statistics and Analytics

```python
@dataclass
class ProjectStatistics:
    """Statistics about the project's evolution"""
    total_saves: int
    total_words: int
    words_added: int
    words_removed: int
    files_count: int
    active_days: int
    avg_words_per_save: float
    writing_velocity: float  # words per day
    most_active_file: str

class StatisticsEngine:
    """Generate statistics about project evolution"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def generate_project_stats(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> ProjectStatistics:
        """Generate comprehensive project statistics"""

        walker = self.repo.walk(self.repo.head.target)

        if since:
            walker = walker.filter(since=since.timestamp())
        if until:
            walker = walker.filter(until=until.timestamp())

        commits = list(walker)

        total_saves = len(commits)
        total_words = self._calculate_current_word_count()
        words_added, words_removed = self._calculate_total_word_changes(commits)
        files_count = self._count_current_files()
        active_days = self._calculate_active_days(commits)
        avg_words_per_save = words_added / total_saves if total_saves > 0 else 0
        writing_velocity = words_added / max(active_days, 1)
        most_active_file = self._find_most_active_file(commits)

        return ProjectStatistics(
            total_saves=total_saves,
            total_words=total_words,
            words_added=words_added,
            words_removed=words_removed,
            files_count=files_count,
            active_days=active_days,
            avg_words_per_save=avg_words_per_save,
            writing_velocity=writing_velocity,
            most_active_file=most_active_file
        )

    def generate_writing_timeline(
        self,
        granularity: str = "daily"  # daily, weekly, monthly
    ) -> List[dict]:
        """Generate timeline of writing activity"""

        walker = self.repo.walk(self.repo.head.target)
        commits = list(walker)

        timeline = {}

        for commit in commits:
            timestamp = datetime.fromtimestamp(commit.commit_time)

            if granularity == "daily":
                key = timestamp.date()
            elif granularity == "weekly":
                key = f"{timestamp.year}-W{timestamp.isocalendar()[1]}"
            elif granularity == "monthly":
                key = f"{timestamp.year}-{timestamp.month:02d}"

            if key not in timeline:
                timeline[key] = {
                    'period': str(key),
                    'saves': 0,
                    'words_added': 0,
                    'words_removed': 0,
                    'files_modified': set()
                }

            timeline[key]['saves'] += 1

            # Calculate word changes for this commit
            word_change = self._calculate_word_count_change_for_commit(commit)
            if word_change > 0:
                timeline[key]['words_added'] += word_change
            else:
                timeline[key]['words_removed'] += abs(word_change)

            # Track modified files
            changed_files = self._get_changed_files(commit)
            timeline[key]['files_modified'].update(changed_files)

        # Convert sets to counts
        for period_data in timeline.values():
            period_data['files_modified'] = len(period_data['files_modified'])

        return list(timeline.values())
```

## Performance Optimization

### Efficient Version Operations

```python
class VersioningOptimizer:
    """Optimizations for versioning operations"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository
        self._word_count_cache = {}
        self._diff_cache = {}

    @lru_cache(maxsize=100)
    def cached_word_count(self, commit_id: str) -> int:
        """Cache word counts for commits"""
        commit = self.repo[commit_id]
        return self._calculate_word_count_at_commit(commit)

    def batch_history_processing(
        self,
        commits: List[pygit2.Commit],
        include_stats: bool = True
    ) -> List[HistoryEntry]:
        """Process multiple commits efficiently"""

        if not include_stats:
            # Fast path without statistics
            return [
                HistoryEntry(
                    save_id=str(commit.id),
                    short_id=str(commit.id)[:8],
                    message=commit.message.strip(),
                    author=commit.author.name,
                    timestamp=datetime.fromtimestamp(commit.commit_time),
                    files_changed=[],
                    word_count=0,
                    word_count_change=0,
                    tags=[]
                )
                for commit in commits
            ]

        # Full processing with optimizations
        return [self._create_history_entry_optimized(commit) for commit in commits]

    def incremental_word_count_update(self, new_commit: pygit2.Commit) -> int:
        """Update word count incrementally"""
        if not new_commit.parents:
            # Initial commit
            word_count = self._calculate_word_count_at_commit(new_commit)
        else:
            parent_commit = new_commit.parents[0]
            parent_word_count = self.cached_word_count(str(parent_commit.id))
            word_change = self._calculate_word_count_change_for_commit(new_commit)
            word_count = parent_word_count + word_change

        # Cache the result
        self._word_count_cache[str(new_commit.id)] = word_count
        return word_count
```

## Integration with Other Systems

### Event System

```python
from enum import Enum
from typing import Callable, List

class VersionEvent(Enum):
    SAVE_COMPLETED = "save_completed"
    VERSION_RESTORED = "version_restored"
    HISTORY_REQUESTED = "history_requested"
    COMPARISON_GENERATED = "comparison_generated"

class VersioningEvents:
    """Event system for versioning operations"""

    def __init__(self):
        self.listeners: dict[VersionEvent, List[Callable]] = {
            event: [] for event in VersionEvent
        }

    def on(self, event: VersionEvent, callback: Callable):
        """Register event listener"""
        self.listeners[event].append(callback)

    def emit(self, event: VersionEvent, data: dict):
        """Emit event to all listeners"""
        for callback in self.listeners[event]:
            try:
                callback(data)
            except Exception as e:
                # Log error but don't break other listeners
                logger.error(f"Event listener error: {e}")

    def save_completed_handler(self, save_result: SaveResult):
        """Handle save completion"""
        self.emit(VersionEvent.SAVE_COMPLETED, {
            'save_id': save_result.save_id,
            'message': save_result.message,
            'files_saved': save_result.files_saved,
            'word_count_change': save_result.word_count_change
        })

# Usage
versioning_events = VersioningEvents()

# Register analytics listener
versioning_events.on(
    VersionEvent.SAVE_COMPLETED,
    lambda data: analytics.track_save(data['save_id'], data['word_count_change'])
)

# Register notification listener
versioning_events.on(
    VersionEvent.SAVE_COMPLETED,
    lambda data: notification_service.notify_collaborators(data)
)
```

---

*GitWrite's versioning system provides writers with powerful version control capabilities while hiding Git's complexity. The system emphasizes clarity, safety, and ease of use, making version control accessible to non-technical users without sacrificing functionality.*