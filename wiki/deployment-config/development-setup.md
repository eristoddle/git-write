# Development Setup

Comprehensive guide for setting up GitWrite development environment, including local development, testing, and deployment preparation. This guide ensures consistent development experience across team members and environments.

## Quick Start

### Prerequisites

- **Python 3.11+** (backend and CLI)
- **Node.js 18+** (frontend)
- **PostgreSQL 14+** (database)
- **Redis 7+** (caching and sessions)
- **Git 2.30+** (version control)
- **Docker & Docker Compose** (containerization)

### One-Command Setup

```bash
# Clone and setup everything
git clone https://github.com/your-org/gitwrite.git
cd gitwrite
./scripts/setup-dev.sh
```

## Detailed Setup

### 1. Environment Configuration

```bash
# Create environment files
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# Edit configuration
vim .env  # Backend configuration
vim frontend/.env.local  # Frontend configuration
```

#### Backend Environment (.env)

```bash
# Database
DATABASE_URL=postgresql://gitwrite:gitwrite@localhost:5432/gitwrite_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=0

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10

# Security
SECRET_KEY=your-secret-key-here-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
PASSWORD_SALT_ROUNDS=12

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
DEBUG=true
LOG_LEVEL=DEBUG

# Git Configuration
GIT_STORAGE_PATH=./data/repositories
GIT_DEFAULT_BRANCH=main
GIT_AUTHOR_NAME=GitWrite System
GIT_AUTHOR_EMAIL=system@gitwrite.com

# Email (for development)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=noreply@gitwrite.local

# File Upload
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_FILE_TYPES=.md,.txt,.docx,.pdf
UPLOAD_PATH=./data/uploads

# External Services
OPENAI_API_KEY=your-openai-key  # Optional for AI features
SENTRY_DSN=  # Optional for error tracking
```

#### Frontend Environment (.env.local)

```bash
# API Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws

# Authentication
REACT_APP_JWT_STORAGE_KEY=gitwrite_token
REACT_APP_REFRESH_TOKEN_KEY=gitwrite_refresh

# Features
REACT_APP_ENABLE_COLLABORATION=true
REACT_APP_ENABLE_AI_FEATURES=false
REACT_APP_ENABLE_ANALYTICS=false

# Development
REACT_APP_ENV=development
GENERATE_SOURCEMAP=true
FAST_REFRESH=true
```

### 2. Database Setup

#### Using Docker (Recommended)

```bash
# Start PostgreSQL and Redis
docker-compose -f docker-compose.dev.yml up -d postgres redis

# Wait for services to be ready
./scripts/wait-for-services.sh
```

#### Manual Installation

```bash
# PostgreSQL setup
createuser -s gitwrite
createdb -O gitwrite gitwrite_dev
createdb -O gitwrite gitwrite_test

# Redis setup (usually runs on default settings)
redis-server --daemonize yes
```

#### Database Migration

```bash
# Install backend dependencies first
cd backend
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Create initial admin user (optional)
python scripts/create_admin.py --email admin@example.com --password admin123
```

### 3. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install

# Start development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Backend Development Commands

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=backend

# Format code
black .
isort .

# Lint code
flake8 .
mypy .

# Security check
bandit -r backend/

# Generate API documentation
python scripts/generate_docs.py
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Open browser
open http://localhost:3000
```

#### Frontend Development Commands

```bash
# Type checking
npm run type-check

# Linting
npm run lint
npm run lint:fix

# Testing
npm run test
npm run test:watch
npm run test:coverage

# Build
npm run build
npm run preview

# Storybook (component development)
npm run storybook
```

### 5. CLI Development Setup

```bash
# Install CLI in development mode
pip install -e ".[cli]"

# Test CLI installation
gitwrite --version
gitwrite --help

# Run CLI tests
pytest tests/cli/

# Test CLI commands
gitwrite repository create test-repo --description "Test repository"
```

## Development Workflow

### Git Workflow

```bash
# Feature development
git checkout develop
git pull origin develop
git checkout -b feature/new-feature

# Development cycle
# ... make changes ...
git add .
git commit -m "feat: add new feature"

# Pre-push checks
./scripts/pre-push-checks.sh

# Push and create PR
git push origin feature/new-feature
# Create PR: feature/new-feature -> develop
```

### Testing Workflow

```bash
# Run all tests
./scripts/test-all.sh

# Run specific test suites
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/e2e/           # End-to-end tests

# Frontend tests
cd frontend
npm run test:unit
npm run test:integration
npm run test:e2e

# Performance tests
pytest tests/performance/ -m performance
```

### Code Quality Checks

```bash
# Automated checks (runs in CI)
./scripts/quality-checks.sh

