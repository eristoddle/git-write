# Backend API (FastAPI)

The GitWrite Backend API provides a comprehensive REST interface built with FastAPI that exposes all GitWrite functionality to client applications. The API emphasizes type safety, automatic documentation, and writer-friendly abstractions while maintaining full Git compatibility.

## API Overview

### Design Principles

**RESTful Architecture**: The API follows REST principles with clear resource-based URLs, appropriate HTTP methods, and standardized response formats.

**Type Safety**: Every endpoint uses Pydantic models for request/response validation, ensuring data integrity and providing automatic API documentation.

**Writer-Centric**: API endpoints use writer-friendly terminology and concepts rather than Git-specific language.

**Authentication**: JWT-based authentication with role-based access control for collaboration features.

**Performance**: Async/await throughout for optimal performance, with caching and optimization for large repositories.

### API Structure

```
/api/v1/
├── auth/                    # Authentication and user management
│   ├── login               # User authentication
│   ├── register            # User registration
│   ├── refresh             # Token refresh
│   └── logout              # Session termination
├── repositories/            # Repository operations
│   ├── /                   # List/create repositories
│   ├── /{repo}/            # Repository details
│   ├── /{repo}/save        # Save changes (commit)
│   ├── /{repo}/history     # Commit history
│   ├── /{repo}/status      # Repository status
│   └── /{repo}/files/      # File operations
├── explorations/           # Branch management (explorations)
│   ├── /{repo}/            # List/create explorations
│   ├── /{repo}/{name}/     # Exploration operations
│   ├── /{repo}/{name}/switch # Switch exploration
│   └── /{repo}/{name}/merge  # Merge exploration
├── annotations/            # Feedback and comments
│   ├── /{repo}/            # List/add annotations
│   ├── /{repo}/{id}        # Annotation details
│   └── /{repo}/{id}/resolve # Resolve annotation
├── export/                 # Document generation
│   ├── /{repo}/epub        # Export to EPUB
│   ├── /{repo}/pdf         # Export to PDF
│   ├── /{repo}/docx        # Export to Word
│   └── /status/{export_id} # Export status
├── collaboration/          # Team features
│   ├── /{repo}/invite      # Invite collaborators
│   ├── /{repo}/permissions # Manage permissions
│   └── /{repo}/members     # List team members
└── uploads/                # File upload handling
    ├── /                   # Upload files
    └── /{upload_id}        # Upload status
```

### Response Format

All API responses follow a consistent format:

**Successful Response:**
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "metadata": {
    "timestamp": "2023-12-01T10:30:00Z",
    "request_id": "req_123456",
    "version": "1.0.0"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "REPOSITORY_NOT_FOUND",
    "message": "The specified repository was not found",
    "details": {
      "repository": "my-novel",
      "suggestions": [
        "Check the repository name spelling",
        "Ensure you have access to this repository"
      ]
    }
  },
  "metadata": {
    "timestamp": "2023-12-01T10:30:00Z",
    "request_id": "req_123456"
  }
}
```

## Base Configuration

### FastAPI Application Setup

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer

app = FastAPI(
    title="GitWrite API",
    description="Version control platform for writers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://gitwrite.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["gitwrite.app", "*.gitwrite.app", "localhost"]
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(repository.router, prefix="/api/v1/repositories", tags=["Repositories"])
app.include_router(annotations.router, prefix="/api/v1/annotations", tags=["Annotations"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["File Uploads"])
```

