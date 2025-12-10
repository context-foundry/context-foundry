/**
 * Hint Generation API Route
 *
 * POST /api/generate/hint
 * Generates study hints for flashcards.
 */

import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import {
  generateCompletion,
  recordUsage,
  DEFAULT_MODEL,
} from '@/lib/openai-client';
import {
  HINT_SYSTEM_PROMPT,
  generateHintPrompt,
  generateProgressiveHintsPrompt,
  parseHintResponse,
  parseProgressiveHintsResponse,
} from '@/lib/prompts/hint-prompt';
import { type FlashCard } from '@/types/card';

/**
 * Request body schema
 */
const RequestSchema = z.object({
  card: z.object({
    id: z.string(),
    transcriptId: z.string(),
    question: z.string(),
    answer: z.string(),
    category: z.enum(['HCM', 'Recruiting', 'Learning', 'Analytics', 'General']),
    conceptType: z.enum(['definition', 'procedure', 'fact', 'comparison']),
    difficulty: z.enum(['easy', 'medium', 'hard']),
    createdAt: z.string(),
  }),
  progressive: z.boolean().default(false),
});

/**
 * Response schema
 */
interface GenerateHintResponse {
  success: boolean;
  hint?: string;
  hints?: string[];
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
export async function POST(request: NextRequest): Promise<NextResponse<GenerateHintResponse>> {
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

    const { card, progressive } = validationResult.data;

    // Generate appropriate prompt
    const userPrompt = progressive
      ? generateProgressiveHintsPrompt(card as FlashCard)
      : generateHintPrompt(card as FlashCard);

    // Call OpenAI
    const result = await generateCompletion(
      HINT_SYSTEM_PROMPT,
      userPrompt,
      {
        maxTokens: 500,
        temperature: 0.8,
      }
    );

    // Record usage
    recordUsage({
      operation: 'generate-hint',
      model: DEFAULT_MODEL,
      promptTokens: result.usage.promptTokens,
      completionTokens: result.usage.completionTokens,
      estimatedCost: result.usage.estimatedCost,
    });

    // Parse response
    if (progressive) {
      const hints = parseProgressiveHintsResponse(result.content);

      if (!hints || hints.length === 0) {
        return NextResponse.json(
          {
            success: false,
            error: 'Failed to generate hints',
            usage: {
              promptTokens: result.usage.promptTokens,
              completionTokens: result.usage.completionTokens,
              estimatedCost: result.usage.estimatedCost,
            },
          },
          { status: 500 }
        );
      }

      return NextResponse.json({
        success: true,
        hints,
        usage: {
          promptTokens: result.usage.promptTokens,
          completionTokens: result.usage.completionTokens,
          estimatedCost: result.usage.estimatedCost,
        },
      });
    } else {
      const hint = parseHintResponse(result.content);

      if (!hint) {
        return NextResponse.json(
          {
            success: false,
            error: 'Failed to generate hint',
            usage: {
              promptTokens: result.usage.promptTokens,
              completionTokens: result.usage.completionTokens,
              estimatedCost: result.usage.estimatedCost,
            },
          },
          { status: 500 }
        );
      }

      return NextResponse.json({
        success: true,
        hint,
        usage: {
          promptTokens: result.usage.promptTokens,
          completionTokens: result.usage.completionTokens,
          estimatedCost: result.usage.estimatedCost,
        },
      });
    }
  } catch (error) {
    console.error('Hint generation error:', error);

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
    endpoint: '/api/generate/hint',
    method: 'POST',
    description: 'Generate study hints for flashcards',
    body: {
      card: 'FlashCard object (required)',
      progressive: 'boolean (optional, default: false)',
    },
  });
}
