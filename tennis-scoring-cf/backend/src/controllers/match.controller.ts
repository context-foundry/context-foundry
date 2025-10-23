import { Request, Response } from 'express';
import * as matchService from '../services/match.service';
import { sendSuccess, sendError } from '../utils/response.util';

/**
 * Create a new match
 */
export async function createMatch(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const match = await matchService.createMatch(req.user.userId, req.body);
    sendSuccess(res, { match }, 'Match created successfully', 201);
  } catch (error: any) {
    sendError(res, 'CREATE_MATCH_ERROR', error.message, 500);
  }
}

/**
 * Get all matches
 */
export async function getAllMatches(req: Request, res: Response): Promise<void> {
  try {
    const filters = {
      status: req.query.status as string,
      page: req.query.page ? parseInt(req.query.page as string) : undefined,
      limit: req.query.limit ? parseInt(req.query.limit as string) : undefined,
      search: req.query.search as string,
      date: req.query.date as string,
    };

    const result = await matchService.getAllMatches(filters);
    sendSuccess(res, result, 'Matches retrieved successfully');
  } catch (error: any) {
    sendError(res, 'GET_MATCHES_ERROR', error.message, 500);
  }
}

/**
 * Get match by ID
 */
export async function getMatchById(req: Request, res: Response): Promise<void> {
  try {
    const matchId = parseInt(req.params.id);
    const match = await matchService.getMatchById(matchId);

    if (!match) {
      sendError(res, 'MATCH_NOT_FOUND', 'Match not found', 404);
      return;
    }

    sendSuccess(res, { match }, 'Match retrieved successfully');
  } catch (error: any) {
    sendError(res, 'GET_MATCH_ERROR', error.message, 500);
  }
}

/**
 * Update match
 */
export async function updateMatch(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const matchId = parseInt(req.params.id);
    const match = await matchService.updateMatch(matchId, req.user.userId, req.body);

    if (!match) {
      sendError(res, 'MATCH_NOT_FOUND', 'Match not found', 404);
      return;
    }

    sendSuccess(res, { match }, 'Match updated successfully');
  } catch (error: any) {
    if (error.message.includes('Unauthorized')) {
      sendError(res, 'UNAUTHORIZED', error.message, 403);
    } else {
      sendError(res, 'UPDATE_MATCH_ERROR', error.message, 500);
    }
  }
}

/**
 * Delete match
 */
export async function deleteMatch(req: Request, res: Response): Promise<void> {
  try {
    if (!req.user) {
      sendError(res, 'UNAUTHORIZED', 'Not authenticated', 401);
      return;
    }

    const matchId = parseInt(req.params.id);
    const deleted = await matchService.deleteMatch(matchId, req.user.userId);

    if (!deleted) {
      sendError(res, 'MATCH_NOT_FOUND', 'Match not found', 404);
      return;
    }

    sendSuccess(res, null, 'Match deleted successfully');
  } catch (error: any) {
    if (error.message.includes('Unauthorized')) {
      sendError(res, 'UNAUTHORIZED', error.message, 403);
    } else {
      sendError(res, 'DELETE_MATCH_ERROR', error.message, 500);
    }
  }
}

/**
 * Get match history
 */
export async function getMatchHistory(req: Request, res: Response): Promise<void> {
  try {
    const matchId = parseInt(req.params.id);
    const history = await matchService.getMatchHistory(matchId);
    sendSuccess(res, history, 'Match history retrieved successfully');
  } catch (error: any) {
    if (error.message.includes('not found')) {
      sendError(res, 'MATCH_NOT_FOUND', error.message, 404);
    } else {
      sendError(res, 'GET_HISTORY_ERROR', error.message, 500);
    }
  }
}
