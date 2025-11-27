#!/usr/bin/env tsx
/**
 * Verify API Routes Configuration
 *
 * Checks that all required API routes are properly implemented with:
 * - Correct file structure
 * - Required exports
 * - Proper error handling
 * - Validation schemas
 */

import fs from 'fs';
import path from 'path';

interface RouteCheck {
  path: string;
  name: string;
  required: boolean;
  exists: boolean;
  hasPostMethod: boolean;
  hasValidation: boolean;
  hasErrorHandling: boolean;
  issues: string[];
}

const REQUIRED_ROUTES = [
  {
    path: 'app/api/generate/scenario/route.ts',
    name: 'Scenario Generation',
    checks: ['POST', 'ScenarioRequestSchema', 'validateScenario', 'NextResponse'],
  },
  {
    path: 'app/api/generate/quiz/route.ts',
    name: 'Quiz Generation',
    checks: ['POST', 'QuizRequestSchema', 'validateQuiz', 'NextResponse'],
  },
  {
    path: 'app/api/generate/image/route.ts',
    name: 'Image Generation',
    checks: ['POST', 'ImageRequestSchema', 'generateImage', 'NextResponse'],
  },
  {
    path: 'app/api/generate/hint/route.ts',
    name: 'Hint Generation',
    checks: ['POST', 'HintRequestSchema', 'HintResponse', 'NextResponse'],
  },
  {
    path: 'app/api/certificate/route.ts',
    name: 'Certificate Generation',
    checks: ['POST', 'CertificateRequestSchema', 'renderToStream', 'NextResponse'],
  },
];

function checkRoute(routePath: string, requiredChecks: string[]): RouteCheck {
  const fullPath = path.join(process.cwd(), routePath);
  const exists = fs.existsSync(fullPath);

  const check: RouteCheck = {
    path: routePath,
    name: routePath.split('/').slice(-2, -1)[0] || 'Unknown',
    required: true,
    exists,
    hasPostMethod: false,
    hasValidation: false,
    hasErrorHandling: false,
    issues: [],
  };

  if (!exists) {
    check.issues.push('File does not exist');
    return check;
  }

  try {
    const content = fs.readFileSync(fullPath, 'utf-8');

    // Check for POST method export
    check.hasPostMethod = /export\s+async\s+function\s+POST/.test(content);
    if (!check.hasPostMethod) {
      check.issues.push('Missing POST method export');
    }

    // Check for validation schema
    check.hasValidation = /Schema\s*=\s*z\.object/.test(content);
    if (!check.hasValidation) {
      check.issues.push('Missing Zod validation schema');
    }

    // Check for error handling
    check.hasErrorHandling =
      content.includes('try {') &&
      content.includes('catch') &&
      content.includes('NextResponse.json');
    if (!check.hasErrorHandling) {
      check.issues.push('Missing proper error handling');
    }

    // Check for required imports/usage
    for (const requiredCheck of requiredChecks) {
      if (!content.includes(requiredCheck)) {
        check.issues.push(`Missing required: ${requiredCheck}`);
      }
    }

    // Check for proper return types
    if (!content.includes('NextResponse')) {
      check.issues.push('Not using NextResponse');
    }

    // Check for request body validation
    if (!content.includes('.safeParse(') && !content.includes('.parse(')) {
      check.issues.push('Missing request validation');
    }

  } catch (error) {
    check.issues.push(`Error reading file: ${error}`);
  }

  return check;
}

function printResults(checks: RouteCheck[]): void {
  console.log('\n' + '='.repeat(80));
  console.log('API ROUTES VERIFICATION REPORT');
  console.log('='.repeat(80) + '\n');

  let totalRoutes = 0;
  let passingRoutes = 0;
  let totalIssues = 0;

  for (const check of checks) {
    totalRoutes++;
    const passed = check.exists && check.issues.length === 0;
    if (passed) passingRoutes++;
    totalIssues += check.issues.length;

    const status = passed ? '✓ PASS' : '✗ FAIL';
    const statusColor = passed ? '\x1b[32m' : '\x1b[31m';
    const resetColor = '\x1b[0m';

    console.log(`${statusColor}${status}${resetColor} ${check.name}`);
    console.log(`     Path: ${check.path}`);
    console.log(`     Exists: ${check.exists ? '✓' : '✗'}`);

    if (check.exists) {
      console.log(`     POST Method: ${check.hasPostMethod ? '✓' : '✗'}`);
      console.log(`     Validation: ${check.hasValidation ? '✓' : '✗'}`);
      console.log(`     Error Handling: ${check.hasErrorHandling ? '✓' : '✗'}`);
    }

    if (check.issues.length > 0) {
      console.log(`     Issues:`);
      for (const issue of check.issues) {
        console.log(`       - ${issue}`);
      }
    }
    console.log('');
  }

  console.log('-'.repeat(80));
  console.log(`\nSummary:`);
  console.log(`  Total Routes: ${totalRoutes}`);
  console.log(`  Passing: ${passingRoutes}`);
  console.log(`  Failing: ${totalRoutes - passingRoutes}`);
  console.log(`  Total Issues: ${totalIssues}`);

  if (totalIssues === 0) {
    console.log(`\n✓ All API routes are properly configured!`);
  } else {
    console.log(`\n✗ Please fix the issues above before deploying.`);
  }

  console.log('\n' + '='.repeat(80) + '\n');
}

// Main execution
function main() {
  const checks: RouteCheck[] = [];

  for (const route of REQUIRED_ROUTES) {
    const check = checkRoute(route.path, route.checks);
    check.name = route.name;
    checks.push(check);
  }

  printResults(checks);

  // Check for certificate template component
  const certificateTemplatePath = 'components/certificate/CertificateTemplate.tsx';
  const fullCertPath = path.join(process.cwd(), certificateTemplatePath);

  console.log('Additional Components:');
  if (fs.existsSync(fullCertPath)) {
    console.log(`  ✓ Certificate Template: ${certificateTemplatePath}`);
  } else {
    console.log(`  ✗ Certificate Template: Missing at ${certificateTemplatePath}`);
  }

  // Exit with appropriate code
  const allPassed = checks.every((c) => c.exists && c.issues.length === 0);
  process.exit(allPassed && fs.existsSync(fullCertPath) ? 0 : 1);
}

main();
