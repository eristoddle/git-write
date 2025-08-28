# API Testing

Comprehensive testing strategy for GitWrite's backend API, covering unit tests, integration tests, contract testing, and automated API validation to ensure robust and reliable service endpoints.

## Testing Strategy Overview

```
API Testing Pyramid
    │
    ├─ Contract Tests (10%)
    │   └─ API Specification Validation
    │
    ├─ Integration Tests (30%)
    │   ├─ Database Integration
    │   ├─ External Service Integration
    │   └─ End-to-End API Flows
    │
    └─ Unit Tests (60%)
        ├─ Route Handler Tests
        ├─ Service Layer Tests
        └─ Validation Tests
```

## Unit Testing

### FastAPI Route Testing

```python
# tests/unit/test_repositories.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.main import app
from app.models import Repository
from app.services.repository_service import RepositoryService

client = TestClient(app)

@pytest.fixture
def mock_repository_service():
    with patch('app.routes.repositories.repository_service') as mock:
        yield mock

@pytest.fixture
def sample_repository():
    return Repository(
        id="test-repo-id",
        name="test-repository",
        description="Test repository",
        owner_id="user-123",
        is_public=False
    )

class TestRepositoryRoutes:

    def test_list_repositories_success(self, mock_repository_service, sample_repository):
        # Arrange
        mock_repository_service.list_repositories.return_value = {
            "items": [sample_repository],
            "total": 1,
            "page": 1,
            "pages": 1
        }

        # Act
        response = client.get("/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "test-repository"
        mock_repository_service.list_repositories.assert_called_once()

    def test_create_repository_success(self, mock_repository_service, sample_repository):
        mock_repository_service.create_repository.return_value = sample_repository

        repository_data = {
            "name": "new-repository",
            "description": "New test repository",
            "is_public": False
        }

        response = client.post("/repositories", json=repository_data)

        assert response.status_code == 201
        assert response.json()["name"] == "test-repository"
        mock_repository_service.create_repository.assert_called_once()

    def test_create_repository_validation_error(self):
        invalid_data = {"name": ""}  # Empty name should fail validation

        response = client.post("/repositories", json=invalid_data)

        assert response.status_code == 422
        assert "validation error" in response.json()["detail"][0]["type"]

    def test_get_repository_not_found(self, mock_repository_service):
        mock_repository_service.get_repository.side_effect = RepositoryNotFoundError()

        response = client.get("/repositories/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_repository_permission_denied(self, mock_repository_service):
        mock_repository_service.update_repository.side_effect = PermissionDeniedError()

        response = client.put("/repositories/test-repo", json={"description": "Updated"})

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
```

### Service Layer Testing

```python
# tests/unit/test_repository_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from app.services.repository_service import RepositoryService
from app.database.models import Repository
from app.exceptions import RepositoryNotFoundError

@pytest.fixture
def mock_db_session():
    return Mock()

@pytest.fixture
def repository_service(mock_db_session):
    return RepositoryService(db=mock_db_session)

class TestRepositoryService:

    @pytest.mark.asyncio
    async def test_create_repository_success(self, repository_service, mock_db_session):
        # Arrange
        create_data = {
            "name": "test-repo",
            "description": "Test repository",
            "owner_id": "user-123"
        }

        mock_db_session.add = Mock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Act
        result = await repository_service.create_repository(create_data)

        # Assert
        assert result.name == "test-repo"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_repository_not_found(self, repository_service, mock_db_session):
        mock_db_session.query().filter().first.return_value = None

        with pytest.raises(RepositoryNotFoundError):
            await repository_service.get_repository("nonexistent")

    @pytest.mark.asyncio
    async def test_list_repositories_with_pagination(self, repository_service, mock_db_session):
        mock_repositories = [
            Repository(id="1", name="repo1"),
            Repository(id="2", name="repo2")
        ]

        mock_query = Mock()
        mock_query.offset().limit().all.return_value = mock_repositories
        mock_query.count.return_value = 2
        mock_db_session.query.return_value = mock_query

        result = await repository_service.list_repositories(page=1, page_size=10)

        assert len(result["items"]) == 2
        assert result["total"] == 2
```

### Validation Testing

