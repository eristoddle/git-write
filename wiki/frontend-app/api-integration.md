# API Integration

GitWrite's frontend provides seamless integration with the backend API through a robust service layer that handles authentication, error management, request optimization, and real-time updates. The integration emphasizes type safety, performance, and developer experience.

## Overview

The API integration layer consists of:
- **Service Layer**: Typed API client interfaces
- **HTTP Client**: Axios-based with interceptors
- **Authentication**: Automatic token management
- **Error Handling**: Global error management with user-friendly messages
- **Caching**: Smart caching with TanStack Query
- **Real-time**: WebSocket integration for live updates
- **Optimistic Updates**: Immediate UI feedback with rollback capability

```
API Integration Architecture
    │
    ├─ Frontend Application
    │   ├─ React Components
    │   ├─ Zustand Stores
    │   └─ TanStack Query
    │
    ├─ Service Layer
    │   ├─ HTTP Client (Axios)
    │   ├─ Type Definitions
    │   ├─ Request/Response Interceptors
    │   └─ Error Handling
    │
    ├─ Network Layer
    │   ├─ REST API Calls
    │   ├─ WebSocket Connection
    │   └─ File Upload/Download
    │
    └─ Backend API
        ├─ FastAPI Endpoints
        ├─ Authentication
        └─ WebSocket Handlers
```

## Core Service Layer

### 1. HTTP Client Configuration

```typescript
// src/lib/apiClient.ts
import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios';
import { useAuthStore } from '../stores/authStore';
import { useUIStore } from '../stores/uiStore';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for authentication
    this.client.interceptors.request.use(
      (config) => {
        const { user } = useAuthStore.getState();

        if (user?.token) {
          config.headers.Authorization = `Bearer ${user.token}`;
        }

        // Add request ID for tracing
        config.headers['X-Request-ID'] = crypto.randomUUID();

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError) => {
        this.handleError(error);
        return Promise.reject(error);
      }
    );
  }

  private handleError(error: AxiosError) {
    const { addNotification } = useUIStore.getState();
    const { logout } = useAuthStore.getState();

    if (error.response?.status === 401) {
      // Unauthorized - logout user
      logout();
      addNotification({
        type: 'error',
        title: 'Authentication Error',
        message: 'Your session has expired. Please log in again.',
      });
    } else if (error.response?.status === 403) {
      // Forbidden
      addNotification({
        type: 'error',
        title: 'Access Denied',
        message: 'You do not have permission to perform this action.',
      });
    } else if (error.response?.status >= 500) {
      // Server error
      addNotification({
        type: 'error',
        title: 'Server Error',
        message: 'Something went wrong on our end. Please try again later.',
      });
    } else if (error.code === 'ECONNABORTED') {
      // Timeout
      addNotification({
        type: 'error',
        title: 'Request Timeout',
        message: 'The request took too long. Please try again.',
      });
    } else if (!error.response) {
      // Network error
      addNotification({
        type: 'error',
        title: 'Network Error',
        message: 'Unable to connect to the server. Please check your connection.',
      });
    }
  }

  public get<T>(url: string, config?: any): Promise<T> {
    return this.client.get(url, config).then(response => response.data);
  }

  public post<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.post(url, data, config).then(response => response.data);
  }

  public put<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.put(url, data, config).then(response => response.data);
  }

  public delete<T>(url: string, config?: any): Promise<T> {
    return this.client.delete(url, config).then(response => response.data);
  }

  public upload<T>(url: string, file: File, onProgress?: (progress: number) => void): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    return this.client.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress(progress);
        }
      },
    }).then(response => response.data);
  }
}

export const apiClient = new ApiClient();
```

### 2. Type Definitions

