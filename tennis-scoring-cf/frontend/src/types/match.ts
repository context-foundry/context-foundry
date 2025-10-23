// Match-related type definitions

export type MatchStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
export type MatchType = 'singles' | 'doubles';
export type MatchFormat = 'best_of_3' | 'best_of_5';

export interface Match {
  id: number;
  createdBy: number;
  player1Name: string;
  player2Name: string;
  player3Name?: string;
  player4Name?: string;
  matchType: MatchType;
  format: MatchFormat;
  status: MatchStatus;
  winner?: 1 | 2;
  location?: string;
  scheduledAt?: string;
  startedAt?: string;
  completedAt?: string;
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

export interface Set {
  id: number;
  matchId: number;
  setNumber: number;
  player1Games: number;
  player2Games: number;
  tiebreakScore?: {
    player1: number;
    player2: number;
  };
  winner?: 1 | 2;
  completedAt?: string;
}

export interface Game {
  id: number;
  setId: number;
  gameNumber: number;
  server: 1 | 2;
  player1Points: number;
  player2Points: number;
  winner?: 1 | 2;
  completedAt?: string;
}

export interface Point {
  id: number;
  gameId: number;
  pointNumber: number;
  winner: 1 | 2;
  scoreAfter: string;
  createdAt: string;
}

export interface MatchDetail extends Match {
  sets: Set[];
  currentSet?: Set;
  currentGame?: Game;
}

export interface CreateMatchData {
  player1Name: string;
  player2Name: string;
  player3Name?: string;
  player4Name?: string;
  matchType: MatchType;
  format: MatchFormat;
  location?: string;
  scheduledAt?: string;
}

export interface UpdateMatchData {
  location?: string;
  scheduledAt?: string;
  status?: MatchStatus;
}

export interface MatchFiltersType {
  status?: MatchStatus;
  search?: string;
  date?: string;
  page?: number;
  limit?: number;
}

export interface MatchListResponse {
  matches: Match[];
  total: number;
  page: number;
  limit: number;
}

export interface ScoreUpdate {
  match: Match;
  currentSet: Set;
  currentGame: Game;
  score: string;
}
