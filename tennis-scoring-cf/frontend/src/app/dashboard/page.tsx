'use client';

import React from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useMatches } from '@/hooks/useMatches';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { MatchList } from '@/components/matches/MatchList';

function DashboardContent() {
  const { user } = useAuth();
  const { matches, loading, total, page, nextPage, prevPage } = useMatches({
    status: 'in_progress',
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Welcome, {user?.firstName}!
        </h1>
        <p className="text-gray-600">Manage your matches and view live scores</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Your Role</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-blue-600 capitalize">
              {user?.role}
            </p>
            {user?.schoolName && (
              <p className="text-sm text-gray-600 mt-1">{user.schoolName}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Live Matches</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600">{total}</p>
            <p className="text-sm text-gray-600 mt-1">Currently in progress</p>
          </CardContent>
        </Card>

        {user?.role === 'coach' && (
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <Link href="/matches/create">
                <Button fullWidth>Create New Match</Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-gray-900">Live Matches</h2>
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

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
