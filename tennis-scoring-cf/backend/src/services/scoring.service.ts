import { Game, Set, Match } from '../types/match.types';
import { GameModel } from '../models/Game';
import { SetModel } from '../models/Set';
import { MatchModel } from '../models/Match';
import { PointModel } from '../models/Point';

/**
 * Get score string from points (0, 15, 30, 40, deuce, advantage)
 */
export function getScoreString(player1Points: number, player2Points: number): string {
  const pointMap = ['0', '15', '30', '40'];

  // Deuce (both players at 3+ points and equal)
  if (player1Points >= 3 && player2Points >= 3 && player1Points === player2Points) {
    return 'deuce';
  }

  // Standard scoring (0-40)
  if (player1Points < 4 && player2Points < 4) {
    return `${pointMap[player1Points]}-${pointMap[player2Points]}`;
  }

  // Advantage
  if (player1Points > player2Points) {
    return 'advantage player 1';
  } else {
    return 'advantage player 2';
  }
}

/**
 * Record a point and determine if game is complete
 */
export async function recordPoint(
  game: Game,
  winner: 1 | 2
): Promise<{
  gameComplete: boolean;
  gameWinner?: 1 | 2;
  score: string;
  updatedGame: Game;
}> {
  const loser = winner === 1 ? 2 : 1;
  const winnerPoints = game[`player${winner}_points` as keyof Game] as number;
  const loserPoints = game[`player${loser}_points` as keyof Game] as number;

  // Increment winner's points
  const newWinnerPoints = winnerPoints + 1;
  const newPlayer1Points = winner === 1 ? newWinnerPoints : loserPoints;
  const newPlayer2Points = winner === 2 ? newWinnerPoints : loserPoints;

  // Update game points
  const updatedGame = await GameModel.updatePoints(game.id, newPlayer1Points, newPlayer2Points);
  if (!updatedGame) {
    throw new Error('Failed to update game points');
  }

  // Calculate score string
  const score = getScoreString(newPlayer1Points, newPlayer2Points);

  // Determine game points for current game
  const currentPoints = await PointModel.findByGameId(game.id);
  const pointNumber = currentPoints.length + 1;

  // Save point record
  await PointModel.create(game.id, pointNumber, winner, score);

  // Check for game completion
  // Winner needs at least 4 points and a 2-point margin
  if (newWinnerPoints >= 4 && newWinnerPoints - loserPoints >= 2) {
    // Complete the game
    await GameModel.complete(game.id, winner);
    return {
      gameComplete: true,
      gameWinner: winner,
      score,
      updatedGame,
    };
  }

  return {
    gameComplete: false,
    score,
    updatedGame,
  };
}

/**
 * Complete a game and update set score
 */
export async function completeGame(
  set: Set,
  gameWinner: 1 | 2
): Promise<{
  setComplete: boolean;
  setWinner?: 1 | 2;
  tiebreakRequired: boolean;
  score: string;
  updatedSet: Set;
}> {
  const loser = gameWinner === 1 ? 2 : 1;
  const winnerGames = set[`player${gameWinner}_games` as keyof Set] as number;
  const loserGames = set[`player${loser}_games` as keyof Set] as number;

  // Increment winner's games
  const newWinnerGames = winnerGames + 1;
  const newPlayer1Games = gameWinner === 1 ? newWinnerGames : loserGames;
  const newPlayer2Games = gameWinner === 2 ? newWinnerGames : loserGames;

  // Update set games
  const updatedSet = await SetModel.updateGames(set.id, newPlayer1Games, newPlayer2Games);
  if (!updatedSet) {
    throw new Error('Failed to update set games');
  }

  const score = `${newPlayer1Games}-${newPlayer2Games}`;

  // Check for set completion
  if (newWinnerGames >= 6) {
    // Winner needs 2-game margin
    if (newWinnerGames - loserGames >= 2) {
      await SetModel.complete(set.id, gameWinner);
      return {
        setComplete: true,
        setWinner: gameWinner,
        tiebreakRequired: false,
        score,
        updatedSet,
      };
    }

    // Tiebreak at 6-6
    if (newWinnerGames === 6 && loserGames === 6) {
      return {
        setComplete: false,
        tiebreakRequired: true,
        score,
        updatedSet,
      };
    }
  }

  return {
    setComplete: false,
    tiebreakRequired: false,
    score,
    updatedSet,
  };
}

