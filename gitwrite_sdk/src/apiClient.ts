import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import {
  RepositoryBranchesResponse,
  RepositoryTagsResponse,
  RepositoryCommitsResponse,
  ListCommitsParams,
  SaveFileRequestPayload,
  SaveFileResponseData,
  // Multi-part upload types
  InputFile,
  FileMetadataForUpload,
  UploadInitiateRequestPayload,
  UploadInitiateResponseData,
  UploadCompleteRequestPayload,
  UploadCompleteResponseData,
  UploadURLData,
  // Types for new methods (Task 8.1)
  RepositoryCreateRequest,
  RepositoryCreateResponse,
  BranchCreateRequest,
  BranchResponse,
  BranchSwitchRequest,
  MergeBranchRequest,
  MergeBranchResponse,
  CompareRefsParams,
  CompareRefsResponse,
  RevertCommitRequest,
  RevertCommitResponse,
  SyncRepositoryRequest,
  SyncRepositoryResponse,
  TagCreateRequest,
  TagCreateResponse,
  IgnoreListResponse,
  IgnorePatternRequest,
  IgnoreAddResponse,
  ReviewBranchParams,
  BranchReviewResponse,
  CherryPickRequest,
  CherryPickResponse,
  EPUBExportRequest,
  EPUBExportResponse,
  // Types for Task 11.3
  RepositoriesListResponse,
  RepositoryTreeResponse,
  // Types for Task 11.4
  FileContentResponse,
  // Types for Task 11.6 (Annotations)
  AnnotationListResponse,
  AnnotationStatus,
  UpdateAnnotationStatusRequest,
  UpdateAnnotationStatusResponse,
  CreateAnnotationRequest,
  CreateAnnotationResponse,
  Annotation, // Base Annotation type
} from './types';

// Define a type for the token, which can be a string or null
export type AuthToken = string | null;

// (Optional) Define interfaces for login credentials and token response
// These might come from a dedicated types file or be defined here if simple
export interface LoginCredentials {
  username?: string; // Making username optional as per API's /token endpoint
  password?: string; // Making password optional as per API's /token endpoint
  // The API's /token endpoint uses form data (username, password),
  // so we'll construct FormData in the login method.
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export class GitWriteClient {
  private baseURL: string;
  private token: AuthToken = null;
  private axiosInstance: AxiosInstance;

  constructor(baseURL: string) {
    this.baseURL = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL;
    this.axiosInstance = axios.create({
      baseURL: this.baseURL,
    });
  }

  public setToken(token: string): void {
    this.token = token;
    this.updateAuthHeader();
  }

  public getToken(): AuthToken {
    return this.token;
  }

  public async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    if (credentials.username) {
        formData.append('username', credentials.username);
    }
    if (credentials.password) {
        formData.append('password', credentials.password);
    }

    try {
      const response = await this.axiosInstance.post<TokenResponse>('/token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      if (response.data.access_token) {
        this.setToken(response.data.access_token);
      }
      return response.data;
    } catch (error) {
      // console.error('Login failed:', error);
      throw error; // Re-throw to allow caller to handle
    }
  }

  public logout(): void {
    this.token = null;
    this.updateAuthHeader();
  }

  private updateAuthHeader(): void {
    if (this.token) {
      this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
    } else {
      delete this.axiosInstance.defaults.headers.common['Authorization'];
    }
  }

  // Generic request method
  public async request<T = any, R = AxiosResponse<T>, D = any>(config: AxiosRequestConfig<D>): Promise<R> {
    try {
      // The token is already set in the axiosInstance defaults by updateAuthHeader
      // So, no need to manually add it here for each request.
      const response = await this.axiosInstance.request<T, R, D>(config);
      return response;
    } catch (error) {
      // Basic error logging, can be expanded
      // console.error(`API request to ${config.url} failed:`, error);
      // It's often better to let the caller handle the error,
      // or transform it into a more specific error type.
      throw error;
    }
  }

  // Example of a GET request using the generic method
  public async get<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R> {
    return this.request<T, R, D>({ ...config, method: 'GET', url });
  }

  // Example of a POST request
  public async post<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R> {
    return this.request<T, R, D>({ ...config, method: 'POST', url, data });
  }

