import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { Match, MatchDetail, MatchFiltersType, CreateMatchData, UpdateMatchData } from '@/types/match';

export function useMatches(filters?: MatchFiltersType) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(filters?.page || 1);

  const fetchMatches = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getMatches({ ...filters, page });
      setMatches(response.matches);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch matches');
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    fetchMatches();
  }, [fetchMatches]);

  const refetch = useCallback(() => {
    fetchMatches();
  }, [fetchMatches]);

  const nextPage = useCallback(() => {
    setPage((prev) => prev + 1);
  }, []);

  const prevPage = useCallback(() => {
    setPage((prev) => Math.max(1, prev - 1));
  }, []);

  return {
    matches,
    loading,
    error,
    total,
    page,
    refetch,
    nextPage,
    prevPage,
  };
}

export function useMatch(id: number) {
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMatch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getMatch(id);
      setMatch(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch match');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchMatch();
  }, [fetchMatch]);

  const refetch = useCallback(() => {
    fetchMatch();
  }, [fetchMatch]);

  const updateMatch = useCallback(
    async (data: UpdateMatchData) => {
      try {
        const updated = await api.updateMatch(id, data);
        setMatch((prev) => (prev ? { ...prev, ...updated } : null));
        return updated;
      } catch (err: any) {
        throw new Error(err.message || 'Failed to update match');
      }
    },
    [id]
  );

  const deleteMatch = useCallback(async () => {
    try {
      await api.deleteMatch(id);
    } catch (err: any) {
      throw new Error(err.message || 'Failed to delete match');
    }
  }, [id]);

  return {
    match,
    loading,
    error,
    refetch,
    updateMatch,
    deleteMatch,
    setMatch,
  };
}

export function useCreateMatch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createMatch = useCallback(async (data: CreateMatchData) => {
    try {
      setLoading(true);
      setError(null);
      const match = await api.createMatch(data);
      return match;
    } catch (err: any) {
      setError(err.message || 'Failed to create match');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    createMatch,
    loading,
    error,
  };
}

export function useMatchScore(id: number) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startMatch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const match = await api.startMatch(id);
      return match;
    } catch (err: any) {
      setError(err.message || 'Failed to start match');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [id]);

  const recordPoint = useCallback(
    async (winner: 1 | 2) => {
      try {
        setLoading(true);
        setError(null);
        const result = await api.recordPoint(id, winner);
        return result;
      } catch (err: any) {
        setError(err.message || 'Failed to record point');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [id]
  );

  const completeMatch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const match = await api.completeMatch(id);
      return match;
    } catch (err: any) {
      setError(err.message || 'Failed to complete match');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [id]);

  return {
    startMatch,
    recordPoint,
    completeMatch,
    loading,
    error,
  };
}
