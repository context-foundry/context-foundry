import pool from '../database/pool';
import { Game } from '../types/match.types';

export class GameModel {
  /**
   * Create a new game
   */
  static async create(setId: number, gameNumber: number, server: 1 | 2): Promise<Game> {
    const query = `
      INSERT INTO games (set_id, game_number, server, player1_points, player2_points)
      VALUES ($1, $2, $3, 0, 0)
      RETURNING *
    `;
    const result = await pool.query(query, [setId, gameNumber, server]);
    return result.rows[0];
  }

  /**
   * Find game by ID
   */
  static async findById(id: number): Promise<Game | null> {
    const query = 'SELECT * FROM games WHERE id = $1';
    const result = await pool.query(query, [id]);
    return result.rows[0] || null;
  }

  /**
   * Find games by set ID
   */
  static async findBySetId(setId: number): Promise<Game[]> {
    const query = 'SELECT * FROM games WHERE set_id = $1 ORDER BY game_number';
    const result = await pool.query(query, [setId]);
    return result.rows;
  }

  /**
   * Get current game for set
   */
  static async getCurrentGame(setId: number): Promise<Game | null> {
    const query = `
      SELECT * FROM games
      WHERE set_id = $1 AND winner IS NULL
      ORDER BY game_number DESC
      LIMIT 1
    `;
    const result = await pool.query(query, [setId]);
    return result.rows[0] || null;
  }

  /**
   * Update game points
   */
  static async updatePoints(
    id: number,
    player1Points: number,
    player2Points: number
  ): Promise<Game | null> {
    const query = `
      UPDATE games
      SET player1_points = $2, player2_points = $3
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id, player1Points, player2Points]);
    return result.rows[0] || null;
  }

  /**
   * Complete game
   */
  static async complete(id: number, winner: 1 | 2): Promise<Game | null> {
    const query = `
      UPDATE games
      SET winner = $2, completed_at = CURRENT_TIMESTAMP
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id, winner]);
    return result.rows[0] || null;
  }
}
