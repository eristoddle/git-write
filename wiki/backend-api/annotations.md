# Annotations API

GitWrite's Annotations API provides comprehensive endpoints for managing feedback, comments, suggestions, and collaborative review workflows. The API enables structured feedback collection, resolution tracking, and integration with version control systems.

## Overview

The Annotations API supports:
- **Feedback Management**: Comments, suggestions, questions, and issues
- **Position Tracking**: Precise location references within documents
- **Review Workflows**: Structured editorial and beta reader processes
- **Resolution Tracking**: Status management and outcome recording
- **Collaboration**: Multi-user feedback and threaded discussions
- **Version Integration**: Annotation linking to specific saves/commits

```
Annotations API Structure
    │
    ├─ /annotations/ (Annotation CRUD)
    ├─ /annotations/{id}/resolve (Resolution Management)
    ├─ /annotations/bulk (Bulk Operations)
    ├─ /reviews/ (Review Sessions)
    └─ /reviews/{id}/annotations (Session-specific Annotations)
```

## Core Models

### 1. Annotation Data Models

```python
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AnnotationType(str, Enum):
    COMMENT = "comment"
    SUGGESTION = "suggestion"
    QUESTION = "question"
    PRAISE = "praise"
    ISSUE = "issue"
    TASK = "task"

class AnnotationStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"

class AnnotationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AnnotationPosition(BaseModel):
    """Position information for annotation placement"""
    file_path: str = Field(..., description="Path to the file within repository")
    line_start: int = Field(..., ge=1, description="Starting line number (1-based)")
    line_end: int = Field(..., ge=1, description="Ending line number (1-based)")
    column_start: Optional[int] = Field(None, ge=0, description="Starting column (0-based)")
    column_end: Optional[int] = Field(None, ge=0, description="Ending column (0-based)")

    # Context for position stability
    context_before: Optional[str] = Field(None, max_length=500)
    context_after: Optional[str] = Field(None, max_length=500)

    class Config:
        schema_extra = {
            "example": {
                "file_path": "chapters/chapter1.md",
                "line_start": 42,
                "line_end": 42,
                "column_start": 15,
                "column_end": 28,
                "context_before": "The protagonist walked slowly",
                "context_after": "towards the mysterious door"
            }
        }

class CreateAnnotationRequest(BaseModel):
    """Request model for creating annotations"""
    type: AnnotationType = Field(AnnotationType.COMMENT)
    content: str = Field(..., min_length=1, max_length=2000)
    position: AnnotationPosition

    # Optional fields
    suggested_text: Optional[str] = Field(None, max_length=1000)
    priority: AnnotationPriority = Field(AnnotationPriority.MEDIUM)
    assigned_to: Optional[str] = Field(None, description="Email of assigned user")
    tags: List[str] = Field(default_factory=list, max_items=10)
    is_private: bool = Field(False, description="Private annotation visible only to author")

    class Config:
        schema_extra = {
            "example": {
                "type": "suggestion",
                "content": "Consider using a stronger verb here to increase tension",
                "position": {
                    "file_path": "chapters/chapter1.md",
                    "line_start": 42,
                    "line_end": 42,
                    "column_start": 15,
                    "column_end": 28
                },
                "suggested_text": "sprinted frantically",
                "priority": "medium",
                "tags": ["pacing", "word-choice"]
            }
        }

class AnnotationResponse(BaseModel):
    """Response model for annotation data"""
    id: str
    type: AnnotationType
    status: AnnotationStatus
    priority: AnnotationPriority

    # Content
    content: str
    suggested_text: Optional[str]

    # Position and context
    position: AnnotationPosition
    save_id: str  # Commit ID when annotation was created

    # Metadata
    author: str
    author_name: str
    created_at: datetime
    updated_at: datetime

    # Resolution info
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolved_by_name: Optional[str]
    resolution_message: Optional[str]
    resolution_action: Optional[str]  # accepted, rejected, custom

    # Collaboration
    assigned_to: Optional[str]
    assigned_to_name: Optional[str]
    thread_id: Optional[str]
    reply_count: int = 0

    # Organization
    tags: List[str]
    is_private: bool

    class Config:
        schema_extra = {
            "example": {
                "id": "ann_123456789",
                "type": "suggestion",
                "status": "open",
                "priority": "medium",
                "content": "Consider using a stronger verb here to increase tension",
                "suggested_text": "sprinted frantically",
                "position": {
                    "file_path": "chapters/chapter1.md",
                    "line_start": 42,
                    "line_end": 42
                },
                "save_id": "a1b2c3d4",
                "author": "editor@example.com",
                "author_name": "Professional Editor",
                "created_at": "2023-11-20T14:30:00Z",
                "updated_at": "2023-11-20T14:30:00Z",
                "tags": ["pacing", "word-choice"],
                "reply_count": 2,
                "is_private": False
            }
        }

router = APIRouter(prefix="/repositories/{repository_name}/annotations", tags=["annotations"])
```

