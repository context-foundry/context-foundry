PHASE 0: CODEBASE ANALYSIS (Enhancement Modes Only)

**⚠️  SKIP THIS PHASE IF mode = "new_project"**

**RUN THIS PHASE IF mode = "fix_bug", "add_feature", "upgrade_deps", "refactor", or "add_tests"**

This phase analyzes the existing codebase before making changes.

**PHASE TRACKING (START):**
Update phase: "Codebase Analysis" (0/7, "analyzing", "Understanding existing codebase")
(See PHASE TRACKING TEMPLATE above for JSON format)

**Objectives:**
1. **Understand Project Structure**
   - List all directories and key files
   - Identify entry points (main.py, index.js, main.rs, etc.)
   - Find configuration files
   - Locate tests directory

2. **Analyze Architecture**
   - Read package/dependency files (requirements.txt, package.json, Cargo.toml, etc.)
   - Understand module/package structure
   - Identify design patterns used
   - Document API routes/endpoints (if applicable)

3. **Review Existing Code** (targeted reading)
   - **For fix_bug mode**: Find files related to the bug
   - **For add_feature mode**: Find files that will be extended
   - **For refactor mode**: Identify code to refactor
   - **For add_tests mode**: Find untested code
   - **For upgrade_deps mode**: Review dependency usage

4. **Check Tests**
   - Find existing test files
   - Understand test framework used
   - Note test coverage gaps

5. **Git Analysis** (if has_git = true)
   - Check current branch
   - Review recent commits for context
   - Note any uncommitted changes (warning if git_clean = false)

6. **Document Findings**
   Create `.context-foundry/codebase-analysis.md` with:
   ```markdown
   # Codebase Analysis Report

   ## Project Overview
   - Type: {project_type}
   - Languages: {languages}
   - Architecture: {describe structure}

   ## Key Files
   - Entry point: {file}
   - Config: {files}
   - Tests: {location}

   ## Dependencies
   {list main dependencies}

   ## Code to Modify
   **Task**: {task description}
   **Files to change**: {list specific files}
   **Approach**: {describe modification strategy}

   ## Risks
   {potential issues with changes}
   ```

7. **Update Phase Tracking (COMPLETE)**
   Update phase: "Codebase Analysis" (0/7, "completed", "Analysis complete")
   Add to phases_completed: ["Codebase Analysis"]

**✅ Codebase Analysis complete. Proceed to Scout.**

