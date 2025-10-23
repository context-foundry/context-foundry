import { Request, Response, NextFunction } from 'express';
import { verifyAccessToken } from '../utils/jwt.util';
import { sendError } from '../utils/response.util';

/**
 * Authentication middleware - Verify JWT token
 */
export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  try {
    // Get token from Authorization header
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      sendError(res, 'NO_TOKEN', 'No authorization token provided', 401);
      return;
    }

    const token = authHeader.substring(7); // Remove 'Bearer ' prefix

    // Verify token
    const payload = verifyAccessToken(token);

    // Attach user to request (with type assertion)
    (req as any).user = {
      userId: payload.userId,
      email: payload.email,
      role: payload.role,
    };

    next();
  } catch (error: any) {
    if (error.name === 'TokenExpiredError') {
      sendError(res, 'TOKEN_EXPIRED', 'Token has expired', 401);
    } else if (error.name === 'JsonWebTokenError') {
      sendError(res, 'INVALID_TOKEN', 'Invalid token', 401);
    } else {
      sendError(res, 'AUTHENTICATION_ERROR', 'Authentication failed', 401);
    }
  }
}

/**
 * Optional authentication middleware - Attach user if token exists
 */
export function optionalAuthMiddleware(req: Request, res: Response, next: NextFunction): void {
  try {
    const authHeader = req.headers.authorization;

    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const payload = verifyAccessToken(token);

      (req as any).user = {
        userId: payload.userId,
        email: payload.email,
        role: payload.role,
      };
    }
  } catch (error) {
    // Ignore errors for optional auth
  }

  next();
}
