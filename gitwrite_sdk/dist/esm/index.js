import axios from 'axios';

class GitWriteClient {
    constructor(baseURL) {
        this.token = null;
        this.baseURL = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL;
        this.axiosInstance = axios.create({
            baseURL: this.baseURL,
        });
    }
    setToken(token) {
        this.token = token;
        this.updateAuthHeader();
    }
    getToken() {
        return this.token;
    }
    async login(credentials) {
        const formData = new URLSearchParams();
        if (credentials.username) {
            formData.append('username', credentials.username);
        }
        if (credentials.password) {
            formData.append('password', credentials.password);
        }
        try {
            const response = await this.axiosInstance.post('/token', formData, {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            });
            if (response.data.access_token) {
                this.setToken(response.data.access_token);
            }
            return response.data;
        }
        catch (error) {
            // console.error('Login failed:', error);
            throw error; // Re-throw to allow caller to handle
        }
    }
    logout() {
        this.token = null;
        this.updateAuthHeader();
    }
    updateAuthHeader() {
        if (this.token) {
            this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
        }
        else {
            delete this.axiosInstance.defaults.headers.common['Authorization'];
        }
    }
    // Generic request method
    async request(config) {
        try {
            // The token is already set in the axiosInstance defaults by updateAuthHeader
            // So, no need to manually add it here for each request.
            const response = await this.axiosInstance.request(config);
            return response;
        }
        catch (error) {
            // Basic error logging, can be expanded
            // console.error(`API request to ${config.url} failed:`, error);
            // It's often better to let the caller handle the error,
            // or transform it into a more specific error type.
            throw error;
        }
    }
    // Example of a GET request using the generic method
    async get(url, config) {
        return this.request({ ...config, method: 'GET', url });
    }
    // Example of a POST request
    async post(url, data, config) {
        return this.request({ ...config, method: 'POST', url, data });
    }
    // Example of a PUT request
    async put(url, data, config) {
        return this.request({ ...config, method: 'PUT', url, data });
    }
    // Example of a DELETE request
    async delete(url, config) {
        return this.request({ ...config, method: 'DELETE', url });
    }
    // Repository Methods
    /**
     * Lists all local branches in the repository.
     * Corresponds to API endpoint: GET /repository/branches
     */
    async listBranches() {
        // The actual response object from Axios is AxiosResponse<RepositoryBranchesResponse>
        // We are interested in the `data` part of it.
        const response = await this.get('/repository/branches');
        return response.data;
    }
    /**
     * Lists all tags in the repository.
     * Corresponds to API endpoint: GET /repository/tags
     */
    async listTags() {
        const response = await this.get('/repository/tags');
        return response.data;
    }
    /**
     * Lists commits for a given branch, or the current branch if branch_name is not provided.
     * Corresponds to API endpoint: GET /repository/commits
     * @param params Optional parameters: branchName, maxCount.
     */
    async listCommits(params) {
        const queryParams = {};
        if (params?.branchName) {
            queryParams['branch_name'] = params.branchName;
        }
        if (params?.maxCount !== undefined) {
            queryParams['max_count'] = params.maxCount;
        }
        const response = await this.get('/repository/commits', {
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
    async save(filePath, content, commitMessage) {
        const payload = {
            file_path: filePath,
            content: content,
            commit_message: commitMessage,
        };
        const response = await this.post('/repository/save', payload);
        return response.data;
    }
    // --- Methods for Project Dashboard and Repository Browser (Task 11.3) ---
    /**
     * Lists all available repositories (projects).
     * Corresponds to conceptual API endpoint: GET /repositories
     */
    async listRepositories() {
        const response = await this.get('/repositories');
        return response.data;
    }
    /**
     * Lists files and folders within a repository at a specific path and ref.
     * Corresponds to conceptual API endpoint: GET /repository/{repo_name}/tree/{ref}?path={dir_path}
     * @param repoName The name of the repository.
     * @param ref The branch name, tag, or commit SHA.
     * @param path Optional directory path within the repository.
     */
    async listRepositoryTree(repoName, ref, path) {
        const queryParams = {};
        if (path) {
            queryParams.path = path;
        }
        const response = await this.get(`/repository/${repoName}/tree/${ref}`, { params: queryParams });
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
    async saveFiles(repoId, files, commitMessage) {
        // Step 1: Prepare metadata and call /initiate endpoint
        const filesMetadata = files.map(file => ({
            file_path: file.path,
            size: file.size ?? (file.content instanceof Blob ? file.content.size : Buffer.byteLength(file.content)),
            // hash: file.hash, // If hash calculation is implemented
        }));
        const initiatePayload = {
            files: filesMetadata,
            commit_message: commitMessage,
        };
        const initiateResponse = await this.post(`/repositories/${repoId}/save/initiate`, initiatePayload);
        const { completion_token, files: uploadInstructions } = initiateResponse.data;
        if (!completion_token || !uploadInstructions || uploadInstructions.length === 0) {
            throw new Error('Invalid response from initiate upload endpoint.');
        }
        // Step 2: Upload individual files in parallel
        const uploadPromises = uploadInstructions.map(async (instruction) => {
            const fileToUpload = files.find(f => f.path === instruction.file_path);
            if (!fileToUpload) {
                throw new Error(`File data not found for path: ${instruction.file_path}`);
            }
            // The instruction.upload_url is expected to be a relative path like /upload-session/{upload_id}
            // Axios will prepend the baseURL to this.
            await this.put(instruction.upload_url, fileToUpload.content, {
                headers: {
                    // Axios typically sets Content-Type automatically for Blob/Buffer,
                    // but being explicit for application/octet-stream can be good.
                    'Content-Type': 'application/octet-stream',
                },
            });
        });
        await Promise.all(uploadPromises);
        // Step 3: Call /complete endpoint
        const completePayload = {
            completion_token: completion_token,
        };
        const completeResponse = await this.post(`/repositories/${repoId}/save/complete`, completePayload);
        return completeResponse.data;
    }
    // New methods for API Parity (Task 8.1)
    /**
     * Initializes a new GitWrite repository.
     * Corresponds to API endpoint: POST /repository/repositories
     * @param payload Optional project name for the repository.
     */
    async initializeRepository(payload) {
        const response = await this.post('/repository/repositories', payload);
        return response.data;
    }
    /**
     * Creates a new branch from the current HEAD and switches to it.
     * Corresponds to API endpoint: POST /repository/branches
     * @param payload Contains the name of the branch to create.
     */
    async createBranch(payload) {
        const response = await this.post('/repository/branches', payload);
        return response.data;
    }
    /**
     * Switches to an existing local branch.
     * Corresponds to API endpoint: PUT /repository/branch
     * @param payload Contains the name of the branch to switch to.
     */
    async switchBranch(payload) {
        const response = await this.put('/repository/branch', payload);
        return response.data;
    }
    /**
     * Merges a specified source branch into the current branch.
     * Corresponds to API endpoint: POST /repository/merges
     * @param payload Contains the name of the source branch to merge.
     */
    async mergeBranch(payload) {
        const response = await this.post('/repository/merges', payload);
        return response.data;
    }
    /**
     * Compares two references in the repository and returns the diff.
     * Corresponds to API endpoint: GET /repository/compare
     * @param params Optional ref1 and ref2. Defaults to HEAD~1 and HEAD.
     */
    async compareRefs(params) {
        const response = await this.get('/repository/compare', { params });
        return response.data;
    }
    /**
     * Reverts a specified commit.
     * Corresponds to API endpoint: POST /repository/revert
     * @param payload Contains the commit reference to revert.
     */
    async revertCommit(payload) {
        const response = await this.post('/repository/revert', payload);
        return response.data;
    }
    /**
     * Synchronizes the local repository branch with its remote counterpart.
     * Corresponds to API endpoint: POST /repository/sync
     * @param payload Contains remote name, branch name, and push options.
     */
    async syncRepository(payload) {
        const response = await this.post('/repository/sync', payload);
        return response.data;
    }
    /**
     * Creates a new tag (lightweight or annotated) in the repository.
     * Corresponds to API endpoint: POST /repository/tags
     * @param payload Contains tag name, message, commit-ish, and force option.
     */
    async createTag(payload) {
        const response = await this.post('/repository/tags', payload);
        return response.data;
    }
    /**
     * Lists all patterns in the .gitignore file of the repository.
     * Corresponds to API endpoint: GET /repository/ignore
     */
    async listIgnorePatterns() {
        const response = await this.get('/repository/ignore');
        return response.data;
    }
    /**
     * Adds a new pattern to the .gitignore file in the repository.
     * Corresponds to API endpoint: POST /repository/ignore
     * @param payload Contains the pattern to add.
     */
    async addIgnorePattern(payload) {
        const response = await this.post('/repository/ignore', payload);
        return response.data;
    }
    /**
     * Retrieves commits present on the specified branch that are not on the current HEAD.
     * Corresponds to API endpoint: GET /repository/review/{branch_name}
     * @param branchName The name of the branch to review.
     * @param params Optional parameters, e.g., limit.
     */
    async reviewBranch(branchName, params) {
        const response = await this.get(`/repository/review/${branchName}`, { params });
        return response.data;
    }
    /**
     * Applies a specific commit from any part of the history to the current branch.
     * Corresponds to API endpoint: POST /repository/cherry-pick
     * @param payload Contains the commit ID and optional mainline parameter.
     */
    async cherryPickCommit(payload) {
        const response = await this.post('/repository/cherry-pick', payload);
        return response.data;
    }
    /**
     * Exports specified markdown files from the repository to an EPUB file.
     * Corresponds to API endpoint: POST /repository/export/epub
     * @param payload Contains commit-ish, file list, and output filename.
     */
    async exportToEPUB(payload) {
        const response = await this.post('/repository/export/epub', payload);
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
    async getFileContent(repoName, // repoName might be used in future if API becomes multi-repo or needs it for namespacing
    filePath, commitSha) {
        // Construct query parameters
        const queryParams = new URLSearchParams({
            file_path: filePath,
            commit_sha: commitSha,
        });
        // The API endpoint is /repository/file-content, repoName is not part of the URL path for this specific endpoint
        // It's included as a parameter for potential future use or consistency with other SDK methods.
        const response = await this.get(`/repository/file-content?${queryParams.toString()}`);
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

export { GitWriteClient };
//# sourceMappingURL=index.js.map
