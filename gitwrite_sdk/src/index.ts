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
} from './types';

// These are the types we need to ensure are exported for runtime checks or direct use by JS consumers
import {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse
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
};

export {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse
};

// You can also export other modules or types here as the SDK grows
// For example:
// export * from './repository';