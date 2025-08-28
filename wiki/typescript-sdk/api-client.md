# API Client

The GitWrite TypeScript SDK provides a comprehensive, type-safe client for interacting with the GitWrite API. Built with modern TypeScript features, it offers automatic request/response transformation, error handling, authentication management, and full IntelliSense support.

## Overview

The API client features:
- **Type Safety**: Full TypeScript support with auto-generated types
- **Authentication**: Automatic token management and refresh
- **Error Handling**: Comprehensive error handling with custom error types
- **Request/Response Transformation**: Automatic data serialization and deserialization
- **Caching**: Intelligent caching with cache invalidation
- **Retry Logic**: Configurable retry strategies for failed requests
- **Real-time Updates**: WebSocket integration for live data
- **Environment Support**: Multiple environment configurations

```
SDK Architecture
    │
    ├─ GitWriteClient (Main Client)
    │   ├─ Authentication Manager
    │   ├─ HTTP Client (Axios)
    │   ├─ Request/Response Interceptors
    │   └─ Error Handler
    │
    ├─ Service Modules
    │   ├─ RepositoryService
    │   ├─ FileService
    │   ├─ AnnotationService
    │   ├─ CollaborationService
    │   └─ ExportService
    │
    ├─ Real-time Client
    │   ├─ WebSocket Manager
    │   ├─ Event Handlers
    │   └─ Subscription Manager
    │
    └─ Utilities
        ├─ Type Guards
        ├─ Validators
        └─ Transformers
```

## Client Initialization

### 1. Basic Setup

```typescript
// Basic client initialization
import { GitWriteClient } from '@gitwrite/sdk';

const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  apiKey: 'your-api-key',
});

// With configuration options
const client = new GitWriteClient({
  baseURL: process.env.GITWRITE_API_URL || 'https://api.gitwrite.com',
  apiKey: process.env.GITWRITE_API_KEY,
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000,
  enableCaching: true,
  cacheTimeout: 300000, // 5 minutes
  enableRealtime: true,
});
```

### 2. Authentication Configuration

```typescript
// API key authentication
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  auth: {
    type: 'apiKey',
    apiKey: 'your-api-key',
  },
});

// OAuth authentication
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  auth: {
    type: 'oauth',
    clientId: 'your-client-id',
    clientSecret: 'your-client-secret',
    redirectUri: 'https://yourapp.com/callback',
  },
});

// JWT token authentication
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  auth: {
    type: 'jwt',
    token: 'your-jwt-token',
    refreshToken: 'your-refresh-token',
    onTokenRefresh: (newToken) => {
      localStorage.setItem('gitwrite_token', newToken);
    },
  },
});

// Custom authentication
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  auth: {
    type: 'custom',
    getAuthHeader: async () => {
      const token = await getTokenFromSecureStorage();
      return `Bearer ${token}`;
    },
  },
});
```

### 3. Environment Configurations

```typescript
// Development environment
const devClient = new GitWriteClient({
  baseURL: 'http://localhost:8000',
  apiKey: 'dev-api-key',
  debug: true,
  logLevel: 'debug',
});

// Production environment
const prodClient = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  apiKey: process.env.GITWRITE_API_KEY!,
  timeout: 60000,
  retryAttempts: 5,
  enableCaching: true,
});

// Testing environment
const testClient = new GitWriteClient({
  baseURL: 'https://api-staging.gitwrite.com',
  apiKey: 'test-api-key',
  timeout: 10000,
  retryAttempts: 1,
  enableCaching: false,
});
```

## Core Client Features

### 1. Repository Operations

```typescript
// Get all repositories
const repositories = await client.repositories.list({
  page: 1,
  pageSize: 20,
  sortBy: 'updated_at',
  sortOrder: 'desc',
});

// Get specific repository
const repository = await client.repositories.get('my-novel');

// Create new repository
const newRepo = await client.repositories.create({
  name: 'my-new-novel',
  description: 'My latest writing project',
  isPublic: false,
  template: 'novel',
});

// Update repository
const updatedRepo = await client.repositories.update('my-novel', {
  description: 'Updated description',
  collaborationEnabled: true,
});

// Delete repository
await client.repositories.delete('old-project');

// Get repository statistics
const stats = await client.repositories.getStatistics('my-novel');
```

### 2. File Operations

```typescript
// List files in repository
const files = await client.files.list('my-novel', {
  path: 'chapters/',
  recursive: true,
  includeContent: false,
});

// Get file content
const fileContent = await client.files.getContent('my-novel', 'chapters/chapter-01.md');

// Create new file
const newFile = await client.files.create('my-novel', {
  path: 'chapters/chapter-05.md',
  content: '# Chapter 5\n\nThe story continues...',
  message: 'Added Chapter 5',
});

// Update file
const updatedFile = await client.files.update('my-novel', 'chapters/chapter-01.md', {
  content: updatedContent,
  message: 'Updated opening scene',
});

// Upload file
const uploadResult = await client.files.upload('my-novel', {
  file: fileBlob,
  path: 'manuscripts/draft.docx',
  autoCommit: true,
  message: 'Uploaded manuscript draft',
});

// Delete file
await client.files.delete('my-novel', 'unused/old-scene.md', {
  message: 'Removed unused scene',
});
```

