import axios from 'axios';
import { GitWriteClient, LoginCredentials, TokenResponse } from '../src/apiClient';
import {
  RepositoryBranchesResponse,
  RepositoryTagsResponse,
  RepositoryCommitsResponse,
  CommitDetail,
  ListCommitsParams,
} from '../src/types'; // Import new types for testing

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
  });
});
