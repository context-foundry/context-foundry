'use client';

import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import {
  UserProgress,
  UserProgressSchema,
  ProgressAction,
  PatternProgress,
} from '@/types/progress';
import { checkAchievements } from './achievement-calculator';

/**
 * Progress Store
 *
 * React Context + useReducer for managing user progress state.
 * Includes IndexedDB persistence for offline support.
 */

// IndexedDB setup
const DB_NAME = 'WorkWiseProgress';
const DB_VERSION = 1;
const STORE_NAME = 'userProgress';
const PROGRESS_KEY = 'default-user';

/**
 * Open IndexedDB connection
 * @returns Promise resolving to database
 */
async function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
}

/**
 * Load progress from IndexedDB
 * @returns User progress or null if not found
 */
async function loadProgress(): Promise<UserProgress | null> {
  try {
    const db = await openDB();
    const transaction = db.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.get(PROGRESS_KEY);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const data = request.result;
        if (!data) {
          resolve(null);
          return;
        }

        try {
          const validated = UserProgressSchema.parse(data);
          resolve(validated);
        } catch (error) {
          console.error('Invalid progress data in IndexedDB:', error);
          resolve(null);
        }
      };
    });
  } catch (error) {
    console.error('Failed to load progress from IndexedDB:', error);
    return null;
  }
}

/**
 * Save progress to IndexedDB
 * @param progress - Progress to save
 */
async function saveProgress(progress: UserProgress): Promise<void> {
  try {
    const db = await openDB();
    const transaction = db.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.put(progress, PROGRESS_KEY);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  } catch (error) {
    console.error('Failed to save progress to IndexedDB:', error);
  }
}

/**
 * Initial progress state
 */
