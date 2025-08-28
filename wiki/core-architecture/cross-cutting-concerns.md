# Cross-Cutting Concerns

Cross-cutting concerns are system-wide requirements that span multiple layers and components of GitWrite. These concerns include logging, security, error handling, monitoring, caching, and other aspects that affect the entire system rather than specific business logic.

## Overview

Cross-cutting concerns in GitWrite are implemented using a combination of patterns and technologies:

- **Aspect-Oriented Programming (AOP)** concepts for separation of concerns
- **Middleware patterns** for request/response processing
- **Decorator patterns** for method-level concerns
- **Configuration-driven** approaches for flexibility
- **Centralized services** for consistency

```
┌─────────────────────────────────────────────┐
│              Application Layer              │
├─────────────────────────────────────────────┤
│           Cross-Cutting Concerns            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │Logging  │ │Security │ │Caching  │  ...  │
│  └─────────┘ └─────────┘ └─────────┘       │
├─────────────────────────────────────────────┤
│              Business Logic                 │
├─────────────────────────────────────────────┤
│               Data Access                   │
└─────────────────────────────────────────────┘
```

## 1. Logging and Observability

### Structured Logging

GitWrite implements structured logging across all components using a consistent format:

```python
import structlog
from typing import Dict, Any

class GitWriteLogger:
    """Centralized logging configuration for GitWrite"""

    def __init__(self):
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    def get_logger(self, name: str) -> structlog.BoundLogger:
        return structlog.get_logger(name)

# Usage across the system
logger = GitWriteLogger().get_logger("gitwrite.core")

def save_changes(repo_path: str, message: str):
    logger.info(
        "Starting save operation",
        repo_path=repo_path,
        message=message,
        operation="save"
    )

    try:
        # ... save logic ...
        logger.info(
            "Save operation completed",
            repo_path=repo_path,
            commit_id=commit_id,
            files_changed=len(changed_files)
        )
    except Exception as e:
        logger.error(
            "Save operation failed",
            repo_path=repo_path,
            error=str(e),
            error_type=type(e).__name__
        )
        raise
```

### Log Levels and Categories

```python
class LogCategory:
    """Standardized log categories across GitWrite"""

    # User actions
    USER_ACTION = "user_action"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"

    # System operations
    GIT_OPERATION = "git_operation"
    FILE_OPERATION = "file_operation"
    EXPORT_OPERATION = "export_operation"

    # Performance and monitoring
    PERFORMANCE = "performance"
    CACHE_OPERATION = "cache_operation"
    DATABASE_OPERATION = "database_operation"

    # Errors and debugging
    ERROR = "error"
    SECURITY_EVENT = "security_event"
    AUDIT_EVENT = "audit_event"

class PerformanceLogger:
    """Performance monitoring decorator"""

    @staticmethod
    def monitor(operation_name: str, category: str = LogCategory.PERFORMANCE):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                logger = structlog.get_logger("gitwrite.performance")

                logger.info(
                    f"{operation_name} started",
                    operation=operation_name,
                    category=category
                )

                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    logger.info(
                        f"{operation_name} completed",
                        operation=operation_name,
                        duration_seconds=duration,
                        category=category
                    )

                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(
                        f"{operation_name} failed",
                        operation=operation_name,
                        duration_seconds=duration,
                        error=str(e),
                        category=category
                    )
                    raise

            return wrapper
        return decorator
```

### Request Correlation

```python
import uuid
from contextvars import ContextVar

# Request correlation context
correlation_id: ContextVar[str] = ContextVar('correlation_id')

class CorrelationMiddleware:
    """Middleware to add correlation IDs to all requests"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Generate or extract correlation ID
            headers = dict(scope["headers"])
            corr_id = headers.get(b"x-correlation-id", str(uuid.uuid4()).encode())

            # Set in context
            correlation_id.set(corr_id.decode())

            # Add to response headers
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", [])
                    message["headers"].append((b"x-correlation-id", corr_id))
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)

# Enhanced logger with correlation
class CorrelatedLogger:
    def __init__(self, name: str):
        self.base_logger = structlog.get_logger(name)

    def _add_correlation(self, **kwargs):
        try:
            kwargs["correlation_id"] = correlation_id.get()
        except LookupError:
            pass
        return kwargs

    def info(self, message, **kwargs):
        self.base_logger.info(message, **self._add_correlation(**kwargs))

    def error(self, message, **kwargs):
        self.base_logger.error(message, **self._add_correlation(**kwargs))
```

