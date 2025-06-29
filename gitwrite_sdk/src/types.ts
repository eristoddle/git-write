// src/types.ts

/**
 * Represents a single Git branch.
 */
export interface Branch {
  name: string; // Assuming the API returns a list of names directly
}

/**
 * Represents a single Git tag.
 */
export interface Tag {
  name: string; // Assuming the API returns a list of names directly
}

/**
 * Represents detailed information about a Git commit.
 * Based on `CommitDetail` Pydantic model in the API.
 */
export interface CommitDetail {
  sha: string;
  message: string;
  author_name: string;
  author_email: string;
  author_date: string; // ISO 8601 date string or number (timestamp)
  committer_name: string;
  committer_email: string;
  committer_date: string; // ISO 8601 date string or number (timestamp)
  parents: string[];
}

/**
 * Represents the API response for listing branches.
 * Based on `BranchListResponse` Pydantic model.
 */
export interface RepositoryBranchesResponse {
  status: string;
  branches: string[]; // The API model has `List[str]` for branches
  message: string;
}

/**
 * Represents the API response for listing tags.
 * Based on `TagListResponse` Pydantic model.
 */
export interface RepositoryTagsResponse {
  status: string;
  tags: string[]; // The API model has `List[str]` for tags
  message: string;
}

/**
 * Represents the API response for listing commits.
 * Based on `CommitListResponse` Pydantic model.
 */
export interface RepositoryCommitsResponse {
  status: string;
  commits: CommitDetail[];
  message: string;
}

/**
 * Represents parameters for listing commits.
 */
export interface ListCommitsParams {
  branchName?: string;
  maxCount?: number;
}

// General API error structure, if common
export interface ApiErrorResponse {
  detail?: string | { msg: string; type: string }[]; // FastAPI error format
}

/**
 * Represents the payload for the save file request.
 * Based on `SaveFileRequest` Pydantic model in the API.
 */
export interface SaveFileRequestPayload {
  file_path: string;
  content: string;
  commit_message: string;
}

/**
 * Represents the response data for the save file operation.
 * Based on `SaveFileResponse` Pydantic model in the API.
 */
export interface SaveFileResponseData {
  status: string;
  message: string;
  commit_id?: string; // Optional, as it might not be present on error
}

// --- Types for File Content Viewer (Task 11.4) ---

/**
 * Response data for retrieving file content.
 * Maps to FileContentResponse in API (gitwrite_api/models.py).
 */
export interface FileContentResponse {
  file_path: string;
  commit_sha: string;
  content: string;
  size: number;
  mode: string; // e.g., "100644"
  is_binary: boolean;
}

// Types for Project Dashboard and Repository Browser (Task 11.3)

export interface RepositoryListItem {
  name: string;
  last_modified: string; // ISO 8601 timestamp
  description?: string | null;
  default_branch: string;
}

export interface RepositoriesListResponse {
  repositories: RepositoryListItem[];
}

export interface RepositoryTreeEntry {
  name: string;
  path: string; // Full path from repo root
  type: 'blob' | 'tree';
  size?: number | null; // Size in bytes for blobs
  mode: string; // Git mode
  oid: string; // Git object ID (SHA)
}

export interface RepositoryTreeBreadcrumbItem {
    name: string;
    path: string;
}

export interface RepositoryTreeResponse {
  repo_name: string;
  ref: string;
  request_path: string;
  entries: RepositoryTreeEntry[];
  breadcrumb?: RepositoryTreeBreadcrumbItem[];
}


// Types for API Parity - Task 8.1

// From gitwrite_api/models.py and gitwrite_api/routers/repository.py

/**
 * Request payload for initializing a repository.
 * POST /repository/repositories
 * Maps to RepositoryCreateRequest in API.
 */
export interface RepositoryCreateRequest {
  project_name?: string | null;
}

/**
 * Response data for initializing a repository.
 * Maps to RepositoryCreateResponse in API.
 */
export interface RepositoryCreateResponse {
  status: string;
  message: string;
  repository_id: string;
  path: string;
}

/**
 * Request payload for creating a branch.
 * POST /repository/branches
 * Maps to BranchCreateRequest in API.
 */
export interface BranchCreateRequest {
  branch_name: string;
}

