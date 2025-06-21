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