### 3. Version Control Operations

```typescript
// Save changes (commit)
const saveResult = await client.version.save('my-novel', {
  message: 'Completed character development arc',
  files: ['chapters/chapter-03.md', 'notes/characters.md'],
  author: {
    name: 'Jane Writer',
    email: 'jane@example.com',
  },
});

// Get commit history
const history = await client.version.getHistory('my-novel', {
  limit: 50,
  since: '2024-01-01',
  author: 'jane@example.com',
});

// Create exploration (branch)
const exploration = await client.explorations.create('my-novel', {
  name: 'alternate-ending',
  description: 'Exploring different story conclusion',
  fromCommit: 'abc123',
});

// Switch exploration
await client.explorations.switch('my-novel', 'alternate-ending');

// Merge exploration
const mergeResult = await client.explorations.merge('my-novel', 'alternate-ending', {
  message: 'Merged alternate ending exploration',
  strategy: 'auto',
  deleteAfterMerge: true,
});

// Create milestone tag
const milestone = await client.milestones.create('my-novel', {
  name: 'first-draft-complete',
  message: 'Completed first draft',
  commit: 'def456',
});
```

### 4. Collaboration Features

```typescript
// Invite collaborator
const invitation = await client.collaboration.invite('my-novel', {
  email: 'editor@example.com',
  role: 'editor',
  permissions: ['read', 'write', 'comment'],
  message: 'Please review my latest chapters',
});

// Get collaboration status
const collaborators = await client.collaboration.list('my-novel');

// Update collaborator permissions
await client.collaboration.updatePermissions('my-novel', 'user-id', {
  role: 'beta_reader',
  permissions: ['read', 'comment'],
});

// Remove collaborator
await client.collaboration.remove('my-novel', 'user-id');

// Get pending invitations
const invitations = await client.collaboration.getInvitations();

// Accept invitation
await client.collaboration.acceptInvitation('invitation-id');
```

### 5. Annotation and Feedback

```typescript
// Create annotation
const annotation = await client.annotations.create('my-novel', {
  filePath: 'chapters/chapter-01.md',
  position: {
    lineStart: 15,
    lineEnd: 17,
    characterStart: 0,
    characterEnd: 50,
  },
  content: 'This dialogue feels unnatural. Consider revising.',
  type: 'suggestion',
  priority: 'medium',
});

// Get annotations
const annotations = await client.annotations.list('my-novel', {
  filePath: 'chapters/chapter-01.md',
  status: 'open',
  author: 'editor@example.com',
});

// Reply to annotation
await client.annotations.reply(annotation.id, {
  content: 'Good point! I\'ll revise this dialogue.',
});

// Resolve annotation
await client.annotations.resolve(annotation.id, {
  resolution: 'implemented',
  message: 'Revised dialogue based on feedback',
});

// Apply suggestion
await client.annotations.applySuggestion(annotation.id, {
  createCommit: true,
  commitMessage: 'Applied editor suggestion',
});
```

## Error Handling

### 1. Error Types

```typescript
import {
  GitWriteError,
  AuthenticationError,
  ValidationError,
  NotFoundError,
  PermissionError,
  NetworkError,
  RateLimitError
} from '@gitwrite/sdk/errors';

try {
  const repository = await client.repositories.get('non-existent-repo');
} catch (error) {
  if (error instanceof NotFoundError) {
    console.log('Repository not found');
  } else if (error instanceof PermissionError) {
    console.log('Insufficient permissions');
  } else if (error instanceof AuthenticationError) {
    console.log('Authentication failed');
  } else if (error instanceof RateLimitError) {
    console.log('Rate limit exceeded, retry after:', error.retryAfter);
  } else if (error instanceof NetworkError) {
    console.log('Network error:', error.message);
  } else {
    console.log('Unknown error:', error);
  }
}
```

### 2. Global Error Handling

```typescript
// Set global error handler
client.onError((error, request) => {
  console.error('GitWrite API Error:', error);

  // Log to error tracking service
  errorTracker.report(error, {
    request: request.url,
    method: request.method,
    timestamp: new Date().toISOString(),
  });

  // Show user-friendly message
  if (error instanceof NetworkError) {
    showNotification('Connection error. Please check your internet connection.');
  } else if (error instanceof AuthenticationError) {
    redirectToLogin();
  }
});

// Retry configuration
client.configureRetry({
  attempts: 3,
  delay: (attempt) => Math.pow(2, attempt) * 1000, // Exponential backoff
  shouldRetry: (error) => {
    return error instanceof NetworkError ||
           (error instanceof GitWriteError && error.status >= 500);
  },
});
```

## Real-time Updates

### 1. WebSocket Connection

