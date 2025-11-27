'use client';

import React, { useState, useMemo } from 'react';
import { PatternCard } from '@/components/patterns/PatternCard';
import { CategoryFilter } from '@/components/patterns/CategoryFilter';
import { SearchBar } from '@/components/patterns/SearchBar';
import { TransformedPattern, Pattern } from '@/types/pattern';
import { useProgress } from '@/lib/progress/progress-store';
import { Loader2 } from 'lucide-react';
import { patternParser } from '@/lib/pattern-parser';

// Load all patterns from the pattern parser
const allPatterns: Pattern[] = patternParser.parsePatterns();

// Transform to display format
function transformPattern(pattern: Pattern): TransformedPattern {
  const difficultyLabels = {
    beginner: 'Beginner',
    intermediate: 'Intermediate',
    advanced: 'Advanced',
  };

  return {
    ...pattern,
    displayName: pattern.name,
    categoryLabel: pattern.category,
    difficultyLabel: pattern.difficulty ? difficultyLabels[pattern.difficulty] : 'Intermediate',
    estimatedTimeLabel: pattern.estimated_time_minutes ? `${pattern.estimated_time_minutes} min` : '30 min',
  };
}

const mockPatterns: TransformedPattern[] = allPatterns.map(transformPattern);

export default function PatternsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { progress } = useProgress();

  // Helper function to calculate completion percentage
  const calculateCompletionPercentage = (patternProgress: any): number => {
    let completed = 0;
    let total = 3; // Quiz, Scenario, Fill-in-blank

    if (patternProgress.quizScore !== undefined && patternProgress.quizScore >= 70) {
      completed++;
    }
    if (patternProgress.scenarioCompleted) {
      completed++;
    }
    if (patternProgress.fillBlankScore !== undefined && patternProgress.fillBlankScore >= 70) {
      completed++;
    }

    return Math.round((completed / total) * 100);
  };

  // Extract unique categories
  const categories = useMemo(() => {
    const cats = new Set(mockPatterns.map((p) => p.category));
    return Array.from(cats).sort();
  }, []);

  // Filter and transform patterns with completion status
  const filteredPatterns = useMemo(() => {
    let filtered = mockPatterns;

    // Apply category filter
    if (selectedCategory) {
      filtered = filtered.filter((p) => p.category === selectedCategory);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.description.toLowerCase().includes(query) ||
          p.category.toLowerCase().includes(query) ||
          p.applies_to.some((at) => at.toLowerCase().includes(query))
      );
    }

    // Add completion status from progress
    return filtered.map((pattern) => {
      const patternProgress = progress.patternsProgress[pattern.id];
      return {
        ...pattern,
        completionStatus: patternProgress?.status || 'not-started',
        completionPercentage: patternProgress
          ? calculateCompletionPercentage(patternProgress)
          : 0,
      };
    });
  }, [searchQuery, selectedCategory, progress.patternsProgress]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Pattern Library</h1>
        <p className="text-gray-600">
          Browse and learn from {mockPatterns.length} Workday best practices
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <SearchBar onSearch={setSearchQuery} />
          </div>
          <CategoryFilter
            categories={categories}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
          />
        </div>

        {/* Active Filters */}
        {(searchQuery || selectedCategory) && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-sm text-gray-600">Active filters:</span>
            {searchQuery && (
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                Search: "{searchQuery}"
                <button
                  onClick={() => setSearchQuery('')}
                  className="hover:text-blue-900"
                  aria-label="Clear search"
                >
                  ×
                </button>
              </span>
            )}
            {selectedCategory && (
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                Category: {selectedCategory}
                <button
                  onClick={() => setSelectedCategory(null)}
                  className="hover:text-blue-900"
                  aria-label="Clear category filter"
                >
                  ×
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Results Count */}
      <div className="mb-4">
        <p className="text-sm text-gray-600">
          Showing {filteredPatterns.length} of {mockPatterns.length} patterns
        </p>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin" aria-hidden="true" />
          <span className="sr-only">Loading patterns...</span>
        </div>
      )}

      {/* Patterns Grid */}
      {!loading && filteredPatterns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPatterns.map((pattern) => (
            <PatternCard key={pattern.id} pattern={pattern} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredPatterns.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-600 mb-4">No patterns found matching your criteria</p>
          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedCategory(null);
            }}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Clear all filters
          </button>
        </div>
      )}
    </div>
  );
}
