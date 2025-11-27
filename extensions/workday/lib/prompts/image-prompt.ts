import { Pattern } from '@/types/pattern';

/**
 * Image Generation Prompt Templates
 *
 * DALL-E 3 prompt engineering templates for generating relevant,
 * professional illustrations for scenarios and patterns.
 */

/**
 * Generate DALL-E prompt for scenario illustration
 * @param scenarioTitle - Scenario title
 * @param scenarioDescription - Scenario description
 * @param pattern - Source pattern
 * @returns Optimized DALL-E prompt
 */
export function generateScenarioImagePrompt(
  scenarioTitle: string,
  scenarioDescription: string,
  pattern: Pattern
): string {
  // Extract key visual elements from scenario
  const category = pattern.category.toLowerCase();
  const context = pattern.applies_to[0] || 'enterprise software';

  return `Professional business illustration showing ${scenarioTitle.toLowerCase()}.

Scene: ${scenarioDescription.substring(0, 200)}

Style: Modern, clean, professional business illustration with flat design aesthetic. Use a cohesive color palette with blues, grays, and accent colors. Isometric perspective preferred.

Elements:
- Professional office environment
- ${getCategoryVisualElements(category)}
- People working collaboratively at computers
- Abstract representations of ${context} workflows
- Clean, minimalist style without text or UI elements

Mood: Professional, educational, optimistic

Quality: High detail, suitable for educational content

IMPORTANT: Do NOT include:
- Actual Workday UI screenshots or specific interface elements
- Text, labels, or written content
- Branded logos or trademarks
- Photorealistic people faces`;
}

/**
 * Generate DALL-E prompt for pattern concept illustration
 * @param pattern - Pattern data
 * @returns Optimized DALL-E prompt
 */
export function generatePatternImagePrompt(pattern: Pattern): string {
  const category = pattern.category.toLowerCase();
  const visualMetaphor = getPatternVisualMetaphor(pattern);

  return `Professional conceptual illustration representing "${pattern.name}".

Concept: ${pattern.description.substring(0, 200)}

Visual metaphor: ${visualMetaphor}

Style: Modern flat design illustration with isometric perspective. Clean, professional, educational. Use a cohesive color palette appropriate for ${category}.

Elements:
- ${getCategoryVisualElements(category)}
- Abstract representations of best practices
- Professional business environment
- Visual hierarchy showing concept flow
- Minimalist, icon-like quality

Mood: Professional, clear, instructive

Quality: High detail, vector-art quality, suitable for educational materials

IMPORTANT: Do NOT include:
- Text, labels, numbers, or written content
- Actual software screenshots or UI elements
- Photorealistic elements
- Branded logos`;
}

/**
 * Generate DALL-E prompt for achievement badge
 * @param achievementName - Achievement name
 * @param achievementDescription - Achievement description
 * @returns Optimized DALL-E prompt
 */
export function generateAchievementBadgePrompt(
  achievementName: string,
  achievementDescription: string
): string {
  return `Design a professional achievement badge for "${achievementName}".

Description: ${achievementDescription}

Style: Modern, flat design badge icon with clean lines and professional aesthetic. Suitable for digital certificates and learning platforms.

Elements:
- Circular or shield-shaped badge
- Relevant symbolic icon in center (trophy, star, ribbon, medal)
- Subtle gradient or solid color scheme
- Professional color palette (gold, silver, blue, green)
- Clean, minimalist design
- Suitable for 256x256px icon

Mood: Accomplished, professional, prestigious

IMPORTANT: Do NOT include:
- Text or numbers
- Overly complex details
- Photorealistic elements
- More than 3-4 colors`;
}

/**
 * Generate DALL-E prompt for error/empty state illustration
 * @param context - Error context
 * @returns Optimized DALL-E prompt
 */
