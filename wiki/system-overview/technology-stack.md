# Technology Stack

GitWrite is built on a carefully selected technology stack that prioritizes reliability, performance, and developer experience while maintaining accessibility for the writing community. The stack is designed to be modern, maintainable, and scalable.

## Technology Overview

GitWrite follows a multi-tier architecture with distinct technology choices for each layer:

```
┌─────────────────────────────────────────────┐
│               Frontend Layer                │
│  React 18 + TypeScript + Tailwind CSS      │
│  Vite (Build) + Vitest (Testing)           │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              Integration Layer              │
│  TypeScript SDK + REST API Client          │
│  Jest (Testing) + Rollup (Build)           │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│               Backend Layer                 │
│  FastAPI + Python 3.10 + Uvicorn          │
│  Pydantic (Validation) + JWT (Auth)        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              Core Logic Layer               │
│  Python 3.10 + pygit2 + Click             │
│  Poetry (Dependencies) + pytest (Testing)  │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│             Data Storage Layer              │
│  Git (libgit2) + File System               │
│  No Traditional Database Required          │
└─────────────────────────────────────────────┘
```

## Backend Technologies

### Core Language: Python 3.10

**Rationale:**
- Excellent library ecosystem for text processing
- Strong Git integration through pygit2
- Mature web framework ecosystem
- Cross-platform compatibility
- Strong typing support with modern Python features

**Key Features Used:**
- Type hints for better code quality
- Dataclasses for clean data structures
- Async/await for web API performance
- Pattern matching (Python 3.10+)
- Context managers for resource management

### Web Framework: FastAPI

**Rationale:**
- Automatic API documentation generation
- Built-in type validation with Pydantic
- High performance with async support
- Modern Python async/await patterns
- Excellent developer experience

**Key Features:**
```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI(
    title="GitWrite API",
    description="Version control for writers",
    version="1.0.0"
)

class SaveRequest(BaseModel):
    message: str
    files: Optional[List[str]] = None

@app.post("/repositories/{repo_name}/save")
async def save_changes(
    repo_name: str,
    request: SaveRequest,
    current_user: User = Depends(get_current_user)
):
    # Automatic validation, authentication, and documentation
    pass
```

**Benefits:**
- Automatic OpenAPI/Swagger documentation
- Built-in validation reduces boilerplate
- Type safety from request to response
- Easy testing with built-in test client
- Production-ready performance

### Git Integration: pygit2 (libgit2)

**Rationale:**
- Native performance without subprocess overhead
- Consistent behavior across platforms
- Direct access to Git internals
- Better error handling than shell commands
- Thread-safe operations

**Architecture:**
```python
import pygit2

# Direct Git operations with full control
repo = pygit2.Repository('/path/to/repo')
index = repo.index
index.add_all()
index.write()

signature = pygit2.Signature('Author', 'author@example.com')
tree = index.write_tree()
commit_id = repo.create_commit(
    'HEAD', signature, signature,
    'Commit message', tree, [repo.head.target]
)
```

**Advantages:**
- No dependency on Git CLI installation
- Better performance for large repositories
- Precise control over Git operations
- Robust error handling
- Support for advanced Git features

### CLI Framework: Click

**Rationale:**
- Intuitive command-line interface creation
- Automatic help generation
- Parameter validation and type conversion
- Nested command support
- Excellent testing support

**Implementation:**
```python
import click

@click.group()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """GitWrite - Version control for writers"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

@cli.command()
@click.argument('message')
@click.option('--files', multiple=True, help='Specific files to save')
def save(message, files):
    """Save your work with a descriptive message"""
    result = gitwrite_core.save_changes(message, list(files) or None)
    click.echo(f"✓ {result.message}")
```

### Dependency Management: Poetry

**Rationale:**
- Modern Python dependency management
- Deterministic builds with lock files
- Virtual environment management
- Easy publishing to PyPI
- Clean separation of dev/prod dependencies

