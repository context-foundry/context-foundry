PHASE 5: DOCUMENTATION


(Only reached if tests PASSED)

**Note:** Phase tracking is handled automatically by the orchestrator using BAML.

0.

1. Create comprehensive README.md in project root:
   Include:
   - Project title and tagline
   - **Hero screenshot** (if available from Screenshot phase):
     ```markdown
     ![Application Screenshot](docs/screenshots/hero.png)
     ```
   - Brief description
   - Features list
   - Installation instructions (step-by-step)
   - Usage guide with examples
   - Testing instructions (how to run tests)
   - Project structure overview
   - Technologies used
   - Contributing guidelines (if applicable)
   - License information
   - Credits: "🤖 Built autonomously by Context Foundry"

   **Screenshot handling:**
   - If docs/screenshots/hero.png exists: Include it prominently after title
   - If screenshots don't exist: Continue without visual elements (graceful degradation)

2. Create docs/ directory with detailed documentation:

   Create docs/INSTALLATION.md:
   - Prerequisites
   - Step-by-step installation
   - Troubleshooting common issues

   Create docs/USAGE.md:
   - Getting started guide
   - Detailed usage examples with **step-by-step screenshots** (if available):
     ```markdown
     ## Getting Started

     ### Step 1: Initial Setup

     Description of what to do...

     ![Step 1](screenshots/step-01-initial-state.png)

     ### Step 2: Using Key Features

     Description of the feature...

     ![Step 2](screenshots/step-02-feature.png)
     ```
   - Configuration options
   - Advanced features

   **Screenshot handling:**
   - Check docs/screenshots/manifest.json for available step screenshots
   - Include screenshots inline with instructions
   - If screenshots don't exist: Continue with text-only instructions

   Create docs/ARCHITECTURE.md:
   - System architecture overview
   - Component descriptions
   - Data flow diagrams (text/ASCII)
   - Design decisions and rationale

   Create docs/TESTING.md:
   - How to run tests
   - Test coverage information
   - Adding new tests
   - Test results from build

   Create docs/API.md (if applicable):
   - API endpoints documentation
   - Request/response examples
   - Error codes
   - Authentication details

3. Update build log:
   Add to .context-foundry/build-log.md:
   - Documentation files created
   - Documentation completeness checklist
