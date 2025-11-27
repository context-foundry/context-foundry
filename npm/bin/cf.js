#!/usr/bin/env node

/**
 * Context Foundry CLI - npm wrapper for Python engine
 *
 * This is a thin shim that delegates to the Python `cf` command.
 * The Python package is installed via pip during npm postinstall.
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');

// ANSI colors
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function log(msg, color = '') {
  console.log(`${color}${msg}${colors.reset}`);
}

function error(msg) {
  console.error(`${colors.red}Error: ${msg}${colors.reset}`);
}

/**
 * Check if Python 3.10+ is available
 */
function checkPython() {
  const pythonCommands = ['python3', 'python'];

  for (const cmd of pythonCommands) {
    try {
      const result = spawnSync(cmd, ['--version'], { encoding: 'utf-8' });
      if (result.status === 0) {
        const version = result.stdout.trim() || result.stderr.trim();
        const match = version.match(/Python (\d+)\.(\d+)/);
        if (match) {
          const major = parseInt(match[1], 10);
          const minor = parseInt(match[2], 10);
          if (major === 3 && minor >= 10) {
            return { cmd, version: `${major}.${minor}` };
          }
        }
      }
    } catch (e) {
      // Continue to next command
    }
  }
  return null;
}

/**
 * Check if the cf command is available in PATH
 */
function checkCfInstalled() {
  const result = spawnSync('which', ['cf'], { encoding: 'utf-8' });
  return result.status === 0;
}

/**
 * Run the Python cf command with all arguments passed through
 */
function runCf(args) {
  const cf = spawn('cf', args, {
    stdio: 'inherit',
    env: process.env
  });

  cf.on('error', (err) => {
    if (err.code === 'ENOENT') {
      error('The `cf` command is not found in your PATH.');
      log('\nThis usually means the Python package is not installed.', colors.yellow);
      log('Try running:', colors.cyan);
      log('  pip install context-foundry', colors.bold);
      log('\nOr reinstall this npm package:', colors.cyan);
      log('  npm install -g context-foundry', colors.bold);
      process.exit(1);
    }
    throw err;
  });

  cf.on('close', (code) => {
    process.exit(code);
  });
}

/**
 * Show help with installation instructions
 */
function showHelp() {
  log(`
${colors.cyan}${colors.bold}Context Foundry${colors.reset} - AI Agent Pattern Learning System

${colors.yellow}Usage:${colors.reset}
  cf              Launch Mission Control TUI
  cf --version    Show version
  cf --help       Show this help

${colors.yellow}Quick Start:${colors.reset}
  1. Run ${colors.cyan}cf${colors.reset} to launch the interactive TUI
  2. Or use the daemon: ${colors.cyan}cfd start${colors.reset}

${colors.yellow}More Info:${colors.reset}
  https://github.com/context-foundry/context-foundry
`);
}

// Main entry point
function main() {
  const args = process.argv.slice(2);

  // Check if Python is available
  const python = checkPython();
  if (!python) {
    error('Python 3.10+ is required but not found.');
    log('\nPlease install Python 3.10 or later:', colors.yellow);
    log('  macOS:  brew install python@3.12', colors.cyan);
    log('  Ubuntu: sudo apt install python3.12', colors.cyan);
    log('  Windows: https://www.python.org/downloads/', colors.cyan);
    process.exit(1);
  }

  // Check if cf is installed
  if (!checkCfInstalled()) {
    log(`${colors.yellow}The Python 'cf' command is not installed.${colors.reset}`);
    log(`Installing context-foundry via pip...`);

    const pip = spawnSync(python.cmd, ['-m', 'pip', 'install', 'context-foundry'], {
      stdio: 'inherit'
    });

    if (pip.status !== 0) {
      error('Failed to install context-foundry via pip.');
      log('\nTry installing manually:', colors.yellow);
      log('  pip install context-foundry', colors.cyan);
      process.exit(1);
    }

    log(`${colors.green}Successfully installed context-foundry!${colors.reset}\n`);
  }

  // Pass all args to the Python cf command
  runCf(args);
}

main();
