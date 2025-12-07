#!/usr/bin/env node

/**
 * Context Foundry Daemon CLI - npm wrapper for Python engine
 *
 * This shim delegates to the Python CLI via `python3 -m context_foundry.daemon.cli`.
 * We invoke the module directly to avoid PATH conflicts (the npm-installed `cfd`
 * command would otherwise find itself via `which cfd`, causing infinite recursion).
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
 * Find Python 3.10+ command
 */
function findPython() {
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
 * Check if context-foundry Python package is installed
 */
function checkPythonPackage(pythonCmd) {
  const result = spawnSync(pythonCmd, ['-c', 'import context_foundry.daemon.cli'], {
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  return result.status === 0;
}

/**
 * Install context-foundry via pipx (preferred) or pip with --user
 */
function installPackage(pythonCmd) {
  // Try pipx first (best for CLI tools on macOS/Linux)
  const pipxCheck = spawnSync('which', ['pipx'], { encoding: 'utf-8' });
  if (pipxCheck.status === 0) {
    log(`${colors.yellow}Installing context-foundry via pipx...${colors.reset}`);
    const pipx = spawnSync('pipx', ['install', 'context-foundry'], {
      stdio: 'inherit'
    });
    if (pipx.status === 0) return true;
    // If pipx fails (already installed, etc), try reinstall
    const pipxReinstall = spawnSync('pipx', ['reinstall', 'context-foundry'], {
      stdio: 'inherit'
    });
    if (pipxReinstall.status === 0) return true;
  }

  // Fallback: pip with --user flag (avoids PEP 668 errors)
  log(`${colors.yellow}Installing context-foundry via pip --user...${colors.reset}`);
  const pip = spawnSync(pythonCmd, ['-m', 'pip', 'install', '--user', 'context-foundry'], {
    stdio: 'inherit'
  });
  if (pip.status === 0) return true;

  // Last resort: suggest pipx installation
  log(`\n${colors.yellow}Tip: Install pipx for better Python CLI tool management:${colors.reset}`);
  log(`  ${colors.cyan}brew install pipx && pipx ensurepath${colors.reset}`);
  return false;
}

/**
 * Run the Python CLI module with all arguments
 */
function runPythonCli(pythonCmd, args) {
  // Call the Python module directly - this avoids PATH issues entirely
  const proc = spawn(pythonCmd, ['-m', 'context_foundry.daemon.cli', ...args], {
    stdio: 'inherit',
    env: process.env
  });

  proc.on('error', (err) => {
    error(`Failed to start Python: ${err.message}`);
    process.exit(1);
  });

  proc.on('close', (code) => {
    process.exit(code || 0);
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

  // Find Python 3.10+
  const python = findPython();
  if (!python) {
    error('Python 3.10+ is required but not found.');
    log('\nPlease install Python 3.10 or later:', colors.yellow);
    log('  brew install python@3.12', colors.cyan);
    process.exit(1);
  }

  // Check if context-foundry is installed
  if (!checkPythonPackage(python.cmd)) {
    log(`${colors.yellow}context-foundry Python package not found.${colors.reset}`);

    if (!installPackage(python.cmd)) {
      error('Failed to install context-foundry via pip.');
      log('\nTry manually:', colors.yellow);
      log('  pip install context-foundry', colors.cyan);
      process.exit(1);
    }

    log(`${colors.green}Successfully installed!${colors.reset}\n`);
  }

  // Run the Python CLI
  runPythonCli(python.cmd, args);
}

main();