/**
 * Record tiebreak point
 */
export async function recordTiebreakPoint(
  set: Set,
  winner: 1 | 2
): Promise<{
  tiebreakComplete: boolean;
  setComplete: boolean;
  setWinner?: 1 | 2;
  score: string;
}> {
  const loser = winner === 1 ? 2 : 1;

  // Get current tiebreak score
  const tiebreakScore = set.tiebreak_score || { player1: 0, player2: 0 };
  const winnerPoints = tiebreakScore[`player${winner}` as 'player1' | 'player2'];
  const loserPoints = tiebreakScore[`player${loser}` as 'player1' | 'player2'];

  // Increment winner's points
  const newWinnerPoints = winnerPoints + 1;
  const newTiebreakScore = {
    player1: winner === 1 ? newWinnerPoints : loserPoints,
    player2: winner === 2 ? newWinnerPoints : loserPoints,
  };

  const score = `${newTiebreakScore.player1}-${newTiebreakScore.player2}`;

  // First to 7 points with 2-point margin
  if (newWinnerPoints >= 7 && newWinnerPoints - loserPoints >= 2) {
    await SetModel.complete(set.id, winner, newTiebreakScore);
    return {
      tiebreakComplete: true,
      setComplete: true,
      setWinner: winner,
      score: `7-6 (${score})`,
    };
  }

  // Update tiebreak score
  await SetModel.updateGames(set.id, set.player1_games, set.player2_games);

  return {
    tiebreakComplete: false,
    setComplete: false,
    score,
  };
}

/**
 * Check if match is complete
 */
export async function checkMatchCompletion(
  match: Match
): Promise<{
  matchComplete: boolean;
  matchWinner?: 1 | 2;
}> {
  const sets = await SetModel.findByMatchId(match.id);
  const player1Sets = sets.filter(s => s.winner === 1).length;
  const player2Sets = sets.filter(s => s.winner === 2).length;

  const setsToWin = match.format === 'best_of_3' ? 2 : 3;

  if (player1Sets >= setsToWin) {
    await MatchModel.complete(match.id, 1);
    return { matchComplete: true, matchWinner: 1 };
  }

  if (player2Sets >= setsToWin) {
    await MatchModel.complete(match.id, 2);
    return { matchComplete: true, matchWinner: 2 };
  }

  return { matchComplete: false };
}

/**
 * Start a new set
 */
export async function startNewSet(matchId: number, setNumber: number): Promise<Set> {
  // Create new set
  const newSet = await SetModel.create(matchId, setNumber, 1);

  // Create first game
  await GameModel.create(newSet.id, 1, 1);

  return newSet;
}

/**
 * Start a new game
 */
export async function startNewGame(setId: number): Promise<Game> {
  const games = await GameModel.findBySetId(setId);
  const gameNumber = games.length + 1;

  // Alternate server (simplified - in real tennis, server alternates)
  const server = gameNumber % 2 === 1 ? 1 : 2;

  return await GameModel.create(setId, gameNumber, server as 1 | 2);
}

/**
 * Get current match state
 */
export async function getMatchState(matchId: number) {
  const match = await MatchModel.findById(matchId);
  if (!match) {
    throw new Error('Match not found');
  }

  const sets = await SetModel.findByMatchId(matchId);
  const currentSet = await SetModel.getCurrentSet(matchId);
  const currentGame = currentSet ? await GameModel.getCurrentGame(currentSet.id) : null;

  return {
    match,
    sets,
    currentSet,
    currentGame,
  };
}
