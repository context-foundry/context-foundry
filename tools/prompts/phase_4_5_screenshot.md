PHASE 4.5: SCREENSHOT CAPTURE (Visual Documentation)


(Only reached if tests PASSED)

**Purpose:** Capture visual documentation of the working application for inclusion in README and user guides.

**Note:** Phase tracking is handled automatically by the orchestrator using BAML.

0.

1. Detect project type:
   - Examine package.json, file structure, and architecture.md
   - Determine if project is: web-app, game, cli-tool, api, desktop-app
   - Select appropriate screenshot strategy from tools/screenshot_templates/screenshot-strategy.json

2. Install Playwright (for web-based projects):
   Execute: npm install -D playwright @playwright/test
   Execute: npx playwright install chromium

3. Copy screenshot templates to project:
   - Copy tools/screenshot_templates/playwright.config.js to project root
   - Copy tools/screenshot_helpers/capture.js to project directory

4. Start application (if needed for screenshots):

   **For web apps/games:**
   - Identify start command from package.json (npm run dev, npm start, etc.)
   - Start dev server in background
   - Wait for server to be ready (check port, typically 3000-8080)
   - Record server process PID for cleanup

   **For CLI tools:**
   - Prepare terminal for capture
   - Prepare command examples from architecture

   **For APIs:**
   - Start server
   - Prepare HTTP client for API documentation screenshots

5. Capture screenshots:

   **Run screenshot capture script:**
   Execute: BASE_URL=http://localhost:{port} node capture.js

   The script will automatically:
   - Navigate to the application
   - Wait for page to be fully loaded
   - Capture hero screenshot (main view) → docs/screenshots/hero.png
   - Capture feature screenshots (key functionality) → docs/screenshots/feature-*.png
   - Capture step-by-step workflow → docs/screenshots/step-*.png
   - Create docs/screenshots/manifest.json documenting all screenshots

6. Screenshot manifest structure:
   {
     "generated": "2025-10-19T...",
     "baseURL": "http://localhost:3000",
     "projectType": "web-app",
     "screenshots": [
       {
         "filename": "hero.png",
         "path": "docs/screenshots/hero.png",
         "type": "hero",
         "description": "Main application view"
       },
       {
         "filename": "feature-01-navigation.png",
         "path": "docs/screenshots/feature-01-navigation.png",
         "type": "feature",
         "description": "Navigation and routing"
       },
       {
         "filename": "step-01-initial-state.png",
         "path": "docs/screenshots/step-01-initial-state.png",
         "type": "step",
         "description": "Initial application state"
       }
     ],
     "total": 5,
     "failed": 0
   }

7. Stop application gracefully:
   - Kill dev server process (if started)
   - Clean up any background processes
   - Ensure all screenshots saved successfully

8. Handle errors gracefully:
   **If screenshot capture fails:**
   - Log warning to .context-foundry/screenshot-capture-log.md
   - Note: "Screenshot capture failed: {error}. Continuing without visual documentation."
   - DO NOT fail the entire build
   - Continue to Documentation
   - Documentation phase will handle missing screenshots gracefully

9. Validate screenshot capture:
   - Verify docs/screenshots/hero.png exists
   - Verify docs/screenshots/manifest.json exists
   - Count total screenshots captured
   - Log summary:
     ```
     Screenshot Capture Summary:
     ✓ Hero screenshot: docs/screenshots/hero.png
     ✓ Feature screenshots: 3
     ✓ Workflow screenshots: 2
     ✓ Total: 6 screenshots
     ✓ Manifest: docs/screenshots/manifest.json
     ```



**IMPORTANT NOTES:**
- Screenshot capture is OPTIONAL - if it fails, continue anyway
- Only web-based projects (web apps, games) will have full screenshot capture
- CLI tools get terminal output screenshots
- APIs get documentation/Postman screenshots
- If project type cannot be determined or screenshots not applicable, create a visual representation of the project structure instead
- Graceful degradation: missing screenshots won't block documentation or deployment
