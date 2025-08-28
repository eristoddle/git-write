# TypeScript SDK

The GitWrite TypeScript SDK provides a comprehensive, type-safe client library for integrating GitWrite functionality into JavaScript and TypeScript applications. The SDK abstracts HTTP API calls into intuitive methods while providing full type safety and excellent developer experience.

## Overview

The TypeScript SDK serves as the primary integration point for:
- **Web Applications**: Frontend interfaces built with React, Vue, Angular, etc.
- **Node.js Applications**: Server-side integrations and automation tools
- **Third-party Tools**: Writing software that needs GitWrite integration
- **Mobile Applications**: React Native and other hybrid mobile apps

## Design Principles

### Type Safety First

Every API interaction is fully typed, providing compile-time safety and excellent IDE support:

```typescript
import { GitWriteClient, Repository, CommitInfo } from '@gitwrite/sdk';

const client = new GitWriteClient('https://api.gitwrite.com', 'your-api-key');

// Fully typed responses - no guessing about return values
const repositories: Repository[] = await client.repositories.list();
const commits: CommitInfo[] = await client.repositories.getCommits('my-novel');

// Type checking prevents runtime errors
const newRepo = await client.repositories.create({
  name: 'my-novel',
  description: 'A thrilling adventure story',
  // TypeScript ensures all required fields are provided
  // and prevents invalid field names or types
});
```

### Consistent API Surface

All SDK methods follow consistent patterns for predictable usage:

```typescript
// Consistent pattern: entity.operation(identifier, options)
await client.repositories.create(config);
await client.repositories.get(repoName);
await client.repositories.update(repoName, updates);
await client.repositories.delete(repoName);

await client.explorations.create(repoName, config);
await client.explorations.list(repoName);
await client.explorations.switch(repoName, explorationName);
```

### Error Handling

Comprehensive error handling with typed error responses:

```typescript
import { GitWriteError, RepositoryError, AuthenticationError } from '@gitwrite/sdk';

try {
  const result = await client.repositories.save('my-novel', {
    message: 'Updated chapter 1',
    files: ['chapters/chapter1.md']
  });
} catch (error) {
  if (error instanceof AuthenticationError) {
    // Handle authentication issues
    redirectToLogin();
  } else if (error instanceof RepositoryError) {
    // Handle repository-specific errors
    showErrorMessage(`Repository error: ${error.message}`);
  } else if (error instanceof GitWriteError) {
    // Handle other GitWrite errors
    console.error('GitWrite error:', error.details);
  }
}
```

## Architecture

### Client Structure

The SDK is organized into logical modules that mirror GitWrite's domain concepts:

```typescript
class GitWriteClient {
  // Core functionality
  public readonly repositories: RepositoryClient;
  public readonly versioning: VersioningClient;
  public readonly explorations: ExplorationClient;

  // Collaboration features
  public readonly annotations: AnnotationClient;
  public readonly collaboration: CollaborationClient;

  // Publishing and export
  public readonly export: ExportClient;
  public readonly publishing: PublishingClient;

  // User and authentication
  public readonly auth: AuthClient;
  public readonly users: UserClient;
}
```

### HTTP Client Layer

The SDK uses a robust HTTP client with built-in features:

```typescript
class HttpClient {
  constructor(
    private baseUrl: string,
    private apiKey?: string,
    private options: ClientOptions = {}
  ) {
    // Configure axios or fetch with:
    // - Automatic retries with exponential backoff
    // - Request/response interceptors
    // - Timeout handling
    // - Response caching (where appropriate)
  }

  async request<T>(config: RequestConfig): Promise<T> {
    // Automatic JSON parsing
    // Error response handling
    // Type validation
    // Request/response logging (in debug mode)
  }
}
```

### Type System

Comprehensive TypeScript definitions for all API entities:

