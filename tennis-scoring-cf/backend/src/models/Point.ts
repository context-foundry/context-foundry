import pool from '../database/pool';
import { Point } from '../types/match.types';

export class PointModel {
  /**
   * Create a new point
   */
  static async create(
    gameId: number,
    pointNumber: number,
    winner: 1 | 2,
    scoreAfter: string
  ): Promise<Point> {
    const query = `
      INSERT INTO points (game_id, point_number, winner, score_after)
      VALUES ($1, $2, $3, $4)
      RETURNING *
    `;
    const result = await pool.query(query, [gameId, pointNumber, winner, scoreAfter]);
    return result.rows[0];
  }

  /**
   * Find points by game ID
   */
  static async findByGameId(gameId: number): Promise<Point[]> {
    const query = 'SELECT * FROM points WHERE game_id = $1 ORDER BY point_number';
    const result = await pool.query(query, [gameId]);
    return result.rows;
  }

  /**
   * Get all points for a match (including set and game info)
   */
  static async findByMatchId(matchId: number): Promise<any[]> {
    const query = `
      SELECT p.*, g.game_number, g.set_id, s.set_number, s.match_id
      FROM points p
      JOIN games g ON p.game_id = g.id
      JOIN sets s ON g.set_id = s.id
      WHERE s.match_id = $1
      ORDER BY s.set_number, g.game_number, p.point_number
    `;
    const result = await pool.query(query, [matchId]);
    return result.rows;
  }
}
