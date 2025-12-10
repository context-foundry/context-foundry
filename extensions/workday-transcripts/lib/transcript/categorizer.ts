/**
 * Transcript Categorizer
 *
 * Maps transcripts and their content to Workday categories.
 */

import { type WorkdayCategory } from '@/types/card';
import { type TranscriptMetadata, type Concept } from '@/types/transcript';

/**
 * Category definitions with keywords
 */
export const CATEGORY_DEFINITIONS: Record<
  WorkdayCategory,
  {
    name: string;
    description: string;
    keywords: string[];
    color: string;
    icon: string;
  }
> = {
  HCM: {
    name: 'Human Capital Management',
    description: 'Core HR functions including hiring, termination, job changes, and worker management',
    keywords: [
      'worker', 'employee', 'hire', 'terminate', 'termination', 'job change',
      'position', 'supervisory organization', 'contingent', 'staffing',
      'compensation', 'benefit', 'payroll', 'time off', 'absence',
      'manager', 'direct report', 'team', 'organization chart',
    ],
    color: 'blue',
    icon: 'Users',
  },
  Recruiting: {
    name: 'Recruiting',
    description: 'Job requisitions, candidate management, and hiring workflows',
    keywords: [
      'requisition', 'job requisition', 'candidate', 'applicant', 'application',
      'job posting', 'interview', 'offer', 'prospect', 'referral',
      'talent pool', 'source', 'recruiting', 'hiring manager',
      'job application', 'disposition', 'screening',
    ],
    color: 'purple',
    icon: 'UserPlus',
  },
  Learning: {
    name: 'Learning',
    description: 'Training courses, programs, enrollments, and learning management',
    keywords: [
      'course', 'lesson', 'program', 'curriculum', 'training',
      'enrollment', 'offering', 'instructor', 'learner', 'learning path',
      'completion', 'certification', 'assessment', 'quiz', 'content',
      'media', 'video', 'blended', 'self-paced',
    ],
    color: 'green',
    icon: 'GraduationCap',
  },
  Analytics: {
    name: 'Analytics & Reporting',
    description: 'Reports, dashboards, discovery boards, and data analysis',
    keywords: [
      'report', 'dashboard', 'worklet', 'analytics', 'data',
      'discovery board', 'worksheet', 'chart', 'graph', 'metric',
      'KPI', 'insight', 'visualization', 'filter', 'drill down',
      'export', 'schedule', 'people analytics',
    ],
    color: 'orange',
    icon: 'BarChart',
  },
  General: {
    name: 'General',
    description: 'Navigation, search, and platform fundamentals',
    keywords: [
      'navigation', 'search', 'home', 'inbox', 'to do', 'task',
      'notification', 'profile', 'menu', 'settings', 'preference',
      'career', 'technology', 'platform', 'administrator',
    ],
    color: 'gray',
    icon: 'Layout',
  },
};

/**
 * Get category definition
 */
export function getCategoryDefinition(category: WorkdayCategory) {
  return CATEGORY_DEFINITIONS[category];
}

/**
 * Get all categories with definitions
 */
export function getAllCategories() {
  return Object.entries(CATEGORY_DEFINITIONS).map(([key, value]) => ({
    id: key as WorkdayCategory,
    ...value,
  }));
}

/**
 * Categorize content based on keyword matching
 */
export function categorizeContent(content: string): WorkdayCategory {
  const lowerContent = content.toLowerCase();
  const scores: Record<WorkdayCategory, number> = {
    HCM: 0,
    Recruiting: 0,
    Learning: 0,
    Analytics: 0,
    General: 0,
  };

  // Count keyword matches for each category
  for (const [category, definition] of Object.entries(CATEGORY_DEFINITIONS)) {
    for (const keyword of definition.keywords) {
      const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
      const matches = lowerContent.match(regex);
      if (matches) {
        scores[category as WorkdayCategory] += matches.length;
      }
    }
  }

  // Find category with highest score
  let maxCategory: WorkdayCategory = 'General';
  let maxScore = 0;

  for (const [category, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      maxCategory = category as WorkdayCategory;
    }
  }

  return maxCategory;
}

/**
 * Get related categories for a transcript
 */
export function getRelatedCategories(
  transcript: TranscriptMetadata,
  content: string
): WorkdayCategory[] {
  const lowerContent = content.toLowerCase();
  const related: WorkdayCategory[] = [transcript.category];

  // Check for content from other categories
  for (const [category, definition] of Object.entries(CATEGORY_DEFINITIONS)) {
    if (category === transcript.category) continue;

    const matchCount = definition.keywords.filter((keyword) =>
      lowerContent.includes(keyword.toLowerCase())
    ).length;

    // If significant keyword matches, consider it related
    if (matchCount >= 3) {
      related.push(category as WorkdayCategory);
    }
  }

  return related;
}

/**
 * Categorize a concept
 */
export function categorizeConcept(concept: Concept): WorkdayCategory {
  // Combine name, definition, and context for categorization
  const textToAnalyze = [
    concept.name,
    concept.definition || '',
    concept.context,
  ].join(' ');

  return categorizeContent(textToAnalyze);
}

/**
 * Get category statistics from transcripts
 */
export function getCategoryStats(transcripts: TranscriptMetadata[]): {
  category: WorkdayCategory;
  count: number;
  percentage: number;
}[] {
  const counts: Record<WorkdayCategory, number> = {
    HCM: 0,
    Recruiting: 0,
    Learning: 0,
    Analytics: 0,
    General: 0,
  };

  for (const transcript of transcripts) {
    counts[transcript.category]++;
  }

  const total = transcripts.length;

  return Object.entries(counts).map(([category, count]) => ({
    category: category as WorkdayCategory,
    count,
    percentage: total > 0 ? Math.round((count / total) * 100) : 0,
  }));
}

/**
 * Group transcripts by category
 */
export function groupTranscriptsByCategory(
  transcripts: TranscriptMetadata[]
): Record<WorkdayCategory, TranscriptMetadata[]> {
  const grouped: Record<WorkdayCategory, TranscriptMetadata[]> = {
    HCM: [],
    Recruiting: [],
    Learning: [],
    Analytics: [],
    General: [],
  };

  for (const transcript of transcripts) {
    grouped[transcript.category].push(transcript);
  }

  return grouped;
}
