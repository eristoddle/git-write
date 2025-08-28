# Annotation System

GitWrite's annotation system provides a comprehensive feedback and collaboration framework that integrates directly with the version control workflow. It allows editors, beta readers, and collaborators to provide structured feedback while maintaining clear relationships to specific versions and locations in the manuscript.

## Overview

The annotation system bridges the gap between traditional commenting tools and version control, enabling:

- **Contextual Feedback**: Comments tied to specific lines, paragraphs, or sections
- **Version Awareness**: Annotations linked to specific saves (commits)
- **Collaborative Workflows**: Structured feedback collection and resolution
- **Integration**: Seamless integration with Git history and branching

```
┌─────────────────────────────────────────────┐
│              Writer Interface               │
│  ┌─────────────────────────────────────────┐ │
│  │  Add Comment    Review Feedback         │ │
│  │  Resolve Issue   Track Changes          │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           Annotation Engine                 │
│  ┌─────────────────────────────────────────┐ │
│  │  Comment Storage    Position Tracking   │ │
│  │  Resolution Logic   Notification System │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│            Storage Layer                    │
│  ┌─────────────────────────────────────────┐ │
│  │  Git Notes       File System            │ │
│  │  Metadata Store  External Database      │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Core Components

### 1. Annotation Data Model

```python
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

class AnnotationType(Enum):
    COMMENT = "comment"
    SUGGESTION = "suggestion"
    QUESTION = "question"
    PRAISE = "praise"
    ISSUE = "issue"
    TASK = "task"

