# Testing Strategy

GitWrite employs a comprehensive testing strategy ensuring reliability across all components through unit tests, integration tests, end-to-end tests, and specialized Git operations testing.

## Testing Philosophy

### Quality Gates
- **Unit Tests**: 90%+ code coverage for core modules
- **Integration Tests**: All API endpoints and cross-module interactions
- **End-to-End Tests**: Complete user workflows from UI to storage
- **Performance Tests**: Response times and load testing
- **Security Tests**: Authentication, authorization, and data protection

### Test Pyramid
```
         E2E Tests (UI/Workflows)
      ┌─────────────────────────────┐
     │     Integration Tests        │
    │    (API/Database/Components)   │
   └─────────────────────────────────┘
           Unit Tests
    ┌─────────────────────────────────┐
   │   Business Logic & Functions     │
  └───────────────────────────────────┘
```

## Unit Testing

### Core Module Testing (pytest)
```python
# tests/test_core_repository.py
class TestRepositoryManagement:
    def test_repository_initialization_success(self):
        config = ProjectConfig(name="test", author="Test Author")
        result = GitWriteRepository.initialize(str(self.test_path), config)

        assert result.success is True
        assert (self.test_path / '.git').exists()
        assert (self.test_path / '.gitwrite').exists()

    def test_repository_status_with_changes(self):
        repo = self.create_test_repository()
        test_file = self.test_path / "test.md"
        test_file.write_text("Test content")

        status = repo.get_status()
        assert status.is_clean is False
        assert "test.md" in status.new_files
```

### API Testing (FastAPI TestClient)
```python
# tests/test_api_repository.py
class TestRepositoryAPI:
    def test_create_repository_success(self):
        repository_data = {
            "name": "test-novel",
            "description": "A test project",
            "type": "novel"
        }

        response = self.client.post("/repositories/", json=repository_data)
        assert response.status_code == 201
        assert response.json()["name"] == "test-novel"
```

## Integration Testing

### Cross-Module Integration
```python
# tests/test_integration_workflow.py
class TestAPIWorkflowIntegration:
    def test_complete_writing_workflow(self):
        # 1. Create repository
        create_response = self.client.post("/repositories/", json=repo_data)
        assert create_response.status_code == 201

        # 2. Save changes
        save_response = self.client.post("/repositories/test/save", json=save_data)
        assert save_response.status_code == 200

        # 3. Create exploration
        exploration_response = self.client.post("/repositories/test/explorations", json=exp_data)
        assert exploration_response.status_code == 201

        # 4. Export document
        export_response = self.client.post("/repositories/test/export/epub")
        assert export_response.status_code == 202
```

## End-to-End Testing

### Frontend Testing (Playwright)
```typescript
// tests/e2e/writing-workflow.spec.ts
test('complete novel writing workflow', async ({ page }) => {
  // Create project
  await page.click('[data-testid=new-project-button]');
  await page.fill('[data-testid=project-name]', 'E2E Test Novel');
  await page.click('[data-testid=create-project-button]');

  // Write content
  const editor = page.locator('[data-testid=markdown-editor]');
  await editor.fill('# Chapter 1\n\nContent...');

  // Save changes
  await page.click('[data-testid=save-button]');
  await page.fill('[data-testid=save-message]', 'Wrote opening');
  await page.click('[data-testid=confirm-save]');

  // Create exploration
  await page.click('[data-testid=new-exploration-button]');
  await page.fill('[data-testid=exploration-name]', 'alternative');
  await page.click('[data-testid=create-exploration]');

  // Export document
  await page.click('[data-testid=export-tab]');
  await page.selectOption('[data-testid=export-format]', 'epub');
  await page.click('[data-testid=start-export]');

  await expect(page.locator('[data-testid=export-status]')).toHaveText('Completed');
});
```

## Performance Testing

### Load Testing (Artillery.js)
```yaml
# tests/performance/load-test.yml
config:
  target: 'https://api.gitwrite.com'
  phases:
    - duration: 60
      arrivalRate: 10
    - duration: 120
      arrivalRate: 50
    - duration: 300
      arrivalRate: 100

scenarios:
  - name: "Writing workflow"
    weight: 70
    flow:
      - post:
          url: "/auth/login"
          json:
            username: "{{ $randomEmail() }}"
            password: "testpassword"
      - post:
          url: "/repositories"
          json:
            name: "perf-test-{{ $randomString() }}"
      - post:
          url: "/repositories/{{ name }}/save"
          json:
            message: "Performance test save"
```

## Specialized Testing

### Git Operations Integrity
```python
class TestGitOperationsIntegrity:
    def test_concurrent_saves_no_corruption(self):
        """Test concurrent operations don't corrupt repository"""
        repo = self.create_test_repository()
        errors = []

        def concurrent_save(thread_id):
            for i in range(10):
                result = save_changes(f"Thread {thread_id} save {i}")
                if not result.success:
                    errors.append(result.error)

        # Run 5 concurrent threads
        threads = [threading.Thread(target=concurrent_save, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0
        assert len(get_history(limit=100)) >= 50
```

### Security Testing
```python
class TestSecurity:
    def test_jwt_token_expiration(self):
        token = create_access_token(data={"sub": "test"}, expires_delta=timedelta(seconds=1))
        assert verify_token(token)["sub"] == "test"

        time.sleep(2)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_token(token)

    def test_role_based_access_control(self):
        editor = User(username="editor", role=UserRole.EDITOR)
        assert require_role(UserRole.WRITER)(editor) == editor

        reader = User(username="reader", role=UserRole.BETA_READER)
        with pytest.raises(HTTPException):
            require_role(UserRole.EDITOR)(reader)
```

## Continuous Integration

### GitHub Actions
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        sudo apt-get install -y libgit2-dev pandoc
        pip install poetry
        poetry install
    - name: Run tests
      run: poetry run pytest tests/unit/ --cov=gitwrite_core --cov=gitwrite_api

  integration-tests:
    needs: unit-tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
    steps:
    - uses: actions/checkout@v3
    - name: Run integration tests
      run: poetry run pytest tests/integration/

  e2e-tests:
    needs: integration-tests
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Install Playwright
      run: npm install @playwright/test
    - name: Run E2E tests
      run: npx playwright test
```

## Test Data Management

### Fixtures and Factories
```python
# tests/conftest.py
@pytest.fixture
def test_repository():
    """Create temporary repository for testing"""
    test_dir = tempfile.mkdtemp()
    config = ProjectConfig(name="test", author="Test")
    result = GitWriteRepository.initialize(test_dir, config)
    yield result.repository
    shutil.rmtree(test_dir)

@pytest.fixture
def authenticated_client():
    """API client with authentication"""
    client = TestClient(app)
    auth_response = client.post("/auth/login", json={
        "username": "test@example.com",
        "password": "testpass"
    })
    token = auth_response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
```

### Test Coverage Requirements
- **Core modules**: 95% line coverage
- **API endpoints**: 90% line coverage
- **Frontend components**: 85% line coverage
- **Integration paths**: 100% critical path coverage
- **Error handling**: 90% error path coverage

---

*This comprehensive testing strategy ensures GitWrite maintains high quality and reliability across all components while providing confidence in new features and changes.*