  // Example of a PUT request
  public async put<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R> {
    return this.request<T, R, D>({ ...config, method: 'PUT', url, data });
  }

  // Example of a DELETE request
  public async delete<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R> {
    return this.request<T, R, D>({ ...config, method: 'DELETE', url });
  }

  // Repository Methods

  /**
   * Lists all local branches in the repository.
   * Corresponds to API endpoint: GET /repository/branches
   */
  public async listBranches(): Promise<RepositoryBranchesResponse> {
    // The actual response object from Axios is AxiosResponse<RepositoryBranchesResponse>
    // We are interested in the `data` part of it.
    const response = await this.get<RepositoryBranchesResponse>('/repository/branches');
    return response.data;
  }

  /**
   * Lists all tags in the repository.
   * Corresponds to API endpoint: GET /repository/tags
   */
  public async listTags(): Promise<RepositoryTagsResponse> {
    const response = await this.get<RepositoryTagsResponse>('/repository/tags');
    return response.data;
  }

  /**
   * Lists commits for a given branch, or the current branch if branch_name is not provided.
   * Corresponds to API endpoint: GET /repository/commits
   * @param params Optional parameters: branchName, maxCount.
   */
  public async listCommits(params?: ListCommitsParams): Promise<RepositoryCommitsResponse> {
    const queryParams: Record<string, string | number> = {};
    if (params?.branchName) {
      queryParams['branch_name'] = params.branchName;
    }
    if (params?.maxCount !== undefined) {
      queryParams['max_count'] = params.maxCount;
    }

    const response = await this.get<RepositoryCommitsResponse>('/repository/commits', {
      params: queryParams,
    });
    return response.data;
  }

  /**
   * Saves a file to the repository and commits the change.
   * Corresponds to API endpoint: POST /repository/save
   * @param filePath The relative path of the file in the repository.
   * @param content The content to be saved to the file.
   * @param commitMessage The commit message for the save operation.
   */
  public async save(filePath: string, content: string, commitMessage: string): Promise<SaveFileResponseData> {
    const payload: SaveFileRequestPayload = {
      file_path: filePath,
      content: content,
      commit_message: commitMessage,
    };
    const response = await this.post<SaveFileResponseData, AxiosResponse<SaveFileResponseData>, SaveFileRequestPayload>(
      '/repository/save',
      payload
    );
    return response.data;
  }

  // --- Methods for Project Dashboard and Repository Browser (Task 11.3) ---

  /**
   * Lists all available repositories (projects).
   * Corresponds to conceptual API endpoint: GET /repositories
   */
  public async listRepositories(): Promise<RepositoriesListResponse> {
    const response = await this.get<RepositoriesListResponse>('/repositories');
    return response.data;
  }

  /**
   * Lists files and folders within a repository at a specific path and ref.
   * Corresponds to conceptual API endpoint: GET /repository/{repo_name}/tree/{ref}?path={dir_path}
   * @param repoName The name of the repository.
   * @param ref The branch name, tag, or commit SHA.
   * @param path Optional directory path within the repository.
   */
  public async listRepositoryTree(
    repoName: string,
    ref: string,
    path?: string
  ): Promise<RepositoryTreeResponse> {
    const queryParams: { path?: string } = {};
    if (path) {
      queryParams.path = path;
    }
    const response = await this.get<RepositoryTreeResponse>(
      `/repository/${repoName}/tree/${ref}`,
      { params: queryParams }
    );
    return response.data;
  }

