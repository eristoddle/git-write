# Installation & Usage

This guide covers installation, setup, and basic usage of the GitWrite TypeScript SDK. The SDK is designed to work in modern JavaScript and TypeScript environments including Node.js, browsers, React Native, and other JavaScript runtimes.

## Installation

### 1. Package Manager Installation

```bash
# npm
npm install @gitwrite/sdk

# yarn
yarn add @gitwrite/sdk

# pnpm
pnpm add @gitwrite/sdk

# bun
bun add @gitwrite/sdk
```

### 2. Development Dependencies

For TypeScript projects, ensure you have TypeScript installed:

```bash
# Install TypeScript (if not already installed)
npm install -D typescript @types/node

# For React projects
npm install -D @types/react @types/react-dom

# For Node.js projects
npm install -D @types/node
```

### 3. CDN Usage (Browser)

```html
<!-- ES Modules -->
<script type="module">
  import { GitWriteClient } from 'https://cdn.jsdelivr.net/npm/@gitwrite/sdk@latest/dist/index.esm.js';
</script>

<!-- UMD (Global) -->
<script src="https://cdn.jsdelivr.net/npm/@gitwrite/sdk@latest/dist/index.umd.js"></script>
<script>
  const client = new GitWrite.GitWriteClient({ /* config */ });
</script>
```

## Environment Setup

### 1. TypeScript Configuration

Create or update `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "lib": ["ES2020", "DOM"],
    "types": ["node"]
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

### 2. Environment Variables

Create `.env` file for configuration:

```bash
# API Configuration
GITWRITE_API_URL=https://api.gitwrite.com
GITWRITE_API_KEY=your_api_key_here

# Optional settings
GITWRITE_TIMEOUT=30000
GITWRITE_RETRY_ATTEMPTS=3
GITWRITE_ENABLE_CACHE=true
GITWRITE_LOG_LEVEL=info

# Development settings
GITWRITE_DEBUG=false
NODE_ENV=development
```

### 3. Environment Types

Create `src/types/env.d.ts`:

```typescript
declare namespace NodeJS {
  interface ProcessEnv {
    GITWRITE_API_URL: string;
    GITWRITE_API_KEY: string;
    GITWRITE_TIMEOUT?: string;
    GITWRITE_RETRY_ATTEMPTS?: string;
    GITWRITE_ENABLE_CACHE?: string;
    GITWRITE_LOG_LEVEL?: 'debug' | 'info' | 'warn' | 'error';
    GITWRITE_DEBUG?: string;
    NODE_ENV: 'development' | 'production' | 'test';
  }
}
```

## Basic Usage

### 1. Client Initialization

```typescript
import { GitWriteClient } from '@gitwrite/sdk';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Create client instance
const client = new GitWriteClient({
  baseURL: process.env.GITWRITE_API_URL,
  apiKey: process.env.GITWRITE_API_KEY,
  timeout: 30000,
  retryAttempts: 3,
});

// Verify connection
async function initialize() {
  try {
    const user = await client.auth.getCurrentUser();
    console.log('Connected as:', user.name);
  } catch (error) {
    console.error('Failed to connect:', error);
  }
}

initialize();
```

### 2. Repository Operations

```typescript
// List repositories
async function listRepositories() {
  const repositories = await client.repositories.list({
    page: 1,
    pageSize: 10,
    sortBy: 'updated_at',
    sortOrder: 'desc',
  });

  console.log(`Found ${repositories.total} repositories`);
  repositories.items.forEach(repo => {
    console.log(`- ${repo.name}: ${repo.description}`);
  });
}

// Create new repository
async function createRepository() {
  const repository = await client.repositories.create({
    name: 'my-new-novel',
    description: 'A compelling story about...',
    isPublic: false,
    template: 'novel',
  });

  console.log('Created repository:', repository.name);
  return repository;
}

