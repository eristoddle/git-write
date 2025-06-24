import axios from 'axios';
import { GitWriteClient, LoginCredentials, TokenResponse } from '../src/apiClient';
import {
  RepositoryBranchesResponse,
  RepositoryTagsResponse,
  RepositoryCommitsResponse,
  CommitDetail,
  ListCommitsParams,
  SaveFileRequestPayload,
  SaveFileResponseData,
  // Multi-part upload types for testing
  InputFile,
  UploadInitiateRequestPayload,
  UploadInitiateResponseData,
  UploadCompleteRequestPayload,
  UploadCompleteResponseData,
  UploadURLData,
  FileMetadataForUpload,
} from '../src/types';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock the axios instance methods
const mockPost = jest.fn();
const mockGet = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();
const mockRequest = jest.fn(); // Added for the generic request method

describe('GitWriteClient', () => {
  const baseURL = 'http://localhost:8000/api/v1';
  let client: GitWriteClient;
  let clientAxiosInstance: any; // To store the instance used by the client for easier access in tests

  beforeEach(() => {
    // Reset all mocks before each test
    mockPost.mockClear();
    mockGet.mockClear();
    mockPut.mockClear();
    mockDelete.mockClear();
    mockRequest.mockClear();

    // This is the instance that the GitWriteClient will use
    clientAxiosInstance = {
      post: mockPost,
      get: mockGet, // Kept for direct client.axiosInstance.get if ever used, but request is primary
      put: mockPut,
      delete: mockDelete,
      request: mockRequest, // This is the one GitWriteClient.request method will call
      defaults: { headers: { common: {} } },
      interceptors: {
        request: { use: jest.fn(), eject: jest.fn() },
        response: { use: jest.fn(), eject: jest.fn() },
      },
    };

    mockedAxios.create.mockReturnValue(clientAxiosInstance);

    client = new GitWriteClient(baseURL);

    mockedAxios.isAxiosError.mockImplementation((payload: any): payload is import('axios').AxiosError => {
        return payload instanceof Error && 'isAxiosError' in payload && payload.isAxiosError === true;
    });
  });

  describe('constructor', () => {
    it('should initialize baseURL correctly and create an axios instance', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith({ baseURL });
    });

    it('should remove trailing slash from baseURL', () => {
      const clientWithSlash = new GitWriteClient('http://localhost:8000/api/v1/');
      // The client instance is created in beforeEach, so we check the last call
      expect(mockedAxios.create).toHaveBeenCalledWith({ baseURL: 'http://localhost:8000/api/v1' });
    });
  });

  describe('login', () => {
    it('should make a POST request to /token with credentials and store the token', async () => {
      const credentials: LoginCredentials = { username: 'testuser', password: 'password' };
      const tokenResponse: TokenResponse = { access_token: 'fake-token', token_type: 'bearer' };

      // mockPost is part of clientAxiosInstance, which is what client.login will use
      mockPost.mockResolvedValueOnce({ data: tokenResponse });

      const response = await client.login(credentials);

      expect(response).toEqual(tokenResponse);
      expect(mockPost).toHaveBeenCalledWith(
        '/token',
        expect.any(URLSearchParams),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );

      const calledParams = mockPost.mock.calls[0][1] as URLSearchParams;
      expect(calledParams.get('username')).toBe('testuser');
      expect(calledParams.get('password')).toBe('password');

      expect(client.getToken()).toBe('fake-token');
      // Check Authorization header on the *client's actual axios instance*
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer fake-token');
    });

    it('should handle login failure', async () => {
      const credentials: LoginCredentials = { username: 'testuser', password: 'password' };
      const error = new Error('Login failed');
      (error as any).isAxiosError = true;
      (error as any).response = { data: 'Invalid credentials' };

      mockPost.mockRejectedValueOnce(error);

      await expect(client.login(credentials)).rejects.toThrow('Login failed');
      expect(client.getToken()).toBeNull();
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBeUndefined();
    });

    it('should make a POST request to /token without credentials if none provided', async () => {
      const tokenResponse: TokenResponse = { access_token: 'guest-token', token_type: 'bearer' };
      mockPost.mockResolvedValueOnce({ data: tokenResponse });

      await client.login({});

      const calledParams = mockPost.mock.calls[0][1] as URLSearchParams;
      expect(calledParams.has('username')).toBe(false);
      expect(calledParams.has('password')).toBe(false);
      expect(client.getToken()).toBe('guest-token');
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer guest-token');
    });
  });

  describe('setToken', () => {
    it('should store the token and update axios instance headers', () => {
      const token = 'manual-token';
      client.setToken(token);
      expect(client.getToken()).toBe(token);
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe(`Bearer ${token}`);
    });
  });

  describe('logout', () => {
    it('should clear the token and remove Authorization header', () => {
      client.setToken('some-token');
      expect(client.getToken()).toBe('some-token');
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer some-token');

      client.logout();

      expect(client.getToken()).toBeNull();
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBeUndefined();
    });
  });

  describe('request method (via get, post, put, delete helpers)', () => {
    beforeEach(() => {
      client.setToken('test-token');
      // This ensures clientAxiosInstance.defaults.headers.common['Authorization'] is set
      // before each request test, as GitWriteClient.request relies on it.
    });

    it('GET request should be made with correct parameters', async () => {
      mockRequest.mockResolvedValueOnce({ data: { message: 'success' } });
      const response = await client.get('/test-get');

      expect(mockRequest).toHaveBeenCalledWith({ method: 'GET', url: '/test-get' });
      expect(response.data).toEqual({ message: 'success' });
      // Authorization header is managed by client.setToken -> updateAuthHeader
      // and is part of clientAxiosInstance.defaults.headers.common
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer test-token');
    });

    it('POST request should be made with correct parameters and data', async () => {
      const postData = { key: 'value' };
      mockRequest.mockResolvedValueOnce({ data: { id: 1, ...postData } });
      const response = await client.post('/test-post', postData);

      expect(mockRequest).toHaveBeenCalledWith({ method: 'POST', url: '/test-post', data: postData });
      expect(response.data).toEqual({ id: 1, ...postData });
      expect(clientAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer test-token');
    });

    it('PUT request should be made with correct parameters and data', async () => {
      const putData = { key: 'updatedValue' };
      mockRequest.mockResolvedValueOnce({ data: { ...putData } });
      const response = await client.put('/test-put/1', putData);

      expect(mockRequest).toHaveBeenCalledWith({ method: 'PUT', url: '/test-put/1', data: putData });
      expect(response.data).toEqual({ ...putData });
    });

    it('DELETE request should be made with correct parameters', async () => {
      mockRequest.mockResolvedValueOnce({ status: 204 });
      const response = await client.delete('/test-delete/1');

      expect(mockRequest).toHaveBeenCalledWith({ method: 'DELETE', url: '/test-delete/1' });
      expect(response.status).toBe(204);
    });

    it('should throw error if request fails', async () => {
      const error = new Error('Network Error');
      (error as any).isAxiosError = true;
      (error as any).response = { status: 500, data: 'Server Error' };

      mockRequest.mockRejectedValueOnce(error); // Mocking the generic request method
      await expect(client.get('/test-error')).rejects.toThrow('Network Error');

      // Reset mock for next call if necessary, or use different error for POST
      mockRequest.mockRejectedValueOnce(new Error('Another Network Error'));
      await expect(client.post('/test-error-post', {})).rejects.toThrow('Another Network Error');
    });
  });

  describe('Repository Methods', () => {
    beforeEach(() => {
      // Ensure client is authenticated for these tests
      client.setToken('test-repo-token');
      // clientAxiosInstance.defaults.headers.common['Authorization'] is set by setToken
    });

    describe('listBranches', () => {
      it('should call GET /repository/branches and return data', async () => {
        const mockResponseData: RepositoryBranchesResponse = {
          status: 'success',
          branches: ['main', 'develop'],
          message: 'Branches listed',
        };
        // The client.get method uses clientAxiosInstance.request
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });

        const result = await client.listBranches();

        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/branches',
        });
        expect(result).toEqual(mockResponseData);
      });

      it('should throw if API call fails for listBranches', async () => {
        const error = new Error('API Error for listBranches');
        mockRequest.mockRejectedValueOnce(error);
        await expect(client.listBranches()).rejects.toThrow('API Error for listBranches');
      });
    });

    describe('listTags', () => {
      it('should call GET /repository/tags and return data', async () => {
        const mockResponseData: RepositoryTagsResponse = {
          status: 'success',
          tags: ['v1.0', 'v1.1'],
          message: 'Tags listed',
        };
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });

        const result = await client.listTags();

        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/tags',
        });
        expect(result).toEqual(mockResponseData);
      });

      it('should throw if API call fails for listTags', async () => {
        const error = new Error('API Error for listTags');
        mockRequest.mockRejectedValueOnce(error);
        await expect(client.listTags()).rejects.toThrow('API Error for listTags');
      });
    });

    describe('listCommits', () => {
      const mockCommit: CommitDetail = {
        sha: 'abcdef123',
        message: 'Test commit',
        author_name: 'Test Author',
        author_email: 'author@example.com',
        author_date: new Date().toISOString(),
        committer_name: 'Test Committer',
        committer_email: 'committer@example.com',
        committer_date: new Date().toISOString(),
        parents: [],
      };
      const mockResponseData: RepositoryCommitsResponse = {
        status: 'success',
        commits: [mockCommit],
        message: 'Commits listed',
      };

      it('should call GET /repository/commits without params and return data', async () => {
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });
        const result = await client.listCommits();
        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/commits',
          params: {}, // Expect empty params when none provided
        });
        expect(result).toEqual(mockResponseData);
      });

      it('should call GET /repository/commits with branchName param', async () => {
        const params: ListCommitsParams = { branchName: 'develop' };
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });
        await client.listCommits(params);
        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/commits',
          params: { branch_name: 'develop' },
        });
      });

      it('should call GET /repository/commits with maxCount param', async () => {
        const params: ListCommitsParams = { maxCount: 10 };
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });
        await client.listCommits(params);
        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/commits',
          params: { max_count: 10 },
        });
      });

      it('should call GET /repository/commits with all params', async () => {
        const params: ListCommitsParams = { branchName: 'feature/test', maxCount: 5 };
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });
        await client.listCommits(params);
        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: '/repository/commits',
          params: { branch_name: 'feature/test', max_count: 5 },
        });
      });

      it('should throw if API call fails for listCommits', async () => {
        const error = new Error('API Error for listCommits');
        mockRequest.mockRejectedValueOnce(error);
        await expect(client.listCommits()).rejects.toThrow('API Error for listCommits');
      });
    });

    describe('save', () => {
      const filePath = 'test.txt';
      const content = 'Hello, world!';
      const commitMessage = 'Add test.txt';

      const mockRequestPayload: SaveFileRequestPayload = {
        file_path: filePath,
        content: content,
        commit_message: commitMessage,
      };

      it('should call POST /repository/save with correct payload and return data', async () => {
        const mockResponseData: SaveFileResponseData = {
          status: 'success',
          message: 'File saved successfully',
          commit_id: 'newcommitsha123',
        };
        // The client.post method uses clientAxiosInstance.request
        mockRequest.mockResolvedValueOnce({ data: mockResponseData });

        const result = await client.save(filePath, content, commitMessage);

        expect(mockRequest).toHaveBeenCalledWith({
          method: 'POST',
          url: '/repository/save',
          data: mockRequestPayload,
        });
        expect(result).toEqual(mockResponseData);
      });

      it('should throw if API call fails for save', async () => {
        const error = new Error('API Error for save');
        mockRequest.mockRejectedValueOnce(error);

        await expect(client.save(filePath, content, commitMessage)).rejects.toThrow('API Error for save');
        expect(mockRequest).toHaveBeenCalledWith({
          method: 'POST',
          url: '/repository/save',
          data: mockRequestPayload,
        });
      });
    });
  });

  describe('saveFiles (Multi-Part Upload)', () => {
    const repoId = 'test-repo';
    const commitMessage = 'Test multi-file commit';
    const file1Content = Buffer.from('Content for file 1');
    const file2Content = Buffer.from('Content for file 2');

    const inputFiles: InputFile[] = [
      { path: 'file1.txt', content: file1Content, size: file1Content.length },
      { path: 'path/to/file2.md', content: file2Content, size: file2Content.length },
    ];

    const mockFilesMetadata: FileMetadataForUpload[] = inputFiles.map(f => ({
        file_path: f.path,
        size: f.size,
    }));

    const mockInitiatePayload: UploadInitiateRequestPayload = {
      files: mockFilesMetadata,
      commit_message: commitMessage,
    };

    const mockUploadURLs: UploadURLData[] = [
      { file_path: 'file1.txt', upload_url: '/upload-session/upload-id-1', upload_id: 'upload-id-1' },
      { file_path: 'path/to/file2.md', upload_url: '/upload-session/upload-id-2', upload_id: 'upload-id-2' },
    ];

    const mockInitiateResponse: UploadInitiateResponseData = {
      status: 'success',
      message: 'Upload initiated',
      completion_token: 'test-completion-token',
      files: mockUploadURLs,
    };

    const mockCompletePayload: UploadCompleteRequestPayload = {
      completion_token: 'test-completion-token',
    };

    const mockCompleteResponse: UploadCompleteResponseData = {
      status: 'success',
      message: 'Files saved successfully',
      commit_id: 'multi-commit-sha456',
    };

    beforeEach(() => {
      // Ensure client is authenticated
      client.setToken('test-savefiles-token');
    });

    it('should successfully perform a multi-part upload', async () => {
      // Mock /initiate call (uses client.post -> client.request)
      mockRequest
        .mockResolvedValueOnce({ data: mockInitiateResponse }); // For initiate POST

      // Mock individual file PUT uploads (uses client.put -> client.request)
      // Two files, so two PUT calls
      mockRequest.mockResolvedValueOnce({ status: 200, data: { message: 'upload 1 ok'} }); // For file1.txt PUT
      mockRequest.mockResolvedValueOnce({ status: 200, data: { message: 'upload 2 ok'} }); // For file2.md PUT

      // Mock /complete call (uses client.post -> client.request)
      mockRequest.mockResolvedValueOnce({ data: mockCompleteResponse }); // For complete POST

      const result = await client.saveFiles(repoId, inputFiles, commitMessage);

      // Verify /initiate call
      expect(mockRequest).toHaveBeenNthCalledWith(1, {
        method: 'POST',
        url: `/repositories/${repoId}/save/initiate`,
        data: mockInitiatePayload,
      });

      // Verify PUT calls for file uploads
      // Order of Promise.all execution isn't strictly guaranteed for map,
      // so check for both calls regardless of order if necessary, or ensure mock setup matches expected call order.
      // For simplicity here, assuming they are called in order of mockRequest setup.
      expect(mockRequest).toHaveBeenNthCalledWith(2, {
        method: 'PUT',
        url: mockUploadURLs[0].upload_url, // /upload-session/upload-id-1
        data: inputFiles[0].content,
        headers: { 'Content-Type': 'application/octet-stream' },
      });
      expect(mockRequest).toHaveBeenNthCalledWith(3, {
        method: 'PUT',
        url: mockUploadURLs[1].upload_url, // /upload-session/upload-id-2
        data: inputFiles[1].content,
        headers: { 'Content-Type': 'application/octet-stream' },
      });

      // Verify /complete call
      expect(mockRequest).toHaveBeenNthCalledWith(4, {
        method: 'POST',
        url: `/repositories/${repoId}/save/complete`,
        data: mockCompletePayload,
      });

      expect(result).toEqual(mockCompleteResponse);
    });

    it('should throw an error if /initiate call fails', async () => {
      const initiateError = new Error('Initiate failed');
      mockRequest.mockRejectedValueOnce(initiateError); // For initiate POST

      await expect(client.saveFiles(repoId, inputFiles, commitMessage)).rejects.toThrow('Initiate failed');
      expect(mockRequest).toHaveBeenCalledTimes(1); // Only initiate should be called
    });

    it('should throw an error if any file upload (PUT) fails', async () => {
      mockRequest.mockResolvedValueOnce({ data: mockInitiateResponse }); // Initiate POST succeeds

      const uploadError = new Error('Upload failed for file1.txt');
      mockRequest.mockRejectedValueOnce(uploadError); // First PUT fails
      // No need to mock the second PUT if the first one throws and Promise.all rejects

      await expect(client.saveFiles(repoId, inputFiles, commitMessage)).rejects.toThrow('Upload failed for file1.txt');

      expect(mockRequest).toHaveBeenCalledTimes(3); // Initiate + 1st PUT
      // (Could be 3 if Promise.all allows other promises to start, but one rejection is enough)
    });

    it('should throw an error if /complete call fails', async () => {
      mockRequest.mockResolvedValueOnce({ data: mockInitiateResponse }); // Initiate POST
      mockRequest.mockResolvedValueOnce({ status: 200 }); // File 1 PUT
      mockRequest.mockResolvedValueOnce({ status: 200 }); // File 2 PUT

      const completeError = new Error('Complete failed');
      mockRequest.mockRejectedValueOnce(completeError); // Complete POST fails

      await expect(client.saveFiles(repoId, inputFiles, commitMessage)).rejects.toThrow('Complete failed');
      expect(mockRequest).toHaveBeenCalledTimes(4); // Initiate + 2 PUTs + Complete
    });

    it('should throw an error if initiate response is invalid (no token)', async () => {
        const invalidInitiateResponse = { ...mockInitiateResponse, completion_token: '' };
        mockRequest.mockResolvedValueOnce({ data: invalidInitiateResponse });

        await expect(client.saveFiles(repoId, inputFiles, commitMessage)).rejects.toThrow('Invalid response from initiate upload endpoint.');
        expect(mockRequest).toHaveBeenCalledTimes(1);
    });

    it('should throw an error if file data is not found for an upload instruction', async () => {
        const modifiedUploadURLs = [
            { file_path: 'nonexistent.txt', upload_url: '/upload-session/upload-id-x', upload_id: 'upload-id-x' }
        ];
        const initiateResponseWithBadFile = { ...mockInitiateResponse, files: modifiedUploadURLs };
        mockRequest.mockResolvedValueOnce({ data: initiateResponseWithBadFile }); // Initiate succeeds

        await expect(client.saveFiles(repoId, inputFiles, commitMessage)).rejects.toThrow('File data not found for path: nonexistent.txt');
        expect(mockRequest).toHaveBeenCalledTimes(1); // Only initiate call
    });
  });

  // New tests for methods added in Task 8.1
  describe('initializeRepository', () => {
    beforeEach(() => {
      client.setToken('test-init-repo-token');
    });

    it('should initialize a repository with a project name', async () => {
      const payload: import('../src/types').RepositoryCreateRequest = { project_name: 'new-project' };
      const mockResponse: import('../src/types').RepositoryCreateResponse = {
        status: 'created',
        message: 'Repository created',
        repository_id: 'new-project',
        path: '/path/to/new-project',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.initializeRepository(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/repositories',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should initialize a repository without a project name (API generates ID)', async () => {
        const mockResponse: import('../src/types').RepositoryCreateResponse = {
          status: 'created',
          message: 'Repository created with generated ID',
          repository_id: 'uuid-generated-id',
          path: '/path/to/uuid-generated-id',
        };
        mockRequest.mockResolvedValueOnce({ data: mockResponse });

        const result = await client.initializeRepository(); // No payload

        expect(mockRequest).toHaveBeenCalledWith({
          method: 'POST',
          url: '/repository/repositories',
          data: undefined, // Or expect not to have data field if client.post handles undefined data correctly
        });
        expect(result).toEqual(mockResponse);
      });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.initializeRepository({ project_name: 'fail-project' })).rejects.toThrow('API Error');
    });
  });

  describe('createBranch', () => {
    beforeEach(() => {
      client.setToken('test-create-branch-token');
    });

    it('should create a new branch', async () => {
      const payload: import('../src/types').BranchCreateRequest = { branch_name: 'feature/new-feature' };
      const mockResponse: import('../src/types').BranchResponse = {
        status: 'success',
        branch_name: 'feature/new-feature',
        message: 'Branch created and switched to',
        head_commit_oid: 'abcdef123',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.createBranch(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/branches',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.createBranch({ branch_name: 'fail-branch' })).rejects.toThrow('API Error');
    });
  });

  describe('switchBranch', () => {
    beforeEach(() => {
      client.setToken('test-switch-branch-token');
    });

    it('should switch to an existing branch', async () => {
      const payload: import('../src/types').BranchSwitchRequest = { branch_name: 'develop' };
      const mockResponse: import('../src/types').BranchResponse = {
        status: 'success',
        branch_name: 'develop',
        message: 'Switched to branch develop',
        head_commit_oid: 'fedcba321',
        previous_branch_name: 'main',
        is_detached: false,
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.switchBranch(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'PUT',
        url: '/repository/branch',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.switchBranch({ branch_name: 'fail-branch' })).rejects.toThrow('API Error');
    });
  });

  describe('mergeBranch', () => {
    beforeEach(() => {
      client.setToken('test-merge-branch-token');
    });

    it('should merge a branch into the current branch', async () => {
      const payload: import('../src/types').MergeBranchRequest = { source_branch: 'feature/new-feature' };
      const mockResponse: import('../src/types').MergeBranchResponse = {
        status: 'success',
        message: 'Merge successful',
        current_branch: 'develop',
        merged_branch: 'feature/new-feature',
        commit_oid: 'mergecommitsha',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.mergeBranch(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/merges',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.mergeBranch({ source_branch: 'fail-branch' })).rejects.toThrow('API Error');
    });
  });

  describe('compareRefs', () => {
    beforeEach(() => {
      client.setToken('test-compare-refs-token');
    });

    it('should compare two references', async () => {
      const params: import('../src/types').CompareRefsParams = { ref1: 'HEAD~1', ref2: 'HEAD' };
      const mockResponse: import('../src/types').CompareRefsResponse = {
        ref1_oid: 'abcdef',
        ref2_oid: '123456',
        ref1_display_name: 'HEAD~1',
        ref2_display_name: 'HEAD',
        patch_text: '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.compareRefs(params);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'GET',
        url: '/repository/compare',
        params: params,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should compare refs with default parameters (API handles defaults)', async () => {
        const mockResponse: import('../src/types').CompareRefsResponse = {
            ref1_oid: 'abcdef',
            ref2_oid: '123456',
            ref1_display_name: 'HEAD~1', // Defaulted by API
            ref2_display_name: 'HEAD',   // Defaulted by API
            patch_text: '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new',
        };
        mockRequest.mockResolvedValueOnce({ data: mockResponse });

        const result = await client.compareRefs(); // No params

        expect(mockRequest).toHaveBeenCalledWith({
            method: 'GET',
            url: '/repository/compare',
            params: undefined,
        });
        expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.compareRefs()).rejects.toThrow('API Error');
    });
  });

  describe('revertCommit', () => {
    beforeEach(() => {
      client.setToken('test-revert-commit-token');
    });

    it('should revert a commit', async () => {
      const payload: import('../src/types').RevertCommitRequest = { commit_ish: 'abcdef123' };
      const mockResponse: import('../src/types').RevertCommitResponse = {
        status: 'success',
        message: 'Commit reverted',
        new_commit_oid: 'revertcommitsha',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.revertCommit(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/revert',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.revertCommit({ commit_ish: 'fail-commit' })).rejects.toThrow('API Error');
    });
  });

  describe('syncRepository', () => {
    beforeEach(() => {
      client.setToken('test-sync-repo-token');
    });

    it('should sync the repository', async () => {
      const payload: import('../src/types').SyncRepositoryRequest = { remote_name: 'origin', branch_name: 'main', push: true };
      const mockResponse: import('../src/types').SyncRepositoryResponse = {
        status: 'success',
        branch_synced: 'main',
        remote: 'origin',
        fetch_status: { message: 'Fetched successfully', received_objects: 10, total_objects: 10 },
        local_update_status: { type: 'fast-forward', message: 'Updated successfully', commit_oid: 'newheadsha', conflicting_files: [] },
        push_status: { pushed: true, message: 'Pushed successfully' },
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.syncRepository(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/sync',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.syncRepository({ remote_name: 'origin' })).rejects.toThrow('API Error');
    });
  });

  describe('createTag', () => {
    beforeEach(() => {
      client.setToken('test-create-tag-token');
    });

    it('should create a new tag', async () => {
      const payload: import('../src/types').TagCreateRequest = { tag_name: 'v1.0.0', message: 'Version 1.0.0' };
      const mockResponse: import('../src/types').TagCreateResponse = {
        status: 'success',
        tag_name: 'v1.0.0',
        tag_type: 'annotated',
        target_commit_oid: 'tagtargetsha',
        message: 'Tag created',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.createTag(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/tags',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.createTag({ tag_name: 'fail-tag' })).rejects.toThrow('API Error');
    });
  });

  describe('listIgnorePatterns', () => {
    beforeEach(() => {
      client.setToken('test-list-ignore-token');
    });

    it('should list .gitignore patterns', async () => {
      const mockResponse: import('../src/types').IgnoreListResponse = {
        status: 'success',
        patterns: ['*.log', 'node_modules/'],
        message: 'Patterns listed',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.listIgnorePatterns();

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'GET',
        url: '/repository/ignore',
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.listIgnorePatterns()).rejects.toThrow('API Error');
    });
  });

  describe('addIgnorePattern', () => {
    beforeEach(() => {
      client.setToken('test-add-ignore-token');
    });

    it('should add a pattern to .gitignore', async () => {
      const payload: import('../src/types').IgnorePatternRequest = { pattern: '*.tmp' };
      const mockResponse: import('../src/types').IgnoreAddResponse = {
        status: 'success',
        message: 'Pattern added',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.addIgnorePattern(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/ignore',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.addIgnorePattern({ pattern: '*.fail' })).rejects.toThrow('API Error');
    });
  });

  describe('reviewBranch', () => {
    beforeEach(() => {
      client.setToken('test-review-branch-token');
    });

    it('should review a branch with limit', async () => {
      const branchName = 'feature/xyz';
      const params: import('../src/types').ReviewBranchParams = { limit: 5 };
      const mockResponse: import('../src/types').BranchReviewResponse = {
        status: 'success',
        branch_name: branchName,
        commits: [{ short_hash: 'abc', author_name: 'tester', date: '2023-01-01', message_short: 'feat: new thing', oid: 'abcdef123' }],
        message: 'Commits reviewed',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.reviewBranch(branchName, params);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'GET',
        url: `/repository/review/${branchName}`,
        params: params,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should review a branch without limit', async () => {
        const branchName = 'feature/xyz';
        const mockResponse: import('../src/types').BranchReviewResponse = {
          status: 'success',
          branch_name: branchName,
          commits: [{ short_hash: 'abc', author_name: 'tester', date: '2023-01-01', message_short: 'feat: new thing', oid: 'abcdef123' }],
          message: 'Commits reviewed',
        };
        mockRequest.mockResolvedValueOnce({ data: mockResponse });

        const result = await client.reviewBranch(branchName); // No params

        expect(mockRequest).toHaveBeenCalledWith({
          method: 'GET',
          url: `/repository/review/${branchName}`,
          params: undefined,
        });
        expect(result).toEqual(mockResponse);
      });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.reviewBranch('fail-branch')).rejects.toThrow('API Error');
    });
  });

  describe('cherryPickCommit', () => {
    beforeEach(() => {
      client.setToken('test-cherry-pick-token');
    });

    it('should cherry-pick a commit', async () => {
      const payload: import('../src/types').CherryPickRequest = { commit_id: 'pickmesha' };
      const mockResponse: import('../src/types').CherryPickResponse = {
        status: 'success',
        message: 'Commit cherry-picked',
        new_commit_oid: 'newcherrysha',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.cherryPickCommit(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/cherry-pick',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.cherryPickCommit({ commit_id: 'fail-commit' })).rejects.toThrow('API Error');
    });
  });

  describe('exportToEPUB', () => {
    beforeEach(() => {
      client.setToken('test-export-epub-token');
    });

    it('should export to EPUB', async () => {
      const payload: import('../src/types').EPUBExportRequest = {
        file_list: ['chapter1.md', 'chapter2.md'],
        output_filename: 'mybook.epub',
      };
      const mockResponse: import('../src/types').EPUBExportResponse = {
        status: 'success',
        message: 'EPUB exported successfully',
        server_file_path: '/path/to/exports/uuid/mybook.epub',
      };
      mockRequest.mockResolvedValueOnce({ data: mockResponse });

      const result = await client.exportToEPUB(payload);

      expect(mockRequest).toHaveBeenCalledWith({
        method: 'POST',
        url: '/repository/export/epub',
        data: payload,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if API call fails', async () => {
      const error = new Error('API Error');
      mockRequest.mockRejectedValueOnce(error);
      await expect(client.exportToEPUB({ file_list: ['fail.md'] })).rejects.toThrow('API Error');
    });
  });
});
