#!/usr/bin/env node
// Generates a new pixel art scene using the OpenAI API (GPT-4o-mini).
// Usage: node generate-scene.js [--dry-run] [--seed-id <id>]
// Requires OPENAI_API_KEY env var.

import OpenAI from 'openai';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
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

// Load data
var manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
var seeds = JSON.parse(readFileSync(seedsPath, 'utf8'));
var promptTemplate = readFileSync(promptPath, 'utf8');

// Pick a seed -- avoid recently used biomes
var usedBiomes = manifest.scenes.slice(-10).map(function(s) { return s.biome; });
var candidates = seeds.filter(function(s) {
  // Skip if this exact seed was already used
  var usedIds = manifest.scenes.map(function(e) { return e.file.replace('.js', ''); });
  if (usedIds.includes(s.id)) return false;
  // Deprioritize recently used biomes (but don't exclude entirely)
  return true;
});

if (candidates.length === 0) {
  console.log('All seeds exhausted. Exiting.');
  process.exit(0);
}

// Weight selection away from recent biomes
var seed;
if (forceSeedId) {
  seed = candidates.find(function(s) { return s.id === forceSeedId; });
  if (!seed) { console.error('Seed not found: ' + forceSeedId); process.exit(1); }
} else {
  var weighted = candidates.map(function(s) {
    var recentCount = usedBiomes.filter(function(b) { return b === s.biome; }).length;
    return { seed: s, weight: recentCount === 0 ? 10 : (recentCount === 1 ? 3 : 1) };
  });
  var totalWeight = weighted.reduce(function(sum, w) { return sum + w.weight; }, 0);
  var roll = Math.random() * totalWeight;
  var cumulative = 0;
  for (var w of weighted) {
    cumulative += w.weight;
    if (roll <= cumulative) { seed = w.seed; break; }
  }
}

console.log('Selected seed: ' + seed.id + ' (' + seed.name + ')');
console.log('  Location: ' + seed.location);
console.log('  Biome: ' + seed.biome);

// Build the prompt
// Pick 2 example scenes (rotate based on seed to get variety)
var exampleFiles = ['foundry.js', 'exuma.js', 'atacama.js', 'challenger.js'];
var hash = seed.id.split('').reduce(function(h, c) { return ((h << 5) - h + c.charCodeAt(0)) | 0; }, 0);
var ex1 = exampleFiles[Math.abs(hash) % exampleFiles.length];
var ex2 = exampleFiles[Math.abs(hash + 1) % exampleFiles.length];
if (ex1 === ex2) ex2 = exampleFiles[(Math.abs(hash) + 2) % exampleFiles.length];

var example1 = readFileSync(join(scenesDir, ex1), 'utf8');
var example2 = readFileSync(join(scenesDir, ex2), 'utf8');

var exampleBlock = '## Example Scene 1 (' + ex1 + ')\n\n```javascript\n' + example1 + '\n```\n\n## Example Scene 2 (' + ex2 + ')\n\n```javascript\n' + example2 + '\n```';

var prompt = promptTemplate
  .replace('{{EXAMPLE_SCENES}}', exampleBlock)
  .replace('{{SCENE_NAME}}', seed.name)
  .replace('{{SCENE_LOCATION}}', seed.location)
  .replace('{{BIOME}}', seed.biome)
  .replace('{{PALETTE}}', seed.palette.join(', '))
  .replace('{{ELEMENTS}}', seed.elements.join(', '))
  .replace('{{MOOD}}', seed.mood);

if (dryRun) {
  console.log('\n--- DRY RUN ---');
  console.log('Prompt length: ' + prompt.length + ' chars');
  console.log('Output file would be: ' + join(scenesDir, seed.id + '.js'));
  process.exit(0);
}

// Call OpenAI API
var client = new OpenAI();
var startTime = Date.now();

