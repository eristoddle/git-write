// SDK entry point
export { GitWriteClient, type AuthToken, type LoginCredentials, type TokenResponse } from './apiClient';

// Export types related to repository operations
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
  // Multi-Part Upload Types
  InputFile,
  FileMetadataForUpload,
  UploadInitiateRequestPayload,
  UploadURLData,
  UploadInitiateResponseData,
  UploadCompleteRequestPayload,
  UploadCompleteResponseData,
} from './types';

// You can also export other modules or types here as the SDK grows
// For example:
// export * from './repository';