```typescript
// src/types/api.ts
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface Repository {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  is_public: boolean;
  collaboration_enabled: boolean;
  word_count: number;
  file_count: number;
  last_activity: string;
}

export interface RepositoryFile {
  path: string;
  name: string;
  size: number;
  type: 'file' | 'directory';
  modified_at: string;
  content?: string;
  word_count?: number;
}

export interface SaveResult {
  success: boolean;
  commit_id: string;
  message: string;
  files_changed: string[];
  word_count_change: number;
}

export interface Annotation {
  id: string;
  content: string;
  position: {
    file_path: string;
    line_start: number;
    line_end: number;
    character_start?: number;
    character_end?: number;
  };
  type: 'comment' | 'suggestion' | 'question' | 'praise';
  status: 'open' | 'resolved' | 'accepted' | 'rejected';
  author: string;
  created_at: string;
  resolved_at?: string;
  suggested_text?: string;
}

export interface Collaboration {
  id: string;
  repository_id: string;
  user_id: string;
  role: 'owner' | 'editor' | 'writer' | 'beta_reader';
  permissions: string[];
  invited_at: string;
  accepted_at?: string;
  status: 'pending' | 'active' | 'suspended';
}
```

### 3. Repository Service

```typescript
// src/services/repositoryService.ts
import { apiClient } from '../lib/apiClient';
import { Repository, RepositoryFile, SaveResult, PaginatedResponse } from '../types/api';

export interface CreateRepositoryRequest {
  name: string;
  description: string;
  is_public: boolean;
  template?: string;
}

export interface UpdateRepositoryRequest {
  name?: string;
  description?: string;
  is_public?: boolean;
}

class RepositoryService {
  async getRepositories(page = 1, pageSize = 20): Promise<PaginatedResponse<Repository>> {
    return apiClient.get(`/repositories?page=${page}&page_size=${pageSize}`);
  }

  async getRepository(name: string): Promise<Repository> {
    return apiClient.get(`/repositories/${name}`);
  }

  async createRepository(data: CreateRepositoryRequest): Promise<Repository> {
    return apiClient.post('/repositories', data);
  }

  async updateRepository(name: string, data: UpdateRepositoryRequest): Promise<Repository> {
    return apiClient.put(`/repositories/${name}`, data);
  }

  async deleteRepository(name: string): Promise<void> {
    return apiClient.delete(`/repositories/${name}`);
  }

  async getFiles(repositoryName: string, path = ''): Promise<RepositoryFile[]> {
    const params = path ? `?path=${encodeURIComponent(path)}` : '';
    return apiClient.get(`/repositories/${repositoryName}/files${params}`);
  }

  async getFileContent(repositoryName: string, filePath: string): Promise<string> {
    const response = await apiClient.get(
      `/repositories/${repositoryName}/files/${encodeURIComponent(filePath)}/content`
    );
    return response.content;
  }

  async saveFile(repositoryName: string, filePath: string, content: string): Promise<SaveResult> {
    return apiClient.post(`/repositories/${repositoryName}/save`, {
      file_path: filePath,
      content,
      message: `Updated ${filePath}`,
    });
  }

  async saveMultipleFiles(
    repositoryName: string,
    files: Array<{ path: string; content: string }>,
    message: string
  ): Promise<SaveResult> {
    return apiClient.post(`/repositories/${repositoryName}/save-multiple`, {
      files,
      message,
    });
  }

  async createExploration(
    repositoryName: string,
    name: string,
    description: string
  ): Promise<{ exploration_name: string }> {
    return apiClient.post(`/repositories/${repositoryName}/explorations`, {
      name,
      description,
    });
  }

  async getExplorations(repositoryName: string): Promise<any[]> {
    return apiClient.get(`/repositories/${repositoryName}/explorations`);
  }

  async switchExploration(
    repositoryName: string,
    explorationName: string
  ): Promise<void> {
    return apiClient.post(`/repositories/${repositoryName}/explorations/${explorationName}/switch`);
  }
}

export const repositoryService = new RepositoryService();
```

### 4. File Upload Service

