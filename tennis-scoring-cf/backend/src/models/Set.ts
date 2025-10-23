import pool from '../database/pool';
import { Set } from '../types/match.types';

export class SetModel {
  /**
   * Create a new set
   */
  static async create(matchId: number, setNumber: number, server: 1 | 2): Promise<Set> {
    const query = `
      INSERT INTO sets (match_id, set_number, player1_games, player2_games)
      VALUES ($1, $2, 0, 0)
      RETURNING *
    `;
    const result = await pool.query(query, [matchId, setNumber]);
    return result.rows[0];
  }

  /**
   * Find set by ID
   */
  static async findById(id: number): Promise<Set | null> {
    const query = 'SELECT * FROM sets WHERE id = $1';
    const result = await pool.query(query, [id]);
    return result.rows[0] || null;
  }

  /**
   * Find sets by match ID
   */
  static async findByMatchId(matchId: number): Promise<Set[]> {
    const query = 'SELECT * FROM sets WHERE match_id = $1 ORDER BY set_number';
    const result = await pool.query(query, [matchId]);
    return result.rows;
  }

  /**
   * Get current set for match
   */
  static async getCurrentSet(matchId: number): Promise<Set | null> {
    const query = `
      SELECT * FROM sets
      WHERE match_id = $1 AND winner IS NULL
      ORDER BY set_number DESC
      LIMIT 1
    `;
    const result = await pool.query(query, [matchId]);
    return result.rows[0] || null;
  }

  /**
   * Update set games
   */
  static async updateGames(
    id: number,
    player1Games: number,
    player2Games: number
  ): Promise<Set | null> {
    const query = `
      UPDATE sets
      SET player1_games = $2, player2_games = $3
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id, player1Games, player2Games]);
    return result.rows[0] || null;
  }

  /**
   * Complete set
   */
  static async complete(id: number, winner: 1 | 2, tiebreakScore?: any): Promise<Set | null> {
    const query = `
      UPDATE sets
      SET winner = $2, tiebreak_score = $3, completed_at = CURRENT_TIMESTAMP
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id, winner, tiebreakScore || null]);
    return result.rows[0] || null;
  }
}
