# Branching System (Explorations)

GitWrite's branching system transforms Git's powerful branching capabilities into "explorations" - a writer-friendly concept that encourages experimentation with different narrative directions, character developments, or structural approaches without risk to the main work.

## Overview

The exploration system allows writers to safely try different approaches to their work. Unlike traditional Git branches that can intimidate non-technical users, explorations use familiar writing terminology and workflows while providing the full power of Git branching underneath.

```
                    Main Story
                        │
                        ├─ Save: "Chapter 1 complete"
                        │
                        ├─ Save: "Added character intro"
                        │
    Alternative Ending  │                    Dialogue Experiment
           ┌────────────┼────────────┐                 │
           │            │            │                 │
           ▼            ▼            ▼                 ▼
    "Try darker tone"   Main    "Experiment with    "Focus on
     exploration      Story    first person"      dialogue tags"
                                exploration       exploration
```

## Core Components

### 1. Exploration Management

```python
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import pygit2

@dataclass
class ExplorationInfo:
    """Information about an exploration (Git branch)"""
    name: str
    description: str
    created_at: datetime
    last_modified: datetime
    creator: str
    base_save_id: str  # Commit ID where exploration started
    current_save_id: str  # Latest commit in exploration
    saves_ahead: int  # Commits ahead of base
    saves_behind: int  # Commits behind main
    word_count_difference: int
    status: str  # active, merged, abandoned

class ExplorationManager:
    """Manages exploration creation, switching, and merging"""

    def __init__(self, repository_path: str):
        self.repo = pygit2.Repository(repository_path)
        self.main_branch = "main"  # or "master"

    def create_exploration(
        self,
        name: str,
        description: str = "",
        from_save: Optional[str] = None,
        auto_switch: bool = True
    ) -> ExplorationInfo:
        """
        Create a new exploration (Git branch)

        Args:
            name: Name for the exploration
            description: Purpose or goal of the exploration
            from_save: Specific save to start from (default: current)
            auto_switch: Switch to the new exploration immediately
        """
        # Validate exploration name
        if not self._is_valid_exploration_name(name):
            raise ValueError(f"Invalid exploration name: {name}")

        # Check if exploration already exists
        if name in [branch.shorthand for branch in self.repo.branches.local]:
            raise ValueError(f"Exploration '{name}' already exists")

        # Determine starting point
        if from_save:
            base_commit = self.repo[from_save]
        else:
            base_commit = self.repo[self.repo.head.target]

        # Create branch
        new_branch = self.repo.branches.local.create(name, base_commit)

        # Store exploration metadata
        exploration_info = ExplorationInfo(
            name=name,
            description=description,
            created_at=datetime.utcnow(),
            last_modified=datetime.utcnow(),
            creator=self._get_current_user(),
            base_save_id=str(base_commit.id),
            current_save_id=str(base_commit.id),
            saves_ahead=0,
            saves_behind=0,
            word_count_difference=0,
            status="active"
        )

        self._store_exploration_metadata(exploration_info)

        # Switch to exploration if requested
        if auto_switch:
            self.switch_to_exploration(name)

        return exploration_info

    def switch_to_exploration(self, name: str) -> bool:
        """
        Switch to an existing exploration
        """
        try:
            # Check for uncommitted changes
            if self._has_uncommitted_changes():
                raise ValueError(
                    "You have unsaved changes. Please save or stash them before switching explorations."
                )

            # Switch branch
            branch = self.repo.branches.local[name]
            self.repo.checkout(branch)

            # Update HEAD reference
            self.repo.head.set_target(branch.target)

            return True

        except KeyError:
            raise ValueError(f"Exploration '{name}' does not exist")

    def list_explorations(self, include_merged: bool = False) -> List[ExplorationInfo]:
        """
        List all explorations with their current status
        """
        explorations = []

        for branch in self.repo.branches.local:
            if branch.shorthand == self.main_branch:
                continue

            exploration_info = self._get_exploration_info(branch)

            # Filter merged explorations if requested
            if not include_merged and exploration_info.status == "merged":
                continue

            explorations.append(exploration_info)

        # Sort by last modified date
        return sorted(explorations, key=lambda x: x.last_modified, reverse=True)

    def _get_exploration_info(self, branch: pygit2.Branch) -> ExplorationInfo:
        """Get detailed information about an exploration"""

        # Load stored metadata
        metadata = self._load_exploration_metadata(branch.shorthand)

        # Calculate current statistics
        main_branch = self.repo.branches.local[self.main_branch]

        # Count commits ahead and behind
        ahead, behind = self._calculate_ahead_behind(branch, main_branch)

        # Calculate word count difference
        word_count_diff = self._calculate_word_count_difference(branch, main_branch)

        # Get latest commit info
        latest_commit = self.repo[branch.target]

        return ExplorationInfo(
            name=branch.shorthand,
            description=metadata.get("description", ""),
            created_at=metadata.get("created_at", datetime.utcnow()),
            last_modified=datetime.fromtimestamp(latest_commit.commit_time),
            creator=metadata.get("creator", latest_commit.author.name),
            base_save_id=metadata.get("base_save_id", ""),
            current_save_id=str(latest_commit.id),
            saves_ahead=ahead,
            saves_behind=behind,
            word_count_difference=word_count_diff,
            status=metadata.get("status", "active")
        )
```

