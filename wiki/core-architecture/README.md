# Core Architecture

GitWrite's architecture is built on proven software engineering principles, emphasizing modularity, maintainability, and extensibility. The system follows a layered architecture pattern with clear separation of concerns between presentation, business logic, and data access layers.

## Architectural Principles

### 1. Layered Architecture
GitWrite implements a strict layered architecture where each layer only communicates with adjacent layers, ensuring loose coupling and high cohesion.

```
┌─────────────────────────────────────────────┐
│           Presentation Layer                │
│  ┌─────────────┐  ┌─────────────┐         │
│  │ Web Client  │  │ CLI Tool    │         │
│  │ (React/TS)  │  │ (Python)    │         │
│  └─────────────┘  └─────────────┘         │
└─────────────┬───────────────┬───────────────┘
              │               │
┌─────────────▼───────────────▼───────────────┐
│              API Gateway                    │
│         ┌─────────────────────┐             │
│         │    FastAPI Server   │             │
│         │   (REST Endpoints)  │             │
│         └─────────────────────┘             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│            Business Logic Layer             │
│         ┌─────────────────────┐             │
│         │   gitwrite_core     │             │
│         │  (Python Library)   │             │
│         └─────────────────────┘             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│            Data Access Layer                │
│         ┌─────────────────────┐             │
│         │      pygit2         │             │
│         │   (Git Operations)  │             │
│         └─────────────────────┘             │
└─────────────────────────────────────────────┘
```

### 2. Separation of Concerns
Each component has a single, well-defined responsibility:

- **Presentation Layer**: User interface and user experience
- **API Gateway**: Request routing, authentication, and validation
- **Business Logic**: Domain-specific operations and Git abstractions
- **Data Access**: Direct Git repository manipulation

### 3. Dependency Inversion
Higher-level modules do not depend on lower-level modules. Both depend on abstractions, enabling easier testing and modification.

## Component Architecture

### Presentation Layer Components

#### Web Client (`gitwrite-web`)
- **Technology**: React 18 with TypeScript
- **Purpose**: Browser-based interface for GitWrite operations
- **Key Features**:
  - Responsive design with Tailwind CSS
  - Real-time diff visualization
  - Interactive project management
  - Role-based UI elements

#### CLI Tool (`gitwrite_cli`)
- **Technology**: Python Click framework
- **Purpose**: Command-line interface for power users and automation
- **Key Features**:
  - Writer-friendly command syntax
  - Rich terminal output with color and formatting
  - Configuration management
  - Integration with external tools

### API Gateway Layer

#### FastAPI Server (`gitwrite_api`)
- **Technology**: FastAPI with Uvicorn ASGI server
- **Purpose**: Centralized API gateway for all client interactions
- **Key Responsibilities**:
  - Request authentication and authorization
  - Input validation and sanitization
  - Response formatting and error handling
  - Route management and middleware

#### Router Architecture
```
gitwrite_api/
├── routers/
│   ├── auth.py          # Authentication endpoints
│   ├── repository.py    # Repository operations
│   ├── annotations.py   # Feedback and comments
│   └── uploads.py       # File management
├── models.py            # Pydantic data models
├── security.py          # JWT and authentication
└── main.py             # Application configuration
```

### Business Logic Layer

#### Core Engine (`gitwrite_core`)
- **Technology**: Pure Python with pygit2 bindings
- **Purpose**: Domain logic and Git operation abstractions
- **Key Modules**:
  - `repository.py`: Repository management and initialization
  - `versioning.py`: Change tracking and history management
  - `branching.py`: Exploration (branch) operations
  - `annotations.py`: Feedback and comment system
  - `export.py`: Document generation and formatting
  - `tagging.py`: Version milestone management
  - `exceptions.py`: Domain-specific error handling

### Data Access Layer

#### Git Operations (`pygit2`)
- **Technology**: libgit2 Python bindings
- **Purpose**: Direct Git repository manipulation
- **Advantages**:
  - Performance: No subprocess overhead
  - Reliability: Consistent cross-platform behavior
  - Features: Access to advanced Git features
  - Safety: Better error handling than shell commands

## Design Patterns

### 1. Facade Pattern
The `gitwrite_core` module acts as a facade, hiding Git's complexity behind writer-friendly operations.

