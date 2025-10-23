import { Request, Response } from 'express';
import * as authService from '../services/auth.service';
import { sendSuccess, sendError } from '../utils/response.util';

/**
 * Register a new user
 */
export async function register(req: Request, res: Response): Promise<void> {
  try {
    const result = await authService.registerUser(req.body);
    sendSuccess(res, result, 'User registered successfully', 201);
  } catch (error: any) {
    if (error.message.includes('already exists')) {
      sendError(res, 'USER_EXISTS', error.message, 409);
    } else {
      sendError(res, 'REGISTRATION_ERROR', error.message, 500);
    }
  }
}

/**
 * Login user
 */
export async function login(req: Request, res: Response): Promise<void> {
  try {
    const result = await authService.loginUser(req.body);
    sendSuccess(res, result, 'Login successful');
  } catch (error: any) {
    if (error.message.includes('Invalid')) {
      sendError(res, 'INVALID_CREDENTIALS', error.message, 401);
    } else {
      sendError(res, 'LOGIN_ERROR', error.message, 500);
    }
  }
}

/**
 * Refresh access token
 */
export async function refresh(req: Request, res: Response): Promise<void> {
  try {
    const { refreshToken } = req.body;
    const result = await authService.refreshAccessToken(refreshToken);
    sendSuccess(res, result, 'Token refreshed successfully');
  } catch (error: any) {
    sendError(res, 'REFRESH_ERROR', error.message, 401);
  }
}

/**
 * Logout user
 */
export async function logout(req: Request, res: Response): Promise<void> {
  try {
    // In a production app, you might want to blacklist the token here
    sendSuccess(res, null, 'Logout successful');
  } catch (error: any) {
    sendError(res, 'LOGOUT_ERROR', error.message, 500);
  }
}

/**
 * Get current user profile
 */
export async function me(req: Request, res: Response): Promise<void> {
  try {
    const reqWithUser = req as Request & { user?: { userId: number; email: string; role: string } };
    if (!reqWithUser.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const user = await authService.getUserProfile(reqWithUser.user.userId);
    sendSuccess(res, { user }, 'User profile retrieved successfully');
  } catch (error: any) {
    sendError(res, 'PROFILE_ERROR', error.message, 500);
  }
}