### 2. Exploration Comparison

```python
from enum import Enum

class ComparisonScope(Enum):
    FULL_PROJECT = "full_project"
    SPECIFIC_FILES = "specific_files"
    SINCE_BRANCH_POINT = "since_branch_point"

@dataclass
class ExplorationComparison:
    """Comparison between explorations or between exploration and main"""
    from_exploration: str
    to_exploration: str
    scope: ComparisonScope
    files_changed: List[str]
    additions: int
    deletions: int
    word_additions: int
    word_deletions: int
    unique_to_from: List[str]  # Files only in from_exploration
    unique_to_to: List[str]    # Files only in to_exploration
    conflicts: List[str]       # Files that would conflict in merge
    diff_content: str

class ExplorationComparator:
    """Compare different explorations and analyze differences"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def compare_explorations(
        self,
        from_exploration: str,
        to_exploration: str = "main",
        scope: ComparisonScope = ComparisonScope.FULL_PROJECT,
        files: Optional[List[str]] = None
    ) -> ExplorationComparison:
        """
        Compare two explorations or exploration with main
        """

        # Get branch references
        from_branch = self.repo.branches.local[from_exploration]
        to_branch = self.repo.branches.local[to_exploration]

        # Get commit objects
        from_commit = self.repo[from_branch.target]
        to_commit = self.repo[to_branch.target]

        # Determine comparison scope
        if scope == ComparisonScope.SINCE_BRANCH_POINT:
            # Find merge base (branch point)
            merge_base = self.repo.merge_base(from_commit.id, to_commit.id)
            from_commit = self.repo[merge_base]

        # Generate diff
        diff = self.repo.diff(from_commit.tree, to_commit.tree)

        # Filter by files if specified
        if files and scope == ComparisonScope.SPECIFIC_FILES:
            diff = self._filter_diff_by_files(diff, files)

        # Analyze differences
        files_changed = [delta.new_file.path for delta in diff.deltas]

        # Calculate word-level statistics
        word_stats = self._calculate_word_level_changes(diff)

        # Find unique files
        unique_to_from, unique_to_to = self._find_unique_files(from_commit, to_commit)

        # Check for potential conflicts
        conflicts = self._detect_potential_conflicts(from_exploration, to_exploration)

        return ExplorationComparison(
            from_exploration=from_exploration,
            to_exploration=to_exploration,
            scope=scope,
            files_changed=files_changed,
            additions=diff.stats.insertions,
            deletions=diff.stats.deletions,
            word_additions=word_stats["additions"],
            word_deletions=word_stats["deletions"],
            unique_to_from=unique_to_from,
            unique_to_to=unique_to_to,
            conflicts=conflicts,
            diff_content=self._generate_readable_diff(diff)
        )

    def _generate_readable_diff(self, diff: pygit2.Diff) -> str:
        """Generate human-readable diff for writers"""

        diff_lines = []

        for delta in diff.deltas:
            file_path = delta.new_file.path

            # Skip binary files
            if self._is_binary_file(file_path):
                diff_lines.append(f"Binary file {file_path} changed")
                continue

            diff_lines.append(f"\n--- Changes in {file_path} ---")

            # Get patch for this file
            patch = diff[delta]

            for hunk in patch.hunks:
                diff_lines.append(f"@@ Line {hunk.old_start} @@")

                for line in hunk.lines:
                    if line.origin == '+':
                        diff_lines.append(f"+ {line.content.rstrip()}")
                    elif line.origin == '-':
                        diff_lines.append(f"- {line.content.rstrip()}")
                    else:
                        diff_lines.append(f"  {line.content.rstrip()}")

        return "\n".join(diff_lines)
```