const initialProgress: UserProgress = {
  userId: 'default',
  patternsProgress: {},
  achievements: [],
  totalPatternsCompleted: 0,
  totalQuizzesPassed: 0,
  totalScenariosCompleted: 0,
  totalTimeSpentMinutes: 0,
  averageQuizScore: 0,
  currentStreak: 0,
  longestStreak: 0,
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

/**
 * Progress reducer
 * @param state - Current state
 * @param action - Action to perform
 * @returns New state
 */
function progressReducer(state: UserProgress, action: ProgressAction): UserProgress {
  const now = Date.now();

  switch (action.type) {
    case 'COMPLETE_QUIZ': {
      const { patternId, patternName, score, timeTaken } = action.payload;

      const existing = state.patternsProgress[patternId] || {
        patternId,
        patternName,
        status: 'not-started' as const,
        quizAttempts: 0,
        scenarioCompleted: false,
        lastAccessed: now,
        timeSpentMinutes: 0,
      };

      const passed = score >= 70;
      const isComplete =
        passed && existing.scenarioCompleted && existing.fillBlankScore !== undefined;

      const newPatternProgress: PatternProgress = {
        ...existing,
        status: isComplete ? 'completed' : 'in-progress',
        quizScore: score,
        quizAttempts: existing.quizAttempts + 1,
        lastAccessed: now,
        timeSpentMinutes: existing.timeSpentMinutes + Math.round(timeTaken / 60),
        completedAt: isComplete ? now : existing.completedAt,
      };

      const newPatternsProgress = {
        ...state.patternsProgress,
        [patternId]: newPatternProgress,
      };

      const totalQuizzesPassed = passed
        ? state.totalQuizzesPassed + 1
        : state.totalQuizzesPassed;

      const totalPatternsCompleted = isComplete && !existing.completedAt
        ? state.totalPatternsCompleted + 1
        : state.totalPatternsCompleted;

      // Calculate average quiz score
      const allQuizScores = Object.values(newPatternsProgress)
        .map((p) => p.quizScore)
        .filter((s): s is number => s !== undefined);

      const averageQuizScore =
        allQuizScores.length > 0
          ? Math.round(
              allQuizScores.reduce((sum, s) => sum + s, 0) / allQuizScores.length
            )
          : 0;

      const newState = {
        ...state,
        patternsProgress: newPatternsProgress,
        totalQuizzesPassed,
        totalPatternsCompleted,
        averageQuizScore,
        updatedAt: now,
      };

      // Check for new achievements
      const newAchievements = checkAchievements(newState, newPatternProgress);

      return {
        ...newState,
        achievements: [...state.achievements, ...newAchievements],
      };
    }

    case 'COMPLETE_SCENARIO': {
      const { patternId, patternName, successful, timeTaken } = action.payload;

      const existing = state.patternsProgress[patternId] || {
        patternId,
        patternName,
        status: 'not-started' as const,
        quizAttempts: 0,
        scenarioCompleted: false,
        lastAccessed: now,
        timeSpentMinutes: 0,
      };

      const isComplete =
        existing.quizScore !== undefined &&
        existing.quizScore >= 70 &&
        existing.fillBlankScore !== undefined;

      const newPatternProgress: PatternProgress = {
        ...existing,
        status: isComplete ? 'completed' : 'in-progress',
        scenarioCompleted: true,
        scenarioSuccessful: successful,
        lastAccessed: now,
        timeSpentMinutes: existing.timeSpentMinutes + Math.round(timeTaken / 60),
        completedAt: isComplete ? now : existing.completedAt,
      };

      const newPatternsProgress = {
        ...state.patternsProgress,
        [patternId]: newPatternProgress,
      };

      const totalScenariosCompleted = state.totalScenariosCompleted + 1;

      const totalPatternsCompleted = isComplete && !existing.completedAt
        ? state.totalPatternsCompleted + 1
        : state.totalPatternsCompleted;

      const newState = {
        ...state,
        patternsProgress: newPatternsProgress,
        totalScenariosCompleted,
        totalPatternsCompleted,
        updatedAt: now,
      };

      const newAchievements = checkAchievements(newState, newPatternProgress);

      return {
        ...newState,
        achievements: [...state.achievements, ...newAchievements],
      };
    }

    case 'COMPLETE_FILL_BLANK': {
      const { patternId, patternName, score, timeTaken } = action.payload;

      const existing = state.patternsProgress[patternId] || {
        patternId,
        patternName,
        status: 'not-started' as const,
        quizAttempts: 0,
        scenarioCompleted: false,
        lastAccessed: now,
        timeSpentMinutes: 0,
      };

      const passed = score >= 70;
      const isComplete =
        passed &&
        existing.quizScore !== undefined &&
        existing.quizScore >= 70 &&
        existing.scenarioCompleted;

      const newPatternProgress: PatternProgress = {
        ...existing,
        status: isComplete ? 'completed' : 'in-progress',
        fillBlankScore: score,
        lastAccessed: now,
        timeSpentMinutes: existing.timeSpentMinutes + Math.round(timeTaken / 60),
        completedAt: isComplete ? now : existing.completedAt,
      };

      const newPatternsProgress = {
        ...state.patternsProgress,
        [patternId]: newPatternProgress,
      };

      const totalPatternsCompleted = isComplete && !existing.completedAt
        ? state.totalPatternsCompleted + 1
        : state.totalPatternsCompleted;

      const newState = {
        ...state,
        patternsProgress: newPatternsProgress,
        totalPatternsCompleted,
        updatedAt: now,
      };

      const newAchievements = checkAchievements(newState, newPatternProgress);

      return {
        ...newState,
        achievements: [...state.achievements, ...newAchievements],
      };
    }

    case 'COMPLETE_PATTERN': {
      const { patternId, patternName } = action.payload;

      const existing = state.patternsProgress[patternId];

      if (!existing || existing.status === 'completed') {
        return state;
      }

      const newPatternProgress: PatternProgress = {
        ...existing,
        status: 'completed',
        completedAt: now,
        lastAccessed: now,
      };

      const newPatternsProgress = {
        ...state.patternsProgress,
        [patternId]: newPatternProgress,
      };

      const newState = {
        ...state,
        patternsProgress: newPatternsProgress,
        totalPatternsCompleted: state.totalPatternsCompleted + 1,
        updatedAt: now,
      };

      const newAchievements = checkAchievements(newState, newPatternProgress);

      return {
        ...newState,
        achievements: [...state.achievements, ...newAchievements],
      };
    }

    case 'UNLOCK_ACHIEVEMENT': {
      return {
        ...state,
        achievements: [...state.achievements, action.payload],
        updatedAt: now,
      };
    }

    case 'UPDATE_TIME_SPENT': {
      const { patternId, minutes } = action.payload;

      const existing = state.patternsProgress[patternId];

      if (!existing) return state;

      return {
        ...state,
        patternsProgress: {
          ...state.patternsProgress,
          [patternId]: {
            ...existing,
            timeSpentMinutes: existing.timeSpentMinutes + minutes,
            lastAccessed: now,
          },
        },
        totalTimeSpentMinutes: state.totalTimeSpentMinutes + minutes,
        updatedAt: now,
      };
    }

    case 'SYNC_PROGRESS': {
      return {
        ...action.payload,
        updatedAt: now,
      };
    }

    case 'RESET_PROGRESS': {
      return {
        ...initialProgress,
        createdAt: now,
        updatedAt: now,
      };
    }

    default:
      return state;
  }
}

/**
 * Progress Context
 */
interface ProgressContextType {
  progress: UserProgress;
  dispatch: React.Dispatch<ProgressAction>;
  isLoading: boolean;
}

const ProgressContext = createContext<ProgressContextType | undefined>(undefined);

/**
 * Progress Provider Props
 */
interface ProgressProviderProps {
  children: ReactNode;
}

/**
 * Progress Provider Component
 */
export function ProgressProvider({ children }: ProgressProviderProps) {
  const [progress, dispatch] = useReducer(progressReducer, initialProgress);
  const [isLoading, setIsLoading] = React.useState(true);

  // Load progress from IndexedDB on mount
  useEffect(() => {
    loadProgress()
      .then((saved) => {
        if (saved) {
          dispatch({ type: 'SYNC_PROGRESS', payload: saved });
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  // Save progress to IndexedDB whenever it changes
  useEffect(() => {
    if (!isLoading) {
      saveProgress(progress);
    }
  }, [progress, isLoading]);

  return (
    <ProgressContext.Provider value={{ progress, dispatch, isLoading }}>
      {children}
    </ProgressContext.Provider>
  );
}

/**
 * Hook to use progress context
 */
export function useProgress() {
  const context = useContext(ProgressContext);

  if (context === undefined) {
    throw new Error('useProgress must be used within a ProgressProvider');
  }

  return context;
}

/**
 * Hook to get pattern progress
 */
export function usePatternProgress(patternId: string) {
  const { progress } = useProgress();
  return progress.patternsProgress[patternId] || null;
}

/**
 * Hook to get achievements
 */
export function useAchievements() {
  const { progress } = useProgress();
  return progress.achievements;
}

/**
 * Hook to get progress statistics
 */
export function useProgressStats() {
  const { progress } = useProgress();

  return {
    totalCompleted: progress.totalPatternsCompleted,
    totalQuizzes: progress.totalQuizzesPassed,
    totalScenarios: progress.totalScenariosCompleted,
    totalTime: progress.totalTimeSpentMinutes,
    averageScore: progress.averageQuizScore,
    currentStreak: progress.currentStreak,
    longestStreak: progress.longestStreak,
    achievementCount: progress.achievements.length,
  };
}
