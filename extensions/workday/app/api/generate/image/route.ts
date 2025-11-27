import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { patternParser } from '@/lib/pattern-parser';
import { generateImage } from '@/lib/openai-client';
import {
  generateScenarioImagePrompt,
  generatePatternImagePrompt,
  generateAchievementBadgePrompt,
  validateImagePrompt,
  IMAGE_PRESETS,
} from '@/lib/prompts/image-prompt';

/**
 * POST /api/generate/image
 *
 * Generate images using DALL-E 3 for scenarios, patterns, or achievements.
 * No caching - images are expensive and generated on-demand only.
 */

// Request validation schema
const ImageRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  type: z.enum(['scenario', 'pattern', 'achievement'], {
    errorMap: () => ({ message: 'Type must be scenario, pattern, or achievement' }),
  }),
  scenarioTitle: z.string().optional(),
  scenarioDescription: z.string().optional(),
  achievementName: z.string().optional(),
  achievementDescription: z.string().optional(),
});

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = ImageRequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.issues,
        },
        { status: 400 }
      );
    }

    const {
      patternId,
      type,
      scenarioTitle,
      scenarioDescription,
      achievementName,
      achievementDescription,
    } = validationResult.data;

    // Load pattern data
    const pattern = patternParser.getPatternById(patternId);
    if (!pattern) {
      return NextResponse.json(
        { error: `Pattern not found: ${patternId}` },
        { status: 404 }
      );
    }

    // Validate required fields based on type
    if (type === 'scenario' && (!scenarioTitle || !scenarioDescription)) {
      return NextResponse.json(
        {
          error: 'scenarioTitle and scenarioDescription are required for scenario images',
        },
        { status: 400 }
      );
    }

    if (type === 'achievement' && (!achievementName || !achievementDescription)) {
      return NextResponse.json(
        {
          error: 'achievementName and achievementDescription are required for achievement images',
        },
        { status: 400 }
      );
    }

    // Generate appropriate prompt based on type
    let imagePrompt: string;
    switch (type) {
      case 'scenario':
        imagePrompt = generateScenarioImagePrompt(
          scenarioTitle!,
          scenarioDescription!,
          pattern
        );
        break;
      case 'pattern':
        imagePrompt = generatePatternImagePrompt(pattern);
        break;
      case 'achievement':
        imagePrompt = generateAchievementBadgePrompt(
          achievementName!,
          achievementDescription!
        );
        break;
    }

    // Validate and truncate prompt if needed
    imagePrompt = validateImagePrompt(imagePrompt);

    // Get image generation parameters
    const preset = IMAGE_PRESETS[type];

    // Generate image with DALL-E 3
    const imageUrl = await generateImage({
      prompt: imagePrompt,
      size: preset.size,
      quality: preset.quality,
      operation: `image-generation-${type}`,
    });

    // Return image URL and metadata
    const response = {
      imageUrl,
      metadata: {
        patternId,
        patternName: pattern.name,
        type,
        size: preset.size,
        quality: preset.quality,
        generatedAt: new Date().toISOString(),
      },
    };

    // Log generation
    if (process.env.NODE_ENV === 'development') {
      console.log('[Image API]', {
        patternId,
        type,
        size: preset.size,
        quality: preset.quality,
        promptLength: imagePrompt.length,
      });
    }

    return NextResponse.json(response, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=2592000', // 30 days
      },
    });
  } catch (error) {
    console.error('[Image API] Error:', error);

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

      if (error.message.includes('content policy')) {
        return NextResponse.json(
          {
            error: 'Image generation failed due to content policy violation',
            message: 'Please try a different pattern or modify the request',
          },
          { status: 400 }
        );
      }
    }

    return NextResponse.json(
      {
        error: 'Failed to generate image',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