```typescript
// Enable real-time updates
const realtimeClient = client.realtime;

// Connect to real-time updates
await realtimeClient.connect();

// Subscribe to repository updates
realtimeClient.subscribe('repository:my-novel', (event) => {
  switch (event.type) {
    case 'file_changed':
      console.log('File updated:', event.data.filePath);
      // Refresh file content
      break;

    case 'collaboration_invite':
      console.log('New collaboration invite:', event.data);
      // Show notification
      break;

    case 'annotation_added':
      console.log('New feedback received:', event.data);
      // Update UI
      break;

    case 'commit_created':
      console.log('New save by collaborator:', event.data);
      // Refresh history
      break;
  }
});

// Subscribe to user notifications
realtimeClient.subscribe('user:notifications', (event) => {
  showNotification(event.data.message, event.data.type);
});

// Unsubscribe
realtimeClient.unsubscribe('repository:my-novel');

// Disconnect
await realtimeClient.disconnect();
```

### 2. Event Handling

```typescript
// Custom event handlers
class RepositoryEventHandler {
  constructor(private repositoryName: string) {}

  handleFileChanged = (event: FileChangedEvent) => {
    // Update local cache
    this.invalidateFileCache(event.filePath);

    // Notify components
    this.emit('fileUpdated', {
      filePath: event.filePath,
      author: event.author
    });
  };

  handleCollaboratorJoined = (event: CollaboratorJoinedEvent) => {
    // Show welcome message
    this.showMessage(`${event.collaborator.name} joined the project`);

    // Update collaborator list
    this.updateCollaboratorList();
  };

  handleConflictDetected = (event: ConflictDetectedEvent) => {
    // Show conflict resolution dialog
    this.showConflictDialog(event.conflictedFiles);
  };
}

const handler = new RepositoryEventHandler('my-novel');
realtimeClient.on('file_changed', handler.handleFileChanged);
realtimeClient.on('collaborator_joined', handler.handleCollaboratorJoined);
realtimeClient.on('conflict_detected', handler.handleConflictDetected);
```

## Advanced Features

### 1. Request Caching

```typescript
// Configure caching
const client = new GitWriteClient({
  baseURL: 'https://api.gitwrite.com',
  caching: {
    enabled: true,
    ttl: 300000, // 5 minutes
    maxSize: 100, // Max 100 cached responses
    keyGenerator: (request) => `${request.method}:${request.url}`,
    shouldCache: (request, response) => {
      // Only cache GET requests with successful responses
      return request.method === 'GET' && response.status < 400;
    },
  },
});

// Manual cache control
client.cache.set('repositories:my-novel', repositoryData, 600000); // 10 minutes
const cached = client.cache.get('repositories:my-novel');
client.cache.invalidate('repositories:*'); // Wildcard invalidation
client.cache.clear(); // Clear all cache
```

### 2. Request Interceptors

```typescript
// Request interceptor
client.addRequestInterceptor((request) => {
  // Add custom headers
  request.headers['X-Client-Version'] = '1.0.0';
  request.headers['X-Request-ID'] = generateRequestId();

  // Log requests in development
  if (process.env.NODE_ENV === 'development') {
    console.log('Request:', request.method, request.url);
  }

  return request;
});

// Response interceptor
client.addResponseInterceptor((response) => {
  // Transform response data
  if (response.data && response.data.created_at) {
    response.data.created_at = new Date(response.data.created_at);
  }

  // Log responses in development
  if (process.env.NODE_ENV === 'development') {
    console.log('Response:', response.status, response.config.url);
  }

  return response;
});
```

### 3. Batch Operations

```typescript
// Batch multiple operations
const batch = client.createBatch();

batch.add(client.files.update('my-novel', 'chapter-01.md', { content: newContent1 }));
batch.add(client.files.update('my-novel', 'chapter-02.md', { content: newContent2 }));
batch.add(client.annotations.create('my-novel', annotationData));

// Execute batch
const results = await batch.execute();

// Handle batch results
results.forEach((result, index) => {
  if (result.success) {
    console.log(`Operation ${index} completed:`, result.data);
  } else {
    console.error(`Operation ${index} failed:`, result.error);
  }
});
```

## TypeScript Integration

### 1. Type Safety

```typescript
// Fully typed responses
const repository: Repository = await client.repositories.get('my-novel');
const files: FileInfo[] = await client.files.list('my-novel');

// Type-safe request parameters
const newFile = await client.files.create('my-novel', {
  path: 'chapters/chapter-05.md', // string
  content: 'Chapter content',      // string
  message: 'Added new chapter',    // string
  autoCommit: true,               // boolean
} satisfies CreateFileRequest);

// Generic type support
const customData = await client.request<CustomResponseType>({
  method: 'GET',
  url: '/custom-endpoint',
});
```

### 2. Custom Type Guards

```typescript
import { isRepository, isFileInfo, isAnnotation } from '@gitwrite/sdk/guards';

// Safe type checking
if (isRepository(data)) {
  // TypeScript knows data is Repository
  console.log(data.name);
}

// Custom validation
function validateRepositoryName(name: unknown): name is string {
  return typeof name === 'string' && name.length > 0 && name.length <= 100;
}
```

---

*The GitWrite TypeScript SDK provides a powerful, type-safe interface for building applications that integrate with GitWrite. With comprehensive error handling, real-time capabilities, and modern TypeScript features, it enables developers to create robust writing applications with confidence.*