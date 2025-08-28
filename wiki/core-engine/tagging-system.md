# Tagging System

GitWrite's tagging system provides writers with a way to mark important milestones, versions, and achievements in their writing projects. Built on Git's tagging functionality, it transforms technical version labels into meaningful writing milestones.

## Overview

The tagging system allows writers to:
- Mark significant milestones (first draft, final draft, published version)
- Create checkpoint versions for safe experimentation
- Organize project timeline with meaningful labels
- Track progress toward writing goals
- Facilitate publishing and submission workflows

```
Writing Timeline with Tags
    │
    ├─ first-chapter (tag)
    ├─ Save: "Completed introduction"
    ├─ Save: "Added character development"
    ├─ first-draft-complete (tag)
    ├─ Save: "Editorial revisions"
    ├─ Save: "Incorporated feedback"
    ├─ ready-for-beta-readers (tag)
    ├─ Save: "Final polish"
    └─ submission-ready (tag)
```

## Core Components

### 1. Tag Management

```python
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import pygit2

class TagType(Enum):
    MILESTONE = "milestone"
    DRAFT = "draft"
    RELEASE = "release"
    CHECKPOINT = "checkpoint"
    SUBMISSION = "submission"
    ACHIEVEMENT = "achievement"

@dataclass
class WritingTag:
    """Represents a writing milestone tag"""
    name: str
    tag_type: TagType
    description: str
    save_id: str  # Git commit ID
    created_at: datetime
    creator: str

    # Metadata
    word_count: Optional[int] = None
    chapter_count: Optional[int] = None
    completion_percentage: Optional[float] = None

    # Goals and achievements
    writing_goals: Optional[List[str]] = None
    achievements: Optional[List[str]] = None

    # Publishing info
    submission_info: Optional[Dict[str, Any]] = None

    # Git tag reference
    git_tag_name: str = None

    def __post_init__(self):
        if self.git_tag_name is None:
            self.git_tag_name = self.name.replace(' ', '-').lower()

class TagManager:
    """Manages writing tags and milestones"""

    def __init__(self, repository_path: str):
        self.repo = pygit2.Repository(repository_path)
        self.tags_metadata_file = os.path.join(repository_path, '.gitwrite', 'tags.json')

    def create_tag(
        self,
        name: str,
        description: str,
        tag_type: TagType = TagType.MILESTONE,
        save_id: Optional[str] = None,
        word_count: Optional[int] = None,
        completion_percentage: Optional[float] = None,
        writing_goals: Optional[List[str]] = None
    ) -> WritingTag:
        """Create a new writing tag"""

        # Use current HEAD if no save_id specified
        if save_id is None:
            save_id = str(self.repo.head.target)

        # Create WritingTag object
        tag = WritingTag(
            name=name,
            tag_type=tag_type,
            description=description,
            save_id=save_id,
            created_at=datetime.utcnow(),
            creator=self._get_current_user(),
            word_count=word_count,
            completion_percentage=completion_percentage,
            writing_goals=writing_goals or []
        )

        # Create Git tag
        commit = self.repo[save_id]
        signature = self.repo.default_signature

        # Create annotated tag with metadata
        tag_message = self._create_tag_message(tag)

        git_tag = self.repo.create_tag(
            tag.git_tag_name,
            commit.id,
            pygit2.GIT_OBJ_COMMIT,
            signature,
            tag_message
        )

        # Store extended metadata
        self._store_tag_metadata(tag)

        return tag

    def get_tags(
        self,
        tag_type: Optional[TagType] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[WritingTag]:
        """Retrieve writing tags with filtering"""

        tags = []

        # Load all Git tags
        for tag_name in self.repo.listall_references():
            if tag_name.startswith('refs/tags/'):
                tag_ref = self.repo.lookup_reference(tag_name)
                tag_obj = tag_ref.peel()

                # Get tag metadata
                tag_metadata = self._load_tag_metadata(tag_name.split('/')[-1])

                if tag_metadata:
                    tag = self._create_writing_tag_from_metadata(tag_metadata, tag_obj)

                    # Apply filters
                    if tag_type and tag.tag_type != tag_type:
                        continue

                    if since and tag.created_at < since:
                        continue

                    if until and tag.created_at > until:
                        continue

                    tags.append(tag)

        # Sort by creation date
        return sorted(tags, key=lambda x: x.created_at, reverse=True)

    def delete_tag(self, tag_name: str) -> bool:
        """Delete a writing tag"""

        try:
            # Delete Git tag
            git_tag_name = tag_name.replace(' ', '-').lower()
            self.repo.delete_tag(git_tag_name)

            # Remove metadata
            self._remove_tag_metadata(git_tag_name)

            return True

        except Exception:
            return False

    def _create_tag_message(self, tag: WritingTag) -> str:
        """Create Git tag message with metadata"""

        lines = [
            f"Writing Milestone: {tag.name}",
            f"Type: {tag.tag_type.value}",
            f"Description: {tag.description}",
            f"Created: {tag.created_at.isoformat()}",
            f"Creator: {tag.creator}"
        ]

        if tag.word_count:
            lines.append(f"Word Count: {tag.word_count:,}")

        if tag.completion_percentage:
            lines.append(f"Completion: {tag.completion_percentage:.1f}%")

        if tag.writing_goals:
            lines.append("Goals:")
            for goal in tag.writing_goals:
                lines.append(f"  - {goal}")

        return '\n'.join(lines)
```