```python
# Complex Git operations hidden behind simple interface
def save_changes(message: str, files: List[str] = None):
    """Save changes with a descriptive message (Git commit)"""
    # Internally handles:
    # - git add (staging)
    # - git commit (saving)
    # - error handling
    # - metadata management
```

### 2. Adapter Pattern
GitWrite adapts Git terminology to writer-friendly concepts:

| Git Concept | GitWrite Concept | Purpose |
|-------------|------------------|---------|
| Repository | Project | Writing project container |
| Commit | Save | Record changes |
| Branch | Exploration | Alternative versions |
| Tag | Milestone | Important versions |
| Merge | Combine | Integrate changes |
| Cherry-pick | Select | Choose specific changes |

### 3. Strategy Pattern
Different export formats use the strategy pattern for flexible document generation:

```python
class ExportStrategy:
    def export(self, content: str, metadata: dict) -> bytes:
        pass

class EPUBExportStrategy(ExportStrategy):
    def export(self, content: str, metadata: dict) -> bytes:
        # EPUB-specific generation logic
        pass

class PDFExportStrategy(ExportStrategy):
    def export(self, content: str, metadata: dict) -> bytes:
        # PDF-specific generation logic
        pass
```

### 4. Observer Pattern
The annotation system uses observers to notify reviewers of changes:

```python
class AnnotationObserver:
    def on_annotation_added(self, annotation: Annotation):
        # Notify relevant users
        pass

    def on_annotation_resolved(self, annotation: Annotation):
        # Update review status
        pass
```

## Data Flow Architecture

### Request Flow
1. **User Interaction**: User performs action in web client or CLI
2. **API Request**: Client sends HTTP request to FastAPI server
3. **Authentication**: JWT token validation and user authorization
4. **Validation**: Request data validation using Pydantic models
5. **Business Logic**: Core module processes the request
6. **Git Operations**: pygit2 performs actual Git operations
7. **Response**: Results propagated back through the stack

### Event Flow
```
User Action
    ↓
Client Interface (Web/CLI)
    ↓
API Gateway (FastAPI)
    ↓
Core Business Logic
    ↓
Git Operations (pygit2)
    ↓
File System (Git Repository)
    ↓
Response Chain (reverse flow)
    ↓
User Feedback
```

## Error Handling Strategy

### Layered Error Handling
Each layer handles errors appropriate to its level of abstraction:

1. **Git Layer**: Low-level Git errors (file conflicts, repository corruption)
2. **Core Layer**: Business logic errors (invalid operations, constraint violations)
3. **API Layer**: HTTP errors (authentication failures, validation errors)
4. **Client Layer**: User-friendly error messages and recovery suggestions

### Error Types
```python
# Core domain exceptions
class GitWriteError(Exception):
    """Base exception for all GitWrite operations"""

class RepositoryError(GitWriteError):
    """Repository-related errors"""

class MergeConflictError(GitWriteError):
    """Merge conflict requiring user resolution"""

class PermissionError(GitWriteError):
    """Insufficient permissions for operation"""
```

## Performance Considerations

### Optimization Strategies
- **Lazy Loading**: Load repository data only when needed
- **Caching**: Cache frequently accessed Git objects
- **Streaming**: Stream large file operations to reduce memory usage
- **Batching**: Batch multiple Git operations for efficiency

### Scalability Design
- **Stateless API**: API servers can be horizontally scaled
- **Database-Free**: Git repositories serve as the data store
- **Microservice-Ready**: Components can be extracted into separate services
- **Container-Native**: Docker support for cloud deployment

## Security Architecture

### Authentication Flow
```
User Login
    ↓
JWT Token Generation
    ↓
Token Storage (Client)
    ↓
API Request with Token
    ↓
Token Validation
    ↓
User Authorization
    ↓
Operation Execution
```

### Security Layers
1. **Transport Security**: HTTPS for all communications
2. **Authentication**: JWT tokens with expiration
3. **Authorization**: Role-based access control
4. **Input Validation**: Pydantic models and sanitization
5. **Git Security**: Repository-level access controls

---

*This architecture ensures GitWrite is maintainable, scalable, and extensible while providing a stable foundation for the writer-centric features that make it unique.*