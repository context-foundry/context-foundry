// API client with axios

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  ApiResponse,
  LoginCredentials,
  RegisterData,
  AuthResponse,
  RefreshTokenResponse,
  User,
  Match,
  MatchDetail,
  CreateMatchData,
  UpdateMatchData,
  MatchListResponse,
  MatchFiltersType,
  ScoreUpdate
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000';

class ApiClient {
  private client: AxiosInstance;
  private refreshTokenPromise: Promise<string> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = this.getAccessToken();
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle 401 and refresh token
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // If 401 and not already retrying
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            // Refresh token
            const newAccessToken = await this.refreshAccessToken();

            // Update header and retry
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            }
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - logout user
            this.clearTokens();
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // Token management
  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('accessToken');
  }

  private getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('refreshToken');
  }

  private setTokens(accessToken: string, refreshToken: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
  }

  private clearTokens(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
  }

  // Refresh access token
  private async refreshAccessToken(): Promise<string> {
    // Prevent multiple simultaneous refresh requests
    if (this.refreshTokenPromise) {
      return this.refreshTokenPromise;
    }

    this.refreshTokenPromise = (async () => {
      try {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        const response = await axios.post<RefreshTokenResponse>(
          `${API_BASE_URL}/api/auth/refresh`,
          { refreshToken }
        );

        const { accessToken } = response.data.data;
        if (typeof window !== 'undefined') {
          localStorage.setItem('accessToken', accessToken);
        }

        return accessToken;
      } finally {
        this.refreshTokenPromise = null;
      }
    })();

    return this.refreshTokenPromise;
  }

  // Auth endpoints
  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/auth/register', data);
    const { accessToken, refreshToken, user } = response.data.data;
    this.setTokens(accessToken, refreshToken);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(user));
    }
    return response.data;
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/auth/login', credentials);
    const { accessToken, refreshToken, user } = response.data.data;
    this.setTokens(accessToken, refreshToken);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(user));
    }
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/auth/logout');
    } finally {
      this.clearTokens();
    }
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<ApiResponse<{ user: User }>>('/api/auth/me');
    return response.data.data!.user;
  }

  // Match endpoints
  async getMatches(filters?: MatchFiltersType): Promise<MatchListResponse> {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.search) params.append('search', filters.search);
    if (filters?.date) params.append('date', filters.date);
    if (filters?.page) params.append('page', filters.page.toString());
    if (filters?.limit) params.append('limit', filters.limit.toString());

    const response = await this.client.get<ApiResponse<MatchListResponse>>(
      `/api/matches?${params.toString()}`
    );
    return response.data.data!;
  }

  async getMatch(id: number): Promise<MatchDetail> {
    const response = await this.client.get<ApiResponse<MatchDetail>>(`/api/matches/${id}`);
    return response.data.data!;
  }

  async createMatch(data: CreateMatchData): Promise<Match> {
    const response = await this.client.post<ApiResponse<{ match: Match }>>('/api/matches', data);
    return response.data.data!.match;
  }

  async updateMatch(id: number, data: UpdateMatchData): Promise<Match> {
    const response = await this.client.put<ApiResponse<{ match: Match }>>(`/api/matches/${id}`, data);
    return response.data.data!.match;
  }

  async deleteMatch(id: number): Promise<void> {
    await this.client.delete(`/api/matches/${id}`);
  }

  async getMatchHistory(id: number): Promise<{ sets: any[]; games: any[]; points: any[] }> {
    const response = await this.client.get<ApiResponse<{ sets: any[]; games: any[]; points: any[] }>>(
      `/api/matches/${id}/history`
    );
    return response.data.data!;
  }

  // Score endpoints
  async startMatch(id: number): Promise<Match> {
    const response = await this.client.post<ApiResponse<{ match: Match }>>(`/api/matches/${id}/start`);
    return response.data.data!.match;
  }

  async recordPoint(id: number, winner: 1 | 2): Promise<ScoreUpdate> {
    const response = await this.client.post<ApiResponse<ScoreUpdate>>(
      `/api/matches/${id}/point`,
      { winner }
    );
    return response.data.data!;
  }

  async completeMatch(id: number): Promise<Match> {
    const response = await this.client.post<ApiResponse<{ match: Match }>>(`/api/matches/${id}/complete`);
    return response.data.data!.match;
  }

  // Health check
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    const response = await this.client.get<ApiResponse<{ status: string; timestamp: string }>>(
      '/api/health'
    );
    return response.data.data!;
  }
}

// Export singleton instance
export const api = new ApiClient();
