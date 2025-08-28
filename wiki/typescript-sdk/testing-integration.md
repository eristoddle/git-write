# Testing & Integration

Comprehensive testing strategies for the GitWrite TypeScript SDK, covering unit tests, integration tests, mocking, and CI/CD setup.

## Testing Strategy Overview

```
Testing Pyramid
    │
    ├─ E2E Tests (10%)
    │   └─ Full user workflows
    │
    ├─ Integration Tests (20%)
    │   ├─ API Integration
    │   └─ Real-time Features
    │
    └─ Unit Tests (70%)
        ├─ Component Tests
        ├─ Service Tests
        └─ Utility Tests
```

## Test Environment Setup

### Jest Configuration

```javascript
// jest.config.js
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/tests/setup.ts'],
  testMatch: ['<rootDir>/src/**/*.{test,spec}.{ts,tsx}'],
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/**/*.d.ts'],
  coverageThreshold: {
    global: { branches: 80, functions: 80, lines: 80, statements: 80 }
  },
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@gitwrite/sdk$': '<rootDir>/src/sdk/index.ts'
  }
};
```

### Test Setup

```typescript
// src/tests/setup.ts
import 'jest-dom/extend-expect';
import { server } from './mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock environment
process.env.GITWRITE_API_URL = 'https://api-test.gitwrite.com';
process.env.GITWRITE_API_KEY = 'test-api-key';
```

## Unit Testing

### SDK Client Tests

```typescript
// src/tests/unit/client.test.ts
import { GitWriteClient } from '@gitwrite/sdk';
import { AuthenticationError } from '@gitwrite/sdk/errors';

describe('GitWriteClient', () => {
  let client: GitWriteClient;

  beforeEach(() => {
    client = new GitWriteClient({
      baseURL: 'https://api-test.gitwrite.com',
      apiKey: 'test-key'
    });
  });

  test('should create client with valid config', () => {
    expect(client).toBeInstanceOf(GitWriteClient);
    expect(client.config.baseURL).toBe('https://api-test.gitwrite.com');
  });

  test('should handle authentication errors', async () => {
    const mockError = new AuthenticationError('Invalid token');
    jest.spyOn(client.http, 'request').mockRejectedValue(mockError);

    await expect(client.repositories.list()).rejects.toThrow(AuthenticationError);
  });

  test('should retry failed requests', async () => {
    const requestSpy = jest.spyOn(client.http, 'request')
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue({ data: [] });

    await client.repositories.list();
    expect(requestSpy).toHaveBeenCalledTimes(2);
  });
});
```

### Service Tests

```typescript
// src/tests/unit/repositories.test.ts
describe('RepositoryService', () => {
  test('should fetch repositories with correct parameters', async () => {
    const mockClient = createMockClient();
    const service = new RepositoryService(mockClient);

    mockClient.http.request.mockResolvedValue({
      data: { items: [], total: 0 }
    });

    await service.list({ page: 2, pageSize: 10 });

    expect(mockClient.http.request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/repositories',
      params: { page: 2, page_size: 10 }
    });
  });
});
```

## Integration Testing

### API Integration

```typescript
// src/tests/integration/api.test.ts
describe('API Integration Tests', () => {
  let client: GitWriteClient;

  beforeAll(() => {
    client = new GitWriteClient({
      baseURL: process.env.TEST_API_URL!,
      apiKey: process.env.TEST_API_KEY!
    });
  });

  test('should perform full repository lifecycle', async () => {
    // Create
    const repo = await client.repositories.create({
      name: 'integration-test',
      description: 'Test repository'
    });
    expect(repo.name).toBe('integration-test');

    // Read
    const retrieved = await client.repositories.get('integration-test');
    expect(retrieved.id).toBe(repo.id);

    // Update
    const updated = await client.repositories.update('integration-test', {
      description: 'Updated description'
    });
    expect(updated.description).toBe('Updated description');

    // Delete
    await client.repositories.delete('integration-test');
    await expect(
      client.repositories.get('integration-test')
    ).rejects.toThrow('Repository not found');
  });
});
```

### Real-time Tests

```typescript
// src/tests/integration/realtime.test.ts
test('should receive real-time events', async () => {
  const client1 = createClient('user1');
  const client2 = createClient('user2');

  const eventPromise = new Promise(resolve => {
    client2.realtime.subscribe('repository:test-repo', resolve);
  });

  await Promise.all([
    client1.realtime.connect(),
    client2.realtime.connect()
  ]);

  // Trigger event
  await client1.files.create('test-repo', {
    path: 'test.md',
    content: 'Test content'
  });

  const event = await eventPromise;
  expect(event.type).toBe('file_changed');
});
```

