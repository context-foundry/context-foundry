import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { patternParser } from '@/lib/pattern-parser';
import { generateStructuredJSON } from '@/lib/openai-client';
import { generateScenarioPrompt, getScenarioSystemMessage } from '@/lib/prompts/scenario-prompt';
import { generateScenarioCacheKey } from '@/lib/cache/cache-keys';
import { getOrSetServerCache } from '@/lib/cache/server-cache';
import { ScenarioSchema, Scenario } from '@/types/learning';
import { validateScenario } from '@/lib/validation/content-validator';
import { createSystemMessage, createUserMessage } from '@/lib/openai-client';

/**
 * POST /api/generate/scenario
 *
 * Generate interactive branching scenario for a pattern using GPT-4o.
 * Implements three-tier caching strategy with server-side KV cache (Tier 3).
 */

// Request validation schema
const ScenarioRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  simple: z.boolean().optional(),
});

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = ScenarioRequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.issues,
        },
        { status: 400 }
      );
    }

    const { patternId, simple } = validationResult.data;

    // Load pattern data
    const pattern = patternParser.getPatternById(patternId);
    if (!pattern) {
      return NextResponse.json(
        { error: `Pattern not found: ${patternId}` },
        { status: 404 }
      );
    }

    // Generate cache key
    const cacheKey = generateScenarioCacheKey(patternId, { simple });

    // Try to get from server cache (Tier 3)
    const cachedResult = await getOrSetServerCache<Scenario>(
      cacheKey,
      async () => {
        // Generate new scenario with GPT-4o
        const prompt = generateScenarioPrompt(pattern);
        const systemMessage = getScenarioSystemMessage();

        const scenarioData = await generateStructuredJSON<Scenario>({
          messages: [
            createSystemMessage(systemMessage),
            createUserMessage(prompt),
          ],
          model: 'gpt-4o',
          temperature: 0.7,
          maxTokens: 4000,
          operation: 'scenario-generation',
        });

        // Validate generated scenario
        const validation = validateScenario(scenarioData, pattern);

        if (!validation.isValid) {
          console.error('[Scenario API] Validation failed:', validation);
          throw new Error(
            `Generated scenario failed validation: ${validation.regenerationReason || 'Unknown error'}`
          );
        }

        // Parse and validate with Zod schema
        const scenario = ScenarioSchema.parse({
          ...scenarioData,
          cacheSource: 'generated',
        });

        return scenario;
      }
    );

    // Determine cache source
    const cacheSource = cachedResult.cached ? 'tier3' : 'generated';
    const scenario: Scenario = {
      ...cachedResult.value,
      cacheSource,
    };

    // Log cache performance
    if (process.env.NODE_ENV === 'development') {
      console.log('[Scenario API]', {
        patternId,
        cacheSource,
        cached: cachedResult.cached,
        nodeCount: scenario.nodes.length,
      });
    }

    return NextResponse.json(scenario, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=604800, stale-while-revalidate=86400',
      },
    });
  } catch (error) {
    console.error('[Scenario API] Error:', error);

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
        error: 'Failed to generate scenario',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