## 2. Security

### Authentication and Authorization

```python
from functools import wraps
import jwt
from datetime import datetime, timedelta

class SecurityContext:
    """Security context for the current request"""

    def __init__(self, user_id: str, roles: List[str], permissions: List[str]):
        self.user_id = user_id
        self.roles = roles
        self.permissions = permissions
        self.timestamp = datetime.utcnow()

class SecurityManager:
    """Centralized security management"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.logger = CorrelatedLogger("gitwrite.security")

    def require_permission(self, permission: str):
        """Decorator to require specific permission"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                context = self.get_security_context()

                if not self.has_permission(context, permission):
                    self.logger.error(
                        "Permission denied",
                        user_id=context.user_id,
                        required_permission=permission,
                        user_permissions=context.permissions,
                        category=LogCategory.SECURITY_EVENT
                    )
                    raise PermissionDeniedError(f"Required permission: {permission}")

                self.logger.info(
                    "Permission granted",
                    user_id=context.user_id,
                    permission=permission,
                    category=LogCategory.AUTHORIZATION
                )

                return await func(*args, **kwargs)
            return wrapper
        return decorator

    def audit_access(self, resource: str, action: str):
        """Decorator for audit logging"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                context = self.get_security_context()

                self.logger.info(
                    "Resource access",
                    user_id=context.user_id,
                    resource=resource,
                    action=action,
                    timestamp=datetime.utcnow().isoformat(),
                    category=LogCategory.AUDIT_EVENT
                )

                result = await func(*args, **kwargs)

                self.logger.info(
                    "Resource access completed",
                    user_id=context.user_id,
                    resource=resource,
                    action=action,
                    category=LogCategory.AUDIT_EVENT
                )

                return result
            return wrapper
        return decorator
```

### Input Validation and Sanitization

```python
from pydantic import BaseModel, validator
import bleach

class SecurityValidationMixin:
    """Mixin for security-aware validation"""

    @validator("*", pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            # Remove potentially dangerous HTML/script content
            v = bleach.clean(v, tags=[], attributes={}, strip=True)
            # Additional sanitization for file paths
            if "path" in cls.__name__.lower():
                v = cls._sanitize_path(v)
        return v

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """Sanitize file paths to prevent directory traversal"""
        import os.path
        # Remove dangerous path components
        path = path.replace("..", "").replace("\\", "/")
        # Normalize path
        return os.path.normpath(path).lstrip("/")

class SecureFileRequest(BaseModel, SecurityValidationMixin):
    file_path: str
    content: str

    @validator("file_path")
    def validate_file_path(cls, v):
        if not v or v.startswith("/") or ".." in v:
            raise ValueError("Invalid file path")
        return v
```

## 3. Error Handling

### Centralized Error Management

```python
from enum import Enum
from typing import Optional, Dict, Any

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class GitWriteError(Exception):
    """Base exception for all GitWrite errors"""

    def __init__(
        self,
        message: str,
        error_code: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_message: Optional[str] = None,
        recovery_suggestions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.user_message = user_message or message
        self.recovery_suggestions = recovery_suggestions or []
        self.context = context or {}
        self.timestamp = datetime.utcnow()

class ErrorHandler:
    """Centralized error handling and reporting"""

    def __init__(self):
        self.logger = CorrelatedLogger("gitwrite.errors")

    def handle_error(self, error: Exception, context: Dict[str, Any] = None):
        """Handle and log errors consistently"""

        context = context or {}

        if isinstance(error, GitWriteError):
            self.logger.error(
                "GitWrite error occurred",
                error_code=error.error_code,
                error_message=error.message,
                severity=error.severity.value,
                user_message=error.user_message,
                recovery_suggestions=error.recovery_suggestions,
                error_context=error.context,
                request_context=context,
                category=LogCategory.ERROR
            )
        else:
            # Unexpected error
            self.logger.error(
                "Unexpected error occurred",
                error_type=type(error).__name__,
                error_message=str(error),
                severity=ErrorSeverity.HIGH.value,
                request_context=context,
                category=LogCategory.ERROR,
                exc_info=True
            )

    def error_boundary(self, default_return=None):
        """Decorator to catch and handle errors"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    self.handle_error(e, {"function": func.__name__})
                    if default_return is not None:
                        return default_return
                    raise
            return wrapper
        return decorator
```