### 3. Exploration Merging

```python
from enum import Enum

class MergeStrategy(Enum):
    AUTO = "auto"           # Automatic merge where possible
    MANUAL = "manual"       # Require manual conflict resolution
    OURS = "ours"          # Prefer main branch in conflicts
    THEIRS = "theirs"      # Prefer exploration in conflicts
    CHERRY_PICK = "cherry_pick"  # Select specific commits

@dataclass
class MergeResult:
    """Result of merging an exploration"""
    success: bool
    strategy_used: MergeStrategy
    merged_save_id: str  # Commit ID of merge
    conflicts: List[str]
    files_merged: List[str]
    word_count_change: int
    message: str
    error: Optional[str] = None

class ExplorationMerger:
    """Handle merging explorations back to main or other explorations"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def merge_exploration(
        self,
        exploration_name: str,
        target_exploration: str = "main",
        strategy: MergeStrategy = MergeStrategy.AUTO,
        message: Optional[str] = None,
        delete_after_merge: bool = True
    ) -> MergeResult:
        """
        Merge an exploration into target (usually main)
        """

        # Validate inputs
        if exploration_name not in [b.shorthand for b in self.repo.branches.local]:
            raise ValueError(f"Exploration '{exploration_name}' does not exist")

        # Get branch references
        source_branch = self.repo.branches.local[exploration_name]
        target_branch = self.repo.branches.local[target_exploration]

        # Switch to target branch
        self.repo.checkout(target_branch)

        # Attempt merge based on strategy
        try:
            if strategy == MergeStrategy.AUTO:
                return self._auto_merge(source_branch, target_branch, message, delete_after_merge)
            elif strategy == MergeStrategy.CHERRY_PICK:
                return self._cherry_pick_merge(source_branch, target_branch, message)
            else:
                return self._strategy_merge(source_branch, target_branch, strategy, message, delete_after_merge)

        except Exception as e:
            return MergeResult(
                success=False,
                strategy_used=strategy,
                merged_save_id="",
                conflicts=[],
                files_merged=[],
                word_count_change=0,
                message="",
                error=str(e)
            )

    def _auto_merge(
        self,
        source_branch: pygit2.Branch,
        target_branch: pygit2.Branch,
        message: Optional[str],
        delete_after_merge: bool
    ) -> MergeResult:
        """Attempt automatic merge with conflict detection"""

        source_commit = self.repo[source_branch.target]
        target_commit = self.repo[target_branch.target]

        # Check if fast-forward is possible
        if self._can_fast_forward(source_branch, target_branch):
            return self._fast_forward_merge(source_branch, target_branch, delete_after_merge)

        # Attempt three-way merge
        merge_base = self.repo.merge_base(source_commit.id, target_commit.id)

        # Analyze for conflicts before attempting merge
        conflicts = self._analyze_merge_conflicts(source_commit, target_commit, merge_base)

        if conflicts:
            return MergeResult(
                success=False,
                strategy_used=MergeStrategy.AUTO,
                merged_save_id="",
                conflicts=conflicts,
                files_merged=[],
                word_count_change=0,
                message="Automatic merge failed due to conflicts",
                error="Manual conflict resolution required"
            )

        # Perform merge
        merge_commit_id = self._create_merge_commit(
            source_commit,
            target_commit,
            message or f"Merge exploration '{source_branch.shorthand}'"
        )

        # Get merged files
        merged_files = self._get_files_changed_in_merge(source_commit, target_commit)

        # Calculate word count change
        word_count_change = self._calculate_merge_word_count_change(source_commit, target_commit)

        # Clean up if requested
        if delete_after_merge:
            self._mark_exploration_as_merged(source_branch.shorthand)

        return MergeResult(
            success=True,
            strategy_used=MergeStrategy.AUTO,
            merged_save_id=str(merge_commit_id),
            conflicts=[],
            files_merged=merged_files,
            word_count_change=word_count_change,
            message=message or f"Successfully merged exploration '{source_branch.shorthand}'"
        )

    def _cherry_pick_merge(
        self,
        source_branch: pygit2.Branch,
        target_branch: pygit2.Branch,
        message: Optional[str]
    ) -> MergeResult:
        """Cherry-pick specific commits from exploration"""

        # Get commits unique to source branch
        source_commits = self._get_unique_commits(source_branch, target_branch)

        if not source_commits:
            return MergeResult(
                success=False,
                strategy_used=MergeStrategy.CHERRY_PICK,
                merged_save_id="",
                conflicts=[],
                files_merged=[],
                word_count_change=0,
                message="No unique commits to cherry-pick"
            )

        # Present commits for selection (this would be interactive in real implementation)
        selected_commits = self._select_commits_for_cherry_pick(source_commits)

        merged_files = []
        total_word_count_change = 0

        for commit in selected_commits:
            try:
                # Cherry-pick the commit
                cherry_pick_result = self.repo.cherrypick(commit.id)

                if cherry_pick_result is not None:
                    # Conflicts occurred
                    return MergeResult(
                        success=False,
                        strategy_used=MergeStrategy.CHERRY_PICK,
                        merged_save_id="",
                        conflicts=self._get_conflicted_files(),
                        files_merged=[],
                        word_count_change=0,
                        message="Cherry-pick conflicts require resolution"
                    )

                # Commit the cherry-pick
                tree = self.repo.index.write_tree()
                cherry_pick_commit = self.repo.create_commit(
                    'HEAD',
                    commit.author,
                    commit.committer,
                    f"Cherry-pick: {commit.message}",
                    tree,
                    [self.repo.head.target]
                )

                # Track changes
                commit_files = self._get_changed_files_in_commit(commit)
                merged_files.extend(commit_files)

                total_word_count_change += self._calculate_word_count_change_for_commit(commit)

            except Exception as e:
                return MergeResult(
                    success=False,
                    strategy_used=MergeStrategy.CHERRY_PICK,
                    merged_save_id="",
                    conflicts=[],
                    files_merged=[],
                    word_count_change=0,
                    message=f"Cherry-pick failed: {str(e)}"
                )

        return MergeResult(
            success=True,
            strategy_used=MergeStrategy.CHERRY_PICK,
            merged_save_id=str(cherry_pick_commit),
            conflicts=[],
            files_merged=list(set(merged_files)),
            word_count_change=total_word_count_change,
            message=f"Successfully cherry-picked {len(selected_commits)} changes"
        )
```

