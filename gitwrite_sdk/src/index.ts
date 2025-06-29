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
  // Word Diff Viewer types (Task 11.5)
  StructuredDiffFile,
  WordDiffHunk,
  WordDiffLine,
  WordDiffSegment,
  // Task 11.6 (Annotation Types)
  Annotation,
  AnnotationListResponse,
  UpdateAnnotationStatusRequest,
  UpdateAnnotationStatusResponse,
  CreateAnnotationRequest,
  CreateAnnotationResponse,
} from './types';

// These are the types we need to ensure are exported for runtime checks or direct use by JS consumers
// For enums, they are actual values, so they need to be imported normally and exported as values.
import {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse,
    // Task 11.4: No value-level export needed for FileContentResponse, it's a type.
    // Task 11.6 (Annotation Enum)
    AnnotationStatus,
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
  // Word Diff Viewer types (Task 11.5)
  StructuredDiffFile,
  WordDiffHunk,
  WordDiffLine,
  WordDiffSegment,
  // Task 11.6 (Annotation Types)
  Annotation,
  AnnotationListResponse,
  UpdateAnnotationStatusRequest,
  UpdateAnnotationStatusResponse,
  CreateAnnotationRequest,
  CreateAnnotationResponse,
};

export {
    RepositoryListItem,
    RepositoriesListResponse,
    RepositoryTreeResponse,
    // Task 11.4: No value-level export needed for FileContentResponse
    // Task 11.6 (Annotation Enum)
    AnnotationStatus,
};

// You can also export other modules or types here as the SDK grows
// For example:
// export * from './repository';