  /**
   * Saves multiple files to the repository using a multi-part upload process.
   * Handles initiating the upload, uploading individual files, and completing the upload.
   * @param repoId The ID of the repository.
   * @param files An array of InputFile objects, each with a path and content (Blob or Buffer).
   * @param commitMessage The commit message for the save operation.
   * @returns A promise that resolves with the response from the complete upload endpoint.
   */
  public async saveFiles(
    repoId: string,
    files: InputFile[],
    commitMessage: string
  ): Promise<UploadCompleteResponseData> {
    // Step 1: Prepare metadata and call /initiate endpoint
    const filesMetadata: FileMetadataForUpload[] = files.map(file => ({
      file_path: file.path,
      size: file.size ?? (file.content instanceof Blob ? file.content.size : Buffer.byteLength(file.content)),
      // hash: file.hash, // If hash calculation is implemented
    }));

    const initiatePayload: UploadInitiateRequestPayload = {
      files: filesMetadata,
      commit_message: commitMessage,
    };

    const initiateResponse = await this.post<UploadInitiateResponseData, AxiosResponse<UploadInitiateResponseData>, UploadInitiateRequestPayload>(
      `/repositories/${repoId}/save/initiate`,
      initiatePayload
    );

    const { completion_token, files: uploadInstructions } = initiateResponse.data;

    if (!completion_token || !uploadInstructions || uploadInstructions.length === 0) {
      throw new Error('Invalid response from initiate upload endpoint.');
    }

    // Step 2: Upload individual files in parallel
    const uploadPromises = uploadInstructions.map(async (instruction: UploadURLData) => {
      const fileToUpload = files.find(f => f.path === instruction.file_path);
      if (!fileToUpload) {
        throw new Error(`File data not found for path: ${instruction.file_path}`);
      }

      // The instruction.upload_url is expected to be a relative path like /upload-session/{upload_id}
      // Axios will prepend the baseURL to this.
      await this.put<any, AxiosResponse<any>, Blob | Buffer>(
        instruction.upload_url,
        fileToUpload.content,
        {
          headers: {
            // Axios typically sets Content-Type automatically for Blob/Buffer,
            // but being explicit for application/octet-stream can be good.
            'Content-Type': 'application/octet-stream',
          },
        }
      );
    });

    await Promise.all(uploadPromises);

    // Step 3: Call /complete endpoint
    const completePayload: UploadCompleteRequestPayload = {
      completion_token: completion_token,
    };

    const completeResponse = await this.post<UploadCompleteResponseData, AxiosResponse<UploadCompleteResponseData>, UploadCompleteRequestPayload>(
      `/repositories/${repoId}/save/complete`,
      completePayload
    );

    return completeResponse.data;
  }

  // New methods for API Parity (Task 8.1)

  /**
   * Initializes a new GitWrite repository.
   * Corresponds to API endpoint: POST /repository/repositories
   * @param payload Optional project name for the repository.
   */
  public async initializeRepository(payload?: RepositoryCreateRequest): Promise<RepositoryCreateResponse> {
    const response = await this.post<RepositoryCreateResponse, AxiosResponse<RepositoryCreateResponse>, RepositoryCreateRequest | undefined>(
      '/repository/repositories',
      payload
    );
    return response.data;
  }

  /**
   * Creates a new branch from the current HEAD and switches to it.
   * Corresponds to API endpoint: POST /repository/branches
   * @param payload Contains the name of the branch to create.
   */
  public async createBranch(payload: BranchCreateRequest): Promise<BranchResponse> {
    const response = await this.post<BranchResponse, AxiosResponse<BranchResponse>, BranchCreateRequest>(
      '/repository/branches',
      payload
    );
    return response.data;
  }

  /**
   * Switches to an existing local branch.
   * Corresponds to API endpoint: PUT /repository/branch
   * @param payload Contains the name of the branch to switch to.
   */
  public async switchBranch(payload: BranchSwitchRequest): Promise<BranchResponse> {
    const response = await this.put<BranchResponse, AxiosResponse<BranchResponse>, BranchSwitchRequest>(
      '/repository/branch',
      payload
    );
    return response.data;
  }

  /**
   * Merges a specified source branch into the current branch.
   * Corresponds to API endpoint: POST /repository/merges
   * @param payload Contains the name of the source branch to merge.
   */
  public async mergeBranch(payload: MergeBranchRequest): Promise<MergeBranchResponse> {
    const response = await this.post<MergeBranchResponse, AxiosResponse<MergeBranchResponse>, MergeBranchRequest>(
      '/repository/merges',
      payload
    );
    return response.data;
  }