## Mocking Strategies

### Mock Client Factory

```typescript
// src/tests/mocks/client.ts
export function createMockClient(): jest.Mocked<GitWriteClient> {
  return {
    repositories: {
      list: jest.fn(),
      get: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn()
    },
    files: {
      list: jest.fn(),
      getContent: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn()
    },
    realtime: {
      connect: jest.fn(),
      disconnect: jest.fn(),
      subscribe: jest.fn(),
      unsubscribe: jest.fn()
    },
    http: { request: jest.fn() }
  } as unknown as jest.Mocked<GitWriteClient>;
}

export function setupDefaultMocks(client: jest.Mocked<GitWriteClient>) {
  client.repositories.list.mockResolvedValue({
    items: [{ id: '1', name: 'test-repo', description: 'Test' }],
    total: 1
  });

  client.files.list.mockResolvedValue([
    { path: 'test.md', name: 'test.md', type: 'file', size: 100 }
  ]);
}
```

### MSW Setup

```typescript
// src/tests/mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  rest.get('*/repositories', (req, res, ctx) => {
    return res(ctx.json({
      items: [{ id: '1', name: 'test-repo' }],
      total: 1
    }));
  }),

  rest.post('*/repositories', (req, res, ctx) => {
    const { name } = req.body as any;
    return res(ctx.status(201), ctx.json({
      id: 'new-id',
      name,
      created_at: new Date()
    }));
  })
];
```

## E2E Testing

### Playwright Tests

```typescript
// e2e/workflow.spec.ts
import { test, expect } from '@playwright/test';

test('complete writing workflow', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[data-testid="email"]', 'test@example.com');
  await page.fill('[data-testid="password"]', 'password');
  await page.click('[data-testid="login"]');

  // Create repository
  await page.click('[data-testid="create-repo"]');
  await page.fill('[data-testid="repo-name"]', 'test-novel');
  await page.click('[data-testid="create"]');

  // Add content
  await page.click('[data-testid="new-file"]');
  await page.fill('[data-testid="file-path"]', 'chapter-01.md');
  await page.fill('[data-testid="editor"]', '# Chapter 1\nContent...');
  await page.click('[data-testid="save"]');

  await expect(page.locator('text=Changes saved')).toBeVisible();
});
```

## Performance Testing

### Load Testing

```typescript
// tests/performance/load.test.ts
describe('Performance Tests', () => {
  test('should handle concurrent requests', async () => {
    const client = createClient();
    const promises = Array(100).fill(0).map(() =>
      client.repositories.list()
    );

    const start = Date.now();
    await Promise.all(promises);
    const duration = Date.now() - start;

    expect(duration).toBeLessThan(5000); // 5 seconds max
  });
});
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - run: npm ci
      - run: npm run test:unit
      - run: npm run test:integration
        env:
          GITWRITE_API_URL: ${{ secrets.TEST_API_URL }}
          GITWRITE_API_KEY: ${{ secrets.TEST_API_KEY }}

      - run: npm run test:e2e
      - run: npm run coverage
```

### Test Scripts

```json
{
  "scripts": {
    "test": "jest",
    "test:unit": "jest --testPathPattern=unit",
    "test:integration": "jest --testPathPattern=integration",
    "test:e2e": "playwright test",
    "test:watch": "jest --watch",
    "coverage": "jest --coverage",
    "test:ci": "jest --ci --coverage --watchAll=false"
  }
}
```

## Best Practices

### Testing Principles

1. **Arrange-Act-Assert**: Structure tests clearly
2. **Test Isolation**: Each test should be independent
3. **Mock External Dependencies**: Use mocks for API calls
4. **Test Real Scenarios**: Include integration tests
5. **Performance Awareness**: Monitor test execution time

### Common Patterns

```typescript
// Test data factories
export const createMockRepository = (overrides = {}) => ({
  id: '1',
  name: 'test-repo',
  description: 'Test repository',
  ...overrides
});

// Test utilities
export const waitForElement = (selector: string) =>
  screen.findByTestId(selector);

// Error simulation
export const simulateNetworkError = (client: any) => {
  client.http.request.mockRejectedValue(new NetworkError('Connection failed'));
};
```

---

*Comprehensive testing ensures the GitWrite TypeScript SDK works reliably across different environments and use cases. This testing strategy covers all aspects from unit tests to end-to-end workflows, providing confidence in SDK functionality and user experience.*