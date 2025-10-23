import { Request, Response } from 'express';
import * as matchService from '../services/match.service';
import { sendSuccess, sendError } from '../utils/response.util';
import { broadcastScoreUpdate, broadcastMatchStatus } from '../services/websocket.service';

/**
 * Start a match
 */
export async function startMatch(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const matchId = parseInt(req.params.id);
    const match = await matchService.startMatch(matchId, req.user.userId);

    // Broadcast match status change
    broadcastMatchStatus(matchId, 'in_progress');

    sendSuccess(res, { match }, 'Match started successfully');
  } catch (error: any) {
    if (error.message.includes('Unauthorized')) {
      sendError(res, 'UNAUTHORIZED', error.message, 403);
    } else if (error.message.includes('not found')) {
      sendError(res, 'MATCH_NOT_FOUND', error.message, 404);
    } else {
      sendError(res, 'START_MATCH_ERROR', error.message, 400);
    }
  }
}

/**
 * Record a point
 */
export async function recordPoint(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const matchId = parseInt(req.params.id);
    const { winner } = req.body;

    const result = await matchService.recordPoint(matchId, req.user.userId, winner);

    // Broadcast score update to all connected clients
    broadcastScoreUpdate(matchId, {
      match: result.match,
      currentSet: result.currentSet,
      currentGame: result.currentGame,
      score: result.score,
      events: result.events,
    });

    sendSuccess(res, result, 'Point recorded successfully');
  } catch (error: any) {
    if (error.message.includes('Unauthorized')) {
      sendError(res, 'UNAUTHORIZED', error.message, 403);
    } else if (error.message.includes('not found')) {
      sendError(res, 'MATCH_NOT_FOUND', error.message, 404);
    } else if (error.message.includes('not in progress')) {
      sendError(res, 'INVALID_MATCH_STATUS', error.message, 400);
    } else {
      sendError(res, 'RECORD_POINT_ERROR', error.message, 500);
    }
  }
}

/**
 * Complete a match manually
 */
export async function completeMatch(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const matchId = parseInt(req.params.id);

    // Get current match details
    const matchDetails = await matchService.getMatchById(matchId);
    if (!matchDetails) {
      sendError(res, 'MATCH_NOT_FOUND', 'Match not found', 404);
      return;
    }

    if (matchDetails.created_by !== req.user.userId) {
      sendError(res, 'UNAUTHORIZED', 'You can only complete your own matches', 403);
      return;
    }

    // Broadcast match completion
    broadcastMatchStatus(matchId, 'completed');

    sendSuccess(res, { match: matchDetails }, 'Match completed successfully');
  } catch (error: any) {
    sendError(res, 'COMPLETE_MATCH_ERROR', error.message, 500);
  }
}
