# Repository Operations

GitWrite's repository operations API provides comprehensive endpoints for managing Git repositories through a writer-friendly interface. These endpoints abstract Git's complexity while providing full access to version control functionality.

## Overview

The repository operations API handles:
- Repository initialization and configuration
- File operations and content management
- Version control operations (save, history, status)
- Branch/exploration management
- Collaboration and permission management

```
API Endpoints Architecture
    │
    ├─ /repositories/ (Repository CRUD)
    ├─ /repositories/{name}/save (Version Control)
    ├─ /repositories/{name}/history (Change History)
    ├─ /repositories/{name}/status (Current State)
    ├─ /repositories/{name}/explorations/ (Branching)
    └─ /repositories/{name}/collaborators/ (Team Management)
```

## Core Endpoints

### 1. Repository Management

```python
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter(prefix="/repositories", tags=["repositories"])

class CreateRepositoryRequest(BaseModel):
    """Request model for creating a new repository"""
    name: str = Field(..., min_length=1, max_length=100, regex="^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(None, max_length=500)
    type: str = Field("novel", regex="^(novel|short-story|article|screenplay|academic|poetry)$")
    template: Optional[str] = Field(None, max_length=50)
    collaboration_enabled: bool = Field(True)
    is_private: bool = Field(False)

    class Config:
        schema_extra = {
            "example": {
                "name": "my-novel",
                "description": "A thrilling science fiction adventure",
                "type": "novel",
                "collaboration_enabled": True,
                "is_private": False
            }
        }

class RepositoryResponse(BaseModel):
    """Response model for repository information"""
    id: str
    name: str
    description: Optional[str]
    type: str
    owner: str
    created_at: datetime
    updated_at: datetime
    status: str  # active, archived, draft

    # Statistics
    word_count: int
    file_count: int
    save_count: int
    exploration_count: int

    # Configuration
    collaboration_enabled: bool
    is_private: bool
    default_exploration: str

    # Collaboration
    collaborator_count: int
    pending_invitations: int

    class Config:
        schema_extra = {
            "example": {
                "id": "repo_123",
                "name": "my-novel",
                "description": "A thrilling science fiction adventure",
                "type": "novel",
                "owner": "jane@writer.com",
                "created_at": "2023-11-15T10:30:00Z",
                "updated_at": "2023-11-20T14:45:00Z",
                "status": "active",
                "word_count": 25000,
                "file_count": 15,
                "save_count": 47,
                "exploration_count": 3,
                "collaboration_enabled": True,
                "is_private": False,
                "default_exploration": "main",
                "collaborator_count": 2,
                "pending_invitations": 1
            }
        }

@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    request: CreateRepositoryRequest,
    current_user: User = Depends(get_current_user)
) -> RepositoryResponse:
    """Create a new writing repository"""

    try:
        # Check if repository name already exists for user
        if await repository_service.exists(request.name, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Repository '{request.name}' already exists"
            )

        # Create repository
        repository = await repository_service.create_repository(
            name=request.name,
            description=request.description,
            owner_id=current_user.id,
            repository_type=request.type,
            template=request.template,
            collaboration_enabled=request.collaboration_enabled,
            is_private=request.is_private
        )

        # Initialize Git repository
        git_result = await git_service.initialize_repository(
            repository.id,
            request.template
        )

        if not git_result.success:
            await repository_service.delete_repository(repository.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Git repository: {git_result.error}"
            )

        # Convert to response model
        return await _convert_to_repository_response(repository)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create repository: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create repository"
        )

@router.get("/", response_model=List[RepositoryResponse])
async def list_repositories(
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    limit: int = Field(50, ge=1, le=100),
    offset: int = Field(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[RepositoryResponse]:
    """List user's repositories with filtering and pagination"""

    try:
        repositories = await repository_service.list_user_repositories(
            user_id=current_user.id,
            status_filter=status_filter,
            type_filter=type_filter,
            limit=limit,
            offset=offset
        )

        return [
            await _convert_to_repository_response(repo)
            for repo in repositories
        ]

    except Exception as e:
        logger.error(f"Failed to list repositories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve repositories"
        )

@router.get("/{repository_name}", response_model=RepositoryResponse)
async def get_repository(
    repository_name: str,
    current_user: User = Depends(get_current_user)
) -> RepositoryResponse:
    """Get detailed information about a specific repository"""

    repository = await _get_user_repository(repository_name, current_user)
    return await _convert_to_repository_response(repository)
```

