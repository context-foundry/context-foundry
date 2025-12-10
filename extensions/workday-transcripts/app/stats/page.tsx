'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, Target, Clock, Calendar, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  getOrCreateUserProgress,
  getAllCardStates,
  getRecentSessions,
  getDailySummaries,
} from '@/lib/cache/client-cache';
import { type UserProgress } from '@/types/progress';
import { type ReviewSession } from '@/types/review';
import { formatInterval } from '@/lib/utils';

export default function StatsPage() {
  const [progress, setProgress] = useState<UserProgress | null>(null);
  const [recentSessions, setRecentSessions] = useState<ReviewSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      setIsLoading(true);
      try {
        const [userProgress, sessions] = await Promise.all([
          getOrCreateUserProgress(),
          getRecentSessions(10),
        ]);

        setProgress(userProgress);
        setRecentSessions(sessions);
      } catch (error) {
        console.error('Failed to load stats:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadStats();
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading statistics...</p>
        </div>
      </div>
    );
  }

  // Use placeholder values if no progress exists
  const stats = progress || {
    totalCards: 250,
    totalReviews: 0,
    cardsLearned: 0,
    cardsInProgress: 0,
    cardsNew: 250,
    cardsDue: 20,
    currentStreak: 0,
    longestStreak: 0,
    retentionRate: 0,
    averageEaseFactor: 2.5,
    totalSessions: 0,
    totalTimeMinutes: 0,
    averageSessionMinutes: 0,
    categoryProgress: {},
  };

  const categories = [
    { id: 'HCM', name: 'Human Capital Management', color: 'bg-blue-500' },
    { id: 'Recruiting', name: 'Recruiting', color: 'bg-purple-500' },
    { id: 'Learning', name: 'Learning', color: 'bg-green-500' },
    { id: 'Analytics', name: 'Analytics', color: 'bg-orange-500' },
    { id: 'General', name: 'General', color: 'bg-gray-500' },
  ];

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" asChild className="mb-4">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>

        <h1 className="text-3xl font-bold">Statistics</h1>
        <p className="text-muted-foreground mt-2">
          Track your learning progress and review performance
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <Target className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Cards Mastered</p>
                <p className="text-2xl font-bold">{stats.cardsLearned}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100">
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Retention Rate</p>
                <p className="text-2xl font-bold">{stats.retentionRate}%</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-100">
                <Calendar className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Current Streak</p>
                <p className="text-2xl font-bold">{stats.currentStreak} days</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-100">
                <Clock className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Reviews</p>
                <p className="text-2xl font-bold">{stats.totalReviews}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Progress by Category */}
        <Card>
          <CardHeader>
            <CardTitle>Progress by Category</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {categories.map((category) => {
              const catProgress = stats.categoryProgress?.[category.id as keyof typeof stats.categoryProgress];
              const total = catProgress?.cardsTotal || 50;
              const learned = catProgress?.cardsLearned || 0;
              const percentage = total > 0 ? Math.round((learned / total) * 100) : 0;

              return (
                <div key={category.id}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${category.color}`} />
                      <span className="text-sm font-medium">{category.name}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {learned}/{total} cards
                    </span>
                  </div>
                  <Progress value={percentage} className="h-2" />
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Learning Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Learning Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Total Cards</span>
                <span className="font-medium">{stats.totalCards}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">New Cards</span>
                <Badge variant="new">{stats.cardsNew}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">In Progress</span>
                <Badge variant="learning_status">{stats.cardsInProgress}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Mastered</span>
                <Badge variant="graduated">{stats.cardsLearned}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Due Today</span>
                <Badge variant="review">{stats.cardsDue}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Average Ease Factor</span>
                <span className="font-medium">{stats.averageEaseFactor.toFixed(2)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Sessions */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Recent Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            {recentSessions.length > 0 ? (
              <div className="space-y-3">
                {recentSessions.map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between p-3 rounded-lg border"
                  >
                    <div>
                      <p className="font-medium">
                        {new Date(session.startedAt).toLocaleDateString('en-US', {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {session.cardsReviewed} cards reviewed
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">
                        {session.cardsReviewed > 0
                          ? Math.round(
                              (session.cardsCorrect / session.cardsReviewed) * 100
                            )
                          : 0}
                        % accuracy
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {Math.floor(session.timeSpentSeconds / 60)}m{' '}
                        {session.timeSpentSeconds % 60}s
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No review sessions yet. Start reviewing to track your progress!
              </p>
            )}
          </CardContent>
        </Card>

        {/* Streak Info */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Study Streak</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-6">
              <div className="text-center">
                <p className="text-4xl font-bold text-primary">{stats.currentStreak}</p>
                <p className="text-sm text-muted-foreground">Current Streak</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-muted-foreground">
                  {stats.longestStreak}
                </p>
                <p className="text-sm text-muted-foreground">Longest Streak</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-muted-foreground">
                  {stats.totalSessions}
                </p>
                <p className="text-sm text-muted-foreground">Total Sessions</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-muted-foreground">
                  {Math.round(stats.totalTimeMinutes)}m
                </p>
                <p className="text-sm text-muted-foreground">Total Time</p>
              </div>
            </div>

            <p className="text-center text-sm text-muted-foreground">
              {stats.currentStreak > 0
                ? `Keep going! You've studied for ${stats.currentStreak} days in a row.`
                : 'Start a streak by reviewing cards today!'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
