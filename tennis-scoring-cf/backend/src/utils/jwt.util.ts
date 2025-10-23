import jwt from 'jsonwebtoken';
import { authConfig } from '../config/auth';
import { TokenPayload } from '../types/auth.types';

/**
 * Generate access token
 * @param payload - Token payload containing user information
 * @returns JWT access token
 */
export function generateAccessToken(payload: TokenPayload): string {
  return jwt.sign(payload, authConfig.jwtAccessSecret, {
    expiresIn: authConfig.jwtAccessExpiry,
    issuer: authConfig.issuer,
    audience: authConfig.audience,
  } as jwt.SignOptions);
}

/**
 * Generate refresh token
 * @param userId - User ID
 * @returns JWT refresh token
 */
export function generateRefreshToken(userId: number): string {
  return jwt.sign({ userId }, authConfig.jwtRefreshSecret, {
    expiresIn: authConfig.jwtRefreshExpiry,
    issuer: authConfig.issuer,
    audience: authConfig.audience,
  } as jwt.SignOptions);
}

/**
 * Verify access token
 * @param token - JWT token to verify
 * @returns Decoded token payload
 */
export function verifyAccessToken(token: string): TokenPayload {
  return jwt.verify(token, authConfig.jwtAccessSecret, {
    issuer: authConfig.issuer,
    audience: authConfig.audience,
  }) as TokenPayload;
}

/**
 * Verify refresh token
 * @param token - JWT refresh token to verify
 * @returns Decoded token payload
 */
export function verifyRefreshToken(token: string): { userId: number } {
  return jwt.verify(token, authConfig.jwtRefreshSecret, {
    issuer: authConfig.issuer,
    audience: authConfig.audience,
  }) as { userId: number };
}
