# Configuration Management

Comprehensive configuration management for GitWrite across all environments, including environment-specific settings, secrets management, feature flags, and configuration validation. This system ensures secure, scalable, and maintainable configuration handling.

## Configuration Architecture

```
Configuration Management
    │
    ├─ Environment-Specific Configs
    │   ├─ Development (.env.dev)
    │   ├─ Staging (.env.staging)
    │   ├─ Production (.env.prod)
    │   └─ Testing (.env.test)
    │
    ├─ Secrets Management
    │   ├─ Environment Variables
    │   ├─ Key Management Service
    │   ├─ Encrypted Config Files
    │   └─ Runtime Secret Injection
    │
    ├─ Feature Flags
    │   ├─ Runtime Feature Control
    │   ├─ A/B Testing Support
    │   └─ Gradual Rollouts
    │
    └─ Configuration Validation
        ├─ Schema Validation
        ├─ Environment Checks
        └─ Health Monitoring
```

## Environment Configuration

### Development Environment

```bash
# .env.development
# ==================
# Development-specific configuration

# Database
DATABASE_URL=postgresql://gitwrite:gitwrite@localhost:5432/gitwrite_dev
DATABASE_POOL_SIZE=5
DATABASE_ECHO=true

# Redis
REDIS_URL=redis://localhost:6379/0

# Security (development only)
SECRET_KEY=dev-secret-key-not-for-production
JWT_EXPIRE_MINUTES=60
DEBUG=true
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
LOG_LEVEL=DEBUG

# Git Storage
GIT_STORAGE_PATH=./data/repositories
GIT_DEFAULT_BRANCH=main

# Email (MailHog for development)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
EMAIL_FROM=dev@gitwrite.local

# File Upload
MAX_FILE_SIZE=52428800  # 50MB for development
UPLOAD_PATH=./data/uploads

# External Services (development)
OPENAI_API_KEY=  # Optional
SENTRY_DSN=  # Disabled in dev
ANALYTICS_ENABLED=false

# Feature Flags
ENABLE_COLLABORATION=true
ENABLE_AI_FEATURES=false
ENABLE_REALTIME=true
ENABLE_METRICS=false
```

### Staging Environment

```bash
# .env.staging
# =============
# Staging environment - production-like for testing

# Database
DATABASE_URL=${DATABASE_URL}  # From environment/secrets
DATABASE_POOL_SIZE=10
DATABASE_ECHO=false

# Redis
REDIS_URL=${REDIS_URL}

# Security
SECRET_KEY=${SECRET_KEY}
JWT_EXPIRE_MINUTES=30
DEBUG=false
CORS_ORIGINS=["https://staging.gitwrite.com"]

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=2
LOG_LEVEL=INFO

# Git Storage
GIT_STORAGE_PATH=/app/data/repositories
GIT_DEFAULT_BRANCH=main

# Email
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=587
SMTP_TLS=true
SMTP_USERNAME=${SMTP_USERNAME}
SMTP_PASSWORD=${SMTP_PASSWORD}
EMAIL_FROM=staging@gitwrite.com

# File Upload
MAX_FILE_SIZE=10485760  # 10MB
UPLOAD_PATH=/app/data/uploads

# External Services
OPENAI_API_KEY=${OPENAI_API_KEY}
SENTRY_DSN=${SENTRY_DSN}
ANALYTICS_ENABLED=true

# Feature Flags
ENABLE_COLLABORATION=true
ENABLE_AI_FEATURES=true
ENABLE_REALTIME=true
ENABLE_METRICS=true
ENABLE_BETA_FEATURES=true
```

### Production Environment