/**
 * Request payload for switching a branch.
 * PUT /repository/branch
 * Maps to BranchSwitchRequest in API.
 */
export interface BranchSwitchRequest {
  branch_name: string;
}

/**
 * Response data for branch operations (create/switch).
 * Maps to BranchResponse in API.
 */
export interface BranchResponse {
  status: string;
  branch_name: string;
  message: string;
  head_commit_oid?: string | null;
  previous_branch_name?: string | null;
  is_detached?: boolean | null;
}

/**
 * Request payload for merging a branch.
 * POST /repository/merges
 * Maps to MergeBranchRequest in API.
 */
export interface MergeBranchRequest {
  source_branch: string;
}

/**
 * Response data for merging a branch.
 * Maps to MergeBranchResponse in API.
 */
export interface MergeBranchResponse {
  status: string;
  message: string;
  current_branch?: string | null;
  merged_branch?: string | null;
  commit_oid?: string | null;
  conflicting_files?: string[] | null;
}

/**
 * Query parameters for comparing references.
 * GET /repository/compare
 */
export interface CompareRefsParams {
  ref1?: string | null;
  ref2?: string | null;
}

/**
 * Response data for comparing references.
 * Maps to CompareRefsResponse in API.
 */
export interface CompareRefsResponse {
  ref1_oid: string;
  ref2_oid: string;
  ref1_display_name: string;
  ref2_display_name: string;
  patch_text: string;
}

/**
 * Request payload for reverting a commit.
 * POST /repository/revert
 * Maps to RevertCommitRequest in API.
 */
export interface RevertCommitRequest {
  commit_ish: string;
}

/**
 * Response data for reverting a commit.
 * Maps to RevertCommitResponse in API.
 */
export interface RevertCommitResponse {
  status: string;
  message: string;
  new_commit_oid?: string | null;
}

/**
 * Sub-model for fetch status in sync operation.
 * Maps to SyncFetchStatus in API.
 */
export interface SyncFetchStatus {
  received_objects?: number | null;
  total_objects?: number | null;
  message: string;
}

/**
 * Sub-model for local update status in sync operation.
 * Maps to SyncLocalUpdateStatus in API.
 */
export interface SyncLocalUpdateStatus {
  type: string;
  message: string;
  commit_oid?: string | null;
  conflicting_files: string[];
}

/**
 * Sub-model for push status in sync operation.
 * Maps to SyncPushStatus in API.
 */
export interface SyncPushStatus {
  pushed: boolean;
  message: string;
}

/**
 * Request payload for syncing a repository.
 * POST /repository/sync
 * Maps to SyncRepositoryRequest in API.
 */
export interface SyncRepositoryRequest {
  remote_name?: string;
  branch_name?: string | null;
  push?: boolean;
  allow_no_push?: boolean;
}

/**
 * Response data for syncing a repository.
 * Maps to SyncRepositoryResponse in API.
 */
export interface SyncRepositoryResponse {
  status: string;
  branch_synced?: string | null;
  remote: string;
  fetch_status: SyncFetchStatus;
  local_update_status: SyncLocalUpdateStatus;
  push_status: SyncPushStatus;
}

/**
 * Request payload for creating a tag.
 * POST /repository/tags
 * Maps to TagCreateRequest in API.
 */
export interface TagCreateRequest {
  tag_name: string;
  message?: string | null;
  commit_ish?: string;
  force?: boolean;
}

/**
 * Response data for creating a tag.
 * Maps to TagCreateResponse in API.
 */
export interface TagCreateResponse {
  status: string;
  tag_name: string;
  tag_type: string;
  target_commit_oid: string;
  message?: string | null;
}

/**
 * Response data for listing .gitignore patterns.
 * GET /repository/ignore
 * Maps to IgnoreListResponse in API.
 */
export interface IgnoreListResponse {
  status: string;
  patterns: string[];
  message: string;
}

/**
 * Request payload for adding a pattern to .gitignore.
 * POST /repository/ignore
 * Maps to IgnorePatternRequest in API.
 */
export interface IgnorePatternRequest {
  pattern: string;
}

/**
 * Response data for adding a pattern to .gitignore.
 * Maps to IgnoreAddResponse in API.
 */
