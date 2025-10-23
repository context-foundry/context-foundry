'use client';

import React, { createContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { User, LoginCredentials, RegisterData, AuthContextType } from '@/types/auth';

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load user from localStorage on mount
  useEffect(() => {
    const loadUser = async () => {
      try {
        const storedUser = localStorage.getItem('user');
        const accessToken = localStorage.getItem('accessToken');

        if (storedUser && accessToken) {
          // Verify token is still valid by fetching current user
          const currentUser = await api.getCurrentUser();
          setUser(currentUser);
          // Update stored user
          localStorage.setItem('user', JSON.stringify(currentUser));
        }
      } catch (error) {
        console.error('Failed to load user:', error);
        // Clear invalid tokens
        localStorage.removeItem('user');
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      try {
        const response = await api.login(credentials);
        setUser(response.data.user);
        router.push('/dashboard');
      } catch (error: any) {
        console.error('Login failed:', error);
        throw new Error(error.response?.data?.error || 'Login failed');
      }
    },
    [router]
  );

  const register = useCallback(
    async (data: RegisterData) => {
      try {
        const response = await api.register(data);
        setUser(response.data.user);
        router.push('/dashboard');
      } catch (error: any) {
        console.error('Registration failed:', error);
        throw new Error(error.response?.data?.error || 'Registration failed');
      }
    },
    [router]
  );

  const logout = useCallback(() => {
    api.logout().catch(console.error);
    setUser(null);
    router.push('/');
  }, [router]);

  const refreshToken = useCallback(async () => {
    // Token refresh is handled automatically by the API client
    // This method is here for manual refresh if needed
    try {
      const currentUser = await api.getCurrentUser();
      setUser(currentUser);
      localStorage.setItem('user', JSON.stringify(currentUser));
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
    }
  }, [logout]);

  const value: AuthContextType = {
    user,
    loading,
    login,
    register,
    logout,
    refreshToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