  /**
   * Compares two references in the repository and returns the diff.
   * Corresponds to API endpoint: GET /repository/compare
   * @param params Optional ref1, ref2, and diff_mode. Defaults to HEAD~1 and HEAD, and 'text' diff_mode.
   */
  public async compareRefs(params?: CompareRefsParams): Promise<CompareRefsResponse> {
    // Ensure params is an object even if undefined is passed.
    const queryParams = { ...params };
    const response = await this.get<CompareRefsResponse>('/repository/compare', { params: queryParams });
    return response.data;
  }

  /**
   * Reverts a specified commit.
   * Corresponds to API endpoint: POST /repository/revert
   * @param payload Contains the commit reference to revert.
   */
  public async revertCommit(payload: RevertCommitRequest): Promise<RevertCommitResponse> {
    const response = await this.post<RevertCommitResponse, AxiosResponse<RevertCommitResponse>, RevertCommitRequest>(
      '/repository/revert',
      payload
    );
    return response.data;
  }

  /**
   * Synchronizes the local repository branch with its remote counterpart.
   * Corresponds to API endpoint: POST /repository/sync
   * @param payload Contains remote name, branch name, and push options.
   */
  public async syncRepository(payload: SyncRepositoryRequest): Promise<SyncRepositoryResponse> {
    const response = await this.post<SyncRepositoryResponse, AxiosResponse<SyncRepositoryResponse>, SyncRepositoryRequest>(
      '/repository/sync',
      payload
    );
    return response.data;
  }

  /**
   * Creates a new tag (lightweight or annotated) in the repository.
   * Corresponds to API endpoint: POST /repository/tags
   * @param payload Contains tag name, message, commit-ish, and force option.
   */
  public async createTag(payload: TagCreateRequest): Promise<TagCreateResponse> {
    const response = await this.post<TagCreateResponse, AxiosResponse<TagCreateResponse>, TagCreateRequest>(
      '/repository/tags',
      payload
    );
    return response.data;
  }

  /**
   * Lists all patterns in the .gitignore file of the repository.
   * Corresponds to API endpoint: GET /repository/ignore
   */
  public async listIgnorePatterns(): Promise<IgnoreListResponse> {
    const response = await this.get<IgnoreListResponse>('/repository/ignore');
    return response.data;
  }

  /**
   * Adds a new pattern to the .gitignore file in the repository.
   * Corresponds to API endpoint: POST /repository/ignore
   * @param payload Contains the pattern to add.
   */
  public async addIgnorePattern(payload: IgnorePatternRequest): Promise<IgnoreAddResponse> {
    const response = await this.post<IgnoreAddResponse, AxiosResponse<IgnoreAddResponse>, IgnorePatternRequest>(
      '/repository/ignore',
      payload
    );
    return response.data;
  }

  /**
   * Retrieves commits present on the specified branch that are not on the current HEAD.
   * Corresponds to API endpoint: GET /repository/review/{branch_name}
   * @param branchName The name of the branch to review.
   * @param params Optional parameters, e.g., limit.
   */
  public async reviewBranch(branchName: string, params?: ReviewBranchParams): Promise<BranchReviewResponse> {
    const response = await this.get<BranchReviewResponse>(
      `/repository/review/${branchName}`,
      { params }
    );
    return response.data;
  }

  /**
   * Applies a specific commit from any part of the history to the current branch.
   * Corresponds to API endpoint: POST /repository/cherry-pick
   * @param payload Contains the commit ID and optional mainline parameter.
   */
  public async cherryPickCommit(payload: CherryPickRequest): Promise<CherryPickResponse> {
    const response = await this.post<CherryPickResponse, AxiosResponse<CherryPickResponse>, CherryPickRequest>(
      '/repository/cherry-pick',
      payload
    );
    return response.data;
  }

  /**
   * Exports specified markdown files from the repository to an EPUB file.
   * Corresponds to API endpoint: POST /repository/export/epub
   * @param payload Contains commit-ish, file list, and output filename.
   */
  public async exportToEPUB(payload: EPUBExportRequest): Promise<EPUBExportResponse> {
    const response = await this.post<EPUBExportResponse, AxiosResponse<EPUBExportResponse>, EPUBExportRequest>(
      '/repository/export/epub',
      payload
    );
    return response.data;
  }

