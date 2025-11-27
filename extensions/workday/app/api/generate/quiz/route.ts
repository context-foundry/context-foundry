import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { patternParser } from '@/lib/pattern-parser';
import { generateStructuredJSON } from '@/lib/openai-client';
import { generateQuizPrompt, getQuizSystemMessage } from '@/lib/prompts/quiz-prompt';
import { generateQuizCacheKey } from '@/lib/cache/cache-keys';
import { getOrSetServerCache } from '@/lib/cache/server-cache';
import { QuizSchema, Quiz } from '@/types/learning';
import { validateQuiz } from '@/lib/validation/content-validator';
import { createSystemMessage, createUserMessage } from '@/lib/openai-client';

/**
 * POST /api/generate/quiz
 *
 * Generate 5-question multiple choice quiz for a pattern using GPT-4o.
 * Implements three-tier caching strategy with server-side KV cache (Tier 3).
 * Passing score: 70% (4 out of 5 correct).
 */

// Request validation schema
const QuizRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  difficulty: z.enum(['easy', 'medium', 'hard']).optional(),
  adaptive: z.boolean().optional(),
});

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = QuizRequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.issues,
        },
        { status: 400 }
      );
    }

    const { patternId, difficulty, adaptive } = validationResult.data;

    // Load pattern data
    const pattern = patternParser.getPatternById(patternId);
    if (!pattern) {
      return NextResponse.json(
        { error: `Pattern not found: ${patternId}` },
        { status: 404 }
      );
    }

    // Generate cache key
    const cacheKey = generateQuizCacheKey(patternId, { adaptive, difficulty });

    // Try to get from server cache (Tier 3)
    const cachedResult = await getOrSetServerCache<Quiz>(
      cacheKey,
      async () => {
        // Generate new quiz with GPT-4o
        const prompt = generateQuizPrompt(pattern);
        const systemMessage = getQuizSystemMessage();

        const quizData = await generateStructuredJSON<Quiz>({
          messages: [
            createSystemMessage(systemMessage),
            createUserMessage(prompt),
          ],
          model: 'gpt-4o',
          temperature: 0.7,
          maxTokens: 3000,
          operation: 'quiz-generation',
        });

        // Validate generated quiz
        const validation = validateQuiz(quizData, pattern);

        if (!validation.isValid) {
          console.error('[Quiz API] Validation failed:', validation);
          throw new Error(
            `Generated quiz failed validation: ${validation.regenerationReason || 'Unknown error'}`
          );
        }

        // Ensure quiz has exactly 5 questions
        if (quizData.questions.length !== 5) {
          throw new Error(
            `Quiz must have exactly 5 questions, got ${quizData.questions.length}`
          );
        }

        // Validate each question has 4 options
        for (const question of quizData.questions) {
          if (question.options.length !== 4) {
            throw new Error(
              `Question "${question.id}" must have exactly 4 options, got ${question.options.length}`
            );
          }
        }

        // Parse and validate with Zod schema
        const quiz = QuizSchema.parse({
          ...quizData,
          passingScore: 70,
          totalPoints: 100,
          cacheSource: 'generated',
        });

        return quiz;
      }
    );

    // Determine cache source
    const cacheSource = cachedResult.cached ? 'tier3' : 'generated';
    const quiz: Quiz = {
      ...cachedResult.value,
      cacheSource,
    };

    // Log cache performance
    if (process.env.NODE_ENV === 'development') {
      console.log('[Quiz API]', {
        patternId,
        cacheSource,
        cached: cachedResult.cached,
        questionCount: quiz.questions.length,
        passingScore: quiz.passingScore,
      });
    }

    return NextResponse.json(quiz, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=604800, stale-while-revalidate=86400',
      },
    });
  } catch (error) {
    console.error('[Quiz API] Error:', error);

    // Handle specific error types
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        {
          error: 'Schema validation failed',
          details: error.issues,
        },
        { status: 400 }
      );
    }

    if (error instanceof Error) {
      // Check if it's an OpenAI API error
      if (error.message.includes('API key')) {
        return NextResponse.json(
          { error: 'OpenAI API configuration error' },
          { status: 500 }
        );
      }

      if (error.message.includes('rate limit')) {
        return NextResponse.json(
          { error: 'Rate limit exceeded. Please try again later.' },
          { status: 429 }
        );
      }
    }

    return NextResponse.json(
      {
        error: 'Failed to generate quiz',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