export function generateEmptyStatePrompt(context: 'no-content' | 'error' | 'loading'): string {
  const prompts = {
    'no-content': `Friendly empty state illustration showing an empty workspace or folder.

Style: Minimalist, friendly, modern flat design. Light, optimistic color palette.

Elements:
- Empty desk or workspace
- Subtle icons suggesting learning content
- Welcoming, non-threatening aesthetic
- Simple geometric shapes

Mood: Encouraging, friendly, clean`,

    'error': `Friendly error state illustration showing a minor technical hiccup.

Style: Minimalist, approachable, modern flat design. Soft colors, non-alarming.

Elements:
- Confused but friendly character or icon
- Disconnected puzzle pieces or broken connection symbol
- Gentle, non-threatening visual language
- Clean, simple composition

Mood: Reassuring, helpful, problem-solvable`,

    'loading': `Modern loading state illustration showing progress or activity.

Style: Abstract, dynamic, modern flat design. Energetic color palette.

Elements:
- Abstract shapes suggesting movement or progress
- Circular or flowing composition
- Sense of activity without specific detail
- Clean, professional aesthetic

Mood: Active, progressive, patient`,
  };

  return `${prompts[context]}

IMPORTANT: Do NOT include:
- Text, labels, or error codes
- Photorealistic elements
- Scary or alarming imagery
- Branded elements`;
}

/**
 * Get category-specific visual elements
 * @param category - Pattern category
 * @returns Visual elements description
 */
function getCategoryVisualElements(category: string): string {
  const elements: Record<string, string> = {
    'security': 'Lock icons, shield symbols, secure connections, encrypted data visualizations',
    'architecture': 'Building blocks, structural diagrams, connected systems, modular components',
    'performance': 'Speed indicators, optimization symbols, efficient workflows, streamlined processes',
    'quality assurance': 'Checkmarks, verification symbols, testing equipment, quality metrics',
    'ui/ux': 'User interface elements, mobile devices, responsive layouts, user interactions',
    'testing': 'Testing tools, verification processes, quality control symbols, bug detection',
    'accessibility': 'Universal access symbols, inclusive design elements, diverse users, assistive technology',
    'error handling': 'Exception handling, error recovery, alert systems, resilient systems',
    'monitoring': 'Dashboards, metrics, analytics, monitoring screens, data visualization',
    'reliability': 'Stable systems, redundancy, backup processes, fault tolerance symbols',
  };

  return elements[category] || 'Professional business and technology symbols';
}

/**
 * Get visual metaphor for pattern concept
 * @param pattern - Pattern data
 * @returns Visual metaphor description
 */
function getPatternVisualMetaphor(pattern: Pattern): string {
  const name = pattern.name.toLowerCase();

  // Mapping patterns to visual metaphors
  if (name.includes('validation')) {
    return 'Checkpoint or verification gate with items being inspected';
  }
  if (name.includes('cache') || name.includes('tier')) {
    return 'Multi-level storage shelves or layered containers';
  }
  if (name.includes('test')) {
    return 'Quality control checkpoint or scientific testing environment';
  }
  if (name.includes('mobile') || name.includes('responsive')) {
    return 'Content flowing across different sized screens';
  }
  if (name.includes('accessibility')) {
    return 'Universal access with diverse users successfully using technology';
  }
  if (name.includes('error') || name.includes('graceful')) {
    return 'Safety net or cushioned landing catching falling objects';
  }
  if (name.includes('cost') || name.includes('budget')) {
    return 'Efficient resource allocation or optimization system';
  }
  if (name.includes('progressive')) {
    return 'Foundation building up with enhanced layers';
  }

  // Default metaphor
  return 'Professional workflow or process diagram showing best practices in action';
}

/**
 * Validate image prompt length (DALL-E has limits)
 * @param prompt - Generated prompt
 * @returns Validated prompt (truncated if needed)
 */
export function validateImagePrompt(prompt: string): string {
  const MAX_LENGTH = 4000; // DALL-E 3 limit

  if (prompt.length <= MAX_LENGTH) {
    return prompt;
  }

  console.warn(`Image prompt exceeded ${MAX_LENGTH} characters, truncating...`);
  return prompt.substring(0, MAX_LENGTH - 3) + '...';
}

/**
 * Get recommended image parameters for different use cases
 */
export const IMAGE_PRESETS = {
  scenario: {
    size: '1792x1024' as const,
    quality: 'standard' as const,
  },
  pattern: {
    size: '1024x1024' as const,
    quality: 'standard' as const,
  },
  achievement: {
    size: '1024x1024' as const,
    quality: 'hd' as const,
  },
  emptyState: {
    size: '1024x1024' as const,
    quality: 'standard' as const,
  },
} as const;