  // --- Methods for Commit History and File Content Viewer (Task 11.4) ---

  /**
   * Retrieves the content of a specific file at a given commit SHA.
   * Corresponds to API endpoint: GET /repository/file-content
   * @param repoName The name of the repository (currently unused by API, but good for consistency).
   * @param filePath The relative path of the file in the repository.
   * @param commitSha The commit SHA from which to retrieve the file.
   */
  public async getFileContent(
    repoName: string, // repoName might be used in future if API becomes multi-repo or needs it for namespacing
    filePath: string,
    commitSha: string
  ): Promise<FileContentResponse> {
    // Construct query parameters
    const queryParams = new URLSearchParams({
      file_path: filePath,
      commit_sha: commitSha,
    });

    // The API endpoint is /repository/file-content, repoName is not part of the URL path for this specific endpoint
    // It's included as a parameter for potential future use or consistency with other SDK methods.
    const response = await this.get<FileContentResponse>(`/repository/file-content?${queryParams.toString()}`);
    return response.data;
  }

  // --- Methods for Annotation Handling (Task 11.6) ---

  /**
   * Lists all annotations from a specified feedback branch.
   * Corresponds to API endpoint: GET /repository/annotations
   * @param repoName The name of the repository (currently for consistency, not used in API path).
   * @param feedbackBranch The name of the feedback branch.
   */
  public async listAnnotations(
    repoName: string, // Included for consistency, though API endpoint doesn't use it in path
    feedbackBranch: string
  ): Promise<AnnotationListResponse> {
    const queryParams = new URLSearchParams({
      feedback_branch: feedbackBranch,
    });
    const response = await this.get<AnnotationListResponse>(`/repository/annotations?${queryParams.toString()}`);
    return response.data;
  }

  /**
   * Updates the status of an existing annotation.
   * Corresponds to API endpoint: PUT /repository/annotations/{annotation_commit_id}
   * @param annotationCommitId The commit ID (SHA) of the original annotation to update.
   * @param payload The request payload, including new_status and feedback_branch.
   */
  public async updateAnnotationStatus(
    annotationCommitId: string,
    payload: UpdateAnnotationStatusRequest
  ): Promise<UpdateAnnotationStatusResponse> {
    const response = await this.put<UpdateAnnotationStatusResponse, AxiosResponse<UpdateAnnotationStatusResponse>, UpdateAnnotationStatusRequest>(
      `/repository/annotations/${annotationCommitId}`,
      payload
    );
    return response.data;
  }

  /**
   * Creates a new annotation.
   * Corresponds to API endpoint: POST /repository/annotations
   * (Added for SDK completeness, though not strictly part of Task 11.6 UI)
   * @param repoName The name of the repository.
   * @param payload The request payload for creating the annotation.
   */
  public async createAnnotation(
    repoName: string, // For consistency
    payload: CreateAnnotationRequest
  ): Promise<CreateAnnotationResponse> {
    const response = await this.post<CreateAnnotationResponse, AxiosResponse<CreateAnnotationResponse>, CreateAnnotationRequest>(
        `/repository/annotations`,
        payload
    );
    return response.data;
  }
}

// Example usage (optional, for testing within this file)
/*
async function main() {
  const client = new GitWriteClient('http://localhost:8000/api/v1'); // Replace with your API base URL

  try {
    // Login
    // Note: The default /token endpoint from FastAPI's OAuth2PasswordBearer expects
    // 'username' and 'password' as form data, not JSON.
    // The API's /token endpoint is currently set up with a dummy user if no credentials are provided.
    // For a real scenario, you'd pass actual credentials.
    const tokenData = await client.login({});
    console.log('Login successful:', tokenData);
    console.log('Token from client:', client.getToken());

    // Example: Make an authenticated GET request (replace with an actual endpoint)
    // const someData = await client.get('/users/me'); // Assuming such an endpoint exists
    // console.log('Fetched data:', someData.data);

    // Logout
    client.logout();
    console.log('Logged out. Token:', client.getToken());

  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('API Error:', error.response?.data || error.message);
    } else {
      console.error('An unexpected error occurred:', error);
    }
  }
}

// main(); // Uncomment to run example
*/