```bash
# .env.production
# ===============
# Production environment configuration

# Database
DATABASE_URL=${DATABASE_URL}
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_ECHO=false

# Redis
REDIS_URL=${REDIS_URL}
REDIS_POOL_SIZE=10

# Security
SECRET_KEY=${SECRET_KEY}
JWT_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7
DEBUG=false
CORS_ORIGINS=["https://gitwrite.com", "https://app.gitwrite.com"]

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
LOG_LEVEL=WARNING

# Git Storage
GIT_STORAGE_PATH=/data/repositories
GIT_DEFAULT_BRANCH=main

# Email
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=587
SMTP_TLS=true
SMTP_USERNAME=${SMTP_USERNAME}
SMTP_PASSWORD=${SMTP_PASSWORD}
EMAIL_FROM=noreply@gitwrite.com

# File Upload
MAX_FILE_SIZE=10485760  # 10MB
UPLOAD_PATH=/data/uploads

# External Services
OPENAI_API_KEY=${OPENAI_API_KEY}
SENTRY_DSN=${SENTRY_DSN}
ANALYTICS_ENABLED=true

# Feature Flags
ENABLE_COLLABORATION=true
ENABLE_AI_FEATURES=true
ENABLE_REALTIME=true
ENABLE_METRICS=true
ENABLE_BETA_FEATURES=false

# Production-specific
RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
BACKUP_ENABLED=true
MONITORING_ENABLED=true
```

## Configuration Management System

### Configuration Schema

```python
# backend/config/schema.py
from pydantic import BaseSettings, validator
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    """Application configuration with validation."""

    # Environment
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 10

    # Security
    secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    password_salt_rounds: int = 12

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    cors_origins: List[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Git
    git_storage_path: str = "./data/repositories"
    git_default_branch: str = "main"
    git_author_name: str = "GitWrite System"
    git_author_email: str = "system@gitwrite.com"

    # Email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_tls: bool = True
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: str = "noreply@gitwrite.com"

    # File Upload
    max_file_size: int = 10485760  # 10MB
    allowed_file_types: List[str] = [".md", ".txt", ".docx", ".pdf"]
    upload_path: str = "./data/uploads"

    # External Services
    openai_api_key: Optional[str] = None
    sentry_dsn: Optional[str] = None
    analytics_enabled: bool = False

    # Feature Flags
    enable_collaboration: bool = True
    enable_ai_features: bool = False
    enable_realtime: bool = True
    enable_metrics: bool = False
    enable_beta_features: bool = False

    # Rate Limiting
    rate_limiting: bool = False
    rate_limit_per_minute: int = 60

    # Backup
    backup_enabled: bool = False
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM
    backup_retention_days: int = 30

    @validator('database_url')
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError('Database URL must be PostgreSQL')
        return v

    @validator('secret_key')
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters')
        return v

    @validator('environment')
    def validate_environment(cls, v):
        allowed = ['development', 'staging', 'production', 'testing']
        if v not in allowed:
            raise ValueError(f'Environment must be one of: {allowed}')
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_nested_delimiter = "__"
```

### Configuration Factory

```python
# backend/config/factory.py
from functools import lru_cache
from typing import Optional
import os
from .schema import Settings

@lru_cache()
def get_settings(env_file: Optional[str] = None) -> Settings:
    """Get application settings with caching."""

    if env_file is None:
        environment = os.getenv('ENVIRONMENT', 'development')
        env_file = f".env.{environment}"

    return Settings(_env_file=env_file)

def create_settings_for_environment(environment: str) -> Settings:
    """Create settings for specific environment."""
    return Settings(_env_file=f".env.{environment}")

# Environment-specific configurations
def get_development_settings() -> Settings:
    return create_settings_for_environment('development')

def get_staging_settings() -> Settings:
    return create_settings_for_environment('staging')

def get_production_settings() -> Settings:
    return create_settings_for_environment('production')

def get_testing_settings() -> Settings:
    return create_settings_for_environment('testing')
```

## Secrets Management

### Environment Variables

```bash
# Production secrets (set in deployment environment)
export DATABASE_URL="postgresql://user:pass@host:port/db"
export REDIS_URL="redis://host:port/0"
export SECRET_KEY="$(openssl rand -base64 32)"
export JWT_SECRET_KEY="$(openssl rand -base64 32)"
export SMTP_PASSWORD="email-service-password"
export OPENAI_API_KEY="openai-api-key"
export SENTRY_DSN="sentry-project-dsn"
```

### Docker Secrets

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    image: gitwrite/backend:latest
    secrets:
      - database_password
      - jwt_secret
      - smtp_password
    environment:
      DATABASE_PASSWORD_FILE: /run/secrets/database_password
      JWT_SECRET_FILE: /run/secrets/jwt_secret
      SMTP_PASSWORD_FILE: /run/secrets/smtp_password

