import pool from '../database/pool';
import { Match, CreateMatchDTO, UpdateMatchDTO } from '../types/match.types';

export class MatchModel {
  /**
   * Create a new match
   */
  static async create(userId: number, matchData: CreateMatchDTO): Promise<Match> {
    const query = `
      INSERT INTO matches (
        created_by, player1_name, player2_name, player3_name, player4_name,
        match_type, format, location, scheduled_at
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING *
    `;

    const values = [
      userId,
      matchData.player1Name,
      matchData.player2Name,
      matchData.player3Name || null,
      matchData.player4Name || null,
      matchData.matchType,
      matchData.format,
      matchData.location || null,
      matchData.scheduledAt || null,
    ];

    const result = await pool.query(query, values);
    return result.rows[0];
  }

  /**
   * Find match by ID
   */
  static async findById(id: number): Promise<Match | null> {
    const query = 'SELECT * FROM matches WHERE id = $1';
    const result = await pool.query(query, [id]);
    return result.rows[0] || null;
  }

  /**
   * Find all matches with filters
   */
  static async findAll(filters: {
    status?: string;
    page?: number;
    limit?: number;
    search?: string;
    date?: string;
  }): Promise<{ matches: Match[]; total: number }> {
    const conditions: string[] = [];
    const values: any[] = [];
    let paramCount = 1;

    if (filters.status) {
      conditions.push(`status = $${paramCount}`);
      values.push(filters.status);
      paramCount++;
    }

    if (filters.search) {
      conditions.push(`(
        player1_name ILIKE $${paramCount} OR
        player2_name ILIKE $${paramCount} OR
        player3_name ILIKE $${paramCount} OR
        player4_name ILIKE $${paramCount}
      )`);
      values.push(`%${filters.search}%`);
      paramCount++;
    }

    if (filters.date) {
      conditions.push(`DATE(scheduled_at) = $${paramCount}`);
      values.push(filters.date);
      paramCount++;
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    // Count total
    const countQuery = `SELECT COUNT(*) FROM matches ${whereClause}`;
    const countResult = await pool.query(countQuery, values);
    const total = parseInt(countResult.rows[0].count);

    // Get matches with pagination
    const page = filters.page || 1;
    const limit = filters.limit || 20;
    const offset = (page - 1) * limit;

    const query = `
      SELECT * FROM matches
      ${whereClause}
      ORDER BY scheduled_at DESC, created_at DESC
      LIMIT $${paramCount} OFFSET $${paramCount + 1}
    `;

    values.push(limit, offset);
    const result = await pool.query(query, values);

    return {
      matches: result.rows,
      total,
    };
  }

  /**
   * Update match
   */
  static async update(id: number, updates: UpdateMatchDTO): Promise<Match | null> {
    const fields: string[] = [];
    const values: any[] = [];
    let paramCount = 1;

    Object.entries(updates).forEach(([key, value]) => {
      if (value !== undefined) {
        fields.push(`${key} = $${paramCount}`);
        values.push(value);
        paramCount++;
      }
    });

    if (fields.length === 0) {
      return this.findById(id);
    }

    values.push(id);
    const query = `
      UPDATE matches
      SET ${fields.join(', ')}
      WHERE id = $${paramCount}
      RETURNING *
    `;

    const result = await pool.query(query, values);
    return result.rows[0] || null;
  }

  /**
   * Delete match
   */
  static async delete(id: number): Promise<boolean> {
    const query = 'DELETE FROM matches WHERE id = $1';
    const result = await pool.query(query, [id]);
    return result.rowCount !== null && result.rowCount > 0;
  }

  /**
   * Start match
   */
  static async start(id: number): Promise<Match | null> {
    const query = `
      UPDATE matches
      SET status = 'in_progress', started_at = CURRENT_TIMESTAMP
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id]);
    return result.rows[0] || null;
  }

  /**
   * Complete match
   */
  static async complete(id: number, winner: 1 | 2): Promise<Match | null> {
    const query = `
      UPDATE matches
      SET status = 'completed', completed_at = CURRENT_TIMESTAMP, winner = $2
      WHERE id = $1
      RETURNING *
    `;
    const result = await pool.query(query, [id, winner]);
    return result.rows[0] || null;
  }
}