### Common Models

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class APIResponse(BaseModel):
    """Base response model for all API endpoints"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UserRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    WRITER = "writer"
    BETA_READER = "beta_reader"

class User(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    avatar_url: Optional[str] = None
    created_at: datetime
    last_active: Optional[datetime] = None

class Repository(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner: str
    type: str = Field(default="novel", description="Project type")
    created_at: datetime
    updated_at: datetime
    status: str = Field(default="active")
    collaboration_enabled: bool = False
    default_exploration: str = "main"
    word_count: int = 0
    file_count: int = 0

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Repository name cannot be empty')
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Repository name must contain only letters, numbers, hyphens, and underscores')
        return v.strip().lower()

class CommitInfo(BaseModel):
    id: str
    short_id: str = Field(description="Short commit hash")
    message: str
    author: Dict[str, str]
    timestamp: datetime
    files_changed: int
    insertions: int = 0
    deletions: int = 0
    exploration: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
```

## Error Handling

### Exception Hierarchy

```python
from fastapi import HTTPException
from typing import List, Optional

class GitWriteAPIException(HTTPException):
    """Base exception for GitWrite API errors"""
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict] = None,
        suggestions: Optional[List[str]] = None
    ):
        self.error_code = error_code
        self.suggestions = suggestions or []

        detail = {
            "code": error_code,
            "message": message,
            "details": details or {},
            "suggestions": self.suggestions
        }
        super().__init__(status_code=status_code, detail=detail)

class RepositoryNotFoundError(GitWriteAPIException):
    def __init__(self, repository_name: str):
        super().__init__(
            status_code=404,
            error_code="REPOSITORY_NOT_FOUND",
            message=f"Repository '{repository_name}' was not found",
            details={"repository": repository_name},
            suggestions=[
                "Check the repository name spelling",
                "Ensure you have access to this repository",
                "Contact the repository owner if you believe you should have access"
            ]
        )

class ValidationError(GitWriteAPIException):
    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message=f"Validation failed for field '{field}': {message}",
            details={"field": field, "validation_message": message}
        )

class ConflictError(GitWriteAPIException):
    def __init__(self, message: str, conflicted_files: List[str] = None):
        super().__init__(
            status_code=409,
            error_code="MERGE_CONFLICT",
            message=message,
            details={"conflicted_files": conflicted_files or []},
            suggestions=[
                "Review the conflicting sections",
                "Choose which version to keep",
                "Or combine both versions creatively"
            ]
        )
```

### Global Error Handlers

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from gitwrite_core.exceptions import GitWriteError
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(GitWriteAPIException)
async def gitwrite_api_exception_handler(request: Request, exc: GitWriteAPIException):
    """Handle GitWrite-specific API exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, "request_id", "unknown"),
                "path": request.url.path
            }
        }
    )

@app.exception_handler(GitWriteError)
async def gitwrite_core_exception_handler(request: Request, exc: GitWriteError):
    """Handle core GitWrite exceptions"""
    logger.error(f"Core GitWrite error: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "CORE_ERROR",
                "message": str(exc),
                "suggestions": getattr(exc, "suggestions", [])
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, "request_id", "unknown")
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "suggestions": [
                    "Try the request again",
                    "Contact support if the problem persists"
                ]
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, "request_id", "unknown")
            }
        }
    )