```typescript
// src/services/fileUploadService.ts
import { apiClient } from '../lib/apiClient';

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface UploadResult {
  success: boolean;
  file_path: string;
  file_size: number;
  word_count?: number;
  processing_time: number;
}

class FileUploadService {
  async uploadFile(
    repositoryName: string,
    file: File,
    options: {
      filePath?: string;
      autoCommit?: boolean;
      commitMessage?: string;
      overwrite?: boolean;
      onProgress?: (progress: UploadProgress) => void;
    } = {}
  ): Promise<UploadResult> {
    const formData = new FormData();
    formData.append('file', file);

    if (options.filePath) {
      formData.append('file_path', options.filePath);
    }
    if (options.autoCommit !== undefined) {
      formData.append('auto_commit', String(options.autoCommit));
    }
    if (options.commitMessage) {
      formData.append('commit_message', options.commitMessage);
    }
    if (options.overwrite !== undefined) {
      formData.append('overwrite', String(options.overwrite));
    }

    return apiClient.client.post(
      `/repositories/${repositoryName}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (options.onProgress && progressEvent.total) {
            const progress: UploadProgress = {
              loaded: progressEvent.loaded,
              total: progressEvent.total,
              percentage: Math.round((progressEvent.loaded / progressEvent.total) * 100),
            };
            options.onProgress(progress);
          }
        },
      }
    ).then(response => response.data);
  }

  async uploadMultipleFiles(
    repositoryName: string,
    files: File[],
    options: {
      baseDirectory?: string;
      autoCommit?: boolean;
      commitMessage?: string;
      overwriteExisting?: boolean;
      onProgress?: (progress: UploadProgress) => void;
      onFileComplete?: (index: number, result: UploadResult) => void;
    } = {}
  ): Promise<UploadResult[]> {
    const results: UploadResult[] = [];
    let totalLoaded = 0;
    const totalSize = files.reduce((sum, file) => sum + file.size, 0);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      try {
        const result = await this.uploadFile(repositoryName, file, {
          filePath: options.baseDirectory ? `${options.baseDirectory}/${file.name}` : undefined,
          autoCommit: false, // We'll commit all at once
          overwrite: options.overwriteExisting,
          onProgress: (fileProgress) => {
            const overallProgress: UploadProgress = {
              loaded: totalLoaded + fileProgress.loaded,
              total: totalSize,
              percentage: Math.round(((totalLoaded + fileProgress.loaded) / totalSize) * 100),
            };
            options.onProgress?.(overallProgress);
          },
        });

        results.push(result);
        totalLoaded += file.size;
        options.onFileComplete?.(i, result);

      } catch (error) {
        console.error(`Failed to upload ${file.name}:`, error);
        results.push({
          success: false,
          file_path: file.name,
          file_size: file.size,
          processing_time: 0,
        });
      }
    }

    // Commit all uploaded files if auto-commit is enabled
    if (options.autoCommit && results.some(r => r.success)) {
      try {
        await repositoryService.saveMultipleFiles(
          repositoryName,
          [], // Files already uploaded
          options.commitMessage || `Bulk upload: ${files.length} files`
        );
      } catch (error) {
        console.error('Failed to commit uploaded files:', error);
      }
    }

    return results;
  }
}

export const fileUploadService = new FileUploadService();
```

### 5. Real-time Integration

```typescript
// src/services/websocketService.ts
interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

