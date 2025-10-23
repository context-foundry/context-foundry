'use client';

import React, { useState } from 'react';
import { useMatches } from '@/hooks/useMatches';
import { MatchList } from '@/components/matches/MatchList';
import { MatchFilters } from '@/components/matches/MatchFilters';
import type { MatchFiltersType } from '@/types/match';

export default function HomePage() {
  const [filters, setFilters] = useState<MatchFiltersType>({});
  const { matches, loading, total, page, refetch, nextPage, prevPage } = useMatches(filters);

  const handleFilterChange = (newFilters: MatchFiltersType) => {
    setFilters(newFilters);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Tennis Matches</h1>
        <p className="text-gray-600">
          Watch live matches and view completed games
        </p>
      </div>

      <div className="space-y-6">
        <MatchFilters onFilterChange={handleFilterChange} />
        <MatchList
          matches={matches}
          loading={loading}
          total={total}
          page={page}
          onNextPage={nextPage}
          onPrevPage={prevPage}
        />
      </div>
    </div>
  );
}
