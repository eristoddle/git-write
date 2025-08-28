# Authentication

The GitWrite Authentication system provides secure user management with JWT-based authentication, role-based access control, and support for both local accounts and OAuth providers. The system is designed to be secure, scalable, and user-friendly.

## Authentication Overview

### Authentication Flow

```mermaid
sequenceDiagram
    participant User as User
    participant Client as Client App
    participant API as GitWrite API
    participant Core as GitWrite Core

    User->>Client: Enter credentials
    Client->>API: POST /auth/login
    API->>Core: Validate credentials
    Core-->>API: User data
    API-->>Client: JWT token + refresh token
    Client->>API: API requests with JWT
    API->>API: Validate JWT
    API-->>Client: Protected resource

    Note over Client,API: Token expires
    Client->>API: POST /auth/refresh
    API-->>Client: New JWT token
```

### Security Features

- **JWT Tokens**: Stateless authentication with configurable expiration
- **Refresh Tokens**: Secure token renewal without re-authentication
- **Role-Based Access Control**: Fine-grained permissions for collaboration
- **Password Security**: bcrypt hashing with salt rounds
- **Rate Limiting**: Protection against brute force attacks
- **OAuth Integration**: Support for GitHub, Google, and other providers

## Authentication Endpoints

### POST /auth/login

Authenticate user with email/username and password.

**Request Body:**
```json
{
  "username": "writer@example.com",
  "password": "secure_password",
  "remember_me": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "usr_123456",
      "username": "writer@example.com",
      "email": "writer@example.com",
      "full_name": "Jane Writer",
      "role": "writer",
      "avatar_url": "https://avatars.example.com/writer.jpg",
      "created_at": "2023-01-15T10:30:00Z",
      "last_active": "2023-12-01T14:20:00Z"
    }
  },
  "metadata": {
    "timestamp": "2023-12-01T15:30:00Z",
    "request_id": "req_auth_123"
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid username or password",
    "suggestions": [
      "Check your email address and password",
      "Use 'Forgot Password' if you can't remember your password",
      "Contact support if you continue having issues"
    ]
  }
}
```

**Implementation:**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, validator
from datetime import timedelta
import bcrypt

router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

    @validator('username')
    def validate_username(cls, v):
        if '@' in v:
            # Email validation
            import re
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
                raise ValueError('Invalid email format')
        return v.lower().strip()

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User

@router.post("/login", response_model=APIResponse[LoginResponse])
async def login(credentials: LoginRequest):
    """
    Authenticate user and return JWT tokens

    - **username**: Email address or username
    - **password**: User's password
    - **remember_me**: Extended session duration if true
    """
    try:
        # Authenticate user
        user = await authenticate_user(credentials.username, credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password",
                    "suggestions": [
                        "Check your email address and password",
                        "Use 'Forgot Password' if you can't remember your password"
                    ]
                }
            )

        # Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "ACCOUNT_DISABLED",
                    "message": "Your account has been disabled",
                    "suggestions": ["Contact support for assistance"]
                }
            )

        # Create tokens
        expires_delta = timedelta(days=30) if credentials.remember_me else timedelta(hours=24)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role, "user_id": user.id},
            expires_delta=expires_delta
        )
        refresh_token = create_refresh_token(data={"sub": user.username, "user_id": user.id})

        # Update last login
        await update_user_last_active(user.id)

        # Log successful login
        logger.info(f"User {user.username} logged in successfully")

        return APIResponse(
            success=True,
            data=LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=int(expires_delta.total_seconds()),
                user=user
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "LOGIN_ERROR",
                "message": "An error occurred during login"
            }
        )