secrets:
  database_password:
    external: true
  jwt_secret:
    external: true
  smtp_password:
    external: true
```

### Kubernetes Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gitwrite-secrets
type: Opaque
stringData:
  database-url: "postgresql://user:pass@postgres:5432/gitwrite"
  redis-url: "redis://redis:6379/0"
  secret-key: "your-secret-key"
  jwt-secret: "your-jwt-secret"
  smtp-password: "smtp-password"
  openai-api-key: "openai-key"
  sentry-dsn: "sentry-dsn"
```

### Secret Loading Utility

```python
# backend/config/secrets.py
import os
from pathlib import Path
from typing import Optional

def load_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """Load secret from file or environment variable."""

    # Try Docker secrets first
    secret_file = Path(f"/run/secrets/{secret_name}")
    if secret_file.exists():
        return secret_file.read_text().strip()

    # Try environment variable with _FILE suffix
    file_path_var = f"{secret_name.upper()}_FILE"
    if file_path_var in os.environ:
        file_path = Path(os.environ[file_path_var])
        if file_path.exists():
            return file_path.read_text().strip()

    # Try direct environment variable
    env_var = secret_name.upper()
    if env_var in os.environ:
        return os.environ[env_var]

    return default

def get_database_url() -> str:
    """Get database URL from various sources."""
    return load_secret("database_url") or load_secret("database-url")

def get_secret_key() -> str:
    """Get secret key with fallback generation."""
    key = load_secret("secret_key") or load_secret("secret-key")
    if not key:
        import secrets
        key = secrets.token_urlsafe(32)
    return key
```

## Feature Flags

### Feature Flag System

```python
# backend/config/features.py
from enum import Enum
from typing import Dict, Any
import os
import json

class FeatureFlag(Enum):
    COLLABORATION = "enable_collaboration"
    AI_FEATURES = "enable_ai_features"
    REALTIME = "enable_realtime"
    METRICS = "enable_metrics"
    BETA_FEATURES = "enable_beta_features"
    RATE_LIMITING = "rate_limiting"
    BACKUP = "backup_enabled"

class FeatureManager:
    """Manage feature flags and runtime configuration."""

    def __init__(self, settings):
        self.settings = settings
        self._feature_overrides = self._load_feature_overrides()

    def _load_feature_overrides(self) -> Dict[str, Any]:
        """Load feature flag overrides from external source."""
        override_file = os.getenv('FEATURE_FLAGS_FILE')
        if override_file and os.path.exists(override_file):
            with open(override_file) as f:
                return json.load(f)
        return {}

    def is_enabled(self, feature: FeatureFlag, user_id: str = None) -> bool:
        """Check if feature is enabled for user."""

        # Check for override first
        if feature.value in self._feature_overrides:
            override = self._feature_overrides[feature.value]

            # Simple boolean override
            if isinstance(override, bool):
                return override

            # Percentage rollout
            if isinstance(override, dict):
                if 'percentage' in override:
                    return self._check_percentage_rollout(
                        override['percentage'],
                        user_id or 'anonymous'
                    )

                # User-specific override
                if 'users' in override and user_id:
                    return user_id in override['users']

        # Fall back to settings
        return getattr(self.settings, feature.value, False)

    def _check_percentage_rollout(self, percentage: int, user_id: str) -> bool:
        """Check if user is in percentage rollout."""
        import hashlib

        hash_input = f"{user_id}:{percentage}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        return (hash_value % 100) < percentage

    def get_feature_config(self, feature: FeatureFlag) -> Dict[str, Any]:
        """Get detailed feature configuration."""
        override = self._feature_overrides.get(feature.value, {})
        if isinstance(override, dict):
            return override
        return {"enabled": self.is_enabled(feature)}

# Global feature manager instance
feature_manager: FeatureManager = None

def init_feature_manager(settings):
    """Initialize global feature manager."""
    global feature_manager
    feature_manager = FeatureManager(settings)

def is_feature_enabled(feature: FeatureFlag, user_id: str = None) -> bool:
    """Check if feature is enabled."""
    if feature_manager is None:
        raise RuntimeError("Feature manager not initialized")
    return feature_manager.is_enabled(feature, user_id)
```

### Feature Flag Configuration

