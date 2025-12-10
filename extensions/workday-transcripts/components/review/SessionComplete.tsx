'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, Clock, Target, TrendingUp, Home } from 'lucide-react';
import type { ReviewSession } from '@/types/review';
import { formatTime } from '@/lib/utils';

interface SessionCompleteProps {
  session: ReviewSession;
  onContinue: () => void;
  onHome: () => void;
}

export function SessionComplete({
  session,
  onContinue,
  onHome,
}: SessionCompleteProps) {
  const accuracy = session.cardsReviewed > 0
    ? Math.round((session.cardsCorrect / session.cardsReviewed) * 100)
    : 0;

  return (
    <Card className="max-w-lg mx-auto">
      <CardHeader className="text-center pb-2">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
        </div>
        <CardTitle className="text-2xl">Session Complete!</CardTitle>
        <p className="text-muted-foreground mt-2">
          Great job completing your review session.
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg text-center">
            <div className="flex items-center justify-center mb-2">
              <Target className="w-5 h-5 text-primary mr-2" />
            </div>
            <p className="text-2xl font-bold">{session.cardsReviewed}</p>
            <p className="text-sm text-muted-foreground">Cards Reviewed</p>
          </div>

          <div className="p-4 bg-muted rounded-lg text-center">
            <div className="flex items-center justify-center mb-2">
              <TrendingUp className="w-5 h-5 text-green-600 mr-2" />
            </div>
            <p className="text-2xl font-bold">{accuracy}%</p>
            <p className="text-sm text-muted-foreground">Accuracy</p>
          </div>

          <div className="p-4 bg-muted rounded-lg text-center">
            <div className="flex items-center justify-center mb-2">
              <Clock className="w-5 h-5 text-blue-600 mr-2" />
            </div>
            <p className="text-2xl font-bold">
              {formatTime(session.timeSpentSeconds * 1000)}
            </p>
            <p className="text-sm text-muted-foreground">Time Spent</p>
          </div>

          <div className="p-4 bg-muted rounded-lg text-center">
            <div className="flex items-center justify-center mb-2">
              <CheckCircle className="w-5 h-5 text-emerald-600 mr-2" />
            </div>
            <p className="text-2xl font-bold">{session.cardsCorrect}</p>
            <p className="text-sm text-muted-foreground">Correct</p>
          </div>
        </div>

        {/* Breakdown */}
        <div className="flex items-center justify-center gap-2 flex-wrap">
          {session.newCardsStudied > 0 && (
            <Badge variant="outline" className="text-blue-600 border-blue-200">
              {session.newCardsStudied} new cards
            </Badge>
          )}
          {session.reviewCardsStudied > 0 && (
            <Badge variant="outline" className="text-amber-600 border-amber-200">
              {session.reviewCardsStudied} reviews
            </Badge>
          )}
        </div>

        {/* Encouragement message */}
        <div className="text-center p-4 bg-primary/5 rounded-lg">
          {accuracy >= 90 ? (
            <p className="text-sm text-primary font-medium">
              Excellent work! Your retention is outstanding! 🌟
            </p>
          ) : accuracy >= 70 ? (
            <p className="text-sm text-primary font-medium">
              Good job! Keep up the consistent practice! 💪
            </p>
          ) : accuracy >= 50 ? (
            <p className="text-sm text-primary font-medium">
              Nice effort! The cards you struggled with will come back sooner. 📚
            </p>
          ) : (
            <p className="text-sm text-primary font-medium">
              Don&apos;t worry! Spaced repetition will help reinforce these concepts. 🎯
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button onClick={onHome} variant="outline" className="flex-1">
            <Home className="w-4 h-4 mr-2" />
            Home
          </Button>
          <Button onClick={onContinue} className="flex-1">
            Continue Learning
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default SessionComplete;
