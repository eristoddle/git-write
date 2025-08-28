# API Gateway with FastAPI

GitWrite's API Gateway is built with FastAPI, serving as the central communication hub between all client interfaces (web, CLI, SDK) and the core business logic. The gateway handles authentication, validation, routing, and response formatting while maintaining high performance and type safety.

## Architecture Overview

The API Gateway follows a router-based architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────┐
│                API Gateway                  │
│  ┌─────────────────────────────────────────┐│
│  │           FastAPI Application           ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐   ││
│  │  │ Auth    │ │ Repo    │ │ Upload  │   ││
│  │  │ Router  │ │ Router  │ │ Router  │   ││
│  │  └─────────┘ └─────────┘ └─────────┘   ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐   ││
│  │  │ Anno    │ │ Export  │ │ Tags    │   ││
│  │  │ Router  │ │ Router  │ │ Router  │   ││
│  │  └─────────┘ └─────────┘ └─────────┘   ││
│  └─────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────┐│
│  │              Middleware                 ││
│  │  • CORS     • Auth      • Validation   ││
│  │  • Logging  • Rate Limit • Error Hand  ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

## Core Components

### 1. Application Configuration (`main.py`)

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .routers import auth, repository, annotations, uploads
from .security import get_current_user

app = FastAPI(
    title="GitWrite API",
    description="Version control platform for writers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration for web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://gitwrite.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "*.gitwrite.app"]
)

# Router registration
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(repository.router, prefix="/repositories", tags=["repositories"])
app.include_router(annotations.router, prefix="/annotations", tags=["annotations"])
app.include_router(uploads.router, prefix="/uploads", tags=["files"])

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    return {"status": "healthy", "service": "gitwrite-api"}
```

### 2. Router Architecture

Each router handles a specific domain of functionality:

#### Authentication Router (`auth.py`)
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from datetime import timedelta

from ..models import UserLogin, UserCreate, Token
from ..security import authenticate_user, create_access_token

router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """
    Authenticate user and return JWT token

    Returns:
        JWT token with expiration and user information
    """
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(hours=24)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=86400,
        user=user
    )

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate):
    """Register new user account"""
    # Implementation handles user creation and initial token
    pass
```

#### Repository Router (`repository.py`)
```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional

from ..models import RepositoryCreate, RepositoryInfo, CommitInfo, BranchInfo
from ..security import get_current_user
from gitwrite_core import repository, versioning, branching

router = APIRouter()

@router.post("/", response_model=RepositoryInfo)
async def create_repository(
    repo_data: RepositoryCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Initialize a new GitWrite project

    Args:
        repo_data: Repository configuration and metadata
        current_user: Authenticated user (from JWT token)

    Returns:
        Repository information and initial status
    """
    try:
        repo_path = repository.initialize_repository(
            name=repo_data.name,
            description=repo_data.description,
            owner=current_user.username,
            template=repo_data.template
        )

        return RepositoryInfo(
            name=repo_data.name,
            path=repo_path,
            owner=current_user.username,
            created_at=datetime.utcnow(),
            status="initialized"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create repository: {str(e)}"
        )

@router.get("/{repo_name}/commits", response_model=List[CommitInfo])
async def get_commit_history(
    repo_name: str,
    limit: int = 50,
    branch: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get project history (Git commit log)

    Args:
        repo_name: Project name
        limit: Maximum number of commits to return
        branch: Specific exploration to examine (optional)

    Returns:
        List of save points (commits) with descriptions
    """
    try:
        commits = versioning.get_commit_history(
            repository_name=repo_name,
            user=current_user.username,
            limit=limit,
            branch=branch
        )

        return [
            CommitInfo(
                id=commit.id,
                message=commit.message,
                author=commit.author.name,
                timestamp=commit.committed_date,
                files_changed=commit.stats.files_changed
            )
            for commit in commits
        ]
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Could not retrieve history: {str(e)}"
        )

@router.post("/{repo_name}/save", response_model=CommitInfo)
async def save_changes(
    repo_name: str,
    save_data: SaveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Save changes to the project (Git commit)

    Args:
        repo_name: Project name
        save_data: Files and description of changes
        background_tasks: For async operations like notifications

    Returns:
        Information about the save operation
    """
    try:
        commit_result = versioning.save_changes(
            repository_name=repo_name,
            user=current_user.username,
            message=save_data.message,
            files=save_data.files
        )

        # Background task for notifications
        background_tasks.add_task(
            notify_collaborators,
            repo_name,
            current_user.username,
            "changes_saved"
        )

        return CommitInfo(
            id=commit_result.commit_id,
            message=save_data.message,
            author=current_user.username,
            timestamp=datetime.utcnow(),
            files_changed=len(save_data.files or [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not save changes: {str(e)}"
        )
```

