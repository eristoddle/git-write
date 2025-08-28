# Test Infrastructure

Comprehensive test infrastructure setup for GitWrite, including CI/CD pipelines, test automation, environment management, and quality assurance tools. This infrastructure ensures consistent, reliable testing across all components and deployment environments.

## Infrastructure Overview

```
Test Infrastructure Architecture
    │
    ├─ CI/CD Pipeline
    │   ├─ GitHub Actions
    │   ├─ Build Automation
    │   └─ Deployment Gates
    │
    ├─ Test Environments
    │   ├─ Development
    │   ├─ Staging
    │   └─ Production Mirror
    │
    ├─ Test Automation
    │   ├─ Unit Test Runner
    │   ├─ Integration Tests
    │   └─ E2E Test Suite
    │
    └─ Quality Gates
        ├─ Code Coverage
        ├─ Security Scanning
        └─ Performance Benchmarks
```

## CI/CD Pipeline Configuration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: GitWrite Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '18'

jobs:
  # Backend testing
  backend-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: gitwrite_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,test]"

      - name: Run linting
        run: |
          black --check .
          isort --check-only .
          flake8 .

      - name: Run tests
        run: |
          pytest tests/ -v --cov=backend --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  # Frontend testing
  frontend-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Run tests
        working-directory: ./frontend
        run: npm run test -- --coverage

  # E2E testing
  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]

    steps:
      - uses: actions/checkout@v4

      - name: Set up environment
        run: |
          docker-compose -f docker-compose.test.yml up -d

      - name: Run E2E tests
        run: npx playwright test

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: e2e-results
          path: test-results/
```

## Test Environment Management

### Docker Test Environment

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  test-db:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: gitwrite_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"

  test-redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"

  test-backend:
    build:
      context: .
      dockerfile: backend/Dockerfile.test
    environment:
      DATABASE_URL: postgresql://test_user:test_password@test-db:5432/gitwrite_test
      TESTING: true
    depends_on:
      - test-db
      - test-redis
    ports:
      - "8001:8000"
```

## Test Automation Framework

### Pytest Configuration

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
addopts =
    --strict-markers
    --verbose
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
```

### Test Configuration

```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import get_db
from backend.models import Base

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine("postgresql://test_user:test_password@localhost:5433/gitwrite_test")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_client(test_engine):
    """Create test client."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": "test@example.com",
        "name": "Test User",
        "password": "test_password_123"
    }
```

## Quality Assurance Tools

### Code Coverage

```ini
# .coveragerc
[run]
source = backend, gitwrite
branch = True
omit = */tests/*, */migrations/*

[report]
show_missing = True
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError

[html]
directory = htmlcov
```

### Code Quality

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
warn_return_any = true
disallow_untyped_defs = true
ignore_missing_imports = true

[tool.bandit]
exclude_dirs = ["tests"]
```

## Performance Monitoring

### Performance Testing

```python
# tests/performance/test_performance.py
import pytest
import time
import statistics

@pytest.mark.performance
class TestAPIPerformance:
    """API performance benchmarks."""

    def test_repository_list_performance(self, test_client, authenticated_user):
        """Test repository listing performance."""
        headers = authenticated_user["headers"]

        times = []
        for _ in range(50):
            start = time.time()
            response = test_client.get("/repositories", headers=headers)
            end = time.time()

            assert response.status_code == 200
            times.append(end - start)

        avg_time = statistics.mean(times)
        assert avg_time < 0.1  # Average under 100ms

    def test_concurrent_requests(self, test_client, authenticated_user):
        """Test concurrent request handling."""
        from concurrent.futures import ThreadPoolExecutor

        headers = authenticated_user["headers"]

        def make_request():
            response = test_client.get("/repositories", headers=headers)
            return response.status_code

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [future.result() for future in futures]

        assert all(code == 200 for code in results)
```

### Monitoring Dashboard

```python
# tests/monitoring/metrics.py
import json
import time
from pathlib import Path

class TestMetricsCollector:
    """Collect test metrics."""

    def __init__(self, output_dir: Path = Path("test-results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.metrics = {
            "timestamp": time.time(),
            "test_runs": [],
            "performance": {},
            "coverage": {}
        }

    def record_test_run(self, test_name: str, duration: float, status: str):
        """Record test execution metrics."""
        self.metrics["test_runs"].append({
            "name": test_name,
            "duration": duration,
            "status": status,
            "timestamp": time.time()
        })

    def save_metrics(self):
        """Save metrics to file."""
        with open(self.output_dir / "metrics.json", "w") as f:
            json.dump(self.metrics, f, indent=2)
```

## Test Data Management

### Test Factories

```python
# tests/factories.py
import factory
from faker import Faker
from backend.models import User, Repository

fake = Faker()

class UserFactory(factory.Factory):
    class Meta:
        model = User

    email = factory.LazyAttribute(lambda obj: fake.email())
    name = factory.LazyAttribute(lambda obj: fake.name())
    password_hash = "hashed_password"

class RepositoryFactory(factory.Factory):
    class Meta:
        model = Repository

    name = factory.LazyAttribute(lambda obj: fake.slug())
    description = factory.LazyAttribute(lambda obj: fake.sentence())
    owner = factory.SubFactory(UserFactory)
```

## Security Testing

### Security Scan Configuration

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [ main ]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r backend/

      - name: Run Safety
        run: |
          pip install safety
          safety check

      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          format: 'sarif'
          output: 'trivy-results.sarif'
```

## Deployment Testing

### Deployment Validation

```python
# tests/deployment/test_deployment.py
import pytest
import requests
import time

@pytest.mark.deployment
class TestDeployment:
    """Test deployment health and functionality."""

    def test_health_check(self, deployment_url):
        """Test application health endpoint."""
        response = requests.get(f"{deployment_url}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data["status"] == "healthy"

    def test_database_connection(self, deployment_url):
        """Test database connectivity."""
        response = requests.get(f"{deployment_url}/health/db")
        assert response.status_code == 200

    def test_api_endpoints(self, deployment_url):
        """Test critical API endpoints."""
        endpoints = ["/docs", "/openapi.json", "/auth/login"]

        for endpoint in endpoints:
            response = requests.get(f"{deployment_url}{endpoint}")
            assert response.status_code in [200, 405]  # 405 for POST-only endpoints
```

---

*GitWrite's test infrastructure provides comprehensive automation, quality gates, and monitoring to ensure reliable software delivery. The infrastructure covers everything from local development testing to production deployment validation, maintaining high quality standards throughout the development lifecycle.*