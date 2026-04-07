#!/usr/bin/env node
// Generates a new pixel art scene using the OpenAI API (GPT-4o-mini).
// Usage: node generate-scene.js [--dry-run] [--seed-id <id>]
// Requires OPENAI_API_KEY env var.

import OpenAI from 'openai';
import { readFileSync, writeFileSync, existsSync, unlinkSync, renameSync } from 'fs';
import { execFileSync } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

var __dirname = dirname(fileURLToPath(import.meta.url));
var docsDir = join(__dirname, '..', '..', 'docs');
var scenesDir = join(docsDir, 'scenes');
var manifestPath = join(scenesDir, 'manifest.json');
var seedsPath = join(__dirname, 'world-seeds.json');
var promptPath = join(__dirname, 'prompt-template.md');
var logPath = join(scenesDir, 'generation-log.json');

var dryRun = process.argv.includes('--dry-run');
var forceSeedId = null;
var seedIdx = process.argv.indexOf('--seed-id');
if (seedIdx !== -1 && process.argv[seedIdx + 1]) forceSeedId = process.argv[seedIdx + 1];

var MODEL = 'gpt-4o-mini';
var MAX_API_ATTEMPTS = 3;
var MAX_VALIDATION_ATTEMPTS = 2;
var MAX_SEEDS_PER_RUN = 3;
var API_RETRY_BASE_DELAY_MS = 2000;

// Load data
var manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
var seeds = JSON.parse(readFileSync(seedsPath, 'utf8'));
var promptTemplate = readFileSync(promptPath, 'utf8');

// Pick a seed -- avoid recently used biomes
var usedBiomes = manifest.scenes.slice(-10).map(function(s) { return s.biome; });
var usedIds = manifest.scenes.map(function(e) { return e.file.replace('.js', ''); });
var candidates = seeds.filter(function(s) {
  return !usedIds.includes(s.id);
});

if (!forceSeedId && candidates.length === 0) {
  console.log('All seeds exhausted. Exiting.');
  process.exit(0);
}

function pickWeightedSeed(weighted) {
  var totalWeight = weighted.reduce(function(sum, w) { return sum + w.weight; }, 0);
  var roll = Math.random() * totalWeight;
  var cumulative = 0;

  for (var w of weighted) {
    cumulative += w.weight;
    if (roll <= cumulative) return w.seed;
  }

  return weighted[weighted.length - 1].seed;
}

function planSeedAttempts(limit) {
  if (forceSeedId) {
    var forced = candidates.find(function(s) { return s.id === forceSeedId; });
    if (!forced) {
      console.error('Seed not found or already used: ' + forceSeedId);
      process.exit(1);
    }
    return [forced];
  }

  var remaining = candidates.slice();
  var recentBiomes = usedBiomes.slice();
  var plan = [];

  while (remaining.length > 0 && plan.length < limit) {
    var weighted = remaining.map(function(s) {
      var recentCount = recentBiomes.filter(function(b) { return b === s.biome; }).length;
      return { seed: s, weight: recentCount === 0 ? 10 : (recentCount === 1 ? 3 : 1) };
    });

    var selected = pickWeightedSeed(weighted);
    plan.push(selected);
    recentBiomes.push(selected.biome);
    remaining = remaining.filter(function(s) { return s.id !== selected.id; });
  }

  return plan;
}

var seedPlan = planSeedAttempts(Math.min(MAX_SEEDS_PER_RUN, candidates.length));

// Build the prompt
// Pick 2 example scenes (rotate based on seed to get variety)
var exampleFiles = ['foundry.js', 'exuma.js', 'atacama.js', 'challenger.js'];

if (dryRun) {
  console.log('\n--- DRY RUN ---');
  console.log('Seed plan: ' + seedPlan.map(function(s) { return s.id; }).join(', '));
  console.log('Output file would be: ' + join(scenesDir, seedPlan[0].id + '.js'));
  console.log('Prompt length: ' + buildPrompt(seedPlan[0]).length + ' chars');
  process.exit(0);
}

if (!process.env.OPENAI_API_KEY) {
  console.error('OPENAI_API_KEY is not set.');
  process.exit(1);
}

// Call OpenAI API
var client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
var startTime = Date.now();

