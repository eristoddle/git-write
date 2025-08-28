# Type Definitions

The GitWrite TypeScript SDK provides comprehensive type definitions that ensure type safety, enable excellent IntelliSense support, and make the API self-documenting. All types are automatically generated from the OpenAPI specification and manually enhanced for optimal developer experience.

## Overview

The type system includes:
- **Domain Models**: Core business entities (Repository, File, Annotation, etc.)
- **Request/Response Types**: API operation parameters and return types
- **Configuration Types**: Client and service configuration options
- **Event Types**: Real-time event data structures
- **Utility Types**: Helper types and type guards
- **Error Types**: Comprehensive error classification

```
Type Hierarchy
    │
    ├─ Core Domain Types
    │   ├─ Repository Types
    │   ├─ File System Types
    │   ├─ Annotation Types
    │   ├─ Collaboration Types
    │   └─ User Types
    │
    ├─ API Types
    │   ├─ Request Types
    │   ├─ Response Types
    │   ├─ Query Parameter Types
    │   └─ Pagination Types
    │
    ├─ Configuration Types
    │   ├─ Client Config
    │   ├─ Authentication Config
    │   └─ Service Config
    │
    └─ Utility Types
        ├─ Generic Helpers
        ├─ Type Guards
        └─ Branded Types
```

## Core Domain Types

### 1. Repository Types

```typescript
export interface Repository {
  id: string;
  name: string;
  description: string;
  owner: User;
  created_at: Date;
  updated_at: Date;

  // Repository settings
  is_public: boolean;
  collaboration_enabled: boolean;
  default_branch: string;

  // Statistics
  file_count: number;
  word_count: number;
  total_size: number;
  commit_count: number;

  // Metadata
  tags: string[];
  language: string;
  license?: string;

  // Collaboration
  collaborators: Collaborator[];
  permissions: RepositoryPermissions;

  // Status
  status: RepositoryStatus;
  last_activity: Date;
}

export type RepositoryStatus =
  | 'active'
  | 'archived'
  | 'suspended'
  | 'migrating';

export interface RepositoryPermissions {
  can_read: boolean;
  can_write: boolean;
  can_admin: boolean;
  can_invite: boolean;
  can_delete: boolean;
}

export interface CreateRepositoryRequest {
  name: string;
  description?: string;
  is_public?: boolean;
  template?: RepositoryTemplate;
  collaboration_enabled?: boolean;
  license?: string;
  tags?: string[];
}

export interface UpdateRepositoryRequest {
  name?: string;
  description?: string;
  is_public?: boolean;
  collaboration_enabled?: boolean;
  default_branch?: string;
  tags?: string[];
}

export type RepositoryTemplate =
  | 'blank'
  | 'novel'
  | 'short-story'
  | 'screenplay'
  | 'poetry'
  | 'academic'
  | 'blog'
  | 'technical-writing';

export interface RepositoryStatistics {
  word_count: number;
  character_count: number;
  file_count: number;
  commit_count: number;
  collaborator_count: number;
  annotation_count: number;

  // Time-based stats
  words_this_week: number;
  words_this_month: number;
  commits_this_week: number;

  // File type breakdown
  file_types: Record<string, number>;

  // Activity timeline
  activity_timeline: ActivityPoint[];
}

export interface ActivityPoint {
  date: Date;
  word_count: number;
  commits: number;
  collaborators_active: number;
}
```

### 2. File System Types

