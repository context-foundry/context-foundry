export interface User {
  id: number;
  email: string;
  password_hash: string;
  role: 'coach' | 'viewer' | 'admin';
  first_name?: string;
  last_name?: string;
  school_name?: string;
  created_at: Date;
  updated_at: Date;
}

export interface RegisterDTO {
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  role: 'coach' | 'viewer';
  schoolName?: string;
}

export interface LoginDTO {
  email: string;
  password: string;
}

export interface TokenPayload {
  userId: number;
  email: string;
  role: string;
}

export interface AuthResponse {
  user: Omit<User, 'password_hash'>;
  accessToken: string;
  refreshToken: string;
}
