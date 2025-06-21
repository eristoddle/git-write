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
} from './types';

// You can also export other modules or types here as the SDK grows
// For example:
// export * from './repository';