```python
# tests/unit/test_validators.py
import pytest
from pydantic import ValidationError
from app.schemas.repository import RepositoryCreateRequest, RepositoryUpdateRequest

class TestRepositoryValidation:

    def test_valid_repository_creation(self):
        data = {
            "name": "valid-repo-name",
            "description": "A valid repository description",
            "is_public": False
        }

        schema = RepositoryCreateRequest(**data)
        assert schema.name == "valid-repo-name"
        assert schema.is_public == False

    def test_invalid_repository_name(self):
        invalid_names = ["", "repo with spaces", "repo/with/slashes", "repo@with@symbols"]

        for invalid_name in invalid_names:
            with pytest.raises(ValidationError):
                RepositoryCreateRequest(name=invalid_name, description="Test")

    def test_description_length_validation(self):
        long_description = "x" * 1001  # Assuming 1000 char limit

        with pytest.raises(ValidationError):
            RepositoryCreateRequest(
                name="test-repo",
                description=long_description
            )

    def test_optional_fields_in_update(self):
        # Should allow partial updates
        update_data = {"description": "Updated description"}
        schema = RepositoryUpdateRequest(**update_data)
        assert schema.description == "Updated description"
        assert schema.name is None  # Should be optional in updates
```

## Integration Testing

### Database Integration Tests

```python
# tests/integration/test_repository_db.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_test_db
from app.services.repository_service import RepositoryService
from app.models import Repository, User

@pytest.fixture
async def db_session():
    async with get_test_db() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def test_user(db_session):
    user = User(
        email="test@example.com",
        name="Test User",
        username="testuser"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

class TestRepositoryDatabaseIntegration:

    @pytest.mark.asyncio
    async def test_repository_crud_operations(self, db_session, test_user):
        service = RepositoryService(db=db_session)

        # Create
        repository_data = {
            "name": "integration-test-repo",
            "description": "Integration test repository",
            "owner_id": test_user.id,
            "is_public": False
        }

        created_repo = await service.create_repository(repository_data)
        assert created_repo.id is not None

        # Read
        retrieved_repo = await service.get_repository(created_repo.id)
        assert retrieved_repo.name == "integration-test-repo"

        # Update
        updated_repo = await service.update_repository(
            created_repo.id,
            {"description": "Updated description"}
        )
        assert updated_repo.description == "Updated description"

        # Delete
        await service.delete_repository(created_repo.id)

        with pytest.raises(RepositoryNotFoundError):
            await service.get_repository(created_repo.id)

    @pytest.mark.asyncio
    async def test_repository_permissions(self, db_session, test_user):
        service = RepositoryService(db=db_session)

        # Create private repository
        repo = await service.create_repository({
            "name": "private-repo",
            "owner_id": test_user.id,
            "is_public": False
        })

        # Test owner permissions
        permissions = await service.get_user_permissions(repo.id, test_user.id)
        assert permissions.can_read == True
        assert permissions.can_write == True
        assert permissions.can_admin == True

        # Test non-owner permissions
        other_user = User(email="other@example.com", name="Other User")
        db_session.add(other_user)
        await db_session.commit()

        permissions = await service.get_user_permissions(repo.id, other_user.id)
        assert permissions.can_read == False  # Private repo
        assert permissions.can_write == False
```

### API Integration Tests

```python
# tests/integration/test_api_flows.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def authenticated_headers():
    # In real tests, this would use actual auth tokens
    return {"Authorization": "Bearer test-token"}

class TestRepositoryAPIFlows:

    def test_complete_repository_workflow(self, authenticated_headers):
        # Create repository
        create_response = client.post(
            "/repositories",
            json={
                "name": "workflow-test-repo",
                "description": "Workflow test",
                "is_public": False
            },
            headers=authenticated_headers
        )
        assert create_response.status_code == 201
        repo_data = create_response.json()
        repo_name = repo_data["name"]

        # Add file to repository
        file_response = client.post(
            f"/repositories/{repo_name}/files",
            json={
                "path": "chapter-01.md",
                "content": "# Chapter 1\n\nContent here...",
                "message": "Add first chapter"
            },
            headers=authenticated_headers
        )
        assert file_response.status_code == 201

        # List files
        files_response = client.get(
            f"/repositories/{repo_name}/files",
            headers=authenticated_headers
        )
        assert files_response.status_code == 200
        files = files_response.json()
        assert any(f["path"] == "chapter-01.md" for f in files)

        # Get commit history
        history_response = client.get(
            f"/repositories/{repo_name}/commits",
            headers=authenticated_headers
        )
        assert history_response.status_code == 200
        commits = history_response.json()
        assert len(commits) >= 1
        assert commits[0]["message"] == "Add first chapter"

        # Clean up
        delete_response = client.delete(
            f"/repositories/{repo_name}",
            headers=authenticated_headers
        )
        assert delete_response.status_code == 204

    def test_collaboration_workflow(self, authenticated_headers):
        # Create repository
        repo_response = client.post(
            "/repositories",
            json={"name": "collab-test", "description": "Collaboration test"},
            headers=authenticated_headers
        )
        repo_name = repo_response.json()["name"]

        # Invite collaborator
        invite_response = client.post(
            f"/repositories/{repo_name}/collaborators",
            json={
                "email": "collaborator@example.com",
                "role": "editor",
                "message": "Please help with editing"
            },
            headers=authenticated_headers
        )
        assert invite_response.status_code == 201

        # List collaborators
        collaborators_response = client.get(
            f"/repositories/{repo_name}/collaborators",
            headers=authenticated_headers
        )
        assert collaborators_response.status_code == 200
        collaborators = collaborators_response.json()
        assert any(c["email"] == "collaborator@example.com" for c in collaborators)
```

