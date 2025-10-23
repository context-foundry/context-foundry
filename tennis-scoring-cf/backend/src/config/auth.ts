import dotenv from 'dotenv';

dotenv.config();

export const authConfig = {
  jwtAccessSecret: process.env.JWT_ACCESS_SECRET || 'your-super-secret-access-token-key',
  jwtRefreshSecret: process.env.JWT_REFRESH_SECRET || 'your-super-secret-refresh-token-key',
  jwtAccessExpiry: process.env.JWT_ACCESS_EXPIRY || '15m',
  jwtRefreshExpiry: process.env.JWT_REFRESH_EXPIRY || '7d',
  bcryptSaltRounds: 12,
  issuer: 'tennis-scoring-app',
  audience: 'tennis-users',
};

export default authConfig;