## 4. Caching

### Multi-Level Caching Strategy

```python
import redis
from typing import Optional, Any
import pickle
import hashlib

class CacheManager:
    """Multi-level caching with Redis and in-memory layers"""

    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)
        self.local_cache = {}  # In-memory cache
        self.logger = CorrelatedLogger("gitwrite.cache")

    def cache_key(self, namespace: str, key: str) -> str:
        """Generate consistent cache keys"""
        return f"gitwrite:{namespace}:{hashlib.md5(key.encode()).hexdigest()}"

    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get from cache with fallback strategy"""
        cache_key = self.cache_key(namespace, key)

        # Try local cache first
        if cache_key in self.local_cache:
            self.logger.debug("Cache hit (local)", key=cache_key, category=LogCategory.CACHE_OPERATION)
            return self.local_cache[cache_key]

        # Try Redis cache
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = pickle.loads(cached_data)
                # Populate local cache
                self.local_cache[cache_key] = data
                self.logger.debug("Cache hit (redis)", key=cache_key, category=LogCategory.CACHE_OPERATION)
                return data
        except Exception as e:
            self.logger.warning("Redis cache error", error=str(e), key=cache_key)

        self.logger.debug("Cache miss", key=cache_key, category=LogCategory.CACHE_OPERATION)
        return None

    async def set(self, namespace: str, key: str, value: Any, ttl: int = 3600):
        """Set cache value with TTL"""
        cache_key = self.cache_key(namespace, key)

        # Set in local cache
        self.local_cache[cache_key] = value

        # Set in Redis cache
        try:
            self.redis_client.setex(
                cache_key,
                ttl,
                pickle.dumps(value)
            )
            self.logger.debug("Cache set", key=cache_key, ttl=ttl, category=LogCategory.CACHE_OPERATION)
        except Exception as e:
            self.logger.warning("Redis cache set error", error=str(e), key=cache_key)

def cache_result(namespace: str, ttl: int = 3600, key_func=None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Try to get from cache
            cached_result = await cache_manager.get(namespace, cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(namespace, cache_key, result, ttl)

            return result
        return wrapper
    return decorator
```

## 5. Monitoring and Health Checks

### Health Check System

```python
from dataclasses import dataclass
from enum import Enum
import asyncio

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    service: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime

class HealthChecker:
    """System health monitoring"""

    def __init__(self):
        self.checks = {}
        self.logger = CorrelatedLogger("gitwrite.health")

    def register_check(self, name: str, check_func, timeout: int = 5):
        """Register a health check"""
        self.checks[name] = {
            "func": check_func,
            "timeout": timeout
        }

    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check"""
        check = self.checks[name]
        start_time = time.time()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check["func"](),
                timeout=check["timeout"]
            )

            response_time = (time.time() - start_time) * 1000

            if result:
                return HealthCheckResult(
                    service=name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    response_time_ms=response_time,
                    timestamp=datetime.utcnow()
                )
            else:
                return HealthCheckResult(
                    service=name,
                    status=HealthStatus.UNHEALTHY,
                    message="Check failed",
                    response_time_ms=response_time,
                    timestamp=datetime.utcnow()
                )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                service=name,
                status=HealthStatus.UNHEALTHY,
                message="Timeout",
                response_time_ms=check["timeout"] * 1000,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return HealthCheckResult(
                service=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow()
            )

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks"""
        tasks = [self.run_check(name) for name in self.checks.keys()]
        results = await asyncio.gather(*tasks)

        return {result.service: result for result in results}

# Example health checks
async def check_database():
    """Check database connectivity"""
    # Implementation depends on database type
    return True

async def check_redis():
    """Check Redis connectivity"""
    # Implementation depends on Redis setup
    return True

async def check_git_operations():
    """Check Git operations are working"""
    # Test basic Git operation
    return True
```

