import { AxiosResponse, AxiosRequestConfig } from 'axios';

/**
 * Represents a single Git branch.
 */
interface Branch {
    name: string;
}
/**
 * Represents a single Git tag.
 */
interface Tag {
    name: string;
}
/**
 * Represents detailed information about a Git commit.
 * Based on `CommitDetail` Pydantic model in the API.
 */
interface CommitDetail {
    sha: string;
    message: string;
    author_name: string;
    author_email: string;
    author_date: string;
    committer_name: string;
    committer_email: string;
    committer_date: string;
    parents: string[];
}
/**
 * Represents the API response for listing branches.
 * Based on `BranchListResponse` Pydantic model.
 */
interface RepositoryBranchesResponse {
    status: string;
    branches: string[];
    message: string;
}
/**
 * Represents the API response for listing tags.
 * Based on `TagListResponse` Pydantic model.
 */
interface RepositoryTagsResponse {
    status: string;
    tags: string[];
    message: string;
}
/**
 * Represents the API response for listing commits.
 * Based on `CommitListResponse` Pydantic model.
 */
interface RepositoryCommitsResponse {
    status: string;
    commits: CommitDetail[];
    message: string;
}
/**
 * Represents parameters for listing commits.
 */
interface ListCommitsParams {
    branchName?: string;
    maxCount?: number;
}
interface ApiErrorResponse {
    detail?: string | {
        msg: string;
        type: string;
    }[];
}
/**
 * Represents the payload for the save file request.
 * Based on `SaveFileRequest` Pydantic model in the API.
 */
interface SaveFileRequestPayload {
    file_path: string;
    content: string;
    commit_message: string;
}
/**
 * Represents the response data for the save file operation.
 * Based on `SaveFileResponse` Pydantic model in the API.
 */
interface SaveFileResponseData {
    status: string;
    message: string;
    commit_id?: string;
}
/**
 * Response data for retrieving file content.
 * Maps to FileContentResponse in API (gitwrite_api/models.py).
 */
interface FileContentResponse {
    file_path: string;
    commit_sha: string;
    content: string;
    size: number;
    mode: string;
    is_binary: boolean;
}
interface RepositoryListItem {
    name: string;
    last_modified: string;
    description?: string | null;
    default_branch: string;
}
interface RepositoriesListResponse {
    repositories: RepositoryListItem[];
}
interface RepositoryTreeEntry {
    name: string;
    path: string;
    type: 'blob' | 'tree';
    size?: number | null;
    mode: string;
    oid: string;
}
interface RepositoryTreeBreadcrumbItem {
    name: string;
    path: string;
}
interface RepositoryTreeResponse {
    repo_name: string;
    ref: string;
    request_path: string;
    entries: RepositoryTreeEntry[];
    breadcrumb?: RepositoryTreeBreadcrumbItem[];
}
/**
 * Request payload for initializing a repository.
 * POST /repository/repositories
 * Maps to RepositoryCreateRequest in API.
 */
interface RepositoryCreateRequest {
    project_name?: string | null;
}
/**
 * Response data for initializing a repository.
 * Maps to RepositoryCreateResponse in API.
 */