### 4. Conflict Resolution

```python
@dataclass
class ConflictInfo:
    """Information about a merge conflict"""
    file_path: str
    conflict_type: str  # content, rename, delete, etc.
    main_content: str
    exploration_content: str
    base_content: str
    line_numbers: Dict[str, List[int]]

class ConflictResolver:
    """Help writers resolve merge conflicts"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def get_conflicts(self) -> List[ConflictInfo]:
        """Get detailed information about current conflicts"""

        if not self.repo.index.conflicts:
            return []

        conflicts = []

        for conflict in self.repo.index.conflicts:
            ancestor_entry, our_entry, their_entry = conflict

            if ancestor_entry and our_entry and their_entry:
                # Content conflict
                conflict_info = ConflictInfo(
                    file_path=our_entry.path,
                    conflict_type="content",
                    main_content=self._get_blob_content(our_entry.id),
                    exploration_content=self._get_blob_content(their_entry.id),
                    base_content=self._get_blob_content(ancestor_entry.id),
                    line_numbers=self._find_conflict_line_numbers(our_entry.path)
                )
                conflicts.append(conflict_info)

            elif our_entry and their_entry and not ancestor_entry:
                # Both added (rare in writing context)
                conflict_info = ConflictInfo(
                    file_path=our_entry.path,
                    conflict_type="both_added",
                    main_content=self._get_blob_content(our_entry.id),
                    exploration_content=self._get_blob_content(their_entry.id),
                    base_content="",
                    line_numbers={}
                )
                conflicts.append(conflict_info)

        return conflicts

    def resolve_conflict_automatically(
        self,
        file_path: str,
        resolution_strategy: str
    ) -> bool:
        """
        Automatically resolve a conflict using specified strategy

        Strategies:
        - take_main: Use version from main branch
        - take_exploration: Use version from exploration
        - take_both: Combine both versions
        - take_newer: Use version with later timestamp
        """

        conflict = self._get_conflict_for_file(file_path)
        if not conflict:
            return False

        if resolution_strategy == "take_main":
            resolved_content = conflict.main_content
        elif resolution_strategy == "take_exploration":
            resolved_content = conflict.exploration_content
        elif resolution_strategy == "take_both":
            resolved_content = self._combine_content(conflict.main_content, conflict.exploration_content)
        elif resolution_strategy == "take_newer":
            resolved_content = self._choose_newer_content(conflict)
        else:
            return False

        # Write resolved content
        full_path = os.path.join(self.repo.workdir, file_path)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(resolved_content)

        # Stage resolved file
        self.repo.index.add(file_path)

        return True

    def generate_conflict_summary(self) -> str:
        """Generate human-readable summary of conflicts for writers"""

        conflicts = self.get_conflicts()

        if not conflicts:
            return "No conflicts found."

        summary_lines = [
            f"Found {len(conflicts)} conflict(s) that need your attention:",
            ""
        ]

        for i, conflict in enumerate(conflicts, 1):
            summary_lines.extend([
                f"{i}. {conflict.file_path}",
                f"   Conflict type: {conflict.conflict_type}",
                f"   Main version: {len(conflict.main_content.split())} words",
                f"   Exploration version: {len(conflict.exploration_content.split())} words",
                ""
            ])

        summary_lines.extend([
            "To resolve conflicts:",
            "1. Review each conflicted file",
            "2. Choose which version to keep, or combine them",
            "3. Save your resolved version",
            "4. Complete the merge",
            ""
        ])

        return "\n".join(summary_lines)
```