### 2. Annotation CRUD Operations

```python
@router.post("/", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    repository_name: str,
    request: CreateAnnotationRequest,
    current_user: User = Depends(get_current_user)
) -> AnnotationResponse:
    """Create a new annotation"""

    repository = await _get_user_repository(repository_name, current_user)

    # Check permissions (read access required for annotations)
    if not await permission_service.can_read(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create annotations"
        )

    try:
        # Validate file exists
        if not await file_service.file_exists(repository.id, request.position.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{request.position.file_path}' not found"
            )

        # Validate assigned user exists (if specified)
        assigned_user = None
        if request.assigned_to:
            assigned_user = await user_service.get_by_email(request.assigned_to)
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User '{request.assigned_to}' not found"
                )

            # Check if assigned user has access to repository
            if not await permission_service.can_read(repository.id, assigned_user.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User '{request.assigned_to}' does not have access to this repository"
                )

        # Get current commit ID
        current_save = await git_service.get_current_commit(repository.id)

        # Create annotation
        annotation = await annotation_service.create_annotation(
            repository_id=repository.id,
            author_id=current_user.id,
            type=request.type,
            content=request.content,
            position=request.position,
            save_id=current_save.id,
            suggested_text=request.suggested_text,
            priority=request.priority,
            assigned_to=assigned_user.id if assigned_user else None,
            tags=request.tags,
            is_private=request.is_private
        )

        # Notify assigned user and collaborators
        await notification_service.notify_annotation_created(
            annotation_id=annotation.id,
            repository_id=repository.id,
            exclude_user_id=current_user.id
        )

        return await _convert_to_annotation_response(annotation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create annotation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create annotation"
        )

@router.get("/", response_model=List[AnnotationResponse])
async def list_annotations(
    repository_name: str,
    file_path: Optional[str] = Query(None, description="Filter by file path"),
    type: Optional[AnnotationType] = Query(None, description="Filter by annotation type"),
    status: Optional[AnnotationStatus] = Query(None, description="Filter by status"),
    author: Optional[str] = Query(None, description="Filter by author email"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    since: Optional[datetime] = Query(None, description="Filter by creation date"),
    include_private: bool = Query(False, description="Include private annotations"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[AnnotationResponse]:
    """List annotations with filtering options"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        annotations = await annotation_service.list_annotations(
            repository_id=repository.id,
            file_path=file_path,
            annotation_type=type,
            status=status,
            author_email=author,
            assigned_to_email=assigned_to,
            tags=tags,
            since=since,
            include_private=include_private and current_user.id,  # Only include private for current user
            limit=limit,
            offset=offset
        )

        return [
            await _convert_to_annotation_response(annotation)
            for annotation in annotations
        ]

    except Exception as e:
        logger.error(f"Failed to list annotations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve annotations"
        )

@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    repository_name: str,
    annotation_id: str,
    current_user: User = Depends(get_current_user)
) -> AnnotationResponse:
    """Get detailed information about a specific annotation"""

    repository = await _get_user_repository(repository_name, current_user)

    annotation = await annotation_service.get_annotation(
        annotation_id=annotation_id,
        repository_id=repository.id
    )

    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found"
        )

    # Check privacy settings
    if annotation.is_private and annotation.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access private annotation"
        )

    return await _convert_to_annotation_response(annotation)

@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    repository_name: str,
    annotation_id: str,
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> AnnotationResponse:
    """Update an existing annotation"""

    repository = await _get_user_repository(repository_name, current_user)

    annotation = await annotation_service.get_annotation(annotation_id, repository.id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found"
        )

    # Check permissions (only author or repository owner can update)
    if (annotation.author_id != current_user.id and
        not await permission_service.is_owner(repository.id, current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update annotation"
        )

    try:
        updated_annotation = await annotation_service.update_annotation(
            annotation_id=annotation_id,
            updates=updates,
            updated_by=current_user.id
        )

        return await _convert_to_annotation_response(updated_annotation)

    except Exception as e:
        logger.error(f"Failed to update annotation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update annotation"
        )
```