// Get repository details
async function getRepository(name: string) {
  try {
    const repository = await client.repositories.get(name);
    console.log('Repository:', repository);
    return repository;
  } catch (error) {
    if (error instanceof NotFoundError) {
      console.log('Repository not found');
    } else {
      console.error('Error fetching repository:', error);
    }
  }
}
```

### 3. File Operations

```typescript
// List files in repository
async function listFiles(repositoryName: string) {
  const files = await client.files.list(repositoryName, {
    path: 'chapters/',
    recursive: true,
  });

  files.forEach(file => {
    console.log(`${file.type}: ${file.path} (${file.size} bytes)`);
  });
}

// Read file content
async function readFile(repositoryName: string, filePath: string) {
  const content = await client.files.getContent(repositoryName, filePath);
  console.log(`Content of ${filePath}:`);
  console.log(content);
  return content;
}

// Create new file
async function createFile(repositoryName: string) {
  const file = await client.files.create(repositoryName, {
    path: 'chapters/chapter-01.md',
    content: `# Chapter 1: The Beginning

It was a dark and stormy night...
`,
    message: 'Added first chapter',
  });

  console.log('Created file:', file.path);
  return file;
}

// Update file content
async function updateFile(repositoryName: string, filePath: string, newContent: string) {
  const result = await client.files.update(repositoryName, filePath, {
    content: newContent,
    message: 'Updated chapter content',
  });

  console.log('Updated file:', result.path);
  return result;
}
```

### 4. Version Control

```typescript
// Save changes (commit)
async function saveChanges(repositoryName: string) {
  const result = await client.version.save(repositoryName, {
    message: 'Completed character development',
    files: ['chapters/chapter-01.md', 'notes/characters.md'],
  });

  console.log('Saved changes:', result.commit_id);
  console.log('Word count change:', result.word_count_change);
  return result;
}

// Get commit history
async function getHistory(repositoryName: string) {
  const history = await client.version.getHistory(repositoryName, {
    limit: 10,
  });

  console.log('Recent commits:');
  history.forEach(commit => {
    console.log(`- ${commit.id.substring(0, 8)}: ${commit.message}`);
    console.log(`  by ${commit.author.name} on ${commit.created_at}`);
  });
}

// Create exploration (branch)
async function createExploration(repositoryName: string) {
  const exploration = await client.explorations.create(repositoryName, {
    name: 'alternate-ending',
    description: 'Trying a different story conclusion',
  });

  console.log('Created exploration:', exploration.name);
  return exploration;
}
```

## Framework Integration

### 1. React Integration

```typescript
// hooks/useGitWrite.ts
import { useState, useEffect, useCallback } from 'react';
import { GitWriteClient } from '@gitwrite/sdk';

const client = new GitWriteClient({
  baseURL: process.env.REACT_APP_GITWRITE_API_URL!,
  apiKey: process.env.REACT_APP_GITWRITE_API_KEY!,
});

export function useRepositories() {
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRepositories = useCallback(async () => {
    try {
      setLoading(true);
      const result = await client.repositories.list();
      setRepositories(result.items);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRepositories();
  }, [fetchRepositories]);

  return { repositories, loading, error, refetch: fetchRepositories };
}

export function useRepository(name: string) {
  const [repository, setRepository] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name) return;

    const fetchRepository = async () => {
      try {
        setLoading(true);
        const repo = await client.repositories.get(name);
        setRepository(repo);
        setError(null);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchRepository();
  }, [name]);

  return { repository, loading, error };
}

// Component usage
import React from 'react';
import { useRepositories } from './hooks/useGitWrite';

export function RepositoryList() {
  const { repositories, loading, error } = useRepositories();

  if (loading) return <div>Loading repositories...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h2>My Repositories</h2>
      {repositories.map(repo => (
        <div key={repo.id}>
          <h3>{repo.name}</h3>
          <p>{repo.description}</p>
          <small>Updated: {new Date(repo.updated_at).toLocaleDateString()}</small>
        </div>
      ))}
    </div>
  );
}
```

### 2. Vue.js Integration

```typescript
// composables/useGitWrite.ts
import { ref, computed, onMounted } from 'vue';
import { GitWriteClient } from '@gitwrite/sdk';