### 2. Milestone Templates

```python
class MilestoneTemplates:
    """Pre-defined milestone templates for common writing achievements"""

    TEMPLATES = {
        "first_chapter": {
            "name": "First Chapter Complete",
            "description": "Completed the opening chapter",
            "tag_type": TagType.MILESTONE,
            "suggested_goals": [
                "Establish main character",
                "Set up central conflict",
                "Hook the reader"
            ]
        },

        "first_draft": {
            "name": "First Draft Complete",
            "description": "Completed the initial draft from beginning to end",
            "tag_type": TagType.DRAFT,
            "completion_percentage": 100.0,
            "suggested_goals": [
                "Complete story arc",
                "All major plot points included",
                "Ready for revision"
            ]
        },

        "beta_ready": {
            "name": "Beta Reader Ready",
            "description": "Manuscript ready for beta reader feedback",
            "tag_type": TagType.MILESTONE,
            "suggested_goals": [
                "Self-editing complete",
                "Plot holes addressed",
                "Character consistency checked"
            ]
        },

        "submission_ready": {
            "name": "Submission Ready",
            "description": "Final version ready for publisher submission",
            "tag_type": TagType.SUBMISSION,
            "suggested_goals": [
                "Professional formatting",
                "All feedback incorporated",
                "Final proofread complete"
            ]
        },

        "published": {
            "name": "Published",
            "description": "Work has been officially published",
            "tag_type": TagType.RELEASE,
            "completion_percentage": 100.0,
            "suggested_goals": [
                "Available to readers",
                "Marketing initiated",
                "Author platform updated"
            ]
        }
    }

    @classmethod
    def create_from_template(
        cls,
        template_name: str,
        tag_manager: TagManager,
        custom_name: str = None,
        additional_goals: List[str] = None
    ) -> WritingTag:
        """Create tag from predefined template"""

        if template_name not in cls.TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = cls.TEMPLATES[template_name]

        # Calculate current project statistics
        stats = tag_manager._calculate_project_stats()

        goals = template.get("suggested_goals", []).copy()
        if additional_goals:
            goals.extend(additional_goals)

        return tag_manager.create_tag(
            name=custom_name or template["name"],
            description=template["description"],
            tag_type=TagType(template["tag_type"]),
            word_count=stats["word_count"],
            completion_percentage=template.get("completion_percentage"),
            writing_goals=goals
        )
```

### 3. Progress Tracking