```typescript
export interface Repository {
  id: string;
  name: string;
  description: string;
  owner: string;
  created_at: string;
  updated_at: string;
  status: 'active' | 'archived' | 'draft';
  collaboration_enabled: boolean;
  default_branch: string;
  word_count: number;
  file_count: number;
}

export interface CommitInfo {
  id: string;
  short_id: string;
  message: string;
  author: {
    name: string;
    email: string;
  };
  timestamp: string;
  files_changed: number;
  insertions: number;
  deletions: number;
  exploration?: string;
}

export interface CreateRepositoryRequest {
  name: string;
  description?: string;
  type?: 'novel' | 'short-story' | 'article' | 'screenplay' | 'academic';
  template?: string;
  collaboration_enabled?: boolean;
  is_private?: boolean;
}
```

## Installation and Setup

### Installation

```bash
# npm
npm install @gitwrite/sdk

# yarn
yarn add @gitwrite/sdk

# pnpm
pnpm add @gitwrite/sdk
```

### Basic Setup

```typescript
import { GitWriteClient } from '@gitwrite/sdk';

// Initialize client
const client = new GitWriteClient('https://api.gitwrite.com');

// With API key for authenticated requests
const authenticatedClient = new GitWriteClient(
  'https://api.gitwrite.com',
  'your-api-key'
);

// With custom configuration
const customClient = new GitWriteClient('https://api.gitwrite.com', 'api-key', {
  timeout: 10000,
  retries: 3,
  debug: process.env.NODE_ENV === 'development'
});
```

### Environment Configuration

```typescript
// Using environment variables
const client = new GitWriteClient(
  process.env.GITWRITE_API_URL || 'https://api.gitwrite.com',
  process.env.GITWRITE_API_KEY
);

// Configuration object
interface ClientConfig {
  apiUrl: string;
  apiKey?: string;
  timeout?: number;
  retries?: number;
  debug?: boolean;
  headers?: Record<string, string>;
}

const config: ClientConfig = {
  apiUrl: 'https://api.gitwrite.com',
  apiKey: process.env.GITWRITE_API_KEY,
  timeout: 30000,
  debug: true
};

const client = new GitWriteClient(config);
```

## Core Functionality

### Repository Management

```typescript
// Create a new repository
const newRepo = await client.repositories.create({
  name: 'my-novel',
  description: 'A science fiction thriller',
  type: 'novel',
  collaboration_enabled: true
});

// List repositories
const repos = await client.repositories.list({
  limit: 10,
  offset: 0,
  status: 'active'
});

// Get repository details
const repo = await client.repositories.get('my-novel');

// Update repository
await client.repositories.update('my-novel', {
  description: 'Updated description',
  collaboration_enabled: false
});

// Delete repository
await client.repositories.delete('my-novel', {
  confirm: true,
  backup: true
});
```

### Version Control Operations

```typescript
// Save changes
const saveResult = await client.versioning.save('my-novel', {
  message: 'Completed chapter 3',
  files: ['chapters/chapter3.md'],
  tag: 'chapter3-complete'
});

// Get commit history
const commits = await client.versioning.getHistory('my-novel', {
  limit: 50,
  since: '2023-11-01',
  author: 'jane@example.com'
});

// Get specific commit
const commit = await client.versioning.getCommit('my-novel', 'a4f7b8c');

// Compare versions
const diff = await client.versioning.compare('my-novel', {
  from: 'main',
  to: 'alternative-ending',
  format: 'unified'
});

// Revert changes
await client.versioning.revert('my-novel', 'a4f7b8c', {
  create_exploration: true,
  exploration_name: 'revert-experiment'
});
```

### Exploration Management