# Manual checks
black --check .               # Code formatting
isort --check-only .         # Import sorting
flake8 .                     # Linting
mypy .                       # Type checking
bandit -r backend/           # Security
pytest --cov=backend        # Test coverage
```

## Development Tools

### Recommended IDE Setup

#### VS Code Extensions

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "ms-python.flake8",
    "ms-python.mypy-type-checker",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next",
    "ms-playwright.playwright"
  ]
}
```

#### VS Code Settings

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### Database Tools

```bash
# pgAdmin (Web interface)
docker run -d \
  -p 5050:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@gitwrite.local \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  dpage/pgadmin4

# Redis CLI
redis-cli monitor  # Monitor Redis operations

# Database migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

### API Development

```bash
# Interactive API docs
open http://localhost:8000/docs

# Alternative API docs
open http://localhost:8000/redoc

# Test API endpoints
curl -X GET "http://localhost:8000/health"
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

## Debugging and Troubleshooting

### Common Issues

#### Database Connection Issues

```bash
# Check PostgreSQL status
pg_isready -h localhost -p 5432

# Check database exists
psql -h localhost -U gitwrite -l

# Reset database
dropdb gitwrite_dev
createdb -O gitwrite gitwrite_dev
alembic upgrade head
```

#### Port Conflicts

```bash
# Check what's using port 8000
lsof -i :8000

# Use different port
export API_PORT=8001
uvicorn backend.main:app --reload --port 8001

# Frontend proxy configuration
# Update vite.config.ts proxy settings
```

#### Python Environment Issues

```bash
# Recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,test]"

# Clear pip cache
pip cache purge

# Upgrade pip
python -m pip install --upgrade pip
```

### Debug Configuration

#### Backend Debugging

```python
# backend/main.py - Add debug middleware
if settings.DEBUG:
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    # debugpy.wait_for_client()  # Uncomment to wait for debugger
```

#### Frontend Debugging

```javascript
// Frontend debugging in Chrome DevTools
// Enable React Developer Tools
// Use React Query DevTools for state inspection

// Add to frontend/src/main.tsx for development
if (import.meta.env.DEV) {
  import('./debug').then(({ setupDebug }) => setupDebug());
}
```

### Performance Profiling

```bash
# Backend profiling
pip install py-spy
py-spy record -o profile.svg -- uvicorn backend.main:app

# Database query profiling
pip install django-debug-toolbar  # Adapt for FastAPI
# Add SQL query logging in development

# Frontend profiling
# Use Chrome DevTools Performance tab
# React Profiler in React DevTools
# Bundle analyzer: npm run analyze
```

## Automation Scripts

### Development Scripts

```bash
# scripts/setup-dev.sh
#!/bin/bash
set -e

echo "Setting up GitWrite development environment..."

# Install system dependencies
./scripts/install-system-deps.sh

# Setup backend
echo "Setting up backend..."
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,test]"

# Setup frontend
echo "Setting up frontend..."
cd frontend
npm install
cd ..

# Setup database
echo "Setting up database..."
docker-compose -f docker-compose.dev.yml up -d postgres redis
./scripts/wait-for-services.sh
alembic upgrade head

# Setup environment files
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

echo "Development environment setup complete!"
echo "Run './scripts/start-dev.sh' to start all services"
```

```bash
# scripts/start-dev.sh
#!/bin/bash

# Start services in background
echo "Starting development services..."

# Start database services
docker-compose -f docker-compose.dev.yml up -d postgres redis

# Wait for services
./scripts/wait-for-services.sh

# Start backend
echo "Starting backend..."
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Development servers started:"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8000/docs"

# Cleanup function
cleanup() {
    echo "Stopping development servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    docker-compose -f docker-compose.dev.yml down
}

trap cleanup EXIT
wait
```

### Quality Assurance Scripts

```bash
# scripts/quality-checks.sh
#!/bin/bash
set -e

echo "Running quality checks..."

# Backend checks
echo "Backend code quality..."
black --check .
isort --check-only .
flake8 .
mypy .
bandit -r backend/

# Frontend checks
echo "Frontend code quality..."
cd frontend
npm run lint
npm run type-check
cd ..

# Security checks
echo "Security checks..."
safety check
npm audit --audit-level=moderate

# Test coverage
echo "Test coverage..."
pytest --cov=backend --cov-fail-under=80

echo "All quality checks passed!"
```

---

*This development setup guide provides everything needed to get GitWrite running locally, from initial setup to advanced debugging and profiling. Following these guidelines ensures a consistent and productive development experience for all team members.*