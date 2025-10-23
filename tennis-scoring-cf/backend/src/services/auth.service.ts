import { UserModel } from '../models/User';
import { RegisterDTO, LoginDTO, AuthResponse, User } from '../types/auth.types';
import { hashPassword, comparePassword } from '../utils/bcrypt.util';
import { generateAccessToken, generateRefreshToken, verifyRefreshToken } from '../utils/jwt.util';

/**
 * Register a new user
 */
export async function registerUser(userData: RegisterDTO): Promise<AuthResponse> {
  // Check if user already exists
  const existingUser = await UserModel.findByEmail(userData.email);
  if (existingUser) {
    throw new Error('User with this email already exists');
  }

  // Hash password
  const password_hash = await hashPassword(userData.password);

  // Create user
  const user = await UserModel.create({
    ...userData,
    password_hash,
  });

  // Generate tokens
  const accessToken = generateAccessToken({
    userId: user.id,
    email: user.email,
    role: user.role,
  });

  const refreshToken = generateRefreshToken(user.id);

  // Remove password from response
  const { password_hash: _, ...userWithoutPassword } = user;

  return {
    user: userWithoutPassword,
    accessToken,
    refreshToken,
  };
}

/**
 * Login user
 */
export async function loginUser(credentials: LoginDTO): Promise<AuthResponse> {
  // Find user
  const user = await UserModel.findByEmail(credentials.email);
  if (!user) {
    throw new Error('Invalid email or password');
  }

  // Verify password
  const isPasswordValid = await comparePassword(credentials.password, user.password_hash);
  if (!isPasswordValid) {
    throw new Error('Invalid email or password');
  }

  // Generate tokens
  const accessToken = generateAccessToken({
    userId: user.id,
    email: user.email,
    role: user.role,
  });

  const refreshToken = generateRefreshToken(user.id);

  // Remove password from response
  const { password_hash: _, ...userWithoutPassword } = user;

  return {
    user: userWithoutPassword,
    accessToken,
    refreshToken,
  };
}

/**
 * Refresh access token
 */
export async function refreshAccessToken(refreshToken: string): Promise<{ accessToken: string }> {
  try {
    // Verify refresh token
    const payload = verifyRefreshToken(refreshToken);

    // Get user
    const user = await UserModel.findById(payload.userId);
    if (!user) {
      throw new Error('User not found');
    }

    // Generate new access token
    const accessToken = generateAccessToken({
      userId: user.id,
      email: user.email,
      role: user.role,
    });

    return { accessToken };
  } catch (error) {
    throw new Error('Invalid refresh token');
  }
}

/**
 * Get user profile
 */
export async function getUserProfile(userId: number): Promise<Omit<User, 'password_hash'>> {
  const user = await UserModel.findById(userId);
  if (!user) {
    throw new Error('User not found');
  }

  const { password_hash: _, ...userWithoutPassword } = user;
  return userWithoutPassword;
}