```typescript
// Create exploration
const exploration = await client.explorations.create('my-novel', {
  name: 'alternative-ending',
  description: 'Trying a darker conclusion',
  from_commit: 'a4f7b8c'
});

// List explorations
const explorations = await client.explorations.list('my-novel');

// Switch exploration
await client.explorations.switch('my-novel', 'alternative-ending');

// Merge exploration
await client.explorations.merge('my-novel', {
  source: 'alternative-ending',
  target: 'main',
  message: 'Merging improved ending',
  strategy: 'auto'
});

// Delete exploration
await client.explorations.delete('my-novel', 'alternative-ending', {
  force: false,
  keep_commits: true
});
```

### Export Operations

```typescript
// Export to EPUB
const epubResult = await client.export.epub('my-novel', {
  title: 'My Great Novel',
  author: 'Jane Writer',
  cover_image: 'cover.jpg',
  template: 'professional'
});

// Export to PDF
const pdfResult = await client.export.pdf('my-novel', {
  title: 'My Great Novel',
  format: 'a4',
  margins: '1in',
  font_family: 'Times New Roman'
});

// Check export status
const status = await client.export.getStatus(epubResult.export_id);

// Download completed export
const fileData = await client.export.download(epubResult.export_id);
```

## Advanced Features

### Authentication

```typescript
// Login with credentials
const authResult = await client.auth.login({
  username: 'jane@example.com',
  password: 'secure-password'
});

// Store token for subsequent requests
localStorage.setItem('gitwrite_token', authResult.access_token);

// Create authenticated client
const authenticatedClient = new GitWriteClient(
  'https://api.gitwrite.com',
  authResult.access_token
);

// Refresh token
const newToken = await client.auth.refresh(authResult.refresh_token);

// Logout
await client.auth.logout();
```

### Collaboration

```typescript
// Invite collaborator
await client.collaboration.invite('my-novel', {
  email: 'editor@example.com',
  role: 'editor',
  message: 'Please review my latest chapters'
});

// List collaborators
const collaborators = await client.collaboration.list('my-novel');

// Update collaborator role
await client.collaboration.updateRole('my-novel', 'editor@example.com', 'senior-editor');

// Remove collaborator
await client.collaboration.remove('my-novel', 'editor@example.com');
```

### Annotations

```typescript
// Add annotation
const annotation = await client.annotations.create('my-novel', {
  file_path: 'chapters/chapter1.md',
  line_number: 42,
  type: 'suggestion',
  content: 'Consider using a stronger verb here',
  suggested_text: 'sprinted'
});

// List annotations
const annotations = await client.annotations.list('my-novel', {
  file_path: 'chapters/chapter1.md',
  type: 'suggestion',
  status: 'open'
});

// Resolve annotation
await client.annotations.resolve('my-novel', annotation.id, {
  action: 'accepted',
  message: 'Good suggestion, implemented'
});
```

### Real-time Features

```typescript
// Subscribe to repository changes (WebSocket)
const subscription = client.realtime.subscribe('my-novel', {
  events: ['commit', 'exploration_created', 'annotation_added'],
  callback: (event) => {
    console.log('Repository event:', event);
    // Update UI based on event
  }
});

// Unsubscribe
subscription.unsubscribe();

// Server-sent events for long-running operations
const exportStream = client.export.stream('my-novel', 'epub');
exportStream.on('progress', (progress) => {
  console.log(`Export progress: ${progress.percentage}%`);
});
exportStream.on('complete', (result) => {
  console.log('Export completed:', result.download_url);
});
```

## Error Handling

### Error Types

```typescript
// Base error class
class GitWriteError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: any
  ) {
    super(message);
  }
}

// Specific error types
class AuthenticationError extends GitWriteError {}
class AuthorizationError extends GitWriteError {}
class RepositoryError extends GitWriteError {}
class ValidationError extends GitWriteError {}
class NetworkError extends GitWriteError {}
class ConflictError extends GitWriteError {}
```

### Error Handling Patterns

