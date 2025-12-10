'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { BookOpen, Brain, BarChart3, Clock, Target, Zap } from 'lucide-react';

interface DashboardStats {
  cardsDue: number;
  totalCards: number;
  cardsLearned: number;
  currentStreak: number;
  retentionRate: number;
  reviewsToday: number;
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats>({
    cardsDue: 0,
    totalCards: 0,
    cardsLearned: 0,
    currentStreak: 0,
    retentionRate: 0,
    reviewsToday: 0,
  });

  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // In a real implementation, this would load from IndexedDB
    // For now, we'll use placeholder data
    const loadStats = async () => {
      try {
        // Simulate loading delay
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Placeholder stats - will be replaced with actual IndexedDB data
        setStats({
          cardsDue: 15,
          totalCards: 250,
          cardsLearned: 45,
          currentStreak: 3,
          retentionRate: 87,
          reviewsToday: 8,
        });
      } catch (error) {
        console.error('Failed to load stats:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadStats();
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      {/* Hero Section */}
      <section className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4">
          Master Workday with
          <span className="text-workday-blue"> Spaced Repetition</span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Transform Workday training transcripts into effective flashcards.
          Learn smarter with the scientifically-proven SM-2 algorithm.
        </p>
      </section>

      {/* Quick Actions */}
      <section className="mb-12">
        <div className="grid md:grid-cols-3 gap-6">
          <Link
            href="/review"
            className="group p-6 rounded-xl border border-border bg-card hover:border-workday-blue hover:shadow-lg transition-all"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-lg bg-workday-blue/10 text-workday-blue group-hover:bg-workday-blue group-hover:text-white transition-colors">
                <Brain className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Start Review</h2>
                <p className="text-sm text-muted-foreground">
                  {isLoading ? '...' : `${stats.cardsDue} cards due`}
                </p>
              </div>
            </div>
            <p className="text-muted-foreground text-sm">
              Review your due cards with spaced repetition for optimal retention.
            </p>
          </Link>

          <Link
            href="/transcripts"
            className="group p-6 rounded-xl border border-border bg-card hover:border-workday-orange hover:shadow-lg transition-all"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-lg bg-workday-orange/10 text-workday-orange group-hover:bg-workday-orange group-hover:text-white transition-colors">
                <BookOpen className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Browse Transcripts</h2>
                <p className="text-sm text-muted-foreground">38 training videos</p>
              </div>
            </div>
            <p className="text-muted-foreground text-sm">
              Explore Workday training content by category and topic.
            </p>
          </Link>

          <Link
            href="/stats"
            className="group p-6 rounded-xl border border-border bg-card hover:border-workday-green hover:shadow-lg transition-all"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-lg bg-workday-green/10 text-workday-green group-hover:bg-workday-green group-hover:text-white transition-colors">
                <BarChart3 className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">View Statistics</h2>
                <p className="text-sm text-muted-foreground">
                  {isLoading ? '...' : `${stats.retentionRate}% retention`}
                </p>
              </div>
            </div>
            <p className="text-muted-foreground text-sm">
              Track your learning progress and review streaks.
            </p>
          </Link>
        </div>
      </section>

      {/* Stats Overview */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">Your Progress</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Target className="w-4 h-4" />
              <span className="text-sm">Cards Learned</span>
            </div>
            <p className="text-2xl font-bold">
              {isLoading ? '-' : stats.cardsLearned}
              <span className="text-sm font-normal text-muted-foreground">
                /{stats.totalCards}
              </span>
            </p>
          </div>

          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Zap className="w-4 h-4" />
              <span className="text-sm">Current Streak</span>
            </div>
            <p className="text-2xl font-bold">
              {isLoading ? '-' : stats.currentStreak}
              <span className="text-sm font-normal text-muted-foreground"> days</span>
            </p>
          </div>

          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-sm">Reviews Today</span>
            </div>
            <p className="text-2xl font-bold">
              {isLoading ? '-' : stats.reviewsToday}
            </p>
          </div>

          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <BarChart3 className="w-4 h-4" />
              <span className="text-sm">Retention Rate</span>
            </div>
            <p className="text-2xl font-bold">
              {isLoading ? '-' : `${stats.retentionRate}%`}
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">How It Works</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="p-6 rounded-lg border border-border bg-card">
            <div className="w-10 h-10 rounded-full bg-workday-blue/10 text-workday-blue flex items-center justify-center font-bold mb-4">
              1
            </div>
            <h3 className="font-semibold mb-2">Review Flashcards</h3>
            <p className="text-sm text-muted-foreground">
              Questions are generated from Workday training transcripts covering
              HCM, Recruiting, Learning, and Analytics.
            </p>
          </div>

          <div className="p-6 rounded-lg border border-border bg-card">
            <div className="w-10 h-10 rounded-full bg-workday-orange/10 text-workday-orange flex items-center justify-center font-bold mb-4">
              2
            </div>
            <h3 className="font-semibold mb-2">Rate Your Recall</h3>
            <p className="text-sm text-muted-foreground">
              After revealing the answer, rate how well you remembered it: Again,
              Hard, Good, or Easy.
            </p>
          </div>

          <div className="p-6 rounded-lg border border-border bg-card">
            <div className="w-10 h-10 rounded-full bg-workday-green/10 text-workday-green flex items-center justify-center font-bold mb-4">
              3
            </div>
            <h3 className="font-semibold mb-2">Optimize Reviews</h3>
            <p className="text-sm text-muted-foreground">
              The SM-2 algorithm schedules reviews at optimal intervals to maximize
              long-term retention.
            </p>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section>
        <h2 className="text-2xl font-semibold mb-6">Content Categories</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { name: 'HCM', count: 10, color: 'bg-blue-500' },
            { name: 'Recruiting', count: 10, color: 'bg-purple-500' },
            { name: 'Learning', count: 8, color: 'bg-green-500' },
            { name: 'Analytics', count: 8, color: 'bg-orange-500' },
            { name: 'General', count: 2, color: 'bg-gray-500' },
          ].map((category) => (
            <div
              key={category.name}
              className="p-4 rounded-lg border border-border bg-card hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-3 h-3 rounded-full ${category.color}`} />
                <span className="font-medium">{category.name}</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {category.count} transcripts
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