### 3. Resolution Management

```python
class ResolveAnnotationRequest(BaseModel):
    """Request model for resolving annotations"""
    action: str = Field(..., regex="^(accept|reject|resolve|custom)$")
    message: Optional[str] = Field(None, max_length=500, description="Resolution message")
    apply_suggestion: bool = Field(False, description="Apply suggested text (for suggestions)")
    create_commit: bool = Field(True, description="Create commit when applying suggestions")

    class Config:
        schema_extra = {
            "example": {
                "action": "accept",
                "message": "Great suggestion! Applied the change.",
                "apply_suggestion": True,
                "create_commit": True
            }
        }

class ResolutionResponse(BaseModel):
    """Response model for annotation resolution"""
    success: bool
    action_taken: str
    message: str

    # Suggestion application results
    suggestion_applied: bool = False
    commit_created: Optional[str] = None
    files_modified: List[str] = []

    # Updated annotation
    annotation: AnnotationResponse

@router.post("/{annotation_id}/resolve", response_model=ResolutionResponse)
async def resolve_annotation(
    repository_name: str,
    annotation_id: str,
    request: ResolveAnnotationRequest,
    current_user: User = Depends(get_current_user)
) -> ResolutionResponse:
    """Resolve an annotation with optional suggestion application"""

    repository = await _get_user_repository(repository_name, current_user)

    annotation = await annotation_service.get_annotation(annotation_id, repository.id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found"
        )

    # Check resolution permissions
    can_resolve = (
        annotation.author_id == current_user.id or  # Author can resolve
        annotation.assigned_to == current_user.id or  # Assigned user can resolve
        await permission_service.can_write(repository.id, current_user.id)  # Writers can resolve
    )

    if not can_resolve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to resolve annotation"
        )

    try:
        suggestion_applied = False
        commit_id = None
        files_modified = []

        # Apply suggestion if requested and annotation is a suggestion
        if (request.apply_suggestion and
            annotation.type == AnnotationType.SUGGESTION and
            annotation.suggested_text):

            # Check write permissions for suggestion application
            if not await permission_service.can_write(repository.id, current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to apply suggestions"
                )

            # Apply the suggestion
            application_result = await suggestion_service.apply_suggestion(
                repository_id=repository.id,
                annotation_id=annotation_id,
                applied_by=current_user.id
            )

            if application_result.success:
                suggestion_applied = True
                files_modified = application_result.files_modified

                # Create commit if requested
                if request.create_commit:
                    commit_result = await git_service.save_changes(
                        repository_id=repository.id,
                        message=f"Applied suggestion: {annotation.content[:50]}...",
                        files=files_modified,
                        author_name=current_user.name,
                        author_email=current_user.email
                    )
                    if commit_result.success:
                        commit_id = commit_result.commit_id

        # Resolve the annotation
        resolution_result = await annotation_service.resolve_annotation(
            annotation_id=annotation_id,
            action=request.action,
            message=request.message,
            resolved_by=current_user.id,
            suggestion_applied=suggestion_applied
        )

        # Notify relevant users
        await notification_service.notify_annotation_resolved(
            annotation_id=annotation_id,
            resolved_by=current_user.id,
            action=request.action
        )

        updated_annotation = await annotation_service.get_annotation(annotation_id, repository.id)

        return ResolutionResponse(
            success=True,
            action_taken=request.action,
            message=f"Annotation {request.action}ed successfully",
            suggestion_applied=suggestion_applied,
            commit_created=commit_id,
            files_modified=files_modified,
            annotation=await _convert_to_annotation_response(updated_annotation)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve annotation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve annotation"
        )

@router.post("/{annotation_id}/replies", response_model=AnnotationResponse)
async def add_reply(
    repository_name: str,
    annotation_id: str,
    reply_content: str = Field(..., min_length=1, max_length=1000),
    current_user: User = Depends(get_current_user)
) -> AnnotationResponse:
    """Add a reply to an annotation thread"""

    repository = await _get_user_repository(repository_name, current_user)

    parent_annotation = await annotation_service.get_annotation(annotation_id, repository.id)
    if not parent_annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation '{annotation_id}' not found"
        )

    try:
        reply = await annotation_service.create_reply(
            parent_annotation_id=annotation_id,
            author_id=current_user.id,
            content=reply_content,
            repository_id=repository.id
        )

        # Update parent annotation reply count
        await annotation_service.increment_reply_count(annotation_id)

        # Notify thread participants
        await notification_service.notify_annotation_reply(
            reply_id=reply.id,
            parent_annotation_id=annotation_id,
            author_id=current_user.id
        )

        return await _convert_to_annotation_response(reply)

    except Exception as e:
        logger.error(f"Failed to add reply: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add reply"
        )
```