function buildPrompt(seed) {
  var hash = seed.id.split('').reduce(function(h, c) { return ((h << 5) - h + c.charCodeAt(0)) | 0; }, 0);
  var ex1 = exampleFiles[Math.abs(hash) % exampleFiles.length];
  var ex2 = exampleFiles[Math.abs(hash + 1) % exampleFiles.length];
  if (ex1 === ex2) ex2 = exampleFiles[(Math.abs(hash) + 2) % exampleFiles.length];

  var example1 = readFileSync(join(scenesDir, ex1), 'utf8');
  var example2 = readFileSync(join(scenesDir, ex2), 'utf8');
  var exampleBlock = '## Example Scene 1 (' + ex1 + ')\n\n```javascript\n' + example1 + '\n```\n\n## Example Scene 2 (' + ex2 + ')\n\n```javascript\n' + example2 + '\n```';

  return promptTemplate
    .replace('{{EXAMPLE_SCENES}}', exampleBlock)
    .replace('{{SCENE_NAME}}', seed.name)
    .replace('{{SCENE_LOCATION}}', seed.location)
    .replace('{{BIOME}}', seed.biome)
    .replace('{{PALETTE}}', seed.palette.join(', '))
    .replace('{{ELEMENTS}}', seed.elements.join(', '))
    .replace('{{MOOD}}', seed.mood);
}

function sleep(ms) {
  return new Promise(function(resolve) {
    setTimeout(resolve, ms);
  });
}

function normalizeErrorMessage(error) {
  var raw = '';
  if (error && error.stderr) raw = error.stderr.toString();
  else if (error && error.message) raw = error.message;
  else if (typeof error === 'string') raw = error;

  raw = raw
    .split('\n')
    .map(function(line) { return line.trim(); })
    .filter(Boolean)
    .join('\n');

  if (!raw) return 'Unknown error';
  if (raw.length > 1200) return raw.slice(0, 1197) + '...';
  return raw;
}

function cleanupTempFile(tempFile) {
  if (!existsSync(tempFile)) return;
  try {
    unlinkSync(tempFile);
  } catch (e) {
    console.warn('Could not clean up temp file ' + tempFile + ': ' + e.message);
  }
}

function validateSceneFile(file) {
  execFileSync('node', [join(__dirname, 'validate-scene.js'), file], { stdio: 'pipe' });
}

function mergeResultTotals(total, next) {
  total.code = next.code;
  total.inputTokens += next.inputTokens;
  total.outputTokens += next.outputTokens;
  total.costUsd += next.costUsd;
}

async function generate(prompt, retryWithError) {
  var userContent = retryWithError
    ? prompt + '\n\n## RETRY -- Previous attempt had this error:\n' + retryWithError + '\n\nFix the error and regenerate the complete file.'
    : prompt;

  var response = await client.chat.completions.create({
    model: MODEL,
    max_tokens: 8192,
    messages: [
      { role: 'system', content: 'You are a pixel art scene generator. Output ONLY valid JavaScript code. No markdown fences, no explanation.' },
      { role: 'user', content: userContent },
    ],
  });

  var code = response.choices && response.choices[0] && response.choices[0].message
    ? response.choices[0].message.content
    : '';
  if (typeof code !== 'string' || code.trim() === '') {
    throw new Error('Model returned an empty completion.');
  }

  // Strip markdown fences if the model wrapped them
  code = code.replace(/^```(?:javascript|js)?\n?/, '').replace(/\n?```\s*$/, '');

  var usage = response.usage || {};
  var inputTokens = usage.prompt_tokens || 0;
  var outputTokens = usage.completion_tokens || 0;
  // GPT-4o-mini: $0.15/M input, $0.60/M output
  var costUsd = (inputTokens * 0.15 + outputTokens * 0.60) / 1000000;

  return { code: code, inputTokens: inputTokens, outputTokens: outputTokens, costUsd: costUsd };
}

async function generateWithRetries(prompt, retryWithError) {
  var lastError;

  for (var attempt = 1; attempt <= MAX_API_ATTEMPTS; attempt++) {
    try {
      var result = await generate(prompt, retryWithError);
      result.apiRetries = attempt - 1;
      return result;
    } catch (error) {
      lastError = error;
      console.warn('Model request failed (' + attempt + '/' + MAX_API_ATTEMPTS + '): ' + normalizeErrorMessage(error));

      if (attempt < MAX_API_ATTEMPTS) {
        var delayMs = API_RETRY_BASE_DELAY_MS * attempt;
        console.log('Waiting ' + (delayMs / 1000).toFixed(1) + 's before retry...');
        await sleep(delayMs);
      }
    }
  }

  throw new Error('Model request failed after ' + MAX_API_ATTEMPTS + ' attempts: ' + normalizeErrorMessage(lastError));
}

