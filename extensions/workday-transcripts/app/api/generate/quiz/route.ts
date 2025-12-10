/**
 * Quiz Generation API Route
 *
 * POST /api/generate/quiz
 * Generates flashcard Q&A pairs from transcript content.
 */

import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import {
  generateCompletion,
  recordUsage,
  DEFAULT_MODEL,
} from '@/lib/openai-client';
import {
  FLASHCARD_SYSTEM_PROMPT,
  generateFlashcardPrompt,
  parseFlashcardResponse,
} from '@/lib/prompts/flashcard-prompt';
import { type FlashCard } from '@/types/card';

/**
 * Request body schema
 */
const RequestSchema = z.object({
  transcriptId: z.string(),
  transcriptTitle: z.string(),
  transcriptContent: z.string(),
  category: z.enum(['HCM', 'Recruiting', 'Learning', 'Analytics', 'General']),
  cardCount: z.number().int().min(3).max(15).default(8),
});

/**
 * Response schema
 */
interface GenerateQuizResponse {
  success: boolean;
  cards?: FlashCard[];
  error?: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    estimatedCost: number;
  };
}

/**
 * POST handler
 */
export async function POST(request: NextRequest): Promise<NextResponse<GenerateQuizResponse>> {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = RequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          success: false,
          error: `Invalid request: ${validationResult.error.message}`,
        },
        { status: 400 }
      );
    }

    const { transcriptId, transcriptTitle, transcriptContent, category, cardCount } =
      validationResult.data;

    // Create parsed transcript structure for prompt generation
    const parsedTranscript = {
      metadata: {
        id: transcriptId,
        filename: '',
        title: transcriptTitle,
        category,
        date: new Date().toISOString().split('T')[0],
        lineCount: transcriptContent.split('\n').length,
        characterCount: transcriptContent.length,
      },
      content: transcriptContent,
      concepts: [],
      procedures: [],
    };

    // Generate flashcard prompt
    const userPrompt = generateFlashcardPrompt(parsedTranscript, cardCount);

    // Call OpenAI
    const result = await generateCompletion(
      FLASHCARD_SYSTEM_PROMPT,
      userPrompt,
      {
        maxTokens: 3000,
        temperature: 0.7,
      }
    );

    // Record usage
    recordUsage({
      operation: 'generate-quiz',
      model: DEFAULT_MODEL,
      promptTokens: result.usage.promptTokens,
      completionTokens: result.usage.completionTokens,
      estimatedCost: result.usage.estimatedCost,
    });

    // Parse response
    const parsed = parseFlashcardResponse(result.content);

    if (!parsed || parsed.cards.length === 0) {
      return NextResponse.json(
        {
          success: false,
          error: 'Failed to generate valid flashcards',
          usage: {
            promptTokens: result.usage.promptTokens,
            completionTokens: result.usage.completionTokens,
            estimatedCost: result.usage.estimatedCost,
          },
        },
        { status: 500 }
      );
    }

    // Create FlashCard objects with IDs
    const cards: FlashCard[] = parsed.cards.map((card) => ({
      id: uuidv4(),
      transcriptId,
      question: card.question,
      answer: card.answer,
      category,
      conceptType: card.conceptType,
      difficulty: card.difficulty,
      createdAt: new Date().toISOString(),
    }));

    return NextResponse.json({
      success: true,
      cards,
      usage: {
        promptTokens: result.usage.promptTokens,
        completionTokens: result.usage.completionTokens,
        estimatedCost: result.usage.estimatedCost,
      },
    });
  } catch (error) {
    console.error('Quiz generation error:', error);

    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * GET handler - return API info
 */
export async function GET(): Promise<NextResponse> {
  return NextResponse.json({
    endpoint: '/api/generate/quiz',
    method: 'POST',
    description: 'Generate flashcard Q&A pairs from transcript content',
    body: {
      transcriptId: 'string (required)',
      transcriptTitle: 'string (required)',
      transcriptContent: 'string (required)',
      category: 'HCM | Recruiting | Learning | Analytics | General (required)',
      cardCount: 'number (optional, default: 8)',
    },
  });
}