### 3. Data Models (`models.py`)

Pydantic models ensure type safety and automatic validation:

```python
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    """User roles in GitWrite system"""
    OWNER = "owner"
    EDITOR = "editor"
    WRITER = "writer"
    BETA_READER = "beta_reader"

class User(BaseModel):
    """User information model"""
    username: str
    email: str
    role: UserRole
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(BaseModel):
    """User registration model"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

    @validator('username')
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'Username must be alphanumeric'
        return v

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str
    expires_in: int
    user: User

class RepositoryCreate(BaseModel):
    """Repository creation model"""
    name: str
    description: Optional[str] = None
    template: Optional[str] = "novel"  # novel, article, screenplay, etc.
    is_private: bool = True

    @validator('name')
    def name_validation(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Repository name must contain only letters, numbers, hyphens, and underscores')
        return v

class SaveRequest(BaseModel):
    """Save operation request model"""
    message: str
    files: Optional[List[str]] = None

    @validator('message')
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Save message cannot be empty')
        return v.strip()

class CommitInfo(BaseModel):
    """Commit information model"""
    id: str
    message: str
    author: str
    timestamp: datetime
    files_changed: int
    short_id: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.short_id = self.id[:8] if self.id else None
```

### 4. Security Layer (`security.py`)

JWT-based authentication with role-based access control:

```python
from datetime import datetime, timedelta
from typing import Optional
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Configuration
SECRET_KEY = "your-secret-key"  # Should be environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password for storage"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Extract current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    user = get_user_by_username(username)  # Database lookup
    if user is None:
        raise credentials_exception
    return user

def require_role(required_role: UserRole):
    """Decorator to require specific user role"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in get_role_hierarchy(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def get_role_hierarchy(role: UserRole) -> List[UserRole]:
    """Get roles that have equal or greater permissions"""
    hierarchy = {
        UserRole.BETA_READER: [UserRole.BETA_READER, UserRole.WRITER, UserRole.EDITOR, UserRole.OWNER],
        UserRole.WRITER: [UserRole.WRITER, UserRole.EDITOR, UserRole.OWNER],
        UserRole.EDITOR: [UserRole.EDITOR, UserRole.OWNER],
        UserRole.OWNER: [UserRole.OWNER]
    }
    return hierarchy.get(role, [])
```

### 5. Error Handling Middleware

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code
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
            "error": {
                "type": "internal_error",
                "message": "An unexpected error occurred",
                "suggestion": "Please try again or contact support if the problem persists"
            }
        }
    )
```

## Performance Features

### 1. Background Tasks
```python
from fastapi import BackgroundTasks

@router.post("/{repo_name}/export")
async def export_document(
    repo_name: str,
    export_config: ExportConfig,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Start document export in background"""
    export_id = generate_export_id()

    background_tasks.add_task(
        process_export,
        repo_name,
        export_config,
        export_id,
        current_user.username
    )

    return {"export_id": export_id, "status": "processing"}
```

### 2. Caching Strategy
```python
from functools import lru_cache
import redis

# Redis for distributed caching
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@lru_cache(maxsize=100)
def get_repository_info(repo_name: str, user: str):
    """Cache repository information"""
    cache_key = f"repo:{repo_name}:{user}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Fetch from core module
    repo_info = repository.get_repository_info(repo_name, user)
    redis_client.setex(cache_key, 300, json.dumps(repo_info))  # 5 min cache

    return repo_info
```

### 3. Rate Limiting
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/save")
@limiter.limit("10/minute")  # Max 10 saves per minute
async def save_changes(request: Request, ...):
    """Rate-limited save operation"""
    pass
```

## API Documentation

FastAPI automatically generates interactive documentation:

- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI Schema**: Available at `/openapi.json`

The documentation includes:
- Request/response schemas
- Authentication requirements
- Example requests and responses
- Error codes and descriptions

---

*The FastAPI gateway provides a robust, high-performance foundation for GitWrite's API layer while maintaining type safety, security, and excellent developer experience through automatic documentation generation.*