### 2. Version Control Operations

```python
class SaveRequest(BaseModel):
    """Request model for saving changes"""
    message: str = Field(..., min_length=1, max_length=200)
    files: Optional[List[str]] = Field(None, description="Specific files to save (optional)")
    auto_stage: bool = Field(True, description="Automatically stage modified files")
    create_tag: Optional[str] = Field(None, description="Create tag for this save")

    class Config:
        schema_extra = {
            "example": {
                "message": "Completed chapter 3 - the big revelation",
                "files": ["chapters/chapter3.md", "outline.md"],
                "auto_stage": True,
                "create_tag": "chapter3-complete"
            }
        }

class SaveResponse(BaseModel):
    """Response model for save operations"""
    success: bool
    save_id: str  # Git commit hash
    message: str
    files_saved: List[str]
    word_count_change: int
    total_word_count: int
    timestamp: datetime
    exploration: str
    tag_created: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "save_id": "a1b2c3d4",
                "message": "Completed chapter 3 - the big revelation",
                "files_saved": ["chapters/chapter3.md", "outline.md"],
                "word_count_change": 847,
                "total_word_count": 15432,
                "timestamp": "2023-11-20T14:45:00Z",
                "exploration": "main",
                "tag_created": "chapter3-complete"
            }
        }

@router.post("/{repository_name}/save", response_model=SaveResponse)
async def save_changes(
    repository_name: str,
    request: SaveRequest,
    current_user: User = Depends(get_current_user)
) -> SaveResponse:
    """Save changes to the repository (Git commit)"""

    repository = await _get_user_repository(repository_name, current_user)

    # Check write permissions
    if not await permission_service.can_write(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to save changes"
        )

    try:
        # Perform the save operation
        save_result = await git_service.save_changes(
            repository_id=repository.id,
            message=request.message,
            files=request.files,
            auto_stage=request.auto_stage,
            author_name=current_user.name,
            author_email=current_user.email
        )

        if not save_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Save failed: {save_result.error}"
            )

        # Create tag if requested
        tag_created = None
        if request.create_tag:
            tag_result = await git_service.create_tag(
                repository_id=repository.id,
                tag_name=request.create_tag,
                commit_id=save_result.commit_id,
                message=f"Tag: {request.create_tag}",
                tagger_name=current_user.name,
                tagger_email=current_user.email
            )
            if tag_result.success:
                tag_created = request.create_tag

        # Update repository statistics
        await repository_service.update_statistics(repository.id)

        # Notify collaborators
        await notification_service.notify_collaborators_of_save(
            repository.id,
            current_user.id,
            save_result
        )

        return SaveResponse(
            success=True,
            save_id=save_result.commit_id[:8],
            message=request.message,
            files_saved=save_result.files_changed,
            word_count_change=save_result.word_count_change,
            total_word_count=save_result.total_word_count,
            timestamp=datetime.utcnow(),
            exploration=save_result.current_branch,
            tag_created=tag_created
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save operation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Save operation failed"
        )

class RepositoryStatus(BaseModel):
    """Repository status information"""
    is_clean: bool
    current_exploration: str
    modified_files: List[str]
    new_files: List[str]
    deleted_files: List[str]
    staged_files: List[str]
    conflicted_files: List[str]
    untracked_files: List[str]

    # Statistics
    uncommitted_word_count_change: int
    last_save_id: Optional[str]
    last_save_message: Optional[str]
    last_save_timestamp: Optional[datetime]

    class Config:
        schema_extra = {
            "example": {
                "is_clean": False,
                "current_exploration": "main",
                "modified_files": ["chapters/chapter1.md"],
                "new_files": ["characters/villain.md"],
                "deleted_files": [],
                "staged_files": [],
                "conflicted_files": [],
                "untracked_files": ["notes/research.md"],
                "uncommitted_word_count_change": 234,
                "last_save_id": "a1b2c3d4",
                "last_save_message": "Updated character development",
                "last_save_timestamp": "2023-11-20T10:30:00Z"
            }
        }

@router.get("/{repository_name}/status", response_model=RepositoryStatus)
async def get_repository_status(
    repository_name: str,
    current_user: User = Depends(get_current_user)
) -> RepositoryStatus:
    """Get current repository status"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        status_result = await git_service.get_repository_status(repository.id)

        return RepositoryStatus(
            is_clean=status_result.is_clean,
            current_exploration=status_result.current_branch,
            modified_files=status_result.modified_files,
            new_files=status_result.new_files,
            deleted_files=status_result.deleted_files,
            staged_files=status_result.staged_files,
            conflicted_files=status_result.conflicted_files,
            untracked_files=status_result.untracked_files,
            uncommitted_word_count_change=status_result.word_count_change,
            last_save_id=status_result.last_commit_id,
            last_save_message=status_result.last_commit_message,
            last_save_timestamp=status_result.last_commit_timestamp
        )

    except Exception as e:
        logger.error(f"Failed to get repository status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve repository status"
        )
```