### 5. Exploration Lifecycle Management

```python
class ExplorationLifecycle:
    """Manage the complete lifecycle of explorations"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository
        self.exploration_manager = ExplorationManager(repository.workdir)

    def archive_exploration(self, exploration_name: str, reason: str = "") -> bool:
        """Archive an exploration that's no longer needed"""

        # Move to archived namespace
        archived_name = f"archived/{exploration_name}"

        try:
            branch = self.repo.branches.local[exploration_name]

            # Create archived branch
            self.repo.branches.local.create(archived_name, branch.target)

            # Update metadata
            metadata = self._load_exploration_metadata(exploration_name)
            metadata["status"] = "archived"
            metadata["archived_at"] = datetime.utcnow()
            metadata["archive_reason"] = reason
            self._store_exploration_metadata_for_branch(archived_name, metadata)

            # Delete original branch
            branch.delete()

            return True

        except Exception:
            return False

    def restore_exploration(self, archived_name: str) -> bool:
        """Restore an archived exploration"""

        archived_branch_name = f"archived/{archived_name}"

        try:
            archived_branch = self.repo.branches.local[archived_branch_name]

            # Create restored branch
            self.repo.branches.local.create(archived_name, archived_branch.target)

            # Update metadata
            metadata = self._load_exploration_metadata(archived_branch_name)
            metadata["status"] = "active"
            metadata["restored_at"] = datetime.utcnow()
            self._store_exploration_metadata_for_branch(archived_name, metadata)

            return True

        except Exception:
            return False

    def cleanup_stale_explorations(self, days_old: int = 30) -> List[str]:
        """Clean up old, inactive explorations"""

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        cleaned_explorations = []

        for exploration in self.exploration_manager.list_explorations():
            if (exploration.status == "active" and
                exploration.last_modified < cutoff_date and
                exploration.saves_ahead == 0):

                # Archive old, unused exploration
                if self.archive_exploration(exploration.name, "Automatic cleanup - inactive"):
                    cleaned_explorations.append(exploration.name)

        return cleaned_explorations

    def suggest_merge_candidates(self) -> List[ExplorationInfo]:
        """Suggest explorations that might be ready to merge"""

        candidates = []

        for exploration in self.exploration_manager.list_explorations():
            # Look for explorations with recent activity and meaningful changes
            if (exploration.status == "active" and
                exploration.saves_ahead > 0 and
                exploration.word_count_difference > 100):  # At least 100 words changed

                # Check if it doesn't conflict with main
                conflicts = self._detect_potential_conflicts(exploration.name, "main")
                if not conflicts:
                    candidates.append(exploration)

        return sorted(candidates, key=lambda x: x.saves_ahead, reverse=True)
```