```json
// feature-flags.json (external configuration)
{
  "enable_ai_features": {
    "percentage": 50,
    "description": "AI writing assistance features",
    "rollout_date": "2024-02-01"
  },
  "enable_beta_features": {
    "users": ["beta-user-1", "beta-user-2"],
    "description": "Beta features for testing"
  },
  "enable_collaboration": true,
  "rate_limiting": {
    "percentage": 100,
    "config": {
      "requests_per_minute": 60,
      "burst_limit": 10
    }
  }
}
```

## Configuration Validation

### Health Checks

```python
# backend/health/config_check.py
from typing import Dict, List
from ..config import get_settings

def validate_configuration() -> Dict[str, Any]:
    """Validate current configuration."""
    settings = get_settings()
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {}
    }

    # Database connectivity
    try:
        from sqlalchemy import create_engine
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        results["checks"]["database"] = "ok"
    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Database connection failed: {e}")
        results["checks"]["database"] = "failed"

    # Redis connectivity
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        results["checks"]["redis"] = "ok"
    except Exception as e:
        results["errors"].append(f"Redis connection failed: {e}")
        results["checks"]["redis"] = "failed"

    # File system permissions
    try:
        import os
        os.makedirs(settings.upload_path, exist_ok=True)
        os.makedirs(settings.git_storage_path, exist_ok=True)
        results["checks"]["filesystem"] = "ok"
    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"File system check failed: {e}")
        results["checks"]["filesystem"] = "failed"

    # External services
    if settings.openai_api_key:
        # Test OpenAI API key (optional)
        results["checks"]["openai"] = "configured"

    if settings.sentry_dsn:
        results["checks"]["sentry"] = "configured"

    # Security validation
    if settings.environment == "production":
        if settings.debug:
            results["warnings"].append("Debug mode enabled in production")

        if len(settings.secret_key) < 32:
            results["valid"] = False
            results["errors"].append("Secret key too short for production")

    return results

def check_environment_consistency() -> List[str]:
    """Check for environment configuration consistency."""
    issues = []
    settings = get_settings()

    if settings.environment == "production":
        if "localhost" in settings.database_url:
            issues.append("Production using localhost database")

        if settings.cors_origins == ["*"]:
            issues.append("CORS allowing all origins in production")

        if not settings.rate_limiting:
            issues.append("Rate limiting disabled in production")

    return issues
```

### Configuration Monitoring

```python
# backend/monitoring/config_monitor.py
import logging
from typing import Dict, Any
from ..config import get_settings
from ..health.config_check import validate_configuration

logger = logging.getLogger(__name__)

class ConfigurationMonitor:
    """Monitor configuration changes and health."""

    def __init__(self):
        self.last_config_hash = None
        self.settings = get_settings()

    def check_configuration_health(self) -> Dict[str, Any]:
        """Perform configuration health check."""
        return validate_configuration()

    def monitor_config_changes(self):
        """Monitor for configuration changes."""
        import hashlib
        import json

        current_config = self.settings.dict()
        config_str = json.dumps(current_config, sort_keys=True)
        current_hash = hashlib.md5(config_str.encode()).hexdigest()

        if self.last_config_hash and self.last_config_hash != current_hash:
            logger.warning("Configuration change detected")
            # Trigger configuration validation
            health = self.check_configuration_health()
            if not health["valid"]:
                logger.error(f"Invalid configuration: {health['errors']}")

        self.last_config_hash = current_hash

    def log_configuration_summary(self):
        """Log current configuration summary."""
        logger.info(f"Environment: {self.settings.environment}")
        logger.info(f"Debug mode: {self.settings.debug}")
        logger.info(f"Database pool size: {self.settings.database_pool_size}")
        logger.info(f"API workers: {self.settings.api_workers}")
        logger.info(f"Features enabled: {self._get_enabled_features()}")

    def _get_enabled_features(self) -> List[str]:
        """Get list of enabled features."""
        features = []
        for attr in dir(self.settings):
            if attr.startswith('enable_') and getattr(self.settings, attr):
                features.append(attr)
        return features
```

---

*GitWrite's configuration management system provides secure, scalable, and maintainable configuration handling across all environments. The system includes comprehensive validation, secrets management, feature flags, and monitoring to ensure reliable operation in any deployment scenario.*