```python
@dataclass
class ProgressMetrics:
    """Metrics for tracking writing progress"""
    current_word_count: int
    target_word_count: Optional[int]
    completion_percentage: float
    words_since_last_tag: int
    days_since_last_tag: int
    writing_velocity: float  # words per day
    estimated_completion_days: Optional[int]

class ProgressTracker:
    """Track writing progress between milestones"""

    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager

    def calculate_progress(
        self,
        target_word_count: Optional[int] = None,
        target_date: Optional[datetime] = None
    ) -> ProgressMetrics:
        """Calculate current writing progress"""

        # Get current project statistics
        current_stats = self.tag_manager._calculate_project_stats()
        current_word_count = current_stats["word_count"]

        # Get last milestone
        tags = self.tag_manager.get_tags()
        last_tag = tags[0] if tags else None

        # Calculate progress since last tag
        if last_tag:
            words_since_last_tag = current_word_count - (last_tag.word_count or 0)
            days_since_last_tag = (datetime.utcnow() - last_tag.created_at).days
            writing_velocity = words_since_last_tag / max(days_since_last_tag, 1)
        else:
            words_since_last_tag = current_word_count
            days_since_last_tag = 0
            writing_velocity = 0

        # Calculate completion percentage
        if target_word_count:
            completion_percentage = (current_word_count / target_word_count) * 100
            remaining_words = target_word_count - current_word_count
            estimated_completion_days = remaining_words / max(writing_velocity, 1) if writing_velocity > 0 else None
        else:
            completion_percentage = 0
            estimated_completion_days = None

        return ProgressMetrics(
            current_word_count=current_word_count,
            target_word_count=target_word_count,
            completion_percentage=min(completion_percentage, 100),
            words_since_last_tag=words_since_last_tag,
            days_since_last_tag=days_since_last_tag,
            writing_velocity=writing_velocity,
            estimated_completion_days=estimated_completion_days
        )

    def suggest_next_milestone(self) -> Optional[str]:
        """Suggest next logical milestone based on progress"""

        progress = self.calculate_progress()
        existing_tags = [tag.name for tag in self.tag_manager.get_tags()]

        # Suggest based on completion percentage and existing milestones
        if "First Chapter Complete" not in existing_tags and progress.current_word_count >= 2000:
            return "first_chapter"

        if "First Draft Complete" not in existing_tags and progress.completion_percentage >= 90:
            return "first_draft"

        if "Beta Reader Ready" not in existing_tags and "First Draft Complete" in existing_tags:
            return "beta_ready"

        if "Submission Ready" not in existing_tags and "Beta Reader Ready" in existing_tags:
            return "submission_ready"

        return None
```

### 4. Tag Workflows

```python
class TagWorkflows:
    """Common workflows involving tags"""

    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager
        self.progress_tracker = ProgressTracker(tag_manager)

    def milestone_achievement_workflow(
        self,
        milestone_name: str,
        celebration_message: str = None
    ) -> Dict[str, Any]:
        """Complete workflow for achieving a milestone"""

        # Create the milestone tag
        if milestone_name in MilestoneTemplates.TEMPLATES:
            tag = MilestoneTemplates.create_from_template(
                milestone_name,
                self.tag_manager
            )
        else:
            # Custom milestone
            tag = self.tag_manager.create_tag(
                name=milestone_name,
                description=f"Achieved milestone: {milestone_name}",
                tag_type=TagType.ACHIEVEMENT
            )

        # Calculate progress metrics
        progress = self.progress_tracker.calculate_progress()

        # Suggest next milestone
        next_milestone = self.progress_tracker.suggest_next_milestone()

        # Generate achievement summary
        summary = {
            "milestone": tag,
            "progress": progress,
            "suggested_next": next_milestone,
            "celebration_message": celebration_message or f"Congratulations on reaching {tag.name}!",
            "writing_streak": self._calculate_writing_streak(),
            "project_timeline": self._generate_timeline_view()
        }

        return summary

    def submission_preparation_workflow(
        self,
        publisher_name: str,
        submission_requirements: Dict[str, Any]
    ) -> WritingTag:
        """Workflow for preparing submission package"""

        # Create submission tag with publisher info
        tag = self.tag_manager.create_tag(
            name=f"Submitted to {publisher_name}",
            description=f"Manuscript submitted to {publisher_name}",
            tag_type=TagType.SUBMISSION
        )

        # Store submission metadata
        tag.submission_info = {
            "publisher": publisher_name,
            "submission_date": datetime.utcnow().isoformat(),
            "requirements": submission_requirements,
            "status": "submitted"
        }

        self.tag_manager._store_tag_metadata(tag)

        return tag

    def version_comparison_workflow(
        self,
        tag1_name: str,
        tag2_name: str
    ) -> Dict[str, Any]:
        """Compare two tagged versions"""

        tags = self.tag_manager.get_tags()
        tag1 = next((t for t in tags if t.name == tag1_name), None)
        tag2 = next((t for t in tags if t.name == tag2_name), None)

        if not tag1 or not tag2:
            raise ValueError("One or both tags not found")

        # Calculate differences
        word_count_diff = (tag2.word_count or 0) - (tag1.word_count or 0)
        time_diff = tag2.created_at - tag1.created_at

        # Generate Git diff
        repo = self.tag_manager.repo
        commit1 = repo[tag1.save_id]
        commit2 = repo[tag2.save_id]
        diff = repo.diff(commit1.tree, commit2.tree)

        return {
            "tag1": tag1,
            "tag2": tag2,
            "word_count_difference": word_count_diff,
            "time_difference_days": time_diff.days,
            "files_changed": len(diff.deltas),
            "git_diff_stats": diff.stats,
            "progress_between": self._calculate_progress_between_tags(tag1, tag2)
        }
```