**Configuration Example:**
```toml
[tool.poetry]
name = "gitwrite"
version = "1.0.0"
description = "Version control platform for writers"

[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.104.0"
pygit2 = "^1.13.0"
click = "^8.1.0"
pydantic = "^2.4.0"
uvicorn = "^0.24.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
black = "^23.0.0"
mypy = "^1.6.0"
```

### Testing: pytest + pytest-asyncio

**Rationale:**
- Comprehensive testing framework
- Async test support for FastAPI
- Excellent fixture system
- Parametrized testing
- Rich plugin ecosystem

## Frontend Technologies

### Core Framework: React 18

**Rationale:**
- Mature component-based architecture
- Excellent TypeScript integration
- Large ecosystem and community
- Server-side rendering capabilities
- Concurrent features for better UX

**Key Features Used:**
- Function components with hooks
- Context API for state management
- Suspense for loading states
- Error boundaries for robustness
- React Query for server state

### Language: TypeScript

**Rationale:**
- Type safety reduces runtime errors
- Better development experience with IntelliSense
- Self-documenting code
- Refactoring safety
- Gradual adoption path

**Type System Benefits:**
```typescript
interface Repository {
  name: string;
  owner: string;
  created_at: string;
  status: 'active' | 'archived' | 'draft';
}

interface CommitInfo {
  id: string;
  message: string;
  author: string;
  timestamp: Date;
  files_changed: number;
}

// Type-safe API calls
const commits: CommitInfo[] = await apiClient.getCommits(repository.name);
```

### Build Tool: Vite

**Rationale:**
- Lightning-fast development server
- Optimized production builds
- Modern ES modules support
- Plugin ecosystem
- TypeScript support out of the box

**Configuration:**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
```

### Styling: Tailwind CSS

**Rationale:**
- Utility-first approach reduces custom CSS
- Consistent design system
- Responsive design built-in
- Tree-shaking for optimal bundle size
- Easy customization and theming

**Example Usage:**
```tsx
function SaveButton({ onSave, disabled }: SaveButtonProps) {
  return (
    <button
      onClick={onSave}
      disabled={disabled}
      className="
        bg-blue-600 hover:bg-blue-700
        disabled:bg-gray-400 disabled:cursor-not-allowed
        text-white font-medium py-2 px-4 rounded-lg
        transition-colors duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500
      "
    >
      Save Changes
    </button>
  );
}
```

### UI Components: Radix UI + Custom Components

**Rationale:**
- Accessible components out of the box
- Unstyled primitives for customization
- Compound component patterns
- Keyboard navigation support
- WAI-ARIA compliance

## SDK Technologies

### TypeScript SDK

**Rationale:**
- Consistent API across all JavaScript/TypeScript applications
- Type safety for third-party integrations
- Auto-completion in IDEs
- Runtime validation
- Easy integration testing

**SDK Architecture:**
```typescript
class GitWriteClient {
  constructor(
    private apiUrl: string,
    private apiKey?: string
  ) {}

  repositories = {
    create: (config: RepositoryConfig): Promise<Repository> => {
      return this.request('POST', '/repositories', config);
    },

    save: (repoName: string, data: SaveRequest): Promise<CommitInfo> => {
      return this.request('POST', `/repositories/${repoName}/save`, data);
    }
  };

  private async request<T>(
    method: string,
    path: string,
    data?: any
  ): Promise<T> {
    // HTTP client implementation with error handling
  }
}
```

### Build Tool: Rollup

**Rationale:**
- Optimized for library building
- Tree-shaking for smaller bundles
- Multiple output formats (ESM, CJS, UMD)
- TypeScript support
- Plugin ecosystem

## Infrastructure Technologies

### Containerization: Docker

**Rationale:**
- Consistent deployment environments
- Easy local development setup
- Scalable deployment options
- Dependency isolation
- Cloud platform compatibility

**Multi-stage Dockerfile:**
```dockerfile
# Build stage
FROM node:18-alpine AS frontend-build
WORKDIR /app/frontend
COPY gitwrite-web/package*.json ./
RUN npm ci --only=production
COPY gitwrite-web/ ./
RUN npm run build

