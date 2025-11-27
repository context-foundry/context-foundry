'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import * as Tabs from '@radix-ui/react-tabs';
import { QuizContainer } from '@/components/learning/quiz/QuizContainer';
import { ScenarioBuilder } from '@/components/learning/scenario/ScenarioBuilder';
import { FillBlankExercise } from '@/components/learning/fill-blank/FillBlankExercise';
import { Quiz, Scenario, FillBlankExercise as FillBlankType, QuizResult } from '@/types/learning';
import { useProgress } from '@/lib/progress/progress-store';
import { ArrowLeft, Loader2, BookOpen, Map, PenTool } from 'lucide-react';
import Link from 'next/link';

export default function LearnPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { dispatch } = useProgress();

  const patternId = params.patternId as string;
  const defaultTab = searchParams.get('tab') || 'quiz';

  const [activeTab, setActiveTab] = useState(defaultTab);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [fillBlank, setFillBlank] = useState<FillBlankType | null>(null);
  const [loading, setLoading] = useState<Record<string, boolean>>({
    quiz: false,
    scenario: false,
    fillBlank: false,
  });
  const [error, setError] = useState<Record<string, string | null>>({
    quiz: null,
    scenario: null,
    fillBlank: null,
  });

  // Load quiz data
  const loadQuiz = async () => {
    if (quiz) return;

    setLoading((prev) => ({ ...prev, quiz: true }));
    setError((prev) => ({ ...prev, quiz: null }));

    try {
      const response = await fetch('/api/generate/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patternId }),
      });

      if (!response.ok) throw new Error('Failed to load quiz');

      const data = await response.json();
      setQuiz(data);
    } catch (err) {
      setError((prev) => ({ ...prev, quiz: err instanceof Error ? err.message : 'Error loading quiz' }));
    } finally {
      setLoading((prev) => ({ ...prev, quiz: false }));
    }
  };

  // Load scenario data
  const loadScenario = async () => {
    if (scenario) return;

    setLoading((prev) => ({ ...prev, scenario: true }));
    setError((prev) => ({ ...prev, scenario: null }));

    try {
      const response = await fetch('/api/generate/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patternId }),
      });

      if (!response.ok) throw new Error('Failed to load scenario');

      const data = await response.json();
      setScenario(data);
    } catch (err) {
      setError((prev) => ({ ...prev, scenario: err instanceof Error ? err.message : 'Error loading scenario' }));
    } finally {
      setLoading((prev) => ({ ...prev, scenario: false }));
    }
  };

  // Load fill-in-blank data
  const loadFillBlank = async () => {
    if (fillBlank) return;

    setLoading((prev) => ({ ...prev, fillBlank: true }));
    setError((prev) => ({ ...prev, fillBlank: null }));

    try {
      // For now, use mock data since we don't have a fill-blank API endpoint
      // In production, this would call an API endpoint
      const mockFillBlank: FillBlankType = {
        patternId,
        patternName: 'Security Group Design',
        sentences: [
          {
            id: 'sentence-1',
            template: 'Security groups should follow the principle of {{blank}} to minimize access risks.',
            blanks: [
              {
                id: 'blank-1',
                correctAnswers: ['least privilege', 'least-privilege', 'minimal access'],
                hint: 'A security principle that limits access rights',
                caseSensitive: false,
              },
            ],
          },
          {
            id: 'sentence-2',
            template: 'Use {{blank}} to prevent conflicts of interest in approval processes.',
            blanks: [
              {
                id: 'blank-2',
                correctAnswers: ['segregation of duties', 'separation of duties', 'SoD'],
                hint: 'A control that separates responsibilities',
                caseSensitive: false,
              },
            ],
          },
        ],
        generatedAt: new Date().toISOString(),
      };

      setFillBlank(mockFillBlank);
    } catch (err) {
      setError((prev) => ({ ...prev, fillBlank: err instanceof Error ? err.message : 'Error loading exercise' }));
    } finally {
      setLoading((prev) => ({ ...prev, fillBlank: false }));
    }
  };

  // Load data based on active tab
  useEffect(() => {
    if (activeTab === 'quiz') loadQuiz();
    if (activeTab === 'scenario') loadScenario();
    if (activeTab === 'fill-blank') loadFillBlank();
  }, [activeTab, patternId]);

  // Handle quiz completion
  const handleQuizComplete = (result: QuizResult) => {
    dispatch({
      type: 'COMPLETE_QUIZ',
      payload: {
        patternId,
        patternName: quiz?.patternName || 'Unknown Pattern',
        score: result.score,
        timeTaken: result.timeTaken,
      },
    });
  };

  // Handle scenario completion
  const handleScenarioComplete = (result: {
    successful: boolean;
    decisionsCorrect: number;
    decisionsTotal: number;
    timeTaken: number;
  }) => {
    dispatch({
      type: 'COMPLETE_SCENARIO',
      payload: {
        patternId,
        patternName: scenario?.patternName || 'Unknown Pattern',
        successful: result.successful,
        timeTaken: result.timeTaken,
      },
    });
  };

  // Handle fill-blank completion
  const handleFillBlankComplete = (result: { score: number; timeTaken: number }) => {
    dispatch({
      type: 'COMPLETE_FILL_BLANK',
      payload: {
        patternId,
        patternName: fillBlank?.patternName || 'Unknown Pattern',
        score: result.score,
        timeTaken: result.timeTaken,
      },
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <Link
        href={`/patterns/${patternId}`}
        className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-6 min-h-[44px]"
        aria-label="Back to pattern details"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Pattern
      </Link>

      {/* Tabs */}
      <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
        <Tabs.List className="flex border-b border-gray-200 mb-8 overflow-x-auto">
          <Tabs.Trigger
            value="quiz"
            className="flex items-center gap-2 px-6 py-3 text-sm font-medium text-gray-700 border-b-2 border-transparent hover:text-blue-600 hover:border-blue-600 data-[state=active]:text-blue-600 data-[state=active]:border-blue-600 transition-colors min-h-[44px]"
            aria-label="Quiz tab"
          >
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            Quiz
          </Tabs.Trigger>

          <Tabs.Trigger
            value="scenario"
            className="flex items-center gap-2 px-6 py-3 text-sm font-medium text-gray-700 border-b-2 border-transparent hover:text-blue-600 hover:border-blue-600 data-[state=active]:text-blue-600 data-[state=active]:border-blue-600 transition-colors min-h-[44px]"
            aria-label="Scenario tab"
          >
            <Map className="h-4 w-4" aria-hidden="true" />
            Scenario
          </Tabs.Trigger>

          <Tabs.Trigger
            value="fill-blank"
            className="flex items-center gap-2 px-6 py-3 text-sm font-medium text-gray-700 border-b-2 border-transparent hover:text-blue-600 hover:border-blue-600 data-[state=active]:text-blue-600 data-[state=active]:border-blue-600 transition-colors min-h-[44px]"
            aria-label="Fill in the blank tab"
          >
            <PenTool className="h-4 w-4" aria-hidden="true" />
            Fill in the Blank
          </Tabs.Trigger>
        </Tabs.List>

        {/* Quiz Tab Content */}
        <Tabs.Content value="quiz" className="focus:outline-none">
          {loading.quiz && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-blue-600 animate-spin" aria-hidden="true" />
              <span className="sr-only">Loading quiz...</span>
            </div>
          )}

          {error.quiz && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
              {error.quiz}
            </div>
          )}

          {quiz && !loading.quiz && !error.quiz && (
            <QuizContainer quiz={quiz} onComplete={handleQuizComplete} />
          )}
        </Tabs.Content>

        {/* Scenario Tab Content */}
        <Tabs.Content value="scenario" className="focus:outline-none">
          {loading.scenario && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-blue-600 animate-spin" aria-hidden="true" />
              <span className="sr-only">Loading scenario...</span>
            </div>
          )}

          {error.scenario && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
              {error.scenario}
            </div>
          )}

          {scenario && !loading.scenario && !error.scenario && (
            <ScenarioBuilder scenario={scenario} onComplete={handleScenarioComplete} />
          )}
        </Tabs.Content>

        {/* Fill-in-Blank Tab Content */}
        <Tabs.Content value="fill-blank" className="focus:outline-none">
          {loading.fillBlank && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-blue-600 animate-spin" aria-hidden="true" />
              <span className="sr-only">Loading exercise...</span>
            </div>
          )}

          {error.fillBlank && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
              {error.fillBlank}
            </div>
          )}

          {fillBlank && !loading.fillBlank && !error.fillBlank && (
            <FillBlankExercise exercise={fillBlank} onComplete={handleFillBlankComplete} />
          )}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