### 4. Bulk Operations

```python
class BulkAnnotationOperation(BaseModel):
    """Request for bulk annotation operations"""
    annotation_ids: List[str] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., regex="^(resolve|delete|assign|tag|update_status)$")
    parameters: Dict[str, Any] = Field(default_factory=dict)

class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success: bool
    processed_count: int
    failed_count: int
    successful_operations: List[str]
    failed_operations: List[Dict[str, str]]  # annotation_id -> error

@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_annotation_operation(
    repository_name: str,
    request: BulkAnnotationOperation,
    current_user: User = Depends(get_current_user)
) -> BulkOperationResponse:
    """Perform bulk operations on annotations"""

    repository = await _get_user_repository(repository_name, current_user)

    successful_operations = []
    failed_operations = []

    for annotation_id in request.annotation_ids:
        try:
            if request.action == "resolve":
                await annotation_service.resolve_annotation(
                    annotation_id=annotation_id,
                    action=request.parameters.get("resolution_action", "resolve"),
                    message=request.parameters.get("message", "Bulk resolution"),
                    resolved_by=current_user.id
                )
            elif request.action == "delete":
                await annotation_service.delete_annotation(
                    annotation_id=annotation_id,
                    deleted_by=current_user.id
                )
            elif request.action == "assign":
                await annotation_service.assign_annotation(
                    annotation_id=annotation_id,
                    assigned_to=request.parameters.get("assigned_to"),
                    assigned_by=current_user.id
                )

            successful_operations.append(annotation_id)

        except Exception as e:
            failed_operations.append({
                "annotation_id": annotation_id,
                "error": str(e)
            })

    return BulkOperationResponse(
        success=len(failed_operations) == 0,
        processed_count=len(successful_operations),
        failed_count=len(failed_operations),
        successful_operations=successful_operations,
        failed_operations=failed_operations
    )
```

### 5. Analytics and Statistics

```python
class AnnotationStatistics(BaseModel):
    """Statistics about annotations in repository"""
    total_annotations: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_priority: Dict[str, int]

    # Activity metrics
    annotations_this_week: int
    annotations_this_month: int
    resolution_rate: float
    avg_resolution_time_hours: float

    # Collaboration metrics
    active_reviewers: int
    most_active_reviewer: Optional[str]
    most_annotated_file: Optional[str]

@router.get("/statistics", response_model=AnnotationStatistics)
async def get_annotation_statistics(
    repository_name: str,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user)
) -> AnnotationStatistics:
    """Get annotation statistics for the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        stats = await annotation_service.get_statistics(
            repository_id=repository.id,
            since=since,
            until=until
        )

        return stats

    except Exception as e:
        logger.error(f"Failed to get annotation statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve annotation statistics"
        )
```

---

*The Annotations API provides comprehensive feedback management capabilities, enabling structured collaboration workflows while maintaining version control integration and user access controls. The system supports complex review processes while remaining accessible to non-technical writers.*