### 3. History and Timeline

```python
class HistoryEntry(BaseModel):
    """Single entry in repository history"""
    save_id: str
    short_id: str
    message: str
    author: str
    timestamp: datetime
    exploration: str

    # File changes
    files_changed: List[str]
    files_added: int
    files_modified: int
    files_deleted: int

    # Content changes
    word_count_change: int
    lines_added: int
    lines_deleted: int

    # Metadata
    tags: List[str]
    is_merge: bool
    parent_saves: List[str]

class HistoryResponse(BaseModel):
    """Repository history response"""
    entries: List[HistoryEntry]
    total_count: int
    has_more: bool
    next_offset: Optional[int]

@router.get("/{repository_name}/history", response_model=HistoryResponse)
async def get_repository_history(
    repository_name: str,
    limit: int = Field(20, ge=1, le=100),
    offset: int = Field(0, ge=0),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    author: Optional[str] = None,
    exploration: Optional[str] = None,
    file_path: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> HistoryResponse:
    """Get repository history with filtering options"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        history_result = await git_service.get_repository_history(
            repository_id=repository.id,
            limit=limit + 1,  # Get one extra to check if there are more
            offset=offset,
            since=since,
            until=until,
            author=author,
            branch=exploration,
            file_path=file_path
        )

        # Check if there are more entries
        has_more = len(history_result.entries) > limit
        if has_more:
            history_result.entries = history_result.entries[:-1]

        return HistoryResponse(
            entries=history_result.entries,
            total_count=history_result.total_count,
            has_more=has_more,
            next_offset=offset + limit if has_more else None
        )

    except Exception as e:
        logger.error(f"Failed to get repository history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve repository history"
        )
```

### 4. Exploration Management

