import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { patternParser } from '@/lib/pattern-parser';
import { generateStructuredJSON, estimateTokenCount } from '@/lib/openai-client';
import { generateQuizHintPrompt } from '@/lib/prompts/quiz-prompt';
import { createSystemMessage, createUserMessage } from '@/lib/openai-client';
import { HintResponse } from '@/types/learning';

/**
 * POST /api/generate/hint
 *
 * Generate helpful hints using GPT-4o-mini (cost-effective model).
 * Returns contextual hints without giving away the answer.
 * Uses minimal tokens to keep costs low.
 */

// Request validation schema
const HintRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  context: z.string().min(1, 'Context is required'),
  userProgress: z.string().optional().default(''),
});

// Response validation schema
const HintResponseSchema = z.object({
  hint: z.string(),
  relatedConcepts: z.array(z.string()),
});

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = HintRequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.issues,
        },
        { status: 400 }
      );
    }

    const { patternId, context, userProgress } = validationResult.data;

    // Load pattern data
    const pattern = patternParser.getPatternById(patternId);
    if (!pattern) {
      return NextResponse.json(
        { error: `Pattern not found: ${patternId}` },
        { status: 404 }
      );
    }

    // Build hint generation prompt
    const systemMessage = `You are a helpful learning assistant providing hints for Workday expertise training.
Your hints should:
- Guide thinking without giving away answers
- Reference relevant best practices
- Encourage critical thinking
- Be concise (1-2 sentences maximum)

Never reveal the direct answer. Help learners discover it themselves.`;

    const userMessage = `A learner is struggling with this question about "${pattern.name}":

CONTEXT: ${context}

USER PROGRESS: ${userProgress || 'No attempts yet'}

RELEVANT BEST PRACTICES:
${pattern.best_practices.slice(0, 3).map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

Provide a helpful hint that guides thinking without revealing the answer.

Respond with JSON:
{
  "hint": "Your helpful hint here (1-2 sentences)",
  "relatedConcepts": ["concept1", "concept2"]
}`;

    // Generate hint using GPT-4o-mini (cost-effective)
    const hintData = await generateStructuredJSON<typeof HintResponseSchema._type>({
      messages: [
        createSystemMessage(systemMessage),
        createUserMessage(userMessage),
      ],
      model: 'gpt-4o-mini',
      temperature: 0.7,
      maxTokens: 150, // Keep it concise for cost savings
      operation: 'hint-generation',
    });

    // Validate response
    const parsedHint = HintResponseSchema.parse(hintData);

    // Estimate cost for this request
    const inputTokens = estimateTokenCount(systemMessage + userMessage);
    const outputTokens = estimateTokenCount(JSON.stringify(parsedHint));
    const estimatedCost =
      (inputTokens / 1_000_000) * 0.15 + // $0.15 per 1M input tokens
      (outputTokens / 1_000_000) * 0.6; // $0.60 per 1M output tokens

    const response: HintResponse = {
      hint: parsedHint.hint,
      relatedConcepts: parsedHint.relatedConcepts,
      costEstimate: estimatedCost,
    };

    // Log hint generation
    if (process.env.NODE_ENV === 'development') {
      console.log('[Hint API]', {
        patternId,
        contextLength: context.length,
        hintLength: parsedHint.hint.length,
        estimatedCost: `$${estimatedCost.toFixed(6)}`,
      });
    }

    return NextResponse.json(response, {
      status: 200,
      headers: {
        'Cache-Control': 'private, no-cache', // Don't cache hints
      },
    });
  } catch (error) {
    console.error('[Hint API] Error:', error);

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
        error: 'Failed to generate hint',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