export interface IgnoreAddResponse {
  status: string;
  message: string;
}

/**
 * Represents a commit for branch review.
 * Maps to BranchReviewCommit in API (from gitwrite_api/models.py).
 */
export interface BranchReviewCommit {
  short_hash: string;
  author_name: string;
  date: string; // ISO 8601 format
  message_short: string;
  oid: string;
}

/**
 * Query parameters for reviewing a branch.
 * GET /repository/review/{branch_name}
 */
export interface ReviewBranchParams {
  limit?: number | null;
}

/**
 * Response data for reviewing a branch.
 * Maps to BranchReviewResponse in API (from gitwrite_api/models.py).
 */
export interface BranchReviewResponse {
  status: string;
  branch_name: string;
  commits: BranchReviewCommit[];
  message: string;
}

/**
 * Request payload for cherry-picking a commit.
 * POST /repository/cherry-pick
 * Maps to CherryPickRequest in API (from gitwrite_api/models.py).
 */
export interface CherryPickRequest {
  commit_id: string;
  mainline?: number | null;
}

/**
 * Response data for cherry-picking a commit.
 * Maps to CherryPickResponse in API (from gitwrite_api/models.py).
 */
export interface CherryPickResponse {
  status: string;
  message: string;
  new_commit_oid?: string | null;
  conflicting_files?: string[] | null;
}

/**
 * Request payload for exporting to EPUB.
 * POST /repository/export/epub
 * Maps to EPUBExportRequest in API (from gitwrite_api/models.py).
 */
export interface EPUBExportRequest {
  commit_ish?: string;
  file_list: string[];
  output_filename?: string;
}

/**
 * Response data for exporting to EPUB.
 * Maps to EPUBExportResponse in API (from gitwrite_api/models.py).
 */
export interface EPUBExportResponse {
  status: string;
  message: string;
  server_file_path?: string | null;
}

// Interfaces for Multi-Part Upload (Task 6.5)

/**
 * Represents a file to be uploaded as part of a multi-file save operation.
 * Content can be Blob (for browser environments) or Buffer (for Node.js).
 */
export interface InputFile {
  path: string;
  content: Blob | Buffer; // Using Blob for browser, Buffer for Node.js
  size?: number; // Optional: size of the content in bytes
  // hash?: string; // Optional: SHA256 hash of the content, if pre-calculated
}

/**
 * Represents metadata for a single file in the upload initiation request.
 * This aligns with the API's expected `FileMetadata` Pydantic model.
 */
export interface FileMetadataForUpload {
  file_path: string;
  size?: number; // Optional: size of the content in bytes
  // hash?: string; // Optional: SHA256 hash of the content
}

/**
 * Represents the payload for initiating a multi-part upload.
 * Aligns with API's `FileUploadInitiateRequest` Pydantic model.
 */
export interface UploadInitiateRequestPayload {
  // repo_id is part of the URL path: /repositories/{repo_id}/save/initiate
  // The body should match the Pydantic model FileUploadInitiateRequest
  files: FileMetadataForUpload[];
  commit_message: string;
}

/**
 * Represents the data for a single file's upload URL and ID, received from the initiate response.
 */
export interface UploadURLData {
  file_path: string;
  upload_url: string; // This will be the relative path like /upload-session/{upload_id}
  upload_id: string;  // The unique ID for this specific file upload session
}

/**
 * Represents the response from the multi-part upload initiation endpoint.
 * Aligns with API's `FileUploadInitiateResponse` Pydantic model.
 */
export interface UploadInitiateResponseData {
  status: string;
  message: string;
  completion_token: string;
  files: UploadURLData[]; // Details for each file to be uploaded
}

/**
 * Represents the payload for completing a multi-part upload.
 * Aligns with API's `FileUploadCompleteRequest` Pydantic model.
 */
export interface UploadCompleteRequestPayload {
  completion_token: string;
}

/**
 * Represents the response from the multi-part upload completion endpoint.
 * Aligns with API's `FileUploadCompleteResponse` Pydantic model.
 */
export interface UploadCompleteResponseData {
  status: string;
  message: string;
  commit_id?: string; // Optional, as it might not be present on error
}