# Python stage
FROM python:3.10-slim AS backend
RUN apt-get update && apt-get install -y \
    libgit2-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY . .
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "gitwrite_api.main:app", "--host", "0.0.0.0"]
```

### Web Server: Uvicorn (ASGI)

**Rationale:**
- High-performance ASGI server
- async/await support
- WebSocket support for future features
- Production-ready
- Easy scaling options

### Document Processing: Pandoc

**Rationale:**
- Universal document converter
- High-quality output formats
- Extensive format support
- Template system
- Command-line integration

**Integration:**
```python
import subprocess
from pathlib import Path

def export_to_epub(
    markdown_content: str,
    metadata: dict,
    output_path: str
) -> bool:
    """Export markdown to EPUB using Pandoc"""
    temp_md = Path("temp.md")
    temp_md.write_text(markdown_content)

    cmd = [
        "pandoc",
        str(temp_md),
        "-o", output_path,
        "--epub-metadata", create_metadata_file(metadata),
        "--template", "epub-template.html"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    temp_md.unlink()  # Clean up

    return result.returncode == 0
```

## Development Tools

### Code Quality

**Linting and Formatting:**
- **Python**: Black (formatting) + flake8 (linting) + mypy (type checking)
- **TypeScript**: ESLint + Prettier
- **Pre-commit hooks**: Automated code quality checks

**Configuration Examples:**
```json
// .eslintrc.json
{
  "extends": [
    "@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "react/react-in-jsx-scope": "off"
  }
}
```

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py310']

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
```

### Testing Strategy

**Backend Testing:**
- Unit tests with pytest
- Integration tests for API endpoints
- Git operation testing with temporary repositories
- Property-based testing for complex scenarios

**Frontend Testing:**
- Component testing with React Testing Library
- End-to-end testing with Playwright
- Visual regression testing
- Accessibility testing

**Example Test:**
```python
import pytest
from gitwrite_core import repository

@pytest.fixture
def temp_repo(tmp_path):
    """Create temporary repository for testing"""
    config = repository.ProjectConfig(
        name="Test Project",
        author="Test Author"
    )
    result = repository.GitWriteRepository.initialize(str(tmp_path), config)
    return result.repository

def test_save_changes(temp_repo):
    """Test saving changes to repository"""
    # Write test content
    (temp_repo.path / "test.md").write_text("Test content")

    # Save changes
    result = temp_repo.save_changes("Added test content")

    assert result.success
    assert "test content" in result.message.lower()
    assert result.commit_id is not None
```

## Performance Considerations

### Backend Performance

**Optimization Strategies:**
- Async/await for I/O operations
- Connection pooling for database operations
- Caching with Redis for frequently accessed data
- Background tasks for long-running operations
- Lazy loading of Git objects

### Frontend Performance

**Optimization Techniques:**
- Code splitting with React.lazy
- Virtual scrolling for large lists
- Memoization with React.memo and useMemo
- Bundle optimization with Vite
- Service worker for offline capabilities

### Git Performance

**Large Repository Handling:**
- Shallow clones for initial setup
- Sparse checkout for large projects
- Git LFS for binary assets
- Incremental loading of commit history
- Efficient diff algorithms

## Security Considerations

### Authentication & Authorization

**Security Measures:**
- JWT tokens with expiration
- Role-based access control (RBAC)
- Secure password hashing with bcrypt
- HTTPS enforcement
- Input validation and sanitization

### Data Protection

**Privacy & Security:**
- Git repository encryption options
- Secure file upload handling
- XSS protection in frontend
- CSRF protection for API endpoints
- Regular security dependency updates

---

*This technology stack provides a solid, modern foundation for GitWrite while prioritizing the unique needs of writers and collaborative writing workflows. Each technology choice is made with consideration for reliability, performance, and maintainability.*