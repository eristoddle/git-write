# Layered Architecture

GitWrite implements a strict layered architecture that promotes separation of concerns, maintainability, and scalability. Each layer has well-defined responsibilities and communicates only with adjacent layers through established interfaces.

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│               Presentation Layer            │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Web Client  │  │    CLI Tool         │   │
│  │ (React/TS)  │  │    (Python)         │   │
│  └─────────────┘  └─────────────────────┘   │
└─────────────┬───────────────┬───────────────┘
              │               │
┌─────────────▼───────────────▼───────────────┐
│              Integration Layer              │
│  ┌─────────────────────────────────────────┐ │
│  │         TypeScript SDK                  │ │
│  │       (Client Libraries)                │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              Application Layer              │
│  ┌─────────────────────────────────────────┐ │
│  │            FastAPI Server              │ │
│  │          (REST Endpoints)              │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│             Business Logic Layer           │
│  ┌─────────────────────────────────────────┐ │
│  │           GitWrite Core                 │ │
│  │         (Domain Logic)                  │ │
│  └─────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│             Data Access Layer              │
│  ┌─────────────────────────────────────────┐ │
│  │            pygit2/libgit2               │ │
│  │          (Git Operations)               │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Layer Responsibilities

### Presentation Layer
**Purpose**: User interface and user experience

**Components**:
- Web Client (React/TypeScript)
- CLI Tool (Python Click)
- Future: Mobile app, IDE plugins

**Responsibilities**:
- User input handling and validation
- UI state management
- Display formatting and styling
- User interaction workflows
- Error message presentation

**Key Principles**:
- No business logic
- Framework-specific code only
- User-friendly abstractions
- Responsive and accessible design

### Integration Layer
**Purpose**: Client-server communication abstraction

**Components**:
- TypeScript SDK
- API client libraries
- Authentication handlers

**Responsibilities**:
- HTTP communication management
- Request/response transformation
- Client-side caching
- Error handling and retry logic
- Type safety for API interactions

### Application Layer
**Purpose**: API gateway and request coordination

**Components**:
- FastAPI server
- REST endpoint definitions
- Middleware pipeline
- Authentication/authorization

**Responsibilities**:
- Request routing and validation
- Authentication and authorization
- Rate limiting and security
- Response formatting
- API documentation generation

### Business Logic Layer
**Purpose**: Core domain logic and Git abstractions

**Components**:
- GitWrite Core library
- Domain models and services
- Business rule enforcement
- Git operation abstractions

**Responsibilities**:
- Writer-friendly Git operations
- Domain logic implementation
- Data validation and constraints
- Business rule enforcement
- Cross-cutting concerns

### Data Access Layer
**Purpose**: Git repository and file system operations

**Components**:
- pygit2 bindings
- File system operations
- Git repository management

**Responsibilities**:
- Git command execution
- File system interaction
- Data persistence
- Transaction management
- Low-level error handling

## Communication Patterns

### Unidirectional Dependencies
```
Presentation → Integration → Application → Business Logic → Data Access
```

Each layer depends only on the layer below it, ensuring:
- Clear separation of concerns
- Easier testing and mocking
- Reduced coupling
- Better maintainability

### Interface Contracts
Each layer defines clear interfaces for communication:

```python
# Business Logic Layer Interface
class RepositoryService:
    def create_repository(self, config: RepoConfig) -> RepositoryResult
    def save_changes(self, message: str, files: List[str]) -> SaveResult
    def get_history(self, limit: int) -> List[CommitInfo]

# Data Access Layer Interface
class GitRepository:
    def init_repository(self, path: str) -> bool
    def commit_changes(self, message: str, files: List[str]) -> str
    def get_commit_log(self, limit: int) -> List[GitCommit]
```

## Benefits of Layered Architecture

### Maintainability
- **Clear Boundaries**: Each layer has well-defined responsibilities
- **Isolation**: Changes in one layer don't affect others
- **Modularity**: Components can be developed independently

### Testability
- **Layer Isolation**: Each layer can be tested independently
- **Mock Interfaces**: Easy to mock dependencies
- **Unit Testing**: Clear units of functionality

### Scalability
- **Horizontal Scaling**: Layers can be scaled independently
- **Load Distribution**: Different layers can run on different servers
- **Technology Flexibility**: Layers can use different technologies

### Technology Flexibility
- **Layer Independence**: Each layer can use optimal technologies
- **Future-Proofing**: Easier to replace individual layers
- **Incremental Upgrades**: Upgrade layers independently

## Implementation Examples

### Cross-Layer Data Flow
```python
# 1. Presentation Layer (React Component)
const handleSave = async (message: string) => {
  try {
    // 2. Integration Layer (SDK)
    const result = await gitwriteClient.repositories.save(repoName, {
      message,
      files: selectedFiles
    });

    // Update UI state
    setSaveStatus('success');
  } catch (error) {
    setSaveStatus('error');
  }
};

# 3. Application Layer (FastAPI)
@router.post("/{repo_name}/save")
async def save_changes(
    repo_name: str,
    save_data: SaveRequest,
    current_user: User = Depends(get_current_user)
):
    # 4. Business Logic Layer
    result = await repository_service.save_changes(
        repo_name, save_data.message, save_data.files, current_user
    )
    return result

# 5. Business Logic Layer (GitWrite Core)
class RepositoryService:
    def save_changes(self, repo_name: str, message: str, files: List[str], user: User):
        # Validate business rules
        if not self._validate_save_permissions(user, repo_name):
            raise PermissionError("User cannot save to this repository")

        # 6. Data Access Layer
        return self.git_repository.commit_changes(message, files)

# 7. Data Access Layer (pygit2)
class GitRepository:
    def commit_changes(self, message: str, files: List[str]) -> str:
        index = self.repo.index
        for file in files:
            index.add(file)
        index.write()

        tree = index.write_tree()
        return self.repo.create_commit('HEAD', signature, signature, message, tree, [])
```

### Error Handling Across Layers
```python
# Data Access Layer - Low-level Git errors
try:
    commit_id = repo.create_commit(...)
except pygit2.GitError as e:
    raise DataAccessError(f"Git operation failed: {e}")

# Business Logic Layer - Domain-specific errors
try:
    result = git_repo.commit_changes(message, files)
except DataAccessError as e:
    if "merge conflict" in str(e):
        raise MergeConflictError("Changes conflict with existing work",
                               suggestions=["Review conflicts", "Resolve manually"])
    raise RepositoryError(f"Failed to save changes: {e}")

# Application Layer - HTTP-appropriate errors
try:
    result = repository_service.save_changes(...)
except MergeConflictError as e:
    raise HTTPException(status_code=409, detail={
        "code": "MERGE_CONFLICT",
        "message": str(e),
        "suggestions": e.suggestions
    })

# Integration Layer - Client-friendly errors
try:
    result = await api_client.post('/save', data)
except HTTPException as e:
    if e.status_code == 409:
        throw new ConflictError(e.detail.message, e.detail.suggestions)

# Presentation Layer - User-friendly display
try {
    await gitwriteClient.save(message, files);
    showSuccessMessage("Changes saved successfully");
} catch (ConflictError as e) {
    showConflictDialog(e.message, e.suggestions);
}
```

---

*The layered architecture ensures GitWrite remains maintainable and scalable while providing clear boundaries for development teams and enabling independent evolution of each system component.*