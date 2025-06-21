import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

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