```typescript
export interface FileInfo {
  path: string;
  name: string;
  type: FileType;
  size: number;

  // Content metadata
  word_count?: number;
  character_count?: number;
  line_count?: number;

  // Version information
  created_at: Date;
  modified_at: Date;
  last_commit_id: string;
  last_modified_by: User;

  // File properties
  mime_type: string;
  encoding: string;
  is_binary: boolean;

  // Content preview
  preview?: string;

  // Permissions
  permissions: FilePermissions;
}

export type FileType = 'file' | 'directory';

export interface FilePermissions {
  can_read: boolean;
  can_write: boolean;
  can_delete: boolean;
}

export interface FileContent {
  content: string;
  encoding: string;
  size: number;
  checksum: string;

  // Metadata
  word_count: number;
  character_count: number;
  line_count: number;

  // Version info
  commit_id: string;
  modified_at: Date;
  author: User;
}

export interface CreateFileRequest {
  path: string;
  content: string;
  message?: string;
  encoding?: string;
  auto_commit?: boolean;
  overwrite?: boolean;
}

export interface UpdateFileRequest {
  content: string;
  message?: string;
  encoding?: string;
  expected_checksum?: string;
}

export interface FileUploadRequest {
  file: File | Blob;
  path?: string;
  message?: string;
  auto_commit?: boolean;
  overwrite?: boolean;
  process_content?: boolean;
}

export interface FileUploadResponse {
  success: boolean;
  file_path: string;
  file_size: number;
  file_type: string;
  checksum: string;

  // Processing results
  processed: boolean;
  processing_details?: ProcessingDetails;

  // Content analysis
  word_count?: number;
  character_count?: number;
  language_detected?: string;

  // Version control
  auto_committed: boolean;
  commit_id?: string;
}

export interface ProcessingDetails {
  format_conversion?: string;
  image_optimization?: boolean;
  text_cleaning?: boolean;
  encoding_detection?: string;
}
```

### 3. Version Control Types

```typescript
export interface Commit {
  id: string;
  message: string;
  author: CommitAuthor;
  committer: CommitAuthor;
  created_at: Date;

  // Changes
  files_changed: string[];
  additions: number;
  deletions: number;

  // Statistics
  word_count_change: number;
  total_word_count: number;

  // Relationships
  parent_ids: string[];
  children_ids?: string[];

  // Metadata
  tags: string[];
  notes?: string;

  // Verification
  verified: boolean;
  signature?: CommitSignature;
}

export interface CommitAuthor {
  name: string;
  email: string;
  timestamp: Date;
}

export interface CommitSignature {
  type: 'gpg' | 'ssh';
  signature: string;
  verified: boolean;
  reason?: string;
}

export interface SaveRequest {
  message: string;
  files?: string[];
  author?: CommitAuthor;
  co_authors?: CommitAuthor[];
  auto_push?: boolean;
}

export interface SaveResponse {
  success: boolean;
  commit_id: string;
  message: string;
  files_changed: string[];
  word_count_change: number;
  total_word_count: number;
  created_at: Date;
}

export interface Exploration {
  name: string;
  description: string;
  created_at: Date;
  created_by: User;

  // Branch information
  base_commit_id: string;
  head_commit_id: string;
  commits_ahead: number;
  commits_behind: number;

  // Status
  status: ExplorationStatus;
  can_merge: boolean;
  has_conflicts: boolean;

  // Statistics
  word_count_difference: number;
  files_changed: number;

  // Metadata
  tags: string[];
  purpose?: ExplorationPurpose;
}

export type ExplorationStatus =
  | 'active'
  | 'merged'
  | 'abandoned'
  | 'archived';

export type ExplorationPurpose =
  | 'experiment'
  | 'feature'
  | 'revision'
  | 'collaboration'
  | 'backup';

export interface CreateExplorationRequest {
  name: string;
  description?: string;
  from_commit?: string;
  purpose?: ExplorationPurpose;
  auto_switch?: boolean;
}

export interface MergeExplorationRequest {
  message?: string;
  strategy?: MergeStrategy;
  delete_after_merge?: boolean;
  create_backup?: boolean;
}

export type MergeStrategy =
  | 'auto'
  | 'ours'
  | 'theirs'
  | 'manual'
  | 'cherry-pick';

export interface MergeResult {
  success: boolean;
  commit_id?: string;
  conflicts?: string[];
  files_merged: string[];
  word_count_change: number;
  message: string;
}
```

### 4. Annotation Types