```typescript
// Basic error handling
try {
  const result = await client.repositories.save('my-novel', saveRequest);
} catch (error) {
  if (error instanceof ConflictError) {
    // Handle merge conflicts
    const conflicts = error.details.conflicts;
    showConflictResolutionUI(conflicts);
  } else {
    // Handle other errors
    showErrorMessage(error.message);
  }
}

// Async/await with error result pattern
const [result, error] = await client.repositories.save('my-novel', saveRequest)
  .then(res => [res, null])
  .catch(err => [null, err]);

if (error) {
  handleError(error);
} else {
  handleSuccess(result);
}

// Retry with exponential backoff
import { retry } from '@gitwrite/sdk/utils';

const result = await retry(
  () => client.repositories.save('my-novel', saveRequest),
  {
    retries: 3,
    factor: 2,
    minTimeout: 1000,
    maxTimeout: 10000
  }
);
```

## Testing

### Unit Testing

```typescript
import { GitWriteClient } from '@gitwrite/sdk';
import { MockAdapter } from '@gitwrite/sdk/testing';

describe('Repository operations', () => {
  let client: GitWriteClient;
  let mockAdapter: MockAdapter;

  beforeEach(() => {
    mockAdapter = new MockAdapter();
    client = new GitWriteClient('https://api.test.com', 'test-key', {
      adapter: mockAdapter
    });
  });

  it('should create repository successfully', async () => {
    const mockRepo = {
      id: 'repo-1',
      name: 'test-novel',
      owner: 'test-user'
    };

    mockAdapter.onPost('/repositories').reply(201, mockRepo);

    const result = await client.repositories.create({
      name: 'test-novel',
      description: 'Test description'
    });

    expect(result).toEqual(mockRepo);
  });
});
```

### Integration Testing

```typescript
import { GitWriteClient } from '@gitwrite/sdk';

describe('Integration tests', () => {
  let client: GitWriteClient;

  beforeAll(() => {
    client = new GitWriteClient(
      process.env.TEST_API_URL!,
      process.env.TEST_API_KEY!
    );
  });

  it('should complete full workflow', async () => {
    // Create repository
    const repo = await client.repositories.create({
      name: 'integration-test-' + Date.now(),
      description: 'Integration test repository'
    });

    // Save changes
    const saveResult = await client.versioning.save(repo.name, {
      message: 'Initial content',
      files: ['README.md']
    });

    // Create exploration
    const exploration = await client.explorations.create(repo.name, {
      name: 'test-exploration',
      description: 'Testing exploration functionality'
    });

    // Clean up
    await client.repositories.delete(repo.name, { confirm: true });

    expect(saveResult.success).toBe(true);
    expect(exploration.name).toBe('test-exploration');
  });
});
```

## Performance Optimization

### Caching

```typescript
// Response caching
const client = new GitWriteClient('https://api.gitwrite.com', 'api-key', {
  cache: {
    enabled: true,
    ttl: 300000, // 5 minutes
    maxSize: 100 // Maximum cached responses
  }
});

// Manual cache control
await client.repositories.get('my-novel', {
  cache: false // Skip cache for this request
});

// Cache invalidation
client.cache.invalidate('repositories/my-novel');
client.cache.clear(); // Clear all cached data
```

### Request Batching

```typescript
// Batch multiple requests
const batch = client.batch()
  .add('repos', client.repositories.list())
  .add('commits', client.versioning.getHistory('my-novel'))
  .add('explorations', client.explorations.list('my-novel'));

const results = await batch.execute();

console.log('Repositories:', results.repos);
console.log('Commits:', results.commits);
console.log('Explorations:', results.explorations);
```

### Streaming

```typescript
// Stream large datasets
const commitStream = client.versioning.streamHistory('my-novel');

for await (const commit of commitStream) {
  console.log('Commit:', commit.message);
  // Process commit without loading all commits into memory
}
```

---

*The TypeScript SDK provides a comprehensive, type-safe interface to all GitWrite functionality, making it easy to integrate GitWrite into any JavaScript or TypeScript application while maintaining excellent developer experience and runtime safety.*