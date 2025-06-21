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