### 5. Tag Analytics

```python
class TagAnalytics:
    """Analytics and insights about writing milestones"""

    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager

    def generate_milestone_report(self) -> Dict[str, Any]:
        """Generate comprehensive milestone report"""

        tags = self.tag_manager.get_tags()

        if not tags:
            return {"message": "No milestones created yet"}

        # Calculate milestone statistics
        total_milestones = len(tags)
        milestone_types = {}
        for tag in tags:
            tag_type = tag.tag_type.value
            milestone_types[tag_type] = milestone_types.get(tag_type, 0) + 1

        # Calculate writing velocity between milestones
        velocities = []
        for i in range(len(tags) - 1):
            current_tag = tags[i]
            previous_tag = tags[i + 1]

            if current_tag.word_count and previous_tag.word_count:
                word_diff = current_tag.word_count - previous_tag.word_count
                time_diff = (current_tag.created_at - previous_tag.created_at).days

                if time_diff > 0:
                    velocity = word_diff / time_diff
                    velocities.append(velocity)

        avg_velocity = sum(velocities) / len(velocities) if velocities else 0

        # Identify achievement patterns
        achievement_frequency = self._calculate_achievement_frequency(tags)
        goal_completion_rate = self._calculate_goal_completion_rate(tags)

        return {
            "total_milestones": total_milestones,
            "milestone_types": milestone_types,
            "writing_velocity": {
                "average_words_per_day": avg_velocity,
                "velocity_trend": self._analyze_velocity_trend(velocities)
            },
            "achievement_patterns": {
                "average_days_between_milestones": achievement_frequency,
                "goal_completion_rate": goal_completion_rate,
                "most_productive_period": self._find_most_productive_period(tags)
            },
            "project_timeline": self._generate_timeline_visualization(tags),
            "recommendations": self._generate_milestone_recommendations(tags)
        }

    def _generate_milestone_recommendations(self, tags: List[WritingTag]) -> List[str]:
        """Generate recommendations based on milestone history"""

        recommendations = []

        # Check milestone frequency
        if len(tags) < 3:
            recommendations.append("Consider setting more frequent milestones to track progress")

        # Check goal completion
        goals_with_outcomes = [tag for tag in tags if tag.writing_goals]
        if len(goals_with_outcomes) < len(tags) * 0.5:
            recommendations.append("Try setting specific goals for each milestone")

        # Check writing velocity
        recent_tags = tags[:3]  # Last 3 milestones
        if len(recent_tags) >= 2:
            time_between = (recent_tags[0].created_at - recent_tags[-1].created_at).days
            if time_between > 30:
                recommendations.append("Consider setting more frequent milestones to maintain momentum")

        return recommendations
```

## Integration Features

### Tag-Based Exports

```python
def export_tagged_version(tag_name: str, export_format: str) -> str:
    """Export document as it existed at specific tag"""

    tag_manager = TagManager(repo_path)
    tags = tag_manager.get_tags()

    target_tag = next((t for t in tags if t.name == tag_name), None)
    if not target_tag:
        raise ValueError(f"Tag '{tag_name}' not found")

    # Export from specific commit
    version_exporter = VersionAwareExporter(tag_manager.repo)
    config = ExportConfiguration(
        format=ExportFormat(export_format),
        include_version_info=True,
        title=f"{tag_name} Version"
    )

    return version_exporter.export_at_version(target_tag.save_id, config)
```

### Automated Tagging

```python
class AutoTagging:
    """Automatic milestone detection and tagging"""

    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager

    def check_auto_milestone_triggers(self) -> List[str]:
        """Check if any automatic milestones should be created"""

        triggers = []
        progress = ProgressTracker(self.tag_manager).calculate_progress()

        # Word count milestones
        word_milestones = [10000, 25000, 50000, 75000, 100000]
        existing_word_tags = {tag.word_count for tag in self.tag_manager.get_tags() if tag.word_count}

        for milestone in word_milestones:
            if (progress.current_word_count >= milestone and
                milestone not in existing_word_tags):
                triggers.append(f"word_count_{milestone}")

        return triggers
```

---

*GitWrite's tagging system transforms technical Git tags into meaningful writing milestones, helping writers track progress, celebrate achievements, and maintain motivation throughout their writing journey.*