## 6. Configuration Management

### Centralized Configuration

```python
from pydantic import BaseSettings
import yaml

class GitWriteSettings(BaseSettings):
    """Centralized configuration management"""

    # Database settings
    database_url: str = "postgresql://localhost/gitwrite"

    # Redis settings
    redis_url: str = "redis://localhost:6379"

    # Security settings
    secret_key: str
    jwt_expiration_hours: int = 24

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"

    # Feature flags
    enable_analytics: bool = True
    enable_caching: bool = True
    enable_export: bool = True

    # Performance settings
    max_file_size_mb: int = 100
    max_repo_size_gb: int = 5
    worker_concurrency: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class ConfigurationManager:
    """Dynamic configuration management"""

    def __init__(self, config_file: str = "config.yaml"):
        self.settings = GitWriteSettings()
        self.config_file = config_file
        self.dynamic_config = self._load_dynamic_config()

    def _load_dynamic_config(self) -> Dict[str, Any]:
        """Load configuration that can change at runtime"""
        try:
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {}

    def get(self, key: str, default=None):
        """Get configuration value with fallback"""
        # Check dynamic config first
        if key in self.dynamic_config:
            return self.dynamic_config[key]

        # Check settings
        return getattr(self.settings, key, default)

    def reload_dynamic_config(self):
        """Reload dynamic configuration"""
        self.dynamic_config = self._load_dynamic_config()
```

## 7. Rate Limiting

### API Rate Limiting

```python
import time
from collections import defaultdict
import asyncio

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.logger = CorrelatedLogger("gitwrite.ratelimit")

    async def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for identifier"""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]

        # Check if under limit
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        else:
            self.logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                requests_in_window=len(self.requests[identifier]),
                max_requests=self.max_requests,
                category=LogCategory.SECURITY_EVENT
            )
            return False

def rate_limit(max_requests: int, window_seconds: int):
    """Decorator for rate limiting endpoints"""
    limiter = RateLimiter(max_requests, window_seconds)

    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Use IP address or user ID as identifier
            identifier = request.client.host
            if hasattr(request, 'user'):
                identifier = request.user.id

            if not await limiter.is_allowed(identifier):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded"
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

## Integration and Implementation

### Middleware Stack

```python
class GitWriteMiddleware:
    """Combined middleware for all cross-cutting concerns"""

    def __init__(self, app):
        self.app = app
        self.security_manager = SecurityManager()
        self.error_handler = ErrorHandler()
        self.rate_limiter = RateLimiter(100, 60)  # 100 requests per minute

    async def __call__(self, scope, receive, send):
        # Apply all cross-cutting concerns
        correlation_middleware = CorrelationMiddleware(self.app)

        # Chain middlewares
        await correlation_middleware(scope, receive, send)
```

### Aspect-Oriented Programming Pattern

```python
class AspectManager:
    """Manage cross-cutting concerns using AOP concepts"""

    def __init__(self):
        self.aspects = {}

    def register_aspect(self, name: str, aspect_func):
        """Register a cross-cutting concern"""
        self.aspects[name] = aspect_func

    def apply_aspects(self, *aspect_names):
        """Apply multiple aspects to a function"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Before aspects
                for name in aspect_names:
                    if name in self.aspects:
                        await self.aspects[name].before(func, args, kwargs)

                try:
                    result = await func(*args, **kwargs)

                    # After aspects
                    for name in aspect_names:
                        if name in self.aspects:
                            await self.aspects[name].after(func, args, kwargs, result)

                    return result

                except Exception as e:
                    # Error aspects
                    for name in aspect_names:
                        if name in self.aspects:
                            await self.aspects[name].on_error(func, args, kwargs, e)
                    raise

            return wrapper
        return decorator
```

---

*Cross-cutting concerns are essential for building a robust, maintainable, and secure system. GitWrite's approach ensures these concerns are handled consistently across all components while remaining flexible and configurable.*