interface WebSocketHandlers {
  [key: string]: (payload: any) => void;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: WebSocketHandlers = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(token: string) {
    const wsUrl = `${process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws'}?token=${token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.attemptReconnect(token);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  private handleMessage(message: WebSocketMessage) {
    const handler = this.handlers[message.type];
    if (handler) {
      handler(message.payload);
    }
  }

  private attemptReconnect(token: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

      setTimeout(() => {
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect(token);
      }, delay);
    }
  }

  on(eventType: string, handler: (payload: any) => void) {
    this.handlers[eventType] = handler;
  }

  off(eventType: string) {
    delete this.handlers[eventType];
  }

  send(type: string, payload: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type,
        payload,
        timestamp: new Date().toISOString(),
      };
      this.ws.send(JSON.stringify(message));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const websocketService = new WebSocketService();

// React hook for WebSocket integration
export const useWebSocket = () => {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const { addNotification } = useUIStore();

  useEffect(() => {
    if (!user?.token) return;

    websocketService.connect(user.token);

    // Set up event handlers
    websocketService.on('repository_updated', (payload) => {
      queryClient.invalidateQueries({
        queryKey: ['repositories', payload.repository_id],
      });
    });

    websocketService.on('file_changed', (payload) => {
      queryClient.invalidateQueries({
        queryKey: ['repositories', payload.repository_id, 'files'],
      });
    });

    websocketService.on('collaboration_invite', (payload) => {
      addNotification({
        type: 'info',
        title: 'Collaboration Invite',
        message: `You've been invited to collaborate on ${payload.repository_name}`,
      });
    });

    websocketService.on('annotation_added', (payload) => {
      queryClient.invalidateQueries({
        queryKey: ['repositories', payload.repository_id, 'annotations'],
      });

      addNotification({
        type: 'info',
        title: 'New Feedback',
        message: `${payload.author} added feedback on ${payload.file_path}`,
      });
    });

    return () => {
      websocketService.disconnect();
    };
  }, [user?.token, queryClient, addNotification]);
};
```

### 6. Optimistic Updates

```typescript
// src/hooks/useOptimisticUpdates.ts
export const useOptimisticSave = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ repositoryName, filePath, content }: SaveFileParams) =>
      repositoryService.saveFile(repositoryName, filePath, content),

    onMutate: async ({ repositoryName, filePath, content }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: ['repositories', repositoryName, 'files', filePath],
      });

      // Snapshot previous value
      const previousContent = queryClient.getQueryData([
        'repositories',
        repositoryName,
        'files',
        filePath,
      ]);

      // Optimistically update
      queryClient.setQueryData(
        ['repositories', repositoryName, 'files', filePath],
        content
      );

      return { previousContent };
    },

    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousContent) {
        queryClient.setQueryData(
          ['repositories', variables.repositoryName, 'files', variables.filePath],
          context.previousContent
        );
      }
    },

    onSettled: (data, error, variables) => {
      // Always refetch after error or success
      queryClient.invalidateQueries({
        queryKey: ['repositories', variables.repositoryName, 'files', variables.filePath],
      });
    },
  });
};
```

### 7. API Error Boundaries

```typescript
// src/components/common/ApiErrorBoundary.tsx
interface ApiErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ApiErrorBoundary extends React.Component<
  React.PropsWithChildren<{}>,
  ApiErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<{}>) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ApiErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('API Error Boundary caught an error:', error, errorInfo);

    // Log to error tracking service
    if (process.env.NODE_ENV === 'production') {
      // analytics.reportError(error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="api-error-boundary">
          <h2>Something went wrong</h2>
          <p>We encountered an error while communicating with the server.</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="retry-button"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

## Performance Optimization

### Request Batching

```typescript
// Batch multiple API requests together
const useBatchedRequests = () => {
  const batchedPromises = useRef<Map<string, Promise<any>>>(new Map());

  const batchRequest = useCallback(<T>(key: string, fn: () => Promise<T>): Promise<T> => {
    if (batchedPromises.current.has(key)) {
      return batchedPromises.current.get(key)!;
    }

    const promise = fn().finally(() => {
      batchedPromises.current.delete(key);
    });

    batchedPromises.current.set(key, promise);
    return promise;
  }, []);

  return batchRequest;
};
```

### Request Deduplication

```typescript
// Prevent duplicate simultaneous requests
const requestCache = new Map<string, Promise<any>>();

export const dedupedRequest = <T>(key: string, fn: () => Promise<T>): Promise<T> => {
  if (requestCache.has(key)) {
    return requestCache.get(key)!;
  }

  const promise = fn().finally(() => {
    requestCache.delete(key);
  });

  requestCache.set(key, promise);
  return promise;
};
```

---

*GitWrite's API integration provides a robust, type-safe, and performant connection between the frontend and backend, handling everything from authentication to real-time updates while maintaining excellent developer experience and user feedback.*