```python
class CreateExplorationRequest(BaseModel):
    """Request to create new exploration"""
    name: str = Field(..., min_length=1, max_length=50, regex="^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(None, max_length=200)
    from_save: Optional[str] = Field(None, description="Start from specific save ID")
    auto_switch: bool = Field(True, description="Switch to exploration after creation")

class ExplorationResponse(BaseModel):
    """Exploration information"""
    name: str
    description: Optional[str]
    created_at: datetime
    last_modified: datetime
    creator: str
    current_save_id: str
    saves_ahead: int
    saves_behind: int
    word_count_difference: int
    status: str  # active, merged, abandoned

@router.post("/{repository_name}/explorations", response_model=ExplorationResponse)
async def create_exploration(
    repository_name: str,
    request: CreateExplorationRequest,
    current_user: User = Depends(get_current_user)
) -> ExplorationResponse:
    """Create a new exploration (Git branch)"""

    repository = await _get_user_repository(repository_name, current_user)

    if not await permission_service.can_write(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create exploration"
        )

    try:
        exploration_result = await git_service.create_exploration(
            repository_id=repository.id,
            name=request.name,
            description=request.description,
            from_commit=request.from_save,
            creator_name=current_user.name,
            creator_email=current_user.email,
            auto_switch=request.auto_switch
        )

        if not exploration_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create exploration: {exploration_result.error}"
            )

        return ExplorationResponse(
            name=request.name,
            description=request.description,
            created_at=datetime.utcnow(),
            last_modified=datetime.utcnow(),
            creator=current_user.name,
            current_save_id=exploration_result.commit_id,
            saves_ahead=0,
            saves_behind=0,
            word_count_difference=0,
            status="active"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create exploration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create exploration"
        )

@router.get("/{repository_name}/explorations", response_model=List[ExplorationResponse])
async def list_explorations(
    repository_name: str,
    include_merged: bool = Field(False),
    current_user: User = Depends(get_current_user)
) -> List[ExplorationResponse]:
    """List all explorations in repository"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        explorations = await git_service.list_explorations(
            repository_id=repository.id,
            include_merged=include_merged
        )

        return explorations

    except Exception as e:
        logger.error(f"Failed to list explorations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list explorations"
        )
```

### 5. Utility Functions

```python
async def _get_user_repository(
    repository_name: str,
    user: User
) -> Repository:
    """Get repository with access validation"""

    repository = await repository_service.get_by_name(repository_name, user.id)

    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_name}' not found"
        )

    # Check read permissions
    if not await permission_service.can_read(repository.id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access repository"
        )

    return repository

async def _convert_to_repository_response(
    repository: Repository
) -> RepositoryResponse:
    """Convert repository model to API response"""

    # Get repository statistics
    stats = await repository_service.get_statistics(repository.id)

    # Get collaboration info
    collab_info = await collaboration_service.get_collaboration_info(repository.id)

    return RepositoryResponse(
        id=repository.id,
        name=repository.name,
        description=repository.description,
        type=repository.type,
        owner=repository.owner.email,
        created_at=repository.created_at,
        updated_at=repository.updated_at,
        status=repository.status,
        word_count=stats.word_count,
        file_count=stats.file_count,
        save_count=stats.commit_count,
        exploration_count=stats.branch_count,
        collaboration_enabled=repository.collaboration_enabled,
        is_private=repository.is_private,
        default_exploration=repository.default_branch,
        collaborator_count=collab_info.collaborator_count,
        pending_invitations=collab_info.pending_invitations
    )
```

## Error Handling

```python
from fastapi import HTTPException, status

class RepositoryAPIError(HTTPException):
    """Base class for repository API errors"""
    pass

class RepositoryNotFoundError(RepositoryAPIError):
    def __init__(self, repository_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_name}' not found"
        )

class RepositoryAlreadyExistsError(RepositoryAPIError):
    def __init__(self, repository_name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository '{repository_name}' already exists"
        )

class InsufficientPermissionsError(RepositoryAPIError):
    def __init__(self, action: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action}"
        )

class GitOperationError(RepositoryAPIError):
    def __init__(self, operation: str, details: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Git operation '{operation}' failed: {details}"
        )
```

## Rate Limiting and Security

```python
from fastapi_limiter.depends import RateLimiter

# Apply rate limiting to write operations
@router.post("/{repository_name}/save")
@rate_limit("10/minute")  # 10 saves per minute
async def save_changes(...):
    pass

# Apply stricter limits to repository creation
@router.post("/")
@rate_limit("5/hour")  # 5 new repositories per hour
async def create_repository(...):
    pass

# Input validation and sanitization
def validate_repository_name(name: str) -> str:
    """Validate and sanitize repository name"""
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError("Repository name contains invalid characters")
    if len(name) > 100:
        raise ValueError("Repository name too long")
    return name.lower()
```

---

*The Repository Operations API provides a comprehensive interface for managing GitWrite repositories, abstracting Git complexity while maintaining full version control functionality. All endpoints include proper error handling, validation, and security measures.*