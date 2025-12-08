/**
 * Version extraction script
 *
 * Extracts version info from git and writes to src/version.json
 * Run this as part of the build process or via npm script.
 *
 * Usage: node scripts/version.js
 */

import { execSync } from 'child_process';
import { writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');
const cfRootDir = join(rootDir, '../..');  // context-foundry root

function exec(cmd, cwd = cfRootDir) {
  try {
    return execSync(cmd, { cwd, encoding: 'utf-8' }).trim();
  } catch {
    return null;
  }
}

function getVersionInfo() {
  // Get version from git describe (e.g., "v2.5.3" or "v2.5.3-43-gc16ca0d")
  // Use --match to only consider release tags (not session-* or nightly tags)
  const gitDescribe = exec("git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]' --always");

  // Parse version components
  let version = '0.0.0';
  let commitsSinceTag = 0;
  let commitHash = '';
  let isDirty = false;

  if (gitDescribe) {
    // Check if working directory is dirty
    const status = exec('git status --porcelain');
    isDirty = Boolean(status);

    // Parse git describe output
    const match = gitDescribe.match(/^v?(\d+\.\d+\.\d+)(?:-(\d+)-g([a-f0-9]+))?$/);
    if (match) {
      version = match[1];
      commitsSinceTag = match[2] ? parseInt(match[2], 10) : 0;
      commitHash = match[3] || exec('git rev-parse --short HEAD') || '';
    } else {
      // Fallback: just a commit hash
      commitHash = gitDescribe;
    }
  }

  // Get last commit date
  const commitDate = exec('git log -1 --format=%ci') || new Date().toISOString();

  // Get remote URL for GitHub link
  const remoteUrl = exec('git remote get-url origin') || '';
  const githubUrl = remoteUrl
    .replace(/\.git$/, '')
    .replace(/^git@github\.com:/, 'https://github.com/');

  return {
    version,
    commitsSinceTag,
    commitHash,
    isDirty,
    commitDate,
    githubUrl,
    buildTime: new Date().toISOString(),
    displayVersion: commitsSinceTag > 0
      ? `${version}+${commitsSinceTag}`
      : version,
  };
}

const versionInfo = getVersionInfo();

// Write to version.json
const outputPath = join(rootDir, 'src', 'version.json');
writeFileSync(outputPath, JSON.stringify(versionInfo, null, 2));

console.log(`Version info written to ${outputPath}`);
console.log(versionInfo);