```typescript
export interface Annotation {
  id: string;
  content: string;
  type: AnnotationType;
  priority: AnnotationPriority;
  status: AnnotationStatus;

  // Position information
  position: AnnotationPosition;

  // Author information
  author: User;
  created_at: Date;
  updated_at: Date;

  // Resolution
  resolved_at?: Date;
  resolved_by?: User;
  resolution_message?: string;

  // Suggestions
  suggested_text?: string;

  // Threading
  thread_id?: string;
  parent_id?: string;
  replies?: Annotation[];

  // Assignment
  assigned_to?: User;

  // Metadata
  tags: string[];
  category?: string;

  // Versioning
  commit_id: string;
  file_version: string;
}

export type AnnotationType =
  | 'comment'
  | 'suggestion'
  | 'question'
  | 'praise'
  | 'issue'
  | 'task';

export type AnnotationPriority =
  | 'low'
  | 'medium'
  | 'high'
  | 'critical';

export type AnnotationStatus =
  | 'open'
  | 'resolved'
  | 'accepted'
  | 'rejected'
  | 'in_progress';

export interface AnnotationPosition {
  file_path: string;
  line_start: number;
  line_end: number;
  column_start?: number;
  column_end?: number;
  character_start?: number;
  character_end?: number;

  // Context
  context_before?: string;
  context_after?: string;

  // Selection
  selected_text?: string;
}

export interface CreateAnnotationRequest {
  content: string;
  type?: AnnotationType;
  priority?: AnnotationPriority;
  position: AnnotationPosition;
  suggested_text?: string;
  assigned_to?: string;
  tags?: string[];
  category?: string;
  thread_id?: string;
  parent_id?: string;
}

export interface UpdateAnnotationRequest {
  content?: string;
  status?: AnnotationStatus;
  priority?: AnnotationPriority;
  assigned_to?: string;
  tags?: string[];
}

export interface ResolveAnnotationRequest {
  resolution: AnnotationResolution;
  message?: string;
}

export type AnnotationResolution =
  | 'resolved'
  | 'accepted'
  | 'rejected'
  | 'wont_fix'
  | 'duplicate';
```

### 5. Collaboration Types

```typescript
export interface User {
  id: string;
  email: string;
  name: string;
  username: string;

  // Profile
  avatar_url?: string;
  bio?: string;
  location?: string;
  website?: string;

  // Preferences
  timezone: string;
  language: string;

  // Status
  status: UserStatus;
  last_active: Date;
  created_at: Date;

  // Writing profile
  writing_genres?: string[];
  experience_level?: ExperienceLevel;
  preferred_role?: CollaborationRole;

  // Statistics
  public_repositories: number;
  total_contributions: number;
  words_written: number;
}

export type UserStatus =
  | 'active'
  | 'inactive'
  | 'suspended'
  | 'pending_verification';

export type ExperienceLevel =
  | 'beginner'
  | 'intermediate'
  | 'advanced'
  | 'professional';

export interface Collaborator {
  user: User;
  role: CollaborationRole;
  permissions: string[];
  invited_at: Date;
  accepted_at?: Date;
  invited_by: User;
  status: CollaboratorStatus;

  // Activity
  last_contribution: Date;
  contributions_count: number;

  // Preferences
  notification_settings: NotificationSettings;
}

export type CollaborationRole =
  | 'owner'
  | 'admin'
  | 'editor'
  | 'writer'
  | 'beta_reader'
  | 'viewer';

export type CollaboratorStatus =
  | 'pending'
  | 'active'
  | 'suspended'
  | 'removed';

export interface CollaborationInvitation {
  id: string;
  repository: Repository;
  inviter: User;
  invitee_email: string;
  role: CollaborationRole;
  permissions: string[];
  message?: string;

  // Status
  status: InvitationStatus;
  sent_at: Date;
  expires_at: Date;
  responded_at?: Date;

  // Response
  response_message?: string;
}

export type InvitationStatus =
  | 'pending'
  | 'accepted'
  | 'declined'
  | 'expired'
  | 'cancelled';

export interface InviteCollaboratorRequest {
  email: string;
  role: CollaborationRole;
  permissions?: string[];
  message?: string;
  expires_in_days?: number;
}

export interface UpdateCollaboratorRequest {
  role?: CollaborationRole;
  permissions?: string[];
  notification_settings?: NotificationSettings;
}

export interface NotificationSettings {
  email_enabled: boolean;
  push_enabled: boolean;

  // Event preferences
  on_mention: boolean;
  on_assignment: boolean;
  on_file_change: boolean;
  on_invitation: boolean;
  on_comment: boolean;

  // Frequency
  digest_frequency: DigestFrequency;
  quiet_hours?: QuietHours;
}

export type DigestFrequency =
  | 'immediate'
  | 'hourly'
  | 'daily'
  | 'weekly'
  | 'never';

export interface QuietHours {
  enabled: boolean;
  start_time: string; // HH:MM format
  end_time: string;   // HH:MM format
  timezone: string;
}
```

## API Operation Types

