'use client';

import React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Brain, Clock, Plus, AlertCircle } from 'lucide-react';

interface ReviewQueueProps {
  dueCount: number;
  newCount: number;
  learningCount: number;
  totalCards: number;
  onStartReview?: () => void;
  className?: string;
}

/**
 * Today's review queue summary
 */
export function ReviewQueue({
  dueCount,
  newCount,
  learningCount,
  totalCards,
  onStartReview,
  className,
}: ReviewQueueProps) {
  const totalDue = dueCount + newCount + learningCount;
  const hasCardsToReview = totalDue > 0;

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="w-5 h-5" />
          Today&apos;s Review
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Queue breakdown */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 rounded-lg bg-blue-50">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Plus className="w-4 h-4 text-blue-600" />
              <span className="text-sm text-muted-foreground">New</span>
            </div>
            <p className="text-2xl font-bold text-blue-600">{newCount}</p>
          </div>

          <div className="text-center p-3 rounded-lg bg-orange-50">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Clock className="w-4 h-4 text-orange-600" />
              <span className="text-sm text-muted-foreground">Due</span>
            </div>
            <p className="text-2xl font-bold text-orange-600">{dueCount}</p>
          </div>

          <div className="text-center p-3 rounded-lg bg-yellow-50">
            <div className="flex items-center justify-center gap-1 mb-1">
              <AlertCircle className="w-4 h-4 text-yellow-600" />
              <span className="text-sm text-muted-foreground">Learning</span>
            </div>
            <p className="text-2xl font-bold text-yellow-600">{learningCount}</p>
          </div>
        </div>

        {/* Total and action */}
        <div className="flex items-center justify-between pt-4 border-t">
          <div>
            <p className="text-sm text-muted-foreground">
              {hasCardsToReview
                ? `${totalDue} cards ready for review`
                : 'All caught up for today!'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalCards} total cards in collection
            </p>
          </div>

          {hasCardsToReview ? (
            <Button onClick={onStartReview} asChild={!onStartReview}>
              {onStartReview ? (
                <>
                  <Brain className="w-4 h-4 mr-2" />
                  Start Review
                </>
              ) : (
                <Link href="/review">
                  <Brain className="w-4 h-4 mr-2" />
                  Start Review
                </Link>
              )}
            </Button>
          ) : (
            <Badge variant="outline" className="py-2 px-4">
              All done!
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default ReviewQueue;