const client = new GitWriteClient({
  baseURL: import.meta.env.VITE_GITWRITE_API_URL,
  apiKey: import.meta.env.VITE_GITWRITE_API_KEY,
});

export function useRepositories() {
  const repositories = ref([]);
  const loading = ref(false);
  const error = ref(null);

  const fetchRepositories = async () => {
    try {
      loading.value = true;
      error.value = null;
      const result = await client.repositories.list();
      repositories.value = result.items;
    } catch (err) {
      error.value = err;
    } finally {
      loading.value = false;
    }
  };

  onMounted(fetchRepositories);

  return {
    repositories: computed(() => repositories.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    refetch: fetchRepositories,
  };
}

// Component usage
<template>
  <div>
    <h2>My Repositories</h2>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">Error: {{ error.message }}</div>
    <div v-else>
      <div v-for="repo in repositories" :key="repo.id">
        <h3>{{ repo.name }}</h3>
        <p>{{ repo.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRepositories } from '@/composables/useGitWrite';

const { repositories, loading, error } = useRepositories();
</script>
```

### 3. Node.js/Express Integration

```typescript
// server.ts
import express from 'express';
import { GitWriteClient } from '@gitwrite/sdk';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const client = new GitWriteClient({
  baseURL: process.env.GITWRITE_API_URL!,
  apiKey: process.env.GITWRITE_API_KEY!,
});

app.use(express.json());

// Middleware to attach GitWrite client
app.use((req, res, next) => {
  req.gitwrite = client;
  next();
});

// Repository routes
app.get('/api/repositories', async (req, res) => {
  try {
    const repositories = await client.repositories.list({
      page: parseInt(req.query.page as string) || 1,
      pageSize: parseInt(req.query.pageSize as string) || 10,
    });
    res.json(repositories);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/repositories', async (req, res) => {
  try {
    const repository = await client.repositories.create(req.body);
    res.status(201).json(repository);
  } catch (error) {
    if (error instanceof ValidationError) {
      res.status(400).json({ error: error.message, fields: error.fieldErrors });
    } else {
      res.status(500).json({ error: error.message });
    }
  }
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
```

## Real-time Updates

### 1. WebSocket Setup

```typescript
// Enable real-time features
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  apiKey: 'your-api-key',
  enableRealtime: true,
});

// Connect to real-time updates
async function setupRealtime() {
  await client.realtime.connect();

  // Subscribe to repository updates
  client.realtime.subscribe('repository:my-novel', (event) => {
    console.log('Repository event:', event);

    switch (event.type) {
      case 'file_changed':
        handleFileChange(event.data);
        break;
      case 'commit_created':
        handleNewCommit(event.data);
        break;
      case 'collaborator_joined':
        handleCollaboratorJoined(event.data);
        break;
    }
  });

  // Subscribe to user notifications
  client.realtime.subscribe('user:notifications', (event) => {
    showNotification(event.data);
  });
}

function handleFileChange(data) {
  console.log(`File ${data.file_path} was ${data.change_type} by ${data.author.name}`);
  // Update UI to reflect changes
}

function handleNewCommit(data) {
  console.log(`New commit: ${data.commit.message}`);
  // Refresh commit history
}

function handleCollaboratorJoined(data) {
  console.log(`${data.collaborator.name} joined as ${data.role}`);
  // Update collaborator list
}

function showNotification(data) {
  // Show in-app notification
  console.log('Notification:', data.title, data.message);
}

// Clean up on app close
window.addEventListener('beforeunload', () => {
  client.realtime.disconnect();
});
```

### 2. React Real-time Hook

```typescript
// hooks/useRealtime.ts
import { useEffect, useCallback } from 'react';
import { GitWriteClient } from '@gitwrite/sdk';

export function useRealtimeUpdates(client: GitWriteClient, repositoryName: string) {
  const handleEvent = useCallback((event) => {
    // Handle real-time events
    console.log('Real-time event:', event);
  }, []);

  useEffect(() => {
    let mounted = true;

    const setupRealtime = async () => {
      try {
        await client.realtime.connect();

        if (mounted) {
          client.realtime.subscribe(`repository:${repositoryName}`, handleEvent);
        }
      } catch (error) {
        console.error('Failed to setup real-time updates:', error);
      }
    };

    setupRealtime();

    return () => {
      mounted = false;
      client.realtime.unsubscribe(`repository:${repositoryName}`);
    };
  }, [client, repositoryName, handleEvent]);
}
```

## Error Handling

### 1. Global Error Handler

```typescript
// utils/errorHandler.ts
import {
  GitWriteError,
  AuthenticationError,
  ValidationError,
  NotFoundError,
  PermissionError,
  NetworkError
} from '@gitwrite/sdk/errors';

export function handleApiError(error: unknown) {
  if (error instanceof AuthenticationError) {
    // Redirect to login
    window.location.href = '/login';
  } else if (error instanceof ValidationError) {
    // Show validation errors
    console.error('Validation errors:', error.fieldErrors);
    return { type: 'validation', errors: error.fieldErrors };
  } else if (error instanceof NotFoundError) {
    // Show not found message
    return { type: 'not_found', message: error.message };
  } else if (error instanceof PermissionError) {
    // Show permission error
    return { type: 'permission', message: 'You do not have permission to perform this action' };
  } else if (error instanceof NetworkError) {
    // Show network error
    return { type: 'network', message: 'Connection failed. Please check your internet connection.' };
  } else if (error instanceof GitWriteError) {
    // Generic GitWrite error
    return { type: 'api', message: error.message };
  } else {
    // Unknown error
    console.error('Unknown error:', error);
    return { type: 'unknown', message: 'An unexpected error occurred' };
  }
}
```

### 2. Async Error Boundary

```typescript
// components/AsyncErrorBoundary.tsx
import React from 'react';

interface AsyncErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class AsyncErrorBoundary extends React.Component<
  React.PropsWithChildren<{}>,
  AsyncErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<{}>) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): AsyncErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Async error caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

## Testing

### 1. Mock Client for Testing

```typescript
// tests/mocks/gitwrite.ts
import { GitWriteClient } from '@gitwrite/sdk';

export function createMockClient(): GitWriteClient {
  const mockClient = {
    repositories: {
      list: jest.fn(),
      get: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
    },
    files: {
      list: jest.fn(),
      getContent: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
    },
    // ... other services
  } as unknown as GitWriteClient;

  return mockClient;
}

// Test setup
beforeEach(() => {
  const mockClient = createMockClient();

  // Setup default mocks
  mockClient.repositories.list.mockResolvedValue({
    items: [
      { id: '1', name: 'test-repo', description: 'Test repository' }
    ],
    total: 1,
  });
});
```

### 2. Integration Tests

```typescript
// tests/integration/repositories.test.ts
import { GitWriteClient } from '@gitwrite/sdk';

describe('Repository Integration Tests', () => {
  let client: GitWriteClient;

  beforeAll(() => {
    client = new GitWriteClient({
      baseURL: process.env.TEST_API_URL,
      apiKey: process.env.TEST_API_KEY,
    });
  });

  test('should create and retrieve repository', async () => {
    // Create repository
    const created = await client.repositories.create({
      name: 'test-integration-repo',
      description: 'Integration test repository',
    });

    expect(created.name).toBe('test-integration-repo');

    // Retrieve repository
    const retrieved = await client.repositories.get(created.name);
    expect(retrieved.id).toBe(created.id);

    // Clean up
    await client.repositories.delete(created.name);
  });
});
```

---

*The GitWrite TypeScript SDK provides a comprehensive, type-safe way to integrate with the GitWrite platform. With proper setup and the examples above, you can quickly build powerful writing applications that leverage GitWrite's collaborative features and version control capabilities.*