### 1. Request/Response Patterns

```typescript
// Generic API response wrapper
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
  request_id: string;
  timestamp: Date;
}

// Paginated responses
export interface PaginatedResponse<T> {
  items: T[];
  pagination: PaginationInfo;
}

export interface PaginationInfo {
  current_page: number;
  total_pages: number;
  page_size: number;
  total_items: number;
  has_next: boolean;
  has_previous: boolean;
}

// Query parameters for list operations
export interface ListQueryParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  filter?: Record<string, any>;
}

// Common request options
export interface RequestOptions {
  timeout?: number;
  retry_attempts?: number;
  cache_ttl?: number;
  abort_signal?: AbortSignal;
  headers?: Record<string, string>;
}
```

### 2. Search and Filter Types

```typescript
export interface SearchRequest {
  query: string;
  filters?: SearchFilters;
  options?: SearchOptions;
}

export interface SearchFilters {
  repository_ids?: string[];
  file_types?: string[];
  authors?: string[];
  date_range?: DateRange;
  word_count_range?: NumberRange;
  tags?: string[];
}

export interface SearchOptions {
  highlight: boolean;
  include_content: boolean;
  max_results?: number;
  fuzzy_matching: boolean;
}

export interface DateRange {
  start_date: Date;
  end_date: Date;
}

export interface NumberRange {
  min: number;
  max: number;
}

export interface SearchResult {
  type: SearchResultType;
  id: string;
  title: string;
  excerpt: string;
  highlights: string[];
  score: number;

  // Context
  repository: Repository;
  file_path?: string;
  line_number?: number;

  // Metadata
  created_at: Date;
  modified_at: Date;
  author: User;
}

export type SearchResultType =
  | 'repository'
  | 'file'
  | 'annotation'
  | 'commit'
  | 'user';
```

## Configuration Types

### 1. Client Configuration

```typescript
export interface GitWriteClientConfig {
  // Connection
  baseURL: string;
  timeout?: number;

  // Authentication
  auth?: AuthenticationConfig;

  // Retry logic
  retryAttempts?: number;
  retryDelay?: number | ((attempt: number) => number);
  retryCondition?: (error: any) => boolean;

  // Caching
  enableCaching?: boolean;
  cacheTimeout?: number;
  cacheMaxSize?: number;

  // Real-time
  enableRealtime?: boolean;
  websocketURL?: string;

  // Logging
  debug?: boolean;
  logLevel?: LogLevel;
  logger?: Logger;

  // Request/Response transformation
  transformRequest?: RequestTransformer[];
  transformResponse?: ResponseTransformer[];

  // Error handling
  onError?: (error: any, request: any) => void;

  // Custom headers
  defaultHeaders?: Record<string, string>;
}

export interface AuthenticationConfig {
  type: AuthenticationType;
  apiKey?: string;
  token?: string;
  refreshToken?: string;
  clientId?: string;
  clientSecret?: string;
  redirectUri?: string;
  onTokenRefresh?: (token: string) => void;
  getAuthHeader?: () => Promise<string>;
}

export type AuthenticationType =
  | 'apiKey'
  | 'jwt'
  | 'oauth'
  | 'custom';

export type LogLevel =
  | 'debug'
  | 'info'
  | 'warn'
  | 'error'
  | 'silent';

export interface Logger {
  debug(message: string, ...args: any[]): void;
  info(message: string, ...args: any[]): void;
  warn(message: string, ...args: any[]): void;
  error(message: string, ...args: any[]): void;
}

export type RequestTransformer = (data: any, headers: any) => any;
export type ResponseTransformer = (data: any) => any;
```

### 2. Service Configuration

```typescript
export interface ServiceConfig {
  // Base service configuration
  baseURL?: string;
  timeout?: number;
  retryAttempts?: number;

  // Service-specific settings
  enableCache?: boolean;
  defaultHeaders?: Record<string, string>;
  transformResponse?: ResponseTransformer[];
}

export interface RepositoryServiceConfig extends ServiceConfig {
  defaultTemplate?: RepositoryTemplate;
  autoCreateBranches?: boolean;
}

export interface FileServiceConfig extends ServiceConfig {
  maxFileSize?: number;
  allowedFileTypes?: string[];
  autoDetectEncoding?: boolean;
  defaultEncoding?: string;
}

export interface AnnotationServiceConfig extends ServiceConfig {
  defaultPriority?: AnnotationPriority;
  enableAutoResolution?: boolean;
  maxThreadDepth?: number;
}
```