class AnnotationStatus(Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"

class AnnotationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AnnotationPosition:
    """Represents the position of an annotation in a file"""
    file_path: str
    line_start: int
    line_end: int
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    character_start: Optional[int] = None
    character_end: Optional[int] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None

@dataclass
class Annotation:
    """Core annotation data structure"""
    id: str
    type: AnnotationType
    status: AnnotationStatus
    priority: AnnotationPriority

    # Content
    content: str
    suggested_text: Optional[str] = None

    # Position and context
    position: AnnotationPosition
    save_id: str  # Git commit ID when annotation was created

    # Metadata
    author: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_message: Optional[str] = None

    # Collaboration
    assigned_to: Optional[str] = None
    thread_id: Optional[str] = None  # For threaded discussions
    parent_id: Optional[str] = None  # For replies

    # Tags and categorization
    tags: List[str] = None
    category: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.id:
            self.id = str(uuid.uuid4())

class AnnotationManager:
    """Manages annotation creation, storage, and retrieval"""

    def __init__(self, repository_path: str):
        self.repo_path = repository_path
        self.storage = AnnotationStorage(repository_path)

    def create_annotation(
        self,
        content: str,
        position: AnnotationPosition,
        type: AnnotationType = AnnotationType.COMMENT,
        priority: AnnotationPriority = AnnotationPriority.MEDIUM,
        author: str = None,
        suggested_text: str = None,
        tags: List[str] = None,
        assigned_to: str = None
    ) -> Annotation:
        """Create a new annotation"""

        # Get current save ID
        repo = pygit2.Repository(self.repo_path)
        current_save_id = str(repo.head.target)

        annotation = Annotation(
            id=str(uuid.uuid4()),
            type=type,
            status=AnnotationStatus.OPEN,
            priority=priority,
            content=content,
            suggested_text=suggested_text,
            position=position,
            save_id=current_save_id,
            author=author or self._get_current_user(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tags=tags or [],
            assigned_to=assigned_to
        )

        # Store the annotation
        self.storage.save_annotation(annotation)

        # Trigger events
        self._trigger_annotation_created(annotation)

        return annotation

    def get_annotations(
        self,
        file_path: Optional[str] = None,
        save_id: Optional[str] = None,
        status: Optional[AnnotationStatus] = None,
        author: Optional[str] = None,
        type: Optional[AnnotationType] = None,
        assigned_to: Optional[str] = None
    ) -> List[Annotation]:
        """Retrieve annotations with filtering"""

        annotations = self.storage.load_annotations()

        # Apply filters
        if file_path:
            annotations = [a for a in annotations if a.position.file_path == file_path]

        if save_id:
            annotations = [a for a in annotations if a.save_id == save_id]

        if status:
            annotations = [a for a in annotations if a.status == status]

        if author:
            annotations = [a for a in annotations if a.author == author]

        if type:
            annotations = [a for a in annotations if a.type == type]

        if assigned_to:
            annotations = [a for a in annotations if a.assigned_to == assigned_to]

        return sorted(annotations, key=lambda x: x.created_at, reverse=True)

    def resolve_annotation(
        self,
        annotation_id: str,
        resolution_message: str = "",
        resolution_action: str = "resolved",
        resolved_by: str = None
    ) -> bool:
        """Resolve an annotation"""

        annotation = self.storage.get_annotation(annotation_id)
        if not annotation:
            return False

        # Update annotation
        annotation.status = AnnotationStatus.RESOLVED
        if resolution_action == "accepted":
            annotation.status = AnnotationStatus.ACCEPTED
        elif resolution_action == "rejected":
            annotation.status = AnnotationStatus.REJECTED

        annotation.resolved_at = datetime.utcnow()
        annotation.resolved_by = resolved_by or self._get_current_user()
        annotation.resolution_message = resolution_message
        annotation.updated_at = datetime.utcnow()

        # Save changes
        self.storage.save_annotation(annotation)

        # Trigger events
        self._trigger_annotation_resolved(annotation)

        return True
```

### 2. Position Tracking and Context

```python
class PositionTracker:
    """Tracks annotation positions across file changes"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def create_position(
        self,
        file_path: str,
        line_start: int,
        line_end: int = None,
        character_start: int = None,
        character_end: int = None,
        context_lines: int = 2
    ) -> AnnotationPosition:
        """Create position with surrounding context"""

        if line_end is None:
            line_end = line_start

        # Read file content
        file_content = self._read_file_content(file_path)
        lines = file_content.splitlines()

        # Extract context
        context_start = max(0, line_start - context_lines)
        context_end = min(len(lines), line_end + context_lines + 1)

        context_before = '\n'.join(lines[context_start:line_start]) if line_start > 0 else None
        context_after = '\n'.join(lines[line_end+1:context_end]) if line_end < len(lines) - 1 else None

        return AnnotationPosition(
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            column_start=character_start,
            column_end=character_end,
            character_start=self._calculate_character_position(lines, line_start, character_start),
            character_end=self._calculate_character_position(lines, line_end, character_end),
            context_before=context_before,
            context_after=context_after
        )

    def update_positions_for_changes(
        self,
        annotations: List[Annotation],
        old_save_id: str,
        new_save_id: str
    ) -> List[Annotation]:
        """Update annotation positions when file content changes"""

        updated_annotations = []

        # Get diff between versions
        old_commit = self.repo[old_save_id]
        new_commit = self.repo[new_save_id]
        diff = self.repo.diff(old_commit.tree, new_commit.tree)

        # Build line mapping for each changed file
        line_mappings = self._build_line_mappings(diff)

        for annotation in annotations:
            if annotation.position.file_path in line_mappings:
                # Update position based on line mapping
                new_position = self._remap_position(
                    annotation.position,
                    line_mappings[annotation.position.file_path]
                )
                annotation.position = new_position

            updated_annotations.append(annotation)

        return updated_annotations

    def _build_line_mappings(self, diff: pygit2.Diff) -> Dict[str, Dict[int, int]]:
        """Build mapping of old line numbers to new line numbers"""

        mappings = {}

        for delta in diff.deltas:
            file_path = delta.new_file.path
            line_mapping = {}

            patch = diff[delta]
            old_line = 0
            new_line = 0

            for hunk in patch.hunks:
                # Skip to hunk start
                old_line = hunk.old_start
                new_line = hunk.new_start

                for line in hunk.lines:
                    if line.origin == '+':
                        # Line added - shift subsequent lines
                        new_line += 1
                    elif line.origin == '-':
                        # Line removed - mark as deleted
                        line_mapping[old_line] = -1  # Deleted
                        old_line += 1
                    else:
                        # Unchanged line
                        line_mapping[old_line] = new_line
                        old_line += 1
                        new_line += 1

            mappings[file_path] = line_mapping

        return mappings

    def _remap_position(
        self,
        position: AnnotationPosition,
        line_mapping: Dict[int, int]
    ) -> AnnotationPosition:
        """Remap annotation position using line mapping"""

        # Map start line
        new_line_start = line_mapping.get(position.line_start, position.line_start)
        new_line_end = line_mapping.get(position.line_end, position.line_end)

        # Handle deleted lines
        if new_line_start == -1 or new_line_end == -1:
            # Find nearest valid line
            new_line_start = self._find_nearest_valid_line(position.line_start, line_mapping)
            new_line_end = self._find_nearest_valid_line(position.line_end, line_mapping)

        return AnnotationPosition(
            file_path=position.file_path,
            line_start=new_line_start,
            line_end=new_line_end,
            column_start=position.column_start,
            column_end=position.column_end,
            context_before=position.context_before,
            context_after=position.context_after
        )
```

### 3. Annotation Storage

```python
import json
import os
from typing import Dict

class AnnotationStorage:
    """Handles persistent storage of annotations"""

    def __init__(self, repository_path: str):
        self.repo_path = repository_path
        self.annotations_dir = os.path.join(repository_path, '.gitwrite', 'annotations')
        self.ensure_storage_directory()

    def ensure_storage_directory(self):
        """Ensure annotation storage directory exists"""
        os.makedirs(self.annotations_dir, exist_ok=True)

    def save_annotation(self, annotation: Annotation):
        """Save annotation to storage"""

        annotation_file = os.path.join(self.annotations_dir, f"{annotation.id}.json")

        # Convert to serializable format
        annotation_data = {
            'id': annotation.id,
            'type': annotation.type.value,
            'status': annotation.status.value,
            'priority': annotation.priority.value,
            'content': annotation.content,
            'suggested_text': annotation.suggested_text,
            'position': {
                'file_path': annotation.position.file_path,
                'line_start': annotation.position.line_start,
                'line_end': annotation.position.line_end,
                'column_start': annotation.position.column_start,
                'column_end': annotation.position.column_end,
                'character_start': annotation.position.character_start,
                'character_end': annotation.position.character_end,
                'context_before': annotation.position.context_before,
                'context_after': annotation.position.context_after
            },
            'save_id': annotation.save_id,
            'author': annotation.author,
            'created_at': annotation.created_at.isoformat(),
            'updated_at': annotation.updated_at.isoformat(),
            'resolved_at': annotation.resolved_at.isoformat() if annotation.resolved_at else None,
            'resolved_by': annotation.resolved_by,
            'resolution_message': annotation.resolution_message,
            'assigned_to': annotation.assigned_to,
            'thread_id': annotation.thread_id,
            'parent_id': annotation.parent_id,
            'tags': annotation.tags,
            'category': annotation.category
        }

        with open(annotation_file, 'w', encoding='utf-8') as f:
            json.dump(annotation_data, f, indent=2)

    def load_annotations(self) -> List[Annotation]:
        """Load all annotations from storage"""

        annotations = []

        if not os.path.exists(self.annotations_dir):
            return annotations

        for filename in os.listdir(self.annotations_dir):
            if filename.endswith('.json'):
                annotation_file = os.path.join(self.annotations_dir, filename)

                try:
                    with open(annotation_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    annotation = self._deserialize_annotation(data)
                    annotations.append(annotation)

                except Exception as e:
                    # Log error but continue loading other annotations
                    print(f"Error loading annotation {filename}: {e}")

        return annotations

    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        """Get specific annotation by ID"""

        annotation_file = os.path.join(self.annotations_dir, f"{annotation_id}.json")

        if not os.path.exists(annotation_file):
            return None

        try:
            with open(annotation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return self._deserialize_annotation(data)

        except Exception:
            return None

    def delete_annotation(self, annotation_id: str) -> bool:
        """Delete annotation from storage"""

        annotation_file = os.path.join(self.annotations_dir, f"{annotation_id}.json")

        if os.path.exists(annotation_file):
            os.remove(annotation_file)
            return True

        return False

    def _deserialize_annotation(self, data: Dict[str, Any]) -> Annotation:
        """Convert stored data back to Annotation object"""

        position = AnnotationPosition(
            file_path=data['position']['file_path'],
            line_start=data['position']['line_start'],
            line_end=data['position']['line_end'],
            column_start=data['position'].get('column_start'),
            column_end=data['position'].get('column_end'),
            character_start=data['position'].get('character_start'),
            character_end=data['position'].get('character_end'),
            context_before=data['position'].get('context_before'),
            context_after=data['position'].get('context_after')
        )

        return Annotation(
            id=data['id'],
            type=AnnotationType(data['type']),
            status=AnnotationStatus(data['status']),
            priority=AnnotationPriority(data['priority']),
            content=data['content'],
            suggested_text=data.get('suggested_text'),
            position=position,
            save_id=data['save_id'],
            author=data['author'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            resolved_by=data.get('resolved_by'),
            resolution_message=data.get('resolution_message'),
            assigned_to=data.get('assigned_to'),
            thread_id=data.get('thread_id'),
            parent_id=data.get('parent_id'),
            tags=data.get('tags', []),
            category=data.get('category')
        )
```

### 4. Suggestion Application

```python
class SuggestionApplicator:
    """Applies annotation suggestions to text content"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def apply_suggestion(
        self,
        annotation: Annotation,
        create_save: bool = True,
        save_message: str = None
    ) -> bool:
        """Apply a suggestion annotation to the file"""

        if annotation.type != AnnotationType.SUGGESTION or not annotation.suggested_text:
            return False

        # Read current file content
        file_path = annotation.position.file_path
        full_path = os.path.join(self.repo.workdir, file_path)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply the suggestion
            modified_content = self._apply_text_replacement(
                content,
                annotation.position,
                annotation.suggested_text
            )

            # Write modified content back
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)

            # Mark suggestion as accepted
            annotation.status = AnnotationStatus.ACCEPTED
            annotation.resolved_at = datetime.utcnow()
            annotation.updated_at = datetime.utcnow()

            # Save changes if requested
            if create_save:
                message = save_message or f"Applied suggestion: {annotation.content[:50]}..."

                # Stage and commit the change
                self.repo.index.add(file_path)
                self.repo.index.write()

                tree = self.repo.index.write_tree()
                signature = self.repo.default_signature

                self.repo.create_commit(
                    'HEAD',
                    signature,
                    signature,
                    message,
                    tree,
                    [self.repo.head.target]
                )

            return True

        except Exception as e:
            print(f"Error applying suggestion: {e}")
            return False

    def _apply_text_replacement(
        self,
        content: str,
        position: AnnotationPosition,
        replacement_text: str
    ) -> str:
        """Apply text replacement at specified position"""

        lines = content.splitlines(keepends=True)

        # Handle line-based replacement
        if position.line_start == position.line_end:
            # Single line replacement
            line_index = position.line_start - 1  # Convert to 0-based

            if position.column_start is not None and position.column_end is not None:
                # Column-based replacement within line
                line = lines[line_index]
                new_line = (
                    line[:position.column_start] +
                    replacement_text +
                    line[position.column_end:]
                )
                lines[line_index] = new_line
            else:
                # Replace entire line
                lines[line_index] = replacement_text + '\n'
        else:
            # Multi-line replacement
            start_index = position.line_start - 1
            end_index = position.line_end - 1

            # Replace the range with new content
            new_lines = replacement_text.splitlines(keepends=True)
            lines[start_index:end_index + 1] = new_lines

        return ''.join(lines)

    def preview_suggestion(self, annotation: Annotation) -> str:
        """Preview what the file would look like with suggestion applied"""

        if annotation.type != AnnotationType.SUGGESTION or not annotation.suggested_text:
            return ""

        # Read current file content
        file_path = annotation.position.file_path
        full_path = os.path.join(self.repo.workdir, file_path)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply the suggestion to a copy
            modified_content = self._apply_text_replacement(
                content,
                annotation.position,
                annotation.suggested_text
            )

            return modified_content

        except Exception:
            return ""