async def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user credentials"""
    user = await get_user_by_username(username)
    if not user:
        return None

    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        return None

    return user
```

### POST /auth/register

Register a new user account.

**Request Body:**
```json
{
  "username": "newwriter",
  "email": "newwriter@example.com",
  "password": "secure_password123",
  "full_name": "New Writer",
  "terms_accepted": true
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_789012",
      "username": "newwriter",
      "email": "newwriter@example.com",
      "full_name": "New Writer",
      "role": "writer",
      "created_at": "2023-12-01T15:45:00Z"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "message": "Account created successfully"
  }
}
```

**Implementation:**
```python
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    terms_accepted: bool

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not v.isalnum():
            raise ValueError('Username must contain only letters and numbers')
        return v.lower()

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

    @validator('terms_accepted')
    def validate_terms(cls, v):
        if not v:
            raise ValueError('You must accept the terms of service')
        return v

@router.post("/register", response_model=APIResponse[dict])
async def register(user_data: RegisterRequest):
    """
    Register a new user account

    - **username**: Unique username (3+ characters, alphanumeric)
    - **email**: Valid email address
    - **password**: Strong password (8+ chars, mixed case, number)
    - **full_name**: User's full name (optional)
    - **terms_accepted**: Must be true to create account
    """
    try:
        # Check if user already exists
        existing_user = await get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "USERNAME_EXISTS",
                    "message": "Username already exists",
                    "suggestions": ["Try a different username"]
                }
            )

        existing_email = await get_user_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "EMAIL_EXISTS",
                    "message": "Email address already registered",
                    "suggestions": [
                        "Use a different email address",
                        "Try logging in if you already have an account"
                    ]
                }
            )

        # Hash password
        hashed_password = bcrypt.hashpw(
            user_data.password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # Create user
        new_user = await create_user(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=UserRole.WRITER  # Default role
        )

        # Generate welcome token
        access_token = create_access_token(
            data={"sub": new_user.username, "role": new_user.role, "user_id": new_user.id}
        )

        # Send welcome email
        await send_welcome_email(new_user.email, new_user.full_name or new_user.username)

        logger.info(f"New user registered: {new_user.username}")

        return APIResponse(
            success=True,
            data={
                "user": new_user,
                "access_token": access_token,
                "message": "Account created successfully"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REGISTRATION_ERROR",
                "message": "An error occurred during registration"
            }
        )
```

### POST /auth/refresh

Refresh an expired access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

### POST /auth/logout

Logout user and invalidate tokens.

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "message": "Logged out successfully"
  }
}
```

## OAuth Integration

### GitHub OAuth

**GET /auth/oauth/github**

Initiate GitHub OAuth flow.

**Response (302 Redirect):**
Redirects to GitHub OAuth authorization URL.

**GET /auth/oauth/github/callback**

Handle GitHub OAuth callback.

**Query Parameters:**
- `code`: Authorization code from GitHub
- `state`: CSRF protection state parameter

**Implementation:**
```python
import httpx
from urllib.parse import urlencode

GITHUB_CLIENT_ID = os.environ["GITHUB_CLIENT_ID"]
GITHUB_CLIENT_SECRET = os.environ["GITHUB_CLIENT_SECRET"]
GITHUB_REDIRECT_URI = os.environ["GITHUB_REDIRECT_URI"]

@router.get("/oauth/github")
async def github_oauth_initiate():
    """Initiate GitHub OAuth flow"""
    state = secrets.token_urlsafe(32)

    # Store state in session or cache for validation
    await store_oauth_state(state)

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "state": state,
        "response_type": "code"
    }

    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=auth_url)

@router.get("/oauth/github/callback")
async def github_oauth_callback(code: str, state: str):
    """Handle GitHub OAuth callback"""
    # Validate state parameter
    if not await validate_oauth_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )

        token_data = token_response.json()
        github_token = token_data.get("access_token")

        if not github_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain GitHub access token"
            )

        # Get user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {github_token}"}
        )

        github_user = user_response.json()

        # Get user email
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"token {github_token}"}
        )

        emails = email_response.json()
        primary_email = next(
            (email["email"] for email in emails if email["primary"]),
            github_user.get("email")
        )

    # Find or create user
    user = await get_user_by_email(primary_email)
    if not user:
        user = await create_user(
            username=github_user["login"],
            email=primary_email,
            full_name=github_user.get("name"),
            avatar_url=github_user.get("avatar_url"),
            oauth_provider="github",
            oauth_id=str(github_user["id"])
        )

    # Create JWT token
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )

    # Redirect to frontend with token
    frontend_url = f"{os.environ['FRONTEND_URL']}/auth/callback?token={access_token}"
    return RedirectResponse(url=frontend_url)
```

## Role-Based Access Control

### User Roles

```python
class UserRole(str, Enum):
    OWNER = "owner"          # Full project control
    EDITOR = "editor"        # Content review and editing
    WRITER = "writer"        # Content creation
    BETA_READER = "beta_reader"  # Read and comment only

ROLE_HIERARCHY = {
    UserRole.BETA_READER: 1,
    UserRole.WRITER: 2,
    UserRole.EDITOR: 3,
    UserRole.OWNER: 4
}
```

### Permission System

```python
from functools import wraps
from typing import List

def require_role(required_role: UserRole):
    """Decorator to require specific role or higher"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            user_level = ROLE_HIERARCHY.get(current_user.role, 0)
            required_level = ROLE_HIERARCHY.get(required_role, 999)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"Role '{required_role}' or higher required",
                        "user_role": current_user.role,
                        "required_role": required_role
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_permissions(permissions: List[str]):
    """Decorator to require specific permissions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            repo_name = kwargs.get('repo_name')

            user_permissions = await get_user_permissions(current_user.id, repo_name)
            missing_permissions = set(permissions) - set(user_permissions)

            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "MISSING_PERMISSIONS",
                        "message": "Insufficient permissions",
                        "missing_permissions": list(missing_permissions)
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage examples
@require_role(UserRole.WRITER)
async def save_changes(repo_name: str, current_user: User = Depends(get_current_user)):
    """Only writers and above can save changes"""
    pass

@require_permissions(["repository.read", "repository.comment"])
async def add_annotation(repo_name: str, current_user: User = Depends(get_current_user)):
    """Requires specific permissions"""
    pass
```

## Security Features

### JWT Token Management

```python
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
```

### Password Security

```python
import bcrypt
import secrets
import string

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_secure_password(length: int = 16) -> str:
    """Generate cryptographically secure password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class PasswordValidator:
    """Password strength validation"""

    @staticmethod
    def validate_strength(password: str) -> Dict[str, bool]:
        """Validate password strength"""
        checks = {
            "min_length": len(password) >= 8,
            "has_upper": any(c.isupper() for c in password),
            "has_lower": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password),
            "not_common": password.lower() not in COMMON_PASSWORDS
        }
        return checks

    @staticmethod
    def is_strong(password: str) -> bool:
        """Check if password meets all requirements"""
        checks = PasswordValidator.validate_strength(password)
        return all(checks.values())
```

---

*The GitWrite Authentication system provides enterprise-grade security with user-friendly features, supporting both traditional password-based authentication and modern OAuth flows while maintaining strict security standards.*