## Event Types

### 1. Real-time Events

```typescript
export interface BaseEvent {
  id: string;
  type: string;
  timestamp: Date;
  source: EventSource;
  user_id: string;
}

export interface EventSource {
  type: 'api' | 'websocket' | 'webhook';
  endpoint?: string;
  client_id?: string;
}

// Repository events
export interface RepositoryEvent extends BaseEvent {
  repository_id: string;
}

export interface FileChangedEvent extends RepositoryEvent {
  type: 'file_changed';
  data: {
    file_path: string;
    change_type: 'created' | 'modified' | 'deleted' | 'renamed';
    commit_id: string;
    author: User;
    word_count_change: number;
  };
}

export interface CommitCreatedEvent extends RepositoryEvent {
  type: 'commit_created';
  data: {
    commit: Commit;
    files_changed: string[];
    word_count_change: number;
  };
}

export interface CollaboratorJoinedEvent extends RepositoryEvent {
  type: 'collaborator_joined';
  data: {
    collaborator: User;
    role: CollaborationRole;
    invited_by: User;
  };
}

// Annotation events
export interface AnnotationEvent extends BaseEvent {
  repository_id: string;
  annotation_id: string;
}

export interface AnnotationCreatedEvent extends AnnotationEvent {
  type: 'annotation_created';
  data: {
    annotation: Annotation;
    file_path: string;
  };
}

export interface AnnotationResolvedEvent extends AnnotationEvent {
  type: 'annotation_resolved';
  data: {
    annotation: Annotation;
    resolution: AnnotationResolution;
    resolved_by: User;
  };
}

// User events
export interface UserEvent extends BaseEvent {
  target_user_id?: string;
}

export interface NotificationEvent extends UserEvent {
  type: 'notification';
  data: {
    title: string;
    message: string;
    category: NotificationCategory;
    action_url?: string;
    priority: 'low' | 'medium' | 'high';
  };
}

export type NotificationCategory =
  | 'collaboration'
  | 'milestone'
  | 'feedback'
  | 'system'
  | 'reminder';
```

## Utility Types

### 1. Type Guards

```typescript
// Type guard functions
export function isRepository(obj: any): obj is Repository {
  return obj &&
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.owner === 'object';
}

export function isFileInfo(obj: any): obj is FileInfo {
  return obj &&
         typeof obj.path === 'string' &&
         typeof obj.name === 'string' &&
         ['file', 'directory'].includes(obj.type);
}

export function isAnnotation(obj: any): obj is Annotation {
  return obj &&
         typeof obj.id === 'string' &&
         typeof obj.content === 'string' &&
         obj.position &&
         typeof obj.position.file_path === 'string';
}

export function isCommit(obj: any): obj is Commit {
  return obj &&
         typeof obj.id === 'string' &&
         typeof obj.message === 'string' &&
         obj.author &&
         typeof obj.author.name === 'string';
}

// Event type guards
export function isFileChangedEvent(event: BaseEvent): event is FileChangedEvent {
  return event.type === 'file_changed' &&
         'repository_id' in event &&
         'data' in event &&
         typeof event.data.file_path === 'string';
}

export function isAnnotationEvent(event: BaseEvent): event is AnnotationEvent {
  return 'annotation_id' in event &&
         typeof (event as any).annotation_id === 'string';
}
```

### 2. Branded Types

```typescript
// Branded types for better type safety
export type RepositoryId = string & { __brand: 'RepositoryId' };
export type UserId = string & { __brand: 'UserId' };
export type CommitId = string & { __brand: 'CommitId' };
export type AnnotationId = string & { __brand: 'AnnotationId' };
export type FilePath = string & { __brand: 'FilePath' };

// Helper functions to create branded types
export function createRepositoryId(id: string): RepositoryId {
  return id as RepositoryId;
}

export function createUserId(id: string): UserId {
  return id as UserId;
}

export function createCommitId(id: string): CommitId {
  return id as CommitId;
}

export function createAnnotationId(id: string): AnnotationId {
  return id as AnnotationId;
}

export function createFilePath(path: string): FilePath {
  return path as FilePath;
}
```

