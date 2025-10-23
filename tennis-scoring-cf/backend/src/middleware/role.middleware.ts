import { Request, Response, NextFunction } from 'express';
import { sendError } from '../utils/response.util';

/**
 * Role-based access control middleware
 */
export function requireRole(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    // Check if user is authenticated
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Authentication required', 401);
      return;
    }

    // Check if user has required role
    if (!allowedRoles.includes(req.user.role)) {
      sendError(
        res,
        'FORBIDDEN',
        `Access denied. Required role: ${allowedRoles.join(' or ')}`,
        403
      );
      return;
    }

    next();
  };
}

/**
 * Coach-only access
 */
export const requireCoach = requireRole('coach', 'admin');

/**
 * Admin-only access
 */
export const requireAdmin = requireRole('admin');