```

### 5. Review Workflows

```python
class ReviewWorkflow:
    """Manages structured review workflows"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository
        self.annotation_manager = AnnotationManager(repository.workdir)

    def start_review_session(
        self,
        reviewer: str,
        files: List[str] = None,
        review_type: str = "general"
    ) -> str:
        """Start a new review session"""

        session_id = str(uuid.uuid4())

        # Create review session metadata
        session_data = {
            'id': session_id,
            'reviewer': reviewer,
            'started_at': datetime.utcnow().isoformat(),
            'review_type': review_type,
            'files': files or [],
            'status': 'in_progress',
            'annotations_created': [],
            'current_save_id': str(self.repo.head.target)
        }

        # Store session data
        self._store_review_session(session_data)

        return session_id

    def add_review_annotation(
        self,
        session_id: str,
        content: str,
        position: AnnotationPosition,
        type: AnnotationType = AnnotationType.COMMENT,
        priority: AnnotationPriority = AnnotationPriority.MEDIUM,
        suggested_text: str = None
    ) -> Annotation:
        """Add annotation as part of a review session"""

        session = self._load_review_session(session_id)
        if not session:
            raise ValueError(f"Review session {session_id} not found")

        # Create annotation
        annotation = self.annotation_manager.create_annotation(
            content=content,
            position=position,
            type=type,
            priority=priority,
            author=session['reviewer'],
            suggested_text=suggested_text,
            tags=[f"review:{session_id}", f"review_type:{session['review_type']}"]
        )

        # Track in session
        session['annotations_created'].append(annotation.id)
        self._store_review_session(session)

        return annotation

    def complete_review_session(
        self,
        session_id: str,
        summary: str = "",
        overall_rating: Optional[int] = None
    ) -> Dict[str, Any]:
        """Complete a review session"""

        session = self._load_review_session(session_id)
        if not session:
            raise ValueError(f"Review session {session_id} not found")

        # Update session
        session['status'] = 'completed'
        session['completed_at'] = datetime.utcnow().isoformat()
        session['summary'] = summary
        session['overall_rating'] = overall_rating

        # Generate review report
        annotations = [
            self.annotation_manager.storage.get_annotation(ann_id)
            for ann_id in session['annotations_created']
        ]

        report = {
            'session_id': session_id,
            'reviewer': session['reviewer'],
            'review_type': session['review_type'],
            'duration_minutes': self._calculate_session_duration(session),
            'annotations_count': len(annotations),
            'annotations_by_type': self._count_annotations_by_type(annotations),
            'annotations_by_priority': self._count_annotations_by_priority(annotations),
            'files_reviewed': session['files'],
            'summary': summary,
            'overall_rating': overall_rating
        }

        self._store_review_session(session)

        return report

    def get_review_statistics(
        self,
        reviewer: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get review statistics"""

        # Load all review sessions
        sessions = self._load_all_review_sessions()

        # Filter sessions
        if reviewer:
            sessions = [s for s in sessions if s['reviewer'] == reviewer]

        if since:
            sessions = [
                s for s in sessions
                if datetime.fromisoformat(s['started_at']) >= since
            ]

        # Calculate statistics
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s['status'] == 'completed'])

        total_annotations = sum(len(s['annotations_created']) for s in sessions)

        avg_annotations_per_session = total_annotations / max(total_sessions, 1)

        return {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'completion_rate': completed_sessions / max(total_sessions, 1),
            'total_annotations': total_annotations,
            'avg_annotations_per_session': avg_annotations_per_session,
            'most_active_reviewer': self._find_most_active_reviewer(sessions),
            'review_types': self._count_review_types(sessions)
        }
