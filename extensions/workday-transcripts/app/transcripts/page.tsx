'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  BookOpen,
  FileText,
  Filter,
  Loader2,
  Search,
} from 'lucide-react';
import type { TranscriptMetadata } from '@/types/transcript';
import type { WorkdayCategory } from '@/types/card';

// Sample transcript data (would normally come from the loader)
const SAMPLE_TRANSCRIPTS: TranscriptMetadata[] = [
  { id: 't1', filename: 'Navigate Workday', title: 'How to Navigate Workday', category: 'HCM', date: '2025-11-03', lineCount: 150, characterCount: 5000 },
  { id: 't2', filename: 'Hire Worker', title: 'How to Hire a Worker', category: 'HCM', date: '2025-11-03', lineCount: 180, characterCount: 6500 },
  { id: 't3', filename: 'Search Workday', title: 'How to Search', category: 'HCM', date: '2025-11-03', lineCount: 120, characterCount: 4000 },
  { id: 't4', filename: 'Create Courses', title: 'How to Create Courses', category: 'Learning', date: '2025-08-12', lineCount: 250, characterCount: 10000 },
  { id: 't5', filename: 'Manage Candidates', title: 'How to Manage Candidates', category: 'Recruiting', date: '2025-09-25', lineCount: 200, characterCount: 9000 },
  { id: 't6', filename: 'Access Reports', title: 'How to Access Reports', category: 'Analytics', date: '2025-08-11', lineCount: 130, characterCount: 4500 },
];

const categoryColors: Record<WorkdayCategory, string> = {
  HCM: 'bg-blue-100 text-blue-800 border-blue-200',
  Recruiting: 'bg-purple-100 text-purple-800 border-purple-200',
  Learning: 'bg-green-100 text-green-800 border-green-200',
  Analytics: 'bg-orange-100 text-orange-800 border-orange-200',
  General: 'bg-gray-100 text-gray-800 border-gray-200',
};

export default function TranscriptsPage() {
  const [loading, setLoading] = useState(true);
  const [transcripts, setTranscripts] = useState<TranscriptMetadata[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<WorkdayCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    // Simulate loading transcripts
    setTimeout(() => {
      setTranscripts(SAMPLE_TRANSCRIPTS);
      setLoading(false);
    }, 500);
  }, []);

  const filteredTranscripts = useMemo(() => {
    return transcripts.filter((t) => {
      const matchesCategory =
        selectedCategory === 'all' || t.category === selectedCategory;
      const matchesSearch =
        searchQuery === '' ||
        t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.category.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [transcripts, selectedCategory, searchQuery]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: transcripts.length };
    for (const t of transcripts) {
      counts[t.category] = (counts[t.category] || 0) + 1;
    }
    return counts;
  }, [transcripts]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const categories: (WorkdayCategory | 'all')[] = [
    'all',
    'HCM',
    'Recruiting',
    'Learning',
    'Analytics',
    'General',
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Training Transcripts</h1>
        <p className="text-muted-foreground mt-1">
          Browse Workday training content by category
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Category filter */}
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(cat)}
              className="capitalize"
            >
              {cat === 'all' ? 'All' : cat}
              <Badge variant="secondary" className="ml-2 text-xs">
                {categoryCounts[cat] || 0}
              </Badge>
            </Button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search transcripts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>

      {/* Transcript grid */}
      {filteredTranscripts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              No transcripts found matching your criteria.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTranscripts.map((transcript) => (
            <Card
              key={transcript.id}
              className="hover:shadow-md transition-shadow"
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base line-clamp-2">
                    {transcript.title}
                  </CardTitle>
                  <Badge
                    className={`shrink-0 ${categoryColors[transcript.category]}`}
                  >
                    {transcript.category}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
                  <span className="flex items-center gap-1">
                    <FileText className="w-4 h-4" />
                    {transcript.lineCount} lines
                  </span>
                  <span>{transcript.date}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <BookOpen className="w-4 h-4 text-primary" />
                  <span className="text-muted-foreground">
                    {transcript.cardCount || '5-10'} flashcards
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Summary */}
      <div className="text-center text-sm text-muted-foreground">
        Showing {filteredTranscripts.length} of {transcripts.length} transcripts
      </div>
    </div>
  );
}