## Contract Testing

### OpenAPI Specification Testing

```python
# tests/contract/test_openapi_spec.py
import pytest
import yaml
from openapi_spec_validator import validate_spec
from app.main import app

def test_openapi_specification_is_valid():
    """Test that the generated OpenAPI specification is valid"""
    openapi_schema = app.openapi()

    # Validate against OpenAPI 3.0 specification
    validate_spec(openapi_schema)

def test_all_endpoints_documented():
    """Ensure all endpoints are documented in the OpenAPI spec"""
    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths", {})

    # List of expected endpoints
    expected_endpoints = [
        "/repositories",
        "/repositories/{repository_name}",
        "/repositories/{repository_name}/files",
        "/repositories/{repository_name}/commits",
        # Add more endpoints as needed
    ]

    for endpoint in expected_endpoints:
        assert endpoint in paths, f"Endpoint {endpoint} not documented"

def test_response_schemas_defined():
    """Test that all responses have proper schema definitions"""
    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            responses = details.get("responses", {})
            for status_code, response_info in responses.items():
                if status_code.startswith("2"):  # Success responses
                    assert "content" in response_info or status_code == "204"
```

### Pact Testing (Consumer-Driven Contracts)

```python
# tests/contract/test_pact.py
import pytest
from pact import Consumer, Provider
from app.main import app

# Consumer test - Frontend perspective
@pytest.fixture(scope="session")
def pact():
    return Consumer("GitWrite-Frontend").has_pact_with(
        Provider("GitWrite-API"),
        port=8000
    )

def test_get_repositories_contract(pact):
    expected = {
        "items": [
            {
                "id": "123",
                "name": "test-repo",
                "description": "Test repository",
                "owner": {"name": "Test User"},
                "created_at": "2024-01-01T00:00:00Z"
            }
        ],
        "total": 1
    }

    (pact
     .given("repositories exist")
     .upon_receiving("a request for repositories")
     .with_request("GET", "/repositories")
     .will_respond_with(200, body=expected))

    with pact:
        # This would be your actual API client call
        response = requests.get("http://localhost:8000/repositories")
        assert response.status_code == 200
        assert response.json() == expected
```

## Performance Testing

### Load Testing with Locust

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between
import random

class GitWriteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login user"""
        response = self.client.post("/auth/login", json={
            "email": "load_test@example.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}

    @task(3)
    def list_repositories(self):
        """Most common operation - list repositories"""
        self.client.get("/repositories", headers=self.headers)

    @task(2)
    def get_repository(self):
        """Get specific repository details"""
        repo_id = random.choice(["repo1", "repo2", "repo3"])
        self.client.get(f"/repositories/{repo_id}", headers=self.headers)

    @task(1)
    def create_file(self):
        """Create new file - less frequent but important"""
        repo_id = "test-repo"
        file_data = {
            "path": f"test-file-{random.randint(1, 1000)}.md",
            "content": "# Test Content\n\nThis is test content.",
            "message": "Add test file"
        }
        self.client.post(
            f"/repositories/{repo_id}/files",
            json=file_data,
            headers=self.headers
        )

    @task(1)
    def search_content(self):
        """Search functionality"""
        query = random.choice(["test", "chapter", "character", "plot"])
        self.client.get(
            f"/search?q={query}",
            headers=self.headers
        )
```

## Test Infrastructure

### Test Configuration

```python
# tests/conftest.py
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.database.models import Base
from app.config import get_test_settings

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    settings = get_test_settings()
    engine = create_async_engine(settings.database_url)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(test_engine):
    """Create database session for each test"""
    async with AsyncSession(test_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services for all tests"""
    with patch('app.services.email_service.send_email'):
        with patch('app.services.git_service.clone_repository'):
            yield
```

### CI/CD Integration

```yaml
# .github/workflows/api-tests.yml
name: API Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: gitwrite_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=app --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:test@localhost/gitwrite_test

      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost/gitwrite_test

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

*Comprehensive API testing ensures GitWrite's backend services are reliable, performant, and maintain backward compatibility. This multi-layered testing approach catches issues early and provides confidence in API behavior across different scenarios and load conditions.*