interface RepositoryCreateResponse {
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
interface BranchCreateRequest {
    branch_name: string;
}
/**
 * Request payload for switching a branch.
 * PUT /repository/branch
 * Maps to BranchSwitchRequest in API.
 */
interface BranchSwitchRequest {
    branch_name: string;
}
/**
 * Response data for branch operations (create/switch).
 * Maps to BranchResponse in API.
 */
interface BranchResponse {
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
interface MergeBranchRequest {
    source_branch: string;
}
/**
 * Response data for merging a branch.
 * Maps to MergeBranchResponse in API.
 */
interface MergeBranchResponse {
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
interface CompareRefsParams {
    ref1?: string | null;
    ref2?: string | null;
    diff_mode?: 'text' | 'word';
}
/**
 * Response data for comparing references.
 * Maps to CompareRefsResponse in API.
 */
interface CompareRefsResponse {
    ref1_oid: string;
    ref2_oid: string;
    ref1_display_name: string;
    ref2_display_name: string;
    patch_data: string | StructuredDiffFile[];
}
/**
 * Represents a segment of a word diff (added, removed, context).
 */
interface WordDiffSegment {
    type: 'added' | 'removed' | 'context';
    content: string;
}
/**
 * Represents a line in a structured diff, potentially with word-level details.
 */
interface WordDiffLine {
    type: 'context' | 'deletion' | 'addition' | 'no_newline';
    content: string;
    words?: WordDiffSegment[];
}
/**
 * Represents a hunk of changes in a structured diff.
 */
interface WordDiffHunk {
    lines: WordDiffLine[];
}
/**
 * Represents the structured diff for a single file.
 * This mirrors the structure from `gitwrite_core.versioning.get_word_level_diff`.
 */
interface StructuredDiffFile {
    file_path: string;
    change_type: 'modified' | 'added' | 'deleted' | 'renamed' | 'copied';
    old_file_path?: string;
    new_file_path?: string;
    is_binary?: boolean;
    hunks: WordDiffHunk[];
}
/**
 * Request payload for reverting a commit.
 * POST /repository/revert
 * Maps to RevertCommitRequest in API.
 */
interface RevertCommitRequest {
    commit_ish: string;
}
/**
 * Response data for reverting a commit.
 * Maps to RevertCommitResponse in API.
 */
interface RevertCommitResponse {
    status: string;
    message: string;
    new_commit_oid?: string | null;
}
/**
 * Sub-model for fetch status in sync operation.
 * Maps to SyncFetchStatus in API.
 */
interface SyncFetchStatus {
    received_objects?: number | null;
    total_objects?: number | null;
    message: string;
}
/**
 * Sub-model for local update status in sync operation.
 * Maps to SyncLocalUpdateStatus in API.
 */
interface SyncLocalUpdateStatus {
    type: string;
    message: string;
    commit_oid?: string | null;
    conflicting_files: string[];
}
/**
 * Sub-model for push status in sync operation.
 * Maps to SyncPushStatus in API.
 */
interface SyncPushStatus {
    pushed: boolean;
    message: string;
}
/**
 * Request payload for syncing a repository.
 * POST /repository/sync
 * Maps to SyncRepositoryRequest in API.
 */
interface SyncRepositoryRequest {
    remote_name?: string;
    branch_name?: string | null;
    push?: boolean;
    allow_no_push?: boolean;
}
/**
 * Response data for syncing a repository.
 * Maps to SyncRepositoryResponse in API.
 */
interface SyncRepositoryResponse {
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
interface TagCreateRequest {
    tag_name: string;
    message?: string | null;
    commit_ish?: string;
    force?: boolean;
}
/**
 * Response data for creating a tag.
 * Maps to TagCreateResponse in API.
 */
interface TagCreateResponse {
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
interface IgnoreListResponse {
    status: string;
    patterns: string[];
    message: string;
}
/**
 * Request payload for adding a pattern to .gitignore.
 * POST /repository/ignore
 * Maps to IgnorePatternRequest in API.
 */
interface IgnorePatternRequest {
    pattern: string;
}
/**
 * Response data for adding a pattern to .gitignore.
 * Maps to IgnoreAddResponse in API.
 */
interface IgnoreAddResponse {
    status: string;
    message: string;
}
/**
 * Represents a commit for branch review.
 * Maps to BranchReviewCommit in API (from gitwrite_api/models.py).
 */
interface BranchReviewCommit {
    short_hash: string;
    author_name: string;
    date: string;
    message_short: string;
    oid: string;
}
/**
 * Query parameters for reviewing a branch.
 * GET /repository/review/{branch_name}
 */
interface ReviewBranchParams {
    limit?: number | null;
}
/**
 * Response data for reviewing a branch.
 * Maps to BranchReviewResponse in API (from gitwrite_api/models.py).
 */
interface BranchReviewResponse {
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
interface CherryPickRequest {
    commit_id: string;
    mainline?: number | null;
}
/**
 * Response data for cherry-picking a commit.
 * Maps to CherryPickResponse in API (from gitwrite_api/models.py).
 */
interface CherryPickResponse {
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
interface EPUBExportRequest {
    commit_ish?: string;
    file_list: string[];
    output_filename?: string;
}
/**
 * Response data for exporting to EPUB.
 * Maps to EPUBExportResponse in API (from gitwrite_api/models.py).
 */
interface EPUBExportResponse {
    status: string;
    message: string;
    server_file_path?: string | null;
}
/**
 * Represents a file to be uploaded as part of a multi-file save operation.
 * Content can be Blob (for browser environments) or Buffer (for Node.js).
 */
interface InputFile {
    path: string;
    content: Blob | Buffer;
    size?: number;
}
/**
 * Represents metadata for a single file in the upload initiation request.
 * This aligns with the API's expected `FileMetadata` Pydantic model.
 */
interface FileMetadataForUpload {
    file_path: string;
    size?: number;
}
/**
 * Represents the payload for initiating a multi-part upload.
 * Aligns with API's `FileUploadInitiateRequest` Pydantic model.
 */
interface UploadInitiateRequestPayload {
    files: FileMetadataForUpload[];
    commit_message: string;
}
/**
 * Represents the data for a single file's upload URL and ID, received from the initiate response.
 */
interface UploadURLData {
    file_path: string;
    upload_url: string;
    upload_id: string;
}
/**
 * Represents the response from the multi-part upload initiation endpoint.
 * Aligns with API's `FileUploadInitiateResponse` Pydantic model.
 */
interface UploadInitiateResponseData {
    status: string;
    message: string;
    completion_token: string;
    files: UploadURLData[];
}
/**
 * Represents the payload for completing a multi-part upload.
 * Aligns with API's `FileUploadCompleteRequest` Pydantic model.
 */
interface UploadCompleteRequestPayload {
    completion_token: string;
}
/**
 * Represents the response from the multi-part upload completion endpoint.
 * Aligns with API's `FileUploadCompleteResponse` Pydantic model.
 */
interface UploadCompleteResponseData {
    status: string;
    message: string;
    commit_id?: string;
}

type AuthToken = string | null;
interface LoginCredentials {
    username?: string;
    password?: string;
}
interface TokenResponse {
    access_token: string;
    token_type: string;
}
declare class GitWriteClient {
    private baseURL;
    private token;
    private axiosInstance;
    constructor(baseURL: string);
    setToken(token: string): void;
    getToken(): AuthToken;
    login(credentials: LoginCredentials): Promise<TokenResponse>;
    logout(): void;
    private updateAuthHeader;
    request<T = any, R = AxiosResponse<T>, D = any>(config: AxiosRequestConfig<D>): Promise<R>;
    get<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    post<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
    put<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
    delete<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    /**
     * Lists all local branches in the repository.
     * Corresponds to API endpoint: GET /repository/branches
     */
    listBranches(): Promise<RepositoryBranchesResponse>;
    /**
     * Lists all tags in the repository.
     * Corresponds to API endpoint: GET /repository/tags
     */
    listTags(): Promise<RepositoryTagsResponse>;
    /**
     * Lists commits for a given branch, or the current branch if branch_name is not provided.
     * Corresponds to API endpoint: GET /repository/commits
     * @param params Optional parameters: branchName, maxCount.
     */
    listCommits(params?: ListCommitsParams): Promise<RepositoryCommitsResponse>;
    /**
     * Saves a file to the repository and commits the change.
     * Corresponds to API endpoint: POST /repository/save
     * @param filePath The relative path of the file in the repository.
     * @param content The content to be saved to the file.
     * @param commitMessage The commit message for the save operation.
     */
    save(filePath: string, content: string, commitMessage: string): Promise<SaveFileResponseData>;
    /**
     * Lists all available repositories (projects).
     * Corresponds to conceptual API endpoint: GET /repositories
     */
    listRepositories(): Promise<RepositoriesListResponse>;
    /**
     * Lists files and folders within a repository at a specific path and ref.
     * Corresponds to conceptual API endpoint: GET /repository/{repo_name}/tree/{ref}?path={dir_path}
     * @param repoName The name of the repository.
     * @param ref The branch name, tag, or commit SHA.
     * @param path Optional directory path within the repository.
     */
    listRepositoryTree(repoName: string, ref: string, path?: string): Promise<RepositoryTreeResponse>;
    /**
     * Saves multiple files to the repository using a multi-part upload process.
     * Handles initiating the upload, uploading individual files, and completing the upload.
     * @param repoId The ID of the repository.
     * @param files An array of InputFile objects, each with a path and content (Blob or Buffer).
     * @param commitMessage The commit message for the save operation.
     * @returns A promise that resolves with the response from the complete upload endpoint.
     */
    saveFiles(repoId: string, files: InputFile[], commitMessage: string): Promise<UploadCompleteResponseData>;
    /**
     * Initializes a new GitWrite repository.
     * Corresponds to API endpoint: POST /repository/repositories
     * @param payload Optional project name for the repository.
     */
    initializeRepository(payload?: RepositoryCreateRequest): Promise<RepositoryCreateResponse>;
    /**
     * Creates a new branch from the current HEAD and switches to it.
     * Corresponds to API endpoint: POST /repository/branches
     * @param payload Contains the name of the branch to create.
     */
    createBranch(payload: BranchCreateRequest): Promise<BranchResponse>;
    /**
     * Switches to an existing local branch.
     * Corresponds to API endpoint: PUT /repository/branch
     * @param payload Contains the name of the branch to switch to.
     */
    switchBranch(payload: BranchSwitchRequest): Promise<BranchResponse>;
    /**
     * Merges a specified source branch into the current branch.
     * Corresponds to API endpoint: POST /repository/merges
     * @param payload Contains the name of the source branch to merge.
     */
    mergeBranch(payload: MergeBranchRequest): Promise<MergeBranchResponse>;
    /**
     * Compares two references in the repository and returns the diff.
     * Corresponds to API endpoint: GET /repository/compare
     * @param params Optional ref1, ref2, and diff_mode. Defaults to HEAD~1 and HEAD, and 'text' diff_mode.
     */
    compareRefs(params?: CompareRefsParams): Promise<CompareRefsResponse>;
    /**
     * Reverts a specified commit.
     * Corresponds to API endpoint: POST /repository/revert
     * @param payload Contains the commit reference to revert.
     */
    revertCommit(payload: RevertCommitRequest): Promise<RevertCommitResponse>;
    /**
     * Synchronizes the local repository branch with its remote counterpart.
     * Corresponds to API endpoint: POST /repository/sync
     * @param payload Contains remote name, branch name, and push options.
     */
    syncRepository(payload: SyncRepositoryRequest): Promise<SyncRepositoryResponse>;
    /**
     * Creates a new tag (lightweight or annotated) in the repository.
     * Corresponds to API endpoint: POST /repository/tags
     * @param payload Contains tag name, message, commit-ish, and force option.
     */
    createTag(payload: TagCreateRequest): Promise<TagCreateResponse>;
    /**
     * Lists all patterns in the .gitignore file of the repository.
     * Corresponds to API endpoint: GET /repository/ignore
     */
    listIgnorePatterns(): Promise<IgnoreListResponse>;
    /**
     * Adds a new pattern to the .gitignore file in the repository.
     * Corresponds to API endpoint: POST /repository/ignore
     * @param payload Contains the pattern to add.
     */
    addIgnorePattern(payload: IgnorePatternRequest): Promise<IgnoreAddResponse>;
    /**
     * Retrieves commits present on the specified branch that are not on the current HEAD.
     * Corresponds to API endpoint: GET /repository/review/{branch_name}
     * @param branchName The name of the branch to review.
     * @param params Optional parameters, e.g., limit.
     */
    reviewBranch(branchName: string, params?: ReviewBranchParams): Promise<BranchReviewResponse>;
    /**
     * Applies a specific commit from any part of the history to the current branch.
     * Corresponds to API endpoint: POST /repository/cherry-pick
     * @param payload Contains the commit ID and optional mainline parameter.
     */
    cherryPickCommit(payload: CherryPickRequest): Promise<CherryPickResponse>;
    /**
     * Exports specified markdown files from the repository to an EPUB file.
     * Corresponds to API endpoint: POST /repository/export/epub
     * @param payload Contains commit-ish, file list, and output filename.
     */
    exportToEPUB(payload: EPUBExportRequest): Promise<EPUBExportResponse>;
    /**
     * Retrieves the content of a specific file at a given commit SHA.
     * Corresponds to API endpoint: GET /repository/file-content
     * @param repoName The name of the repository (currently unused by API, but good for consistency).
     * @param filePath The relative path of the file in the repository.
     * @param commitSha The commit SHA from which to retrieve the file.
     */
    getFileContent(repoName: string, // repoName might be used in future if API becomes multi-repo or needs it for namespacing
    filePath: string, commitSha: string): Promise<FileContentResponse>;
}

export { GitWriteClient };
export type { ApiErrorResponse, AuthToken, Branch, CommitDetail, FileContentResponse, FileMetadataForUpload, InputFile, ListCommitsParams, LoginCredentials, RepositoriesListResponse, RepositoryBranchesResponse, RepositoryCommitsResponse, RepositoryListItem, RepositoryTagsResponse, RepositoryTreeBreadcrumbItem, RepositoryTreeEntry, RepositoryTreeResponse, SaveFileRequestPayload, SaveFileResponseData, Tag, TokenResponse, UploadCompleteRequestPayload, UploadCompleteResponseData, UploadInitiateRequestPayload, UploadInitiateResponseData, UploadURLData };
