#!/usr/bin/env node

/**
 * Context Foundry Daemon CLI - npm wrapper for Python engine
 *
 * This is a thin shim that delegates to the Python `cfd` command.
 */

const { spawn, spawnSync } = require('child_process');

// ANSI colors
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function error(msg) {
  console.error(`${colors.red}Error: ${msg}${colors.reset}`);
}

function log(msg, color = '') {
  console.log(`${color}${msg}${colors.reset}`);
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
 * Get the path to cfd from the Python package
 */
function getCfdPath() {
  // First try: check if cfd is in PATH
  const which = spawnSync('which', ['cfd'], { encoding: 'utf-8' });
  if (which.status === 0) {
    return 'cfd';
  }

  // Second try: use the tools/cfd script directly if we're in the repo
  const localCfd = require('path').join(__dirname, '../../tools/cfd');
  try {
    require('fs').accessSync(localCfd, require('fs').constants.X_OK);
    return localCfd;
  } catch (e) {
    // Not in repo or not executable
  }

  return null;
}

/**
 * Run the Python cfd command with all arguments passed through
 */
function runCfd(cfdPath, args) {
  const cfd = spawn(cfdPath, args, {
    stdio: 'inherit',
    env: process.env
  });

  cfd.on('error', (err) => {
    if (err.code === 'ENOENT') {
      error('The `cfd` command is not found.');
      log('\nTry running:', colors.cyan);
      log('  pip install context-foundry', colors.bold);
      process.exit(1);
    }
    throw err;
  });

  cfd.on('close', (code) => {
    process.exit(code);
  });
}

function showHelp() {
  log(`
${colors.cyan}${colors.bold}Context Foundry Daemon (cfd)${colors.reset}

${colors.yellow}Usage:${colors.reset}
  cfd start           Start the daemon
  cfd stop            Stop the daemon
  cfd status          Get daemon status
  cfd submit          Submit a job
  cfd list            List jobs
  cfd logs <job-id>   Show job logs
  cfd --help          Full help

${colors.yellow}More Info:${colors.reset}
  https://github.com/context-foundry/context-foundry
`);
}

// Main entry point
function main() {
  const args = process.argv.slice(2);

  // Check Python availability
  const python = checkPython();
  if (!python) {
    error('Python 3.10+ is required but not found.');
    process.exit(1);
  }

  // Find cfd command
  const cfdPath = getCfdPath();
  if (!cfdPath) {
    log(`${colors.yellow}The 'cfd' command is not installed.${colors.reset}`);
    log(`Installing context-foundry via pip...`);

    const pip = spawnSync(python.cmd, ['-m', 'pip', 'install', 'context-foundry'], {
      stdio: 'inherit'
    });

    if (pip.status !== 0) {
      error('Failed to install context-foundry via pip.');
      process.exit(1);
    }

    log(`${colors.green}Successfully installed!${colors.reset}\n`);
  }

  // Run cfd with all arguments
  runCfd(cfdPath || 'cfd', args);
}

main();
