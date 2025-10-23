export interface Match {
  id: number;
  created_by: number;
  player1_name: string;
  player2_name: string;
  player3_name?: string;
  player4_name?: string;
  match_type: 'singles' | 'doubles';
  format: 'best_of_3' | 'best_of_5';
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
  winner?: 1 | 2;
  location?: string;
  scheduled_at?: Date;
  started_at?: Date;
  completed_at?: Date;
  metadata?: any;
  created_at: Date;
  updated_at: Date;
}

export interface Set {
  id: number;
  match_id: number;
  set_number: number;
  player1_games: number;
  player2_games: number;
  tiebreak_score?: {
    player1: number;
    player2: number;
  };
  winner?: 1 | 2;
  completed_at?: Date;
}

export interface Game {
  id: number;
  set_id: number;
  game_number: number;
  server: 1 | 2;
  player1_points: number;
  player2_points: number;
  winner?: 1 | 2;
  completed_at?: Date;
}

export interface Point {
  id: number;
  game_id: number;
  point_number: number;
  winner: 1 | 2;
  score_after?: string;
  created_at: Date;
}

export interface CreateMatchDTO {
  player1Name: string;
  player2Name: string;
  player3Name?: string;
  player4Name?: string;
  matchType: 'singles' | 'doubles';
  format: 'best_of_3' | 'best_of_5';
  location?: string;
  scheduledAt?: Date;
}

export interface UpdateMatchDTO {
  location?: string;
  scheduledAt?: Date;
  status?: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
}

export interface RecordPointDTO {
  winner: 1 | 2;
}

export interface MatchWithDetails extends Match {
  sets?: Set[];
  currentSet?: Set;
  currentGame?: Game;
}