```

## Middleware

### Request/Response Middleware

```python
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Add request tracking and timing"""

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Add request headers
        request.state.user_agent = request.headers.get("user-agent", "unknown")
        request.state.client_ip = request.client.host

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        # Log request
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"-> {response.status_code} ({process_time:.3f}s)"
        )

        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()

        # Clean old entries
        self.clients = {
            ip: times for ip, times in self.clients.items()
            if times and times[-1] > now - self.period
        }

        # Check rate limit
        if client_ip in self.clients:
            calls_in_period = [t for t in self.clients[client_ip] if t > now - self.period]
            if len(calls_in_period) >= self.calls:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded: {self.calls} calls per {self.period} seconds",
                            "retry_after": self.period
                        }
                    }
                )
            self.clients[client_ip] = calls_in_period + [now]
        else:
            self.clients[client_ip] = [now]

        return await call_next(request)

# Apply middleware
app.add_middleware(RequestTrackingMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)
```

## API Documentation

### OpenAPI Configuration

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="GitWrite API",
        version="1.0.0",
        description="""
        ## GitWrite API

        The GitWrite API provides version control capabilities specifically designed for writers.

        ### Key Features
        - **Writer-Friendly**: Uses familiar writing terminology instead of Git concepts
        - **Collaboration**: Built-in support for editors, beta readers, and team workflows
        - **Type Safety**: Full TypeScript support with automatic client generation
        - **Export**: Generate professional documents in multiple formats

        ### Authentication
        Most endpoints require authentication using JWT tokens. Include the token in the Authorization header:
        ```
        Authorization: Bearer your-jwt-token
        ```

        ### Rate Limiting
        - 100 requests per minute per IP address
        - 1000 requests per hour for authenticated users
        - 10,000 requests per day for premium accounts

        ### Support
        - Documentation: https://docs.gitwrite.com
        - Community: https://community.gitwrite.com
        - Support: support@gitwrite.com
        """,
        routes=app.routes,
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    # Add examples
    openapi_schema["components"]["examples"] = {
        "RepositoryCreate": {
            "summary": "Create a novel project",
            "value": {
                "name": "my-great-novel",
                "description": "A thrilling adventure story",
                "type": "novel",
                "collaboration_enabled": True
            }
        },
        "SaveChanges": {
            "summary": "Save chapter updates",
            "value": {
                "message": "Completed chapter 3 - the revelation scene",
                "files": ["chapters/chapter3.md"],
                "tag": "chapter3-complete"
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### Automatic Documentation Features

**Interactive API Explorer**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)

**Schema Generation**: Automatic OpenAPI 3.0 schema generation from type hints

**Example Generation**: Automatic request/response examples from Pydantic models

**Client Generation**: Support for generating clients in multiple languages

## Performance Optimizations

### Caching Strategy

```python
from functools import lru_cache
import redis
import json
from typing import Optional

# Redis for distributed caching
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@lru_cache(maxsize=128)
def get_repository_info_cached(repo_name: str, user_id: str) -> Optional[Dict]:
    """Cache repository information"""
    cache_key = f"repo:{repo_name}:{user_id}"

    # Try Redis first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch from database/core
    repo_info = get_repository_info(repo_name, user_id)
    if repo_info:
        # Cache for 5 minutes
        redis_client.setex(cache_key, 300, json.dumps(repo_info))

    return repo_info

class CacheMiddleware(BaseHTTPMiddleware):
    """Response caching middleware"""

    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Generate cache key
        cache_key = f"response:{request.url}"

        # Check cache
        cached_response = redis_client.get(cache_key)
        if cached_response:
            data = json.loads(cached_response)
            return JSONResponse(
                content=data["content"],
                status_code=data["status_code"],
                headers={"X-Cache": "HIT"}
            )

        # Process request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            response_data = {
                "content": response.body.decode(),
                "status_code": response.status_code
            }
            redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(response_data)
            )
            response.headers["X-Cache"] = "MISS"

        return response
```

### Background Tasks

```python
from fastapi import BackgroundTasks
import asyncio

async def send_notification_email(user_email: str, message: str):
    """Send notification email in background"""
    # Email sending logic
    await asyncio.sleep(1)  # Simulate email service call
    logger.info(f"Notification sent to {user_email}")

async def process_export_job(export_id: str, repo_name: str, format: str):
    """Process document export in background"""
    try:
        # Update export status
        update_export_status(export_id, "processing")

        # Generate document
        result = await generate_document(repo_name, format)

        # Update with success
        update_export_status(export_id, "completed", download_url=result.url)

    except Exception as e:
        logger.error(f"Export failed: {e}")
        update_export_status(export_id, "failed", error=str(e))

@router.post("/{repo_name}/save")
async def save_changes(
    repo_name: str,
    save_data: SaveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Save changes with background notifications"""

    result = await save_repository_changes(repo_name, save_data, current_user)

    if result.success:
        # Send notifications in background
        background_tasks.add_task(
            send_notification_email,
            current_user.email,
            f"Changes saved to {repo_name}"
        )

        # Notify collaborators
        collaborators = await get_repository_collaborators(repo_name)
        for collaborator in collaborators:
            background_tasks.add_task(
                send_notification_email,
                collaborator.email,
                f"{current_user.username} updated {repo_name}"
            )

    return result
```

---

*The GitWrite Backend API provides a robust, well-documented, and writer-friendly interface to all GitWrite functionality, built with modern FastAPI features and optimized for performance and reliability.*