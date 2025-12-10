/**
 * Transcript Loader
 *
 * Loads transcript files from the data directory.
 * Works both at build time (Node.js) and runtime (browser).
 */

import {
  type TranscriptFile,
  type TranscriptMetadata,
  createTranscriptMetadata,
} from '@/types/transcript';

/**
 * List of transcript filenames (hardcoded for browser compatibility)
 * In a full implementation, this would be generated at build time
 */
export const TRANSCRIPT_FILES = [
  'Workday - Building a Career with Workday Technology Learn with Workday - 2025-04-09.txt',
  'Workday - How Candidates Apply for Jobs Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Access Reports Workday Analytics and Reporting - 2025-08-11.txt',
  'Workday - How to Access Reports and Performance Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - How to Access and View Discovery Boards Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - How to Create Courses Workday Learning - 2025-08-12.txt',
  'Workday - How to Create Learning Rules Workday Learning - 2025-08-15.txt',
  'Workday - How to Create Programs Workday Learning - 2025-08-15.txt',
  'Workday - How to Create Prospects & Candidates Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Create Referrals Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Create a Simple Discovery Board Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - How to Create and Copy Job Requisitions Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Create and Update Job Postings Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Enhance Media Files and Create Lessons Workday Learning - 2025-08-15.txt',
  'Workday - How to Hire a Worker Workday HCM - 2025-11-03.txt',
  'Workday - How to Initiate a Change Job Workday Workday HCM - 2025-11-03.txt',
  'Workday - How to Initiate a Termination Workday HCM - 2025-11-03.txt',
  'Workday - How to Interact with Dashboards and Worklets Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - How to Interact with a Report Workday Analytics and Reporting - 2025-08-11.txt',
  'Workday - How to Manage Candidates Workday Recruiting - 2025-09-25.txt',
  'Workday - How to Manage Contingent Workers Workday HCM - 2025-11-03.txt',
  'Workday - How to Manage Enrollments Workday Learning - 2025-08-15.txt',
  'Workday - How to Manage Events Workday HCM - 2025-11-03.txt',
  'Workday - How to Manage Job Requisitions Workday Recruiting - 2025-08-15.txt',
  'Workday - How to Manage Learning Completions Workday Learning - 2025-08-15.txt',
  'Workday - How to Manage Offerings Workday Learning - 2025-08-15.txt',
  'Workday - How to Manage Positions Workday HCM - 2025-11-03.txt',
  'Workday - How to Manage a Supervisory Organization Workday HCM - 2025-11-03.txt',
  'Workday - How to Manage the Job Application Business Process Workday Recruiting - 2025-09-25.txt',
  'Workday - How to Navigate Workday Workday HCM - 2025-11-03.txt',
  'Workday - How to Navigate the Job Application Business Process Workday Recruiting - 2025-09-25.txt',
  'Workday - How to Schedule Reports Workday Analytics and Reporting - 2025-08-11.txt',
  'Workday - How to Search Workday HCM - 2025-11-03.txt',
  'Workday - How to Understand the Report Output Workday Analytics and Reporting - 2025-08-11.txt',
  'Workday - How to Use Different Report Types Workday Analytics and Reporting - 2025-08-11.txt',
  'Workday - How to Use People Analytics Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - How to Use Worksheets Workday Analytics and Reporting - 2025-07-25.txt',
  'Workday - What is a Workday Platform Administrator Learn with Workday - 2025-10-30.txt',
];

/**
 * Base path for transcript files
 */
const TRANSCRIPT_BASE_PATH = '/data/transcripts';

/**
 * Load a single transcript file (browser runtime)
 * Fetches from the public data directory
 */
export async function loadTranscriptContent(filename: string): Promise<string> {
  const response = await fetch(`${TRANSCRIPT_BASE_PATH}/${encodeURIComponent(filename)}`);

  if (!response.ok) {
    throw new Error(`Failed to load transcript: ${filename}`);
  }

  return response.text();
}

/**
 * Load a transcript with metadata
 */
export async function loadTranscript(filename: string): Promise<TranscriptFile> {
  const content = await loadTranscriptContent(filename);
  const metadata = createTranscriptMetadata(filename, content);

  return {
    filename,
    path: `${TRANSCRIPT_BASE_PATH}/${filename}`,
    content,
    metadata,
  };
}

/**
 * Load all transcripts
 */
export async function loadAllTranscripts(): Promise<TranscriptFile[]> {
  const transcripts: TranscriptFile[] = [];

  for (const filename of TRANSCRIPT_FILES) {
    try {
      const transcript = await loadTranscript(filename);
      transcripts.push(transcript);
    } catch (error) {
      console.error(`Failed to load transcript: ${filename}`, error);
    }
  }

  return transcripts;
}

/**
 * Get transcript metadata without loading content
 */
export function getTranscriptMetadataList(): TranscriptMetadata[] {
  return TRANSCRIPT_FILES.map((filename) => {
    // Create metadata with placeholder values for line/character count
    return {
      id: generateTranscriptIdFromFilename(filename),
      filename,
      title: extractTitleFromFilename(filename),
      category: extractCategoryFromFilename(filename),
      date: extractDateFromFilename(filename),
      lineCount: 0, // Will be populated when content is loaded
      characterCount: 0,
    };
  });
}

/**
 * Helper function to generate transcript ID from filename
 */
function generateTranscriptIdFromFilename(filename: string): string {
  let hash = 0;
  for (let i = 0; i < filename.length; i++) {
    const char = filename.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return `transcript_${Math.abs(hash).toString(16)}`;
}

/**
 * Helper to extract title from filename
 */
function extractTitleFromFilename(filename: string): string {
  let title = filename.replace(/^Workday - /, '');
  title = title.replace(
    / (Workday HCM|Workday Recruiting|Workday Learning|Analytics and Reporting|Learn with Workday)/,
    ''
  );
  title = title.replace(/ - \d{4}-\d{2}-\d{2}\.txt$/, '');
  title = title.replace(/\.txt$/, '');
  return title.trim();
}

/**
 * Helper to extract category from filename
 */
function extractCategoryFromFilename(
  filename: string
): 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General' {
  if (/Workday HCM/i.test(filename)) return 'HCM';
  if (/Workday Recruiting/i.test(filename)) return 'Recruiting';
  if (/Workday Learning/i.test(filename)) return 'Learning';
  if (/Analytics and Reporting/i.test(filename)) return 'Analytics';
  if (/Learn with Workday/i.test(filename)) return 'General';
  return 'General';
}

/**
 * Helper to extract date from filename
 */
function extractDateFromFilename(filename: string): string {
  const dateMatch = filename.match(/(\d{4}-\d{2}-\d{2})/);
  return dateMatch ? dateMatch[1] : new Date().toISOString().split('T')[0];
}

/**
 * Get transcript count by category
 */
export function getTranscriptCountByCategory(): Record<string, number> {
  const counts: Record<string, number> = {
    HCM: 0,
    Recruiting: 0,
    Learning: 0,
    Analytics: 0,
    General: 0,
  };

  for (const filename of TRANSCRIPT_FILES) {
    const category = extractCategoryFromFilename(filename);
    counts[category]++;
  }

  return counts;
}