async function tryGenerateSeed(seed) {
  var prompt = buildPrompt(seed);
  var outputFile = join(scenesDir, seed.id + '.js');
  var tempFile = outputFile + '.tmp';
  var result = { code: '', inputTokens: 0, outputTokens: 0, costUsd: 0 };
  var validationFeedback = null;
  var validationRetries = 0;
  var apiRetries = 0;

  try {
    for (var attempt = 1; attempt <= MAX_VALIDATION_ATTEMPTS; attempt++) {
      validationRetries = attempt - 1;
      console.log(attempt === 1 ? 'Generating scene...' : 'Retrying with validation feedback...');

      var nextResult = await generateWithRetries(prompt, validationFeedback);
      apiRetries += nextResult.apiRetries;
      mergeResultTotals(result, nextResult);
      console.log('Generated: ' + nextResult.code.split('\n').length + ' lines, $' + nextResult.costUsd.toFixed(4));

      writeFileSync(tempFile, nextResult.code);

      try {
        validateSceneFile(tempFile);
        console.log(attempt === 1 ? 'Validation: PASSED' : 'Retry validation: PASSED');
        renameSync(tempFile, outputFile);

        return {
          success: true,
          seed: seed,
          result: result,
          retries: validationRetries,
          apiRetries: apiRetries,
          outputFile: outputFile,
        };
      } catch (error) {
        cleanupTempFile(tempFile);
        validationFeedback = normalizeErrorMessage(error);
        console.warn('Validation FAILED: ' + validationFeedback);
      }
    }

    throw new Error('Validation failed after ' + MAX_VALIDATION_ATTEMPTS + ' attempts: ' + validationFeedback);
  } catch (error) {
    cleanupTempFile(tempFile);
    appendLog(seed, result, validationRetries, 'fail', normalizeErrorMessage(error), apiRetries);

    return {
      success: false,
      seed: seed,
      result: result,
      retries: validationRetries,
      apiRetries: apiRetries,
      error: error,
    };
  }
}

function updateManifest(seed, result) {
  manifest.scenes.push({
    file: seed.id + '.js',
    name: seed.name,
    location: seed.location,
    biome: seed.biome,
    generated: new Date().toISOString(),
    model: MODEL,
    lines: result.code.split('\n').length,
    generation: manifest.scenes.length + 1,
  });
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log('Updated manifest: ' + manifest.scenes.length + ' scenes');
}

function appendLog(seed, result, retries, status, errorMessage, apiRetries) {
  var log = [];
  if (existsSync(logPath)) {
    try { log = JSON.parse(readFileSync(logPath, 'utf8')); } catch (e) { log = []; }
  }
  var entry = {
    ts: new Date().toISOString(),
    scene: seed.id + '.js',
    seed_id: seed.id,
    biome: seed.biome,
    model: MODEL,
    input_tokens: result.inputTokens || 0,
    output_tokens: result.outputTokens || 0,
    cost_usd: Math.round((result.costUsd || 0) * 10000) / 10000,
    retries: retries,
    api_retries: apiRetries || 0,
    validation: status,
  };
  if (errorMessage) entry.error = errorMessage;
  log.push(entry);
  writeFileSync(logPath, JSON.stringify(log, null, 2) + '\n');
}

async function main() {
  console.log('Seed plan: ' + seedPlan.map(function(s) { return s.id + ' (' + s.biome + ')'; }).join(', '));

  var lastFailure = null;

  for (var i = 0; i < seedPlan.length; i++) {
    var seed = seedPlan[i];
    console.log('');
    console.log('Attempt ' + (i + 1) + '/' + seedPlan.length + ': ' + seed.id + ' (' + seed.name + ')');
    console.log('  Location: ' + seed.location);
    console.log('  Biome: ' + seed.biome);

    var attempt = await tryGenerateSeed(seed);
    if (attempt.success) {
      console.log('Wrote: ' + attempt.outputFile);
      updateManifest(seed, attempt.result);
      appendLog(seed, attempt.result, attempt.retries, 'pass', null, attempt.apiRetries);

      var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log('Done in ' + elapsed + 's. Cost: $' + attempt.result.costUsd.toFixed(4));
      return;
    }

    lastFailure = attempt.error;
    console.error('Seed ' + seed.id + ' failed: ' + normalizeErrorMessage(attempt.error));
    if (i < seedPlan.length - 1) console.log('Trying next candidate seed...');
  }

  throw lastFailure || new Error('All candidate seeds failed.');
}

main().catch(function(e) {
  console.error('Fatal: ' + e.message);
  process.exit(1);
});