### 3. Conditional Types

```typescript
// Conditional types for flexible APIs
export type CreateRequest<T> = Omit<T, 'id' | 'created_at' | 'updated_at'>;
export type UpdateRequest<T> = Partial<Omit<T, 'id' | 'created_at'>>;

// Extract specific fields
export type RepositoryInfo = Pick<Repository, 'id' | 'name' | 'description' | 'owner'>;
export type FileMetadata = Pick<FileInfo, 'path' | 'name' | 'size' | 'modified_at'>;

// Make specific fields optional
export type PartialRepository = Partial<Repository> & Pick<Repository, 'id' | 'name'>;

// Utility types for API responses
export type ApiResult<T> = Promise<ApiResponse<T>>;
export type PaginatedResult<T> = Promise<ApiResponse<PaginatedResponse<T>>>;

// Event handler types
export type EventHandler<T extends BaseEvent> = (event: T) => void | Promise<void>;
export type EventSubscription = () => void;

// Service method types
export type ServiceMethod<TParams = void, TResult = void> =
  TParams extends void
    ? () => Promise<TResult>
    : (params: TParams) => Promise<TResult>;
```

## Error Types

### 1. Error Hierarchy

```typescript
export class GitWriteError extends Error {
  public readonly name = 'GitWriteError';
  public readonly status?: number;
  public readonly code?: string;
  public readonly details?: any;

  constructor(
    message: string,
    status?: number,
    code?: string,
    details?: any
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export class AuthenticationError extends GitWriteError {
  public readonly name = 'AuthenticationError';

  constructor(message = 'Authentication failed', details?: any) {
    super(message, 401, 'AUTHENTICATION_ERROR', details);
  }
}

export class ValidationError extends GitWriteError {
  public readonly name = 'ValidationError';
  public readonly fieldErrors: Record<string, string[]>;

  constructor(
    message = 'Validation failed',
    fieldErrors: Record<string, string[]> = {},
    details?: any
  ) {
    super(message, 400, 'VALIDATION_ERROR', details);
    this.fieldErrors = fieldErrors;
  }
}

export class NotFoundError extends GitWriteError {
  public readonly name = 'NotFoundError';
  public readonly resource: string;

  constructor(resource: string, identifier?: string) {
    const message = identifier
      ? `${resource} '${identifier}' not found`
      : `${resource} not found`;
    super(message, 404, 'NOT_FOUND', { resource, identifier });
    this.resource = resource;
  }
}

export class PermissionError extends GitWriteError {
  public readonly name = 'PermissionError';
  public readonly requiredPermissions: string[];

  constructor(
    message = 'Insufficient permissions',
    requiredPermissions: string[] = []
  ) {
    super(message, 403, 'PERMISSION_ERROR', { requiredPermissions });
    this.requiredPermissions = requiredPermissions;
  }
}

export class ConflictError extends GitWriteError {
  public readonly name = 'ConflictError';
  public readonly conflictType: ConflictType;

  constructor(message: string, conflictType: ConflictType) {
    super(message, 409, 'CONFLICT_ERROR', { conflictType });
    this.conflictType = conflictType;
  }
}

export type ConflictType =
  | 'merge_conflict'
  | 'file_locked'
  | 'concurrent_modification'
  | 'name_collision';

export class RateLimitError extends GitWriteError {
  public readonly name = 'RateLimitError';
  public readonly retryAfter: number;
  public readonly limit: number;
  public readonly remaining: number;

  constructor(retryAfter: number, limit: number, remaining: number) {
    super(`Rate limit exceeded. Retry after ${retryAfter} seconds.`, 429, 'RATE_LIMIT_ERROR');
    this.retryAfter = retryAfter;
    this.limit = limit;
    this.remaining = remaining;
  }
}

export class NetworkError extends GitWriteError {
  public readonly name = 'NetworkError';
  public readonly originalError: Error;

  constructor(message: string, originalError: Error) {
    super(message, undefined, 'NETWORK_ERROR', { originalError: originalError.message });
    this.originalError = originalError;
  }
}
```

---

*The GitWrite TypeScript SDK's comprehensive type system ensures type safety throughout the API, provides excellent developer experience with IntelliSense support, and makes the codebase self-documenting. All types are designed to be both strict enough to catch errors and flexible enough to support evolving requirements.*