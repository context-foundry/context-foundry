'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { useCreateMatch } from '@/hooks/useMatches';
import type { MatchType, MatchFormat } from '@/types/match';

function CreateMatchContent() {
  const router = useRouter();
  const { createMatch, loading, error } = useCreateMatch();
  const [formData, setFormData] = useState({
    player1Name: '',
    player2Name: '',
    player3Name: '',
    player4Name: '',
    matchType: 'singles' as MatchType,
    format: 'best_of_3' as MatchFormat,
    location: '',
    scheduledAt: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.player1Name) {
      newErrors.player1Name = 'Player 1 name is required';
    }
    if (!formData.player2Name) {
      newErrors.player2Name = 'Player 2 name is required';
    }

    if (formData.matchType === 'doubles') {
      if (!formData.player3Name) {
        newErrors.player3Name = 'Player 3 name is required for doubles';
      }
      if (!formData.player4Name) {
        newErrors.player4Name = 'Player 4 name is required for doubles';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    try {
      const matchData = {
        player1Name: formData.player1Name,
        player2Name: formData.player2Name,
        player3Name: formData.matchType === 'doubles' ? formData.player3Name : undefined,
        player4Name: formData.matchType === 'doubles' ? formData.player4Name : undefined,
        matchType: formData.matchType,
        format: formData.format,
        location: formData.location || undefined,
        scheduledAt: formData.scheduledAt || undefined,
      };

      const match = await createMatch(matchData);
      router.push(`/matches/${match.id}`);
    } catch (err) {
      console.error('Failed to create match:', err);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Create New Match</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Match Type */}
            <div>
              <label htmlFor="matchType" className="block text-sm font-medium text-gray-700 mb-1">
                Match Type
              </label>
              <select
                id="matchType"
                name="matchType"
                value={formData.matchType}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px]"
              >
                <option value="singles">Singles</option>
                <option value="doubles">Doubles</option>
              </select>
            </div>

            {/* Format */}
            <div>
              <label htmlFor="format" className="block text-sm font-medium text-gray-700 mb-1">
                Format
              </label>
              <select
                id="format"
                name="format"
                value={formData.format}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px]"
              >
                <option value="best_of_3">Best of 3 Sets</option>
                <option value="best_of_5">Best of 5 Sets</option>
              </select>
            </div>

            {/* Players */}
            <div className="space-y-4">
              <h3 className="font-medium text-gray-900">
                {formData.matchType === 'singles' ? 'Players' : 'Team 1'}
              </h3>
              <Input
                name="player1Name"
                label="Player 1"
                value={formData.player1Name}
                onChange={handleChange}
                error={errors.player1Name}
                placeholder="John Doe"
              />
              {formData.matchType === 'doubles' && (
                <Input
                  name="player3Name"
                  label="Player 3 (Partner)"
                  value={formData.player3Name}
                  onChange={handleChange}
                  error={errors.player3Name}
                  placeholder="Jane Smith"
                />
              )}
            </div>

            <div className="space-y-4">
              <h3 className="font-medium text-gray-900">
                {formData.matchType === 'singles' ? '' : 'Team 2'}
              </h3>
              <Input
                name="player2Name"
                label="Player 2"
                value={formData.player2Name}
                onChange={handleChange}
                error={errors.player2Name}
                placeholder="Bob Johnson"
              />
              {formData.matchType === 'doubles' && (
                <Input
                  name="player4Name"
                  label="Player 4 (Partner)"
                  value={formData.player4Name}
                  onChange={handleChange}
                  error={errors.player4Name}
                  placeholder="Alice Williams"
                />
              )}
            </div>

            {/* Optional Fields */}
            <Input
              name="location"
              label="Location (Optional)"
              value={formData.location}
              onChange={handleChange}
              placeholder="Court 1, Main Stadium"
            />

            <Input
              type="datetime-local"
              name="scheduledAt"
              label="Scheduled Time (Optional)"
              value={formData.scheduledAt}
              onChange={handleChange}
            />

            {/* Submit Button */}
            <div className="flex gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                fullWidth
              >
                Cancel
              </Button>
              <Button type="submit" loading={loading} fullWidth>
                Create Match
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CreateMatchPage() {
  return (
    <ProtectedRoute requireRole="coach">
      <CreateMatchContent />
    </ProtectedRoute>
  );
}
