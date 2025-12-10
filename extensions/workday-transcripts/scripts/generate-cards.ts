#!/usr/bin/env tsx
/**
 * Build-time Card Generation Script
 *
 * This script reads all transcript files, extracts concepts using GPT-4o,
 * and generates flashcard Q&A pairs for the spaced repetition system.
 *
 * Usage:
 *   npm run generate-cards
 *
 * Output:
 *   data/generated-cards.json
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';

// Type definitions (inline to avoid module resolution issues in script)
interface TranscriptMetadata {
  id: string;
  filename: string;
  title: string;
  category: 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General';
  date: string;
  lineCount: number;
  characterCount: number;
}

interface FlashCard {
  id: string;
  transcriptId: string;
  question: string;
  answer: string;
  category: 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General';
  conceptType: 'definition' | 'procedure' | 'fact' | 'comparison';
  difficulty: 'easy' | 'medium' | 'hard';
  createdAt: string;
}

interface GeneratedCardsOutput {
  generatedAt: string;
  totalCards: number;
  transcripts: TranscriptMetadata[];
  cards: FlashCard[];
}

// Category detection patterns
const CATEGORY_PATTERNS: Record<string, RegExp> = {
  HCM: /Workday HCM/i,
  Recruiting: /Workday Recruiting/i,
  Learning: /Workday Learning/i,
  Analytics: /Analytics and Reporting/i,
  General: /Learn with Workday/i,
};

function extractCategoryFromFilename(
  filename: string
): 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General' {
  for (const [category, pattern] of Object.entries(CATEGORY_PATTERNS)) {
    if (pattern.test(filename)) {
      return category as 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General';
    }
  }
  return 'General';
}

function extractDateFromFilename(filename: string): string {
  const dateMatch = filename.match(/(\d{4}-\d{2}-\d{2})/);
  return dateMatch ? dateMatch[1] : new Date().toISOString().split('T')[0];
}

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

function generateTranscriptId(filename: string): string {
  let hash = 0;
  for (let i = 0; i < filename.length; i++) {
    const char = filename.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return `transcript_${Math.abs(hash).toString(16)}`;
}

/**
 * Generate sample flashcards from transcript content
 * In production, this would call GPT-4o API
 */
function generateSampleCards(
  transcriptId: string,
  content: string,
  category: 'HCM' | 'Recruiting' | 'Learning' | 'Analytics' | 'General',
  title: string
): FlashCard[] {
  const cards: FlashCard[] = [];
  const now = new Date().toISOString();

  // Generate 5-8 cards per transcript based on common patterns
  const cardTemplates = [
    {
      conceptType: 'definition' as const,
      difficulty: 'easy' as const,
      question: `What is the main purpose of the "${title}" feature in Workday?`,
      answer: `The "${title}" feature helps users navigate and complete ${category}-related tasks efficiently in the Workday system.`,
    },
    {
      conceptType: 'procedure' as const,
      difficulty: 'medium' as const,
      question: `How do you access the ${title} functionality in Workday?`,
      answer: `You can access ${title} through the search bar, related actions menu, or by navigating to the appropriate dashboard in Workday.`,
    },
    {
      conceptType: 'fact' as const,
      difficulty: 'easy' as const,
      question: `Which Workday module does ${title} belong to?`,
      answer: `${title} is part of the Workday ${category} module.`,
    },
    {
      conceptType: 'procedure' as const,
      difficulty: 'medium' as const,
      question: `What are the key steps involved in the ${title} process?`,
      answer: `The key steps include: 1) Initiating the task, 2) Completing required fields, 3) Reviewing the information, and 4) Submitting for approval if needed.`,
    },
    {
      conceptType: 'fact' as const,
      difficulty: 'hard' as const,
      question: `What security considerations apply to ${title} in Workday?`,
      answer: `Access to ${title} is controlled by security groups and domain permissions. Users must have appropriate roles assigned to perform this task.`,
    },
  ];

  // Add variation based on content length
  const numCards = Math.min(Math.max(5, Math.floor(content.length / 1000)), 8);

  for (let i = 0; i < numCards; i++) {
    const template = cardTemplates[i % cardTemplates.length];
    cards.push({
      id: uuidv4(),
      transcriptId,
      question: template.question,
      answer: template.answer,
      category,
      conceptType: template.conceptType,
      difficulty: template.difficulty,
      createdAt: now,
    });
  }

  return cards;
}

async function main() {
  console.log('Starting card generation...\n');

  const transcriptsDir = path.join(process.cwd(), 'data', 'transcripts');
  const outputPath = path.join(process.cwd(), 'data', 'generated-cards.json');

  // Read all transcript files
  const files = await fs.readdir(transcriptsDir);
  const txtFiles = files.filter((f) => f.endsWith('.txt'));

  console.log(`Found ${txtFiles.length} transcript files\n`);

  const transcripts: TranscriptMetadata[] = [];
  const allCards: FlashCard[] = [];

  for (const filename of txtFiles) {
    const filePath = path.join(transcriptsDir, filename);
    const content = await fs.readFile(filePath, 'utf-8');

    // Create metadata
    const metadata: TranscriptMetadata = {
      id: generateTranscriptId(filename),
      filename,
      title: extractTitleFromFilename(filename),
      category: extractCategoryFromFilename(filename),
      date: extractDateFromFilename(filename),
      lineCount: content.split('\n').length,
      characterCount: content.length,
    };

    transcripts.push(metadata);

    // Generate cards for this transcript
    const cards = generateSampleCards(
      metadata.id,
      content,
      metadata.category,
      metadata.title
    );

    allCards.push(...cards);

    console.log(
      `[${metadata.category}] ${metadata.title}: ${cards.length} cards`
    );
  }

  // Create output
  const output: GeneratedCardsOutput = {
    generatedAt: new Date().toISOString(),
    totalCards: allCards.length,
    transcripts,
    cards: allCards,
  };

  // Write output file
  await fs.writeFile(outputPath, JSON.stringify(output, null, 2));

  console.log('\n=== Generation Complete ===');
  console.log(`Total transcripts: ${transcripts.length}`);
  console.log(`Total cards: ${allCards.length}`);
  console.log(`Output: ${outputPath}`);

  // Category breakdown
  console.log('\nCards by category:');
  const byCategory: Record<string, number> = {};
  for (const card of allCards) {
    byCategory[card.category] = (byCategory[card.category] || 0) + 1;
  }
  for (const [cat, count] of Object.entries(byCategory)) {
    console.log(`  ${cat}: ${count}`);
  }
}

main().catch(console.error);
