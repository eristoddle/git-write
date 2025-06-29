// SDK entry point
export { GitWriteClient, type AuthToken, type LoginCredentials, type TokenResponse } from './apiClient';

// Import then export types to ensure they are part of the module's explicit interface
import type {
  Branch,
  Tag,
  CommitDetail,
  RepositoryBranchesResponse,
  RepositoryTagsResponse,
  RepositoryCommitsResponse,
  ListCommitsParams,
  ApiErrorResponse,
  SaveFileRequestPayload,
  SaveFileResponseData,
  InputFile,
  FileMetadataForUpload,
  UploadInitiateRequestPayload,
  UploadURLData,
  UploadInitiateResponseData,
  UploadCompleteRequestPayload,
  UploadCompleteResponseData,
  RepositoryTreeEntry,
  RepositoryTreeBreadcrumbItem,
  // Task 11.4
  FileContentResponse,
} from './types';

// These are the types we need to ensure are exported for runtime checks or direct use by JS consumers
import {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse,
    // Task 11.4: No value-level export needed for FileContentResponse, it's a type.
} from './types';

export type {
  Branch,
  Tag,
  CommitDetail,
  RepositoryBranchesResponse,
  RepositoryTagsResponse,
  RepositoryCommitsResponse,
  ListCommitsParams,
  ApiErrorResponse,
  SaveFileRequestPayload,
  SaveFileResponseData,
  InputFile,
  FileMetadataForUpload,
  UploadInitiateRequestPayload,
  UploadURLData,
  UploadInitiateResponseData,
  UploadCompleteRequestPayload,
  UploadCompleteResponseData,
  RepositoryTreeEntry,
  RepositoryTreeBreadcrumbItem,
  // Task 11.4
  FileContentResponse,
};

export {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse,
    // Task 11.4: No value-level export needed for FileContentResponse
};

// You can also export other modules or types here as the SDK grows
// For example:
// export * from './repository';