## Integration with Writer Workflows

### Exploration Templates

```python
class ExplorationTemplates:
    """Pre-defined exploration templates for common writing scenarios"""

    TEMPLATES = {
        "character_development": {
            "description": "Explore character backstory and development",
            "suggested_files": ["characters/", "notes/character_notes.md"],
            "tips": [
                "Focus on one character at a time",
                "Explore motivations and conflicts",
                "Consider how changes affect other characters"
            ]
        },
        "plot_alternative": {
            "description": "Try a different plot direction or ending",
            "suggested_files": ["outline.md", "chapters/"],
            "tips": [
                "Save your current outline first",
                "Consider pacing implications",
                "Think about character consistency"
            ]
        },
        "style_experiment": {
            "description": "Experiment with different writing styles",
            "suggested_files": ["chapters/"],
            "tips": [
                "Try different narrative perspectives",
                "Experiment with tense or voice",
                "Consider your target audience"
            ]
        },
        "dialogue_revision": {
            "description": "Revise dialogue and character voice",
            "suggested_files": ["chapters/", "characters/dialogue_notes.md"],
            "tips": [
                "Read dialogue aloud",
                "Ensure each character has distinct voice",
                "Check for natural flow"
            ]
        }
    }

    def create_from_template(
        self,
        template_name: str,
        exploration_name: str,
        custom_description: str = ""
    ) -> ExplorationInfo:
        """Create exploration using a template"""

        if template_name not in self.TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = self.TEMPLATES[template_name]
        description = custom_description or template["description"]

        # Create the exploration
        exploration_manager = ExplorationManager(self.repo.workdir)
        exploration = exploration_manager.create_exploration(exploration_name, description)

        # Add template metadata
        metadata = self._load_exploration_metadata(exploration_name)
        metadata["template"] = template_name
        metadata["suggested_files"] = template["suggested_files"]
        metadata["tips"] = template["tips"]
        self._store_exploration_metadata(exploration_name, metadata)

        return exploration
```

---

*GitWrite's branching system (explorations) empowers writers to experiment fearlessly while maintaining the safety and power of Git's branching capabilities. The system emphasizes clarity, safety, and writer-centric workflows while providing access to advanced Git features when needed.*