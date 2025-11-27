#!/usr/bin/env node

/**
 * Post-install script for context-foundry npm package
 *
 * This script runs after `npm install` and ensures the Python
 * package is installed via pip.
 */

const { spawnSync } = require('child_process');

// ANSI colors
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  dim: '\x1b[2m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function log(msg, color = '') {
  console.log(`${color}${msg}${colors.reset}`);
}

function error(msg) {
  console.error(`${colors.red}${msg}${colors.reset}`);
}

/**
 * Find Python 3.10+ executable
 */
function findPython() {
  const pythonCommands = ['python3', 'python'];

  for (const cmd of pythonCommands) {
    try {
      const result = spawnSync(cmd, ['--version'], {
        encoding: 'utf-8',
        timeout: 5000
      });

      if (result.status === 0) {
        const version = result.stdout.trim() || result.stderr.trim();
        const match = version.match(/Python (\d+)\.(\d+)/);
        if (match) {
          const major = parseInt(match[1], 10);
          const minor = parseInt(match[2], 10);
          if (major === 3 && minor >= 10) {
            return { cmd, major, minor };
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
 * Check if context-foundry Python package is already installed
 */
function checkInstalled(pythonCmd) {
  const result = spawnSync(pythonCmd, ['-m', 'pip', 'show', 'context-foundry'], {
    encoding: 'utf-8',
    timeout: 10000
  });
  return result.status === 0;
}

/**
 * Install the Python package
 */
function installPythonPackage(pythonCmd) {
  log('\nInstalling context-foundry Python package...', colors.cyan);

  const result = spawnSync(
    pythonCmd,
    ['-m', 'pip', 'install', '--upgrade', 'context-foundry'],
    {
      stdio: 'inherit',
      timeout: 300000 // 5 minutes
    }
  );

  return result.status === 0;
}

function main() {
  log(`\n${'='.repeat(50)}`, colors.dim);
  log(`${colors.bold}Context Foundry${colors.reset} - Post-install setup`);
  log(`${'='.repeat(50)}`, colors.dim);

  // Step 1: Find Python
  log('\nChecking Python installation...', colors.cyan);
  const python = findPython();

  if (!python) {
    log(`\n${colors.yellow}Warning: Python 3.10+ not found.${colors.reset}`);
    log(`\nThe npm package is installed, but you'll need Python to run it.`);
    log(`\nInstall Python 3.10+ from:`);
    log(`  macOS:   ${colors.cyan}brew install python@3.12${colors.reset}`);
    log(`  Ubuntu:  ${colors.cyan}sudo apt install python3.12${colors.reset}`);
    log(`  Windows: ${colors.cyan}https://www.python.org/downloads/${colors.reset}`);
    log(`\nThen run: ${colors.cyan}pip install context-foundry${colors.reset}\n`);
    // Don't fail - the bin scripts will handle this at runtime
    return;
  }

  log(`  Found ${colors.green}Python ${python.major}.${python.minor}${colors.reset} (${python.cmd})`);

  // Step 2: Check if already installed
  if (checkInstalled(python.cmd)) {
    log(`  ${colors.green}context-foundry already installed${colors.reset}`);
    log(`\n${colors.green}Ready to use!${colors.reset} Run ${colors.cyan}cf${colors.reset} to get started.\n`);
    return;
  }

  // Step 3: Install Python package
  const installed = installPythonPackage(python.cmd);

  if (installed) {
    log(`\n${colors.green}Python package installed!${colors.reset}`);

    // Run cf setup to configure Claude Code
    log(`\nConfiguring Claude Code integration...`);
    const setup = spawnSync('cf', ['setup'], {
      stdio: 'inherit',
      timeout: 30000
    });

    if (setup.status === 0) {
      log(`\n${colors.green}Setup complete!${colors.reset}`);
    } else {
      log(`\n${colors.yellow}Note: Run 'cf setup' manually to configure Claude Code.${colors.reset}`);
    }
  } else {
    error(`\nFailed to install Python package.`);
    log(`\nTry installing manually:`);
    log(`  ${colors.cyan}pip install context-foundry${colors.reset}\n`);
    // Don't fail npm install - user can fix this manually
  }
}

main();