```

## Integration with Git

### Git Notes Integration

```python
class GitNotesAnnotations:
    """Store annotations as Git notes for better Git integration"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository
        self.notes_ref = "refs/notes/gitwrite-annotations"

    def attach_annotation_to_commit(
        self,
        commit_id: str,
        annotation: Annotation
    ):
        """Attach annotation to specific commit using Git notes"""

        # Get existing notes for commit
        try:
            note = self.repo.lookup_note(commit_id, self.notes_ref)
            existing_annotations = json.loads(note.message)
        except KeyError:
            existing_annotations = []

        # Add new annotation
        annotation_data = self._serialize_annotation(annotation)
        existing_annotations.append(annotation_data)

        # Store updated notes
        signature = self.repo.default_signature
        notes_message = json.dumps(existing_annotations, indent=2)

        try:
            # Update existing note
            self.repo.create_note(
                notes_message,
                signature,
                signature,
                commit_id,
                self.notes_ref,
                force=True
            )
        except:
            # Create new note
            self.repo.create_note(
                notes_message,
                signature,
                signature,
                commit_id,
                self.notes_ref
            )

    def get_annotations_for_commit(self, commit_id: str) -> List[Annotation]:
        """Retrieve annotations attached to specific commit"""

        try:
            note = self.repo.lookup_note(commit_id, self.notes_ref)
            annotations_data = json.loads(note.message)

            return [
                self._deserialize_annotation(data)
                for data in annotations_data
            ]
        except KeyError:
            return []
```

---

*GitWrite's annotation system provides a comprehensive framework for collaborative feedback that integrates seamlessly with version control workflows. It enables structured, contextual feedback collection while maintaining clear relationships to specific versions and positions in the manuscript.*