async function generate(retryWithError) {
  var userContent = retryWithError
    ? prompt + '\n\n## RETRY -- Previous attempt had this error:\n' + retryWithError + '\n\nFix the error and regenerate the complete file.'
    : prompt;

  var response = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    max_tokens: 8192,
    messages: [
      { role: 'system', content: 'You are a pixel art scene generator. Output ONLY valid JavaScript code. No markdown fences, no explanation.' },
      { role: 'user', content: userContent },
    ],
  });

  var code = response.choices[0].message.content;

  // Strip markdown fences if the model wrapped them
  code = code.replace(/^```(?:javascript|js)?\n?/, '').replace(/\n?```\s*$/, '');

  var inputTokens = response.usage.prompt_tokens;
  var outputTokens = response.usage.completion_tokens;
  // GPT-4o-mini: $0.15/M input, $0.60/M output
  var costUsd = (inputTokens * 0.15 + outputTokens * 0.60) / 1000000;

  return { code: code, inputTokens: inputTokens, outputTokens: outputTokens, costUsd: costUsd };
}

async function main() {
  var result;
  var retries = 0;

  // First attempt
  console.log('Generating scene...');
  result = await generate(null);
  console.log('Generated: ' + result.code.split('\n').length + ' lines, $' + result.costUsd.toFixed(4));

  // Write to temp file for validation
  var outputFile = join(scenesDir, seed.id + '.js');
  var tempFile = outputFile + '.tmp';
  writeFileSync(tempFile, result.code);

  // Validate
  try {
    execSync('node ' + join(__dirname, 'validate-scene.js') + ' ' + tempFile, { stdio: 'pipe' });
    console.log('Validation: PASSED');
  } catch (e) {
    var validationError = e.stderr ? e.stderr.toString() : e.message;
    console.warn('Validation FAILED: ' + validationError);

    // Retry once
    console.log('Retrying with error feedback...');
    retries = 1;
    var result2 = await generate(validationError);
    result.inputTokens += result2.inputTokens;
    result.outputTokens += result2.outputTokens;
    result.costUsd += result2.costUsd;
    result.code = result2.code;

    writeFileSync(tempFile, result.code);
    try {
      execSync('node ' + join(__dirname, 'validate-scene.js') + ' ' + tempFile, { stdio: 'pipe' });
      console.log('Retry validation: PASSED');
    } catch (e2) {
      console.error('Retry validation FAILED. Giving up.');
      execSync('rm -f ' + tempFile);
      appendLog(seed, result, retries, 'fail');
      process.exit(1);
    }
  }

  // Move temp to final
  execSync('mv ' + tempFile + ' ' + outputFile);
  console.log('Wrote: ' + outputFile);

  // Update manifest
  manifest.scenes.push({
    file: seed.id + '.js',
    name: seed.name,
    location: seed.location,
    biome: seed.biome,
    generated: new Date().toISOString(),
    model: 'gpt-4o-mini',
    lines: result.code.split('\n').length,
    generation: manifest.scenes.length + 1,
  });
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log('Updated manifest: ' + manifest.scenes.length + ' scenes');

  // Append to generation log
  appendLog(seed, result, retries, 'pass');

  var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log('Done in ' + elapsed + 's. Cost: $' + result.costUsd.toFixed(4));
}

function appendLog(seed, result, retries, status) {
  var log = [];
  if (existsSync(logPath)) {
    try { log = JSON.parse(readFileSync(logPath, 'utf8')); } catch (e) { log = []; }
  }
  log.push({
    ts: new Date().toISOString(),
    scene: seed.id + '.js',
    seed_id: seed.id,
    biome: seed.biome,
    model: 'gpt-4o-mini',
    input_tokens: result.inputTokens,
    output_tokens: result.outputTokens,
    cost_usd: Math.round(result.costUsd * 10000) / 10000,
    retries: retries,
    validation: status,
  });
  writeFileSync(logPath, JSON.stringify(log, null, 2) + '\n');
}

main().catch(function(e) {
  console.error('Fatal: ' + e.message);
  process.exit(1);
});
