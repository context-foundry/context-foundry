import { MatchModel } from '../models/Match';
import { SetModel } from '../models/Set';
import { GameModel } from '../models/Game';
import { PointModel } from '../models/Point';
import { CreateMatchDTO, UpdateMatchDTO, Match, MatchWithDetails } from '../types/match.types';
import * as scoringService from './scoring.service';

/**
 * Create a new match
 */
export async function createMatch(userId: number, matchData: CreateMatchDTO): Promise<Match> {
  return await MatchModel.create(userId, matchData);
}

/**
 * Get match by ID with full details
 */
export async function getMatchById(id: number): Promise<MatchWithDetails | null> {
  const match = await MatchModel.findById(id);
  if (!match) {
    return null;
  }

  const sets = await SetModel.findByMatchId(id);
  const currentSet = await SetModel.getCurrentSet(id);
  const currentGame = currentSet ? await GameModel.getCurrentGame(currentSet.id) : null;

  return {
    ...match,
    sets,
    currentSet: currentSet || undefined,
    currentGame: currentGame || undefined,
  };
}

/**
 * Get all matches with filters
 */
export async function getAllMatches(filters: {
  status?: string;
  page?: number;
  limit?: number;
  search?: string;
  date?: string;
}): Promise<{ matches: Match[]; total: number; page: number; limit: number }> {
  const result = await MatchModel.findAll(filters);
  return {
    ...result,
    page: filters.page || 1,
    limit: filters.limit || 20,
  };
}

/**
 * Update match
 */
export async function updateMatch(
  id: number,
  userId: number,
  updates: UpdateMatchDTO
): Promise<Match | null> {
  // Verify ownership
  const match = await MatchModel.findById(id);
  if (!match) {
    return null;
  }

  if (match.created_by !== userId) {
    throw new Error('Unauthorized: You can only update your own matches');
  }

  return await MatchModel.update(id, updates);
}

/**
 * Delete match
 */
export async function deleteMatch(id: number, userId: number): Promise<boolean> {
  // Verify ownership
  const match = await MatchModel.findById(id);
  if (!match) {
    return false;
  }

  if (match.created_by !== userId) {
    throw new Error('Unauthorized: You can only delete your own matches');
  }

  return await MatchModel.delete(id);
}

/**
 * Start match
 */
export async function startMatch(id: number, userId: number): Promise<Match> {
  // Verify ownership
  const match = await MatchModel.findById(id);
  if (!match) {
    throw new Error('Match not found');
  }

  if (match.created_by !== userId) {
    throw new Error('Unauthorized: You can only start your own matches');
  }

  if (match.status !== 'scheduled') {
    throw new Error('Match has already been started or completed');
  }

  // Start match and create first set
  const updatedMatch = await MatchModel.start(id);
  if (!updatedMatch) {
    throw new Error('Failed to start match');
  }

  // Create first set and first game
  await scoringService.startNewSet(id, 1);

  return updatedMatch;
}

/**
 * Record a point
 */
export async function recordPoint(
  matchId: number,
  userId: number,
  winner: 1 | 2
): Promise<{
  match: Match;
  currentSet: any;
  currentGame: any;
  score: string;
  events: string[];
}> {
  // Verify ownership
  const match = await MatchModel.findById(matchId);
  if (!match) {
    throw new Error('Match not found');
  }

  if (match.created_by !== userId) {
    throw new Error('Unauthorized: You can only record points for your own matches');
  }

  if (match.status !== 'in_progress') {
    throw new Error('Match is not in progress');
  }

  const events: string[] = [];

  // Get current game
  let currentSet = await SetModel.getCurrentSet(matchId);
  if (!currentSet) {
    throw new Error('No active set found');
  }

  let currentGame = await GameModel.getCurrentGame(currentSet.id);
  if (!currentGame) {
    throw new Error('No active game found');
  }

  // Record point
  const pointResult = await scoringService.recordPoint(currentGame, winner);
  currentGame = pointResult.updatedGame;
  let score = pointResult.score;
  events.push(`Point won by player ${winner}: ${score}`);

  // Check if game is complete
  if (pointResult.gameComplete && pointResult.gameWinner) {
    events.push(`Game won by player ${pointResult.gameWinner}`);

    // Complete game and check set
    const gameResult = await scoringService.completeGame(currentSet, pointResult.gameWinner);
    currentSet = gameResult.updatedSet;
    events.push(`Set score: ${gameResult.score}`);

    // Check if tiebreak is required
    if (gameResult.tiebreakRequired) {
      events.push('Tiebreak required at 6-6');
      // Create tiebreak "game"
      currentGame = await scoringService.startNewGame(currentSet.id);
    }
    // Check if set is complete
    else if (gameResult.setComplete && gameResult.setWinner) {
      events.push(`Set won by player ${gameResult.setWinner}`);

      // Check if match is complete
      const matchResult = await scoringService.checkMatchCompletion(match);

      if (matchResult.matchComplete && matchResult.matchWinner) {
        events.push(`Match won by player ${matchResult.matchWinner}`);
        return {
          match: await MatchModel.findById(matchId) as Match,
          currentSet: null,
          currentGame: null,
          score: gameResult.score,
          events,
        };
      } else {
        // Start new set
        const sets = await SetModel.findByMatchId(matchId);
        const newSetNumber = sets.length + 1;
        currentSet = await scoringService.startNewSet(matchId, newSetNumber);
        currentGame = await GameModel.getCurrentGame(currentSet.id);
        events.push(`Starting set ${newSetNumber}`);
      }
    } else {
      // Start new game
      currentGame = await scoringService.startNewGame(currentSet.id);
    }
  }

  return {
    match: await MatchModel.findById(matchId) as Match,
    currentSet,
    currentGame,
    score,
    events,
  };
}

/**
 * Get match history (all points, games, sets)
 */
export async function getMatchHistory(matchId: number) {
  const match = await MatchModel.findById(matchId);
  if (!match) {
    throw new Error('Match not found');
  }

  const sets = await SetModel.findByMatchId(matchId);
  const games = await Promise.all(
    sets.map(async (set) => ({
      set,
      games: await GameModel.findBySetId(set.id),
    }))
  );
  const points = await PointModel.findByMatchId(matchId);

  return {
    match,
    sets,
    games,
    points,
  };
}
