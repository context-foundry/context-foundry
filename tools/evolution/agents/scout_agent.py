#!/usr/bin/env python3
"""
Scout Agent - Autonomous code analyzer for Context Foundry Evolution System

Scans codebase to discover:
- Security vulnerabilities
- Performance bottlenecks
- Missing tests
- Best practice violations
- Outdated dependencies
- Architectural debt
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any, Union
import json


import sys
from tools.evolution.framework.agent_base import Agent
from tools.evolution.framework.llm_provider import LLMProvider, LocalClaudeProvider


class Finding:
    """Represents a discovered issue or enhancement"""

    def __init__(
        self,
        title: str,
        finding_type: str,  # 'bug', 'security', 'performance', 'enhancement', 'debt'
        priority: str,  # 'P0', 'P1', 'P2', 'P3', 'P4'
        category: List[str],
        description: str,
        file_path: str = None,
        line_number: int = None,
        evidence: str = None,
        effort: str = "medium",
    ):  # 'small', 'medium', 'large'
        self.title = title
        self.finding_type = finding_type
        self.priority = priority
        self.category = category
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.evidence = evidence
        self.effort = effort
        self.research = None  # Will be populated by research phase
        self.architectural_analysis = None  # Will be populated by architect if needed

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "type": self.finding_type,
            "priority": self.priority,
            "category": self.category,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "effort": self.effort,
            "research": self.research,
            "architectural_analysis": self.architectural_analysis,
        }


class ScoutAgent(Agent):
    """
    Autonomous code analysis agent

    Philosophy: Simple heuristics + pattern matching = 90% of issues found
    Complex ML = 10% improvement at 1000x cost
    """

    # Flowise project indicators - files/patterns that indicate a Flowise project
    FLOWISE_INDICATORS = [
        # Direct Flowise files
        "chatflow.json",
        "agentflow.json",
        "*.flowise",
        ".flowise",
        "flowise-chatflows",
        "flowise-agentflows",
        # Flowise export patterns
        "Chatflow-*.json",
        "Agentflow-*.json",
        # Flowise config
        "flowise.config.json",
        ".flowiserc",
        # Common Flowise directory names
        "chatflows",
        "agentflows",
        "flows",
    ]

    # MCP project indicators
    MCP_INDICATORS = [
        "mcp.json",
        "mcp-config.json",
        "mcp_config.json",
        ".mcp",
        "fastmcp",
        "mcp-server",
        "mcp_server",
    ]

    TEST_PATH_KEYWORDS = {
        "test",
        "tests",
        "__tests__",
        "testdata",
        "test_data",
        "fixtures",
        "fixture",
        "samples",
        "sample_data",
        "mocks",
        "stubs",
        "snapshots",
    }

    DEPENDENCY_PATH_KEYWORDS = {
        # Virtual environments
        "venv",
        ".venv",
        "virtualenv",
        ".virtualenv",
        "site-packages",
        "dist-packages",
        "__pypackages__",
        # Build/distribution directories
        "build",
        "dist",
        ".egg",
        ".eggs",
        "*.egg-info",
        # Cache directories
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        ".tox",
        ".nox",
        # Third-party/vendored code
        "vendor",
        "vendors",
        "third_party",
        "node_modules",
        # IDE directories
        ".vscode",
        ".idea",
        ".vs",
        # Git internals
        ".git",
    }

    def __init__(self, project_root: Path, llm_provider: LLMProvider = None):
        # Default to LocalClaudeProvider for backward compatibility
        if llm_provider is None:
            llm_provider = LocalClaudeProvider()

        super().__init__("Scout", llm_provider)
        self.project_root = project_root
        self.findings: List[Finding] = []
        # Store codex patterns that were actually queried and applied
        self.codex_patterns_applied: List[Dict[str, str]] = []
        self.detected_project_type: Optional[str] = None
        # Track if codex module was available (for reporting)
        self.codex_available: bool = True

    def _query_codex_for_patterns(self, project_type: Optional[str]) -> str:
        """
        Actually invoke codex tools to query for relevant patterns.

        This is NOT just prompt text - it actually calls the codex functions
        and returns the results as context for the LLM.

        Returns:
            Formatted string with codex query results to include in prompt context.
        """
        results = []
        queries_by_type = {
            "flowise": [
                ("flowise routing pattern", None),
                ("flowise common issues", "common-issues"),
                ("flowise agentflow", None),
            ],
            "mcp": [
                ("mcp server pattern", None),
                ("mcp common issues", "common-issues"),
                ("fastmcp implementation", None),
            ],
        }

        # Default queries for any project
        default_queries = [
            ("common issues", "common-issues"),
        ]

        queries = queries_by_type.get(project_type, default_queries)

        try:
            from tools.mcp_utils.codex import codex_search, codex_get_entry
        except ImportError:
            print(
                "  ⚠️ Codex module not available, skipping codex queries",
                file=sys.stderr,
            )
            self.codex_available = False
            return ""

        print(
            f"  📚 Querying Context Codex for {project_type or 'general'} patterns...",
            file=sys.stderr,
        )

        for query, category in queries:
            try:
                search_result = codex_search(query, category=category)
                if search_result and isinstance(search_result, dict):
                    entries = search_result.get("entries", [])
                    if entries:
                        results.append(f"### Query: '{query}'")
                        for entry in entries[:3]:  # Limit to top 3 per query
                            entry_id = entry.get("id", "unknown")
                            title = entry.get("title", entry_id)
                            relevance = entry.get("relevance_score", "N/A")
                            results.append(
                                f"- **{title}** (`{entry_id}`) - relevance: {relevance}"
                            )

                            # Store for later use in report
                            self.codex_patterns_applied.append(
                                {
                                    "pattern_id": entry_id,
                                    "title": title,
                                    "query": query,
                                    "relevance": str(relevance),
                                }
                            )
            except Exception as e:
                print(f"  ⚠️ Codex query '{query}' failed: {e}", file=sys.stderr)

        # Also try to get specific well-known patterns for the project type
        specific_patterns = {
            "flowise": [
                "afv2-routing-pattern",
                "flowise-start-node",
                "flowise-disconnected-agents",
            ],
            "mcp": ["mcp-server-template", "fastmcp-pattern"],
        }

        for pattern_id in specific_patterns.get(project_type, []):
            try:
                entry = codex_get_entry(pattern_id)
                if entry and not entry.get("error"):
                    results.append(f"\n### Pattern: `{pattern_id}`")
                    description = entry.get("description", "")[:200]
                    results.append(f"- {description}...")

                    # Store for report
                    if not any(
                        p["pattern_id"] == pattern_id
                        for p in self.codex_patterns_applied
                    ):
                        self.codex_patterns_applied.append(
                            {
                                "pattern_id": pattern_id,
                                "title": entry.get("title", pattern_id),
                                "query": "direct lookup",
                                "relevance": "direct match",
                            }
                        )
            except Exception:
                pass  # Pattern not found is OK

        if results:
            print(
                f"  ✅ Found {len(self.codex_patterns_applied)} relevant codex patterns",
                file=sys.stderr,
            )
            return (
                "\n## Context Codex Results (Pre-queried)\n\n"
                + "\n".join(results)
                + "\n"
            )
        else:
            print("  ℹ️ No matching codex patterns found", file=sys.stderr)
            return (
                "\n## Context Codex Results\n\n_No matching patterns found in codex._\n"
            )

    def run(
        self,
        working_directory: Union[Path, str],
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Finding]:
        """Run the scout agent (implements Agent interface)"""
        # Scout primarily uses project_root from init, but we can update it if passed
        if working_directory:
            self.project_root = (
                Path(working_directory)
                if isinstance(working_directory, str)
                else working_directory
            )

        # Reset codex patterns for this run
        self.codex_patterns_applied = []

        # Detect project type early - used for both new and existing projects
        self.detected_project_type = self._detect_project_type_from_repo()

        # Check if this is a new project (no meaningful code to scan)
        is_new_project = self._is_new_project()

        if is_new_project:
            print(
                "🆕 New project detected - analyzing requirements instead of scanning code"
            )
            # For new projects, use LLM to analyze the task description
            self._analyze_new_project_requirements(instruction, context, event_callback)
        else:
            # Existing codebase - run the scan
            findings = self.scan()

            # ACTUALLY query codex before AI analysis (not just prompt text)
            codex_context = self._query_codex_for_patterns(self.detected_project_type)

            # AI Analysis (uses LLM) - pass codex results as actual context
            self._ai_analyze_findings(
                findings, event_callback, codex_context=codex_context
            )

            # Save findings to file for downstream consumption (Architect/Builder)
            self._save_findings(findings, self.project_root)

        return self.findings

    def _detect_project_type_from_repo(self) -> Optional[str]:
        """
        Detect project type by scanning repository files.

        Samples up to 100 files and checks multiple indicators to ensure
        reliable detection even for larger projects.

        Returns:
            Project type string (e.g., 'flowise', 'mcp', 'fastapi') or None
        """
        # Check for Flowise indicators (file/directory names)
        for indicator in self.FLOWISE_INDICATORS:
            if "*" in indicator:
                # Glob pattern - check both root and subdirs
                if list(self.project_root.glob(indicator)) or list(
                    self.project_root.glob(f"**/{indicator}")
                ):
                    return "flowise"
            else:
                # Exact file/dir name
                if (self.project_root / indicator).exists():
                    return "flowise"
                # Also check in subdirectories (limit depth for performance)
                matches = list(self.project_root.glob(f"**/{indicator}"))[:5]
                if matches:
                    return "flowise"

        # Check for MCP server indicators
        for indicator in self.MCP_INDICATORS:
            if (self.project_root / indicator).exists():
                return "mcp"
            matches = list(self.project_root.glob(f"**/{indicator}"))[:5]
            if matches:
                return "mcp"

        # Check JSON files for Flowise structure (chatflow/agentflow exports)
        json_files = list(self.project_root.glob("**/*.json"))[:50]
        for json_file in json_files:
            if json_file.name in [
                ".package-lock.json",
                "package-lock.json",
                "node_modules",
            ]:
                continue
            try:
                content = json_file.read_text()[:10000]  # First 10KB
                # Flowise export structure indicators
                if '"nodes"' in content and '"edges"' in content:
                    if any(
                        x in content
                        for x in [
                            '"chatflowId"',
                            '"agentflowId"',
                            '"ChatOpenAI"',
                            '"AgentNode"',
                            '"ToolNode"',
                        ]
                    ):
                        return "flowise"
            except Exception:
                pass

        # Check Python files for framework patterns - INCREASED SAMPLE SIZE
        py_files = list(self.project_root.glob("**/*.py"))[:100]  # Sample 100 files
        flowise_score = 0
        mcp_score = 0

        for py_file in py_files:
            try:
                content = py_file.read_text()[:8000]  # First 8KB
                content_lower = content.lower()

                # MCP indicators
                if "from fastmcp" in content or "import fastmcp" in content:
                    mcp_score += 3
                if "mcp_server" in content_lower or "mcpserver" in content_lower:
                    mcp_score += 2
                if "@mcp.tool" in content or "mcp.resource" in content:
                    mcp_score += 2

                # Flowise indicators
                if "flowise" in content_lower:
                    flowise_score += 2
                if "chatflow" in content_lower or "agentflow" in content_lower:
                    flowise_score += 1
                if "FlowiseClient" in content or "flowise_api" in content_lower:
                    flowise_score += 2

            except Exception:
                pass

        # Check TypeScript/JavaScript files too
        js_files = list(self.project_root.glob("**/*.ts")) + list(
            self.project_root.glob("**/*.js")
        )
        for js_file in js_files[:50]:
            try:
                content = js_file.read_text()[:8000]
                if "flowise" in content.lower():
                    flowise_score += 2
                if "chatflow" in content.lower() or "agentflow" in content.lower():
                    flowise_score += 1
            except Exception:
                pass

        # Return based on scores (threshold of 3)
        if flowise_score >= 3:
            return "flowise"
        if mcp_score >= 3:
            return "mcp"

        return None

    def _is_new_project(self) -> bool:
        """Detect if this is a new project with no meaningful code to scan"""
        # Check for source code files (excluding .context-foundry)
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".html",
            ".css",
        }

        for path in self.project_root.rglob("*"):
            # Skip .context-foundry directory
            if ".context-foundry" in str(path):
                continue
            # Skip hidden files/directories
            if any(part.startswith(".") for part in path.parts):
                continue
            # Skip node_modules, venv, etc
            if self._is_dependency_path(path):
                continue
            # Check if it's a code file
            if path.is_file() and path.suffix.lower() in code_extensions:
                return False

        return True

    def _analyze_new_project_requirements(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]],
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """Use LLM to analyze task description for a new project"""

        # Get system prompt from context if available
        system_prompt = "You are a senior software architect analyzing requirements for a new project."
        if context and context.get("system_prompt"):
            system_prompt = context["system_prompt"]

        # Detect project type - check multiple sources:
        # 1. Context project_type (explicit)
        # 2. Instruction text (keywords)
        # 3. Repository files (scan for indicators)
        project_type = context.get("project_type", "") if context else ""
        instruction_lower = instruction.lower()

        # Use already-detected type from run() or detect now
        if not self.detected_project_type:
            self.detected_project_type = self._detect_project_type_from_repo()

        # Determine effective project type from multiple signals
        effective_type = self.detected_project_type
        if not effective_type:
            if "flowise" in instruction_lower or project_type == "flowise":
                effective_type = "flowise"
            elif (
                "mcp" in instruction_lower
                or "model context protocol" in instruction_lower
                or project_type == "mcp"
            ):
                effective_type = "mcp"

        # ACTUALLY query codex for new projects (not just prompt text)
        # This ensures codex is invoked for both new and existing projects
        codex_context = self._query_codex_for_patterns(effective_type)

        # Build codex section with ACTUAL results (not instructions to query)
        if self.codex_patterns_applied:
            codex_instructions = (
                codex_context
                + """
**NOTE**: The above patterns were pre-queried from Context Codex. Reference relevant pattern IDs in your codex_patterns_applied field.
"""
            )
        elif codex_context:
            # Codex was queried but no patterns found
            codex_instructions = codex_context
        else:
            # Codex module unavailable
            codex_instructions = """
## Context Codex

_Codex module unavailable - analysis proceeding without pattern lookup._
"""

        user_prompt = f"""Analyze the following project requirements and create a comprehensive scout report.

## Project Task
{instruction}
{codex_instructions}
## Your Analysis Should Include

1. **Project Type**: What kind of application is this? (web app, CLI, API, game, etc.)
2. **Core Features**: List the main features that need to be built
3. **Technical Requirements**: What technologies, frameworks, or libraries are recommended?
4. **File Structure**: Suggest a basic project structure
5. **Implementation Priorities**: What should be built first?
6. **Potential Challenges**: Any technical challenges to be aware of?
7. **Best Practices**: Relevant best practices for this type of project
8. **Codex Patterns Applied**: Reference any patterns from the pre-queried codex results above

## Output Format

Return a JSON object with this structure:
```json
{{
  "project_type": "string",
  "project_name": "string",
  "description": "string",
  "codex_patterns_applied": [
    {{"pattern_id": "string", "relevance": "string"}}
  ],
  "core_features": [
    {{"name": "string", "description": "string", "priority": "P0|P1|P2|P3"}}
  ],
  "technical_stack": {{
    "language": "string",
    "framework": "string",
    "additional_libraries": ["string"]
  }},
  "file_structure": [
    "path/to/file.ext"
  ],
  "implementation_order": ["feature1", "feature2"],
  "challenges": ["string"],
  "best_practices": ["string"]
}}
```

Return the JSON analysis based on the requirements and any codex patterns shown above."""

        try:
            print("🤖 Analyzing project requirements with AI...")
            print(f"   Provider: {type(self.llm_provider).__name__}", file=sys.stderr)

            response_text = self.llm_provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                working_directory=self.project_root,
                event_callback=event_callback,
            )

            print(
                f"   Response length: {len(response_text) if response_text else 0} chars",
                file=sys.stderr,
            )
            if response_text:
                print(f"   Response preview: {response_text[:500]}...", file=sys.stderr)
            else:
                print("   Response is empty!", file=sys.stderr)

            # For LocalClaudeProvider using --print mode, Claude's response includes
            # <write_to_file> or <write> tags that aren't actually executed.
            # We need to extract the content and write it ourselves.
            analysis = self._extract_scout_json_from_response(response_text)
            if analysis is None:
                raise ValueError("Could not extract structured analysis from response")

            # Convert analysis to findings for downstream phases
            self._convert_analysis_to_findings(analysis)

            # Save the full analysis
            self._save_new_project_analysis(analysis)

            print(
                f"✅ Scout analyzed {len(analysis.get('core_features', []))} features for {analysis.get('project_type', 'unknown')} project"
            )

        except Exception as e:
            import traceback

            print(f"⚠️ AI analysis parsing failed: {e}", file=sys.stderr)

            # Check if Claude CLI already created the files directly (via <write> tool)
            cf_dir = self.project_root / ".context-foundry"
            json_report = cf_dir / "scout_report.json"
            md_report = cf_dir / "scout-report.md"

            if json_report.exists() and json_report.stat().st_size > 100:
                # Files already created by Claude CLI - read and parse them
                try:
                    analysis = json.loads(json_report.read_text())
                    print(
                        "📖 Found existing scout_report.json created by Claude CLI",
                        file=sys.stderr,
                    )

                    # If it's already in the proper format, use it
                    if "core_features" in analysis or "project_type" in analysis:
                        self._convert_analysis_to_findings(analysis)
                        print(
                            f"✅ Scout analyzed {len(analysis.get('core_features', []))} features",
                            file=sys.stderr,
                        )
                        return
                except Exception as parse_err:
                    print(
                        f"⚠️ Could not parse existing scout_report.json: {parse_err}",
                        file=sys.stderr,
                    )

            # Check markdown file
            if md_report.exists() and md_report.stat().st_size > 500:
                print(
                    f"📖 Found existing scout-report.md ({md_report.stat().st_size} bytes)",
                    file=sys.stderr,
                )
                # Don't overwrite the good report
                return

            print(f"   Full traceback: {traceback.format_exc()}", file=sys.stderr)
            # Create minimal finding to continue the build only if no good report exists
            self.findings.append(
                Finding(
                    title=f"Build new project: {instruction[:80]}",
                    finding_type="enhancement",
                    priority="P0",
                    category=["new-project", "build"],
                    description=instruction,
                    effort="large",
                )
            )
            self._save_findings(self.findings, self.project_root)

    def _extract_scout_json_from_response(self, response_text: str) -> Optional[dict]:
        """
        Extract scout JSON from Claude's response.

        Claude may output JSON in various formats:
        1. Pure JSON
        2. JSON in markdown code blocks (```json ... ```)
        3. JSON inside <write_to_file> or <write> tags
        4. JSON inside <content> tags
        """
        import re

        # Try 1: Check for <write_to_file> or <write> with scout_report.json
        json_patterns = [
            r"<path>.*?scout_report\.json</path>\s*<content>(.*?)</content>",
            r"scout_report\.json.*?<content>(.*?)</content>",
            r'"scout_report\.json"[^{]*(\{[\s\S]*?\n\})',  # JSON after filename
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                json_content = match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    continue

        # Try 2: Look for JSON code block with project_type or core_features
        json_block_pattern = r"```json\s*([\s\S]*?)```"
        for match in re.finditer(json_block_pattern, response_text):
            json_content = match.group(1).strip()
            try:
                data = json.loads(json_content)
                if isinstance(data, dict) and (
                    "core_features" in data or "project_type" in data
                ):
                    return data
            except json.JSONDecodeError:
                continue

        # Try 3: Look for raw JSON object with expected fields
        json_pattern = r'\{\s*"project_type"[\s\S]*?"core_features"[\s\S]*?\}'
        match = re.search(json_pattern, response_text)
        if match:
            # Find the complete JSON by counting braces
            start = match.start()
            brace_count = 0
            end = start
            for i, char in enumerate(response_text[start:]):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = start + i + 1
                        break

            json_content = response_text[start:end]
            try:
                return json.loads(json_content)
            except json.JSONDecodeError:
                pass

        # Try 4: Extract markdown scout report and create minimal JSON from it
        md_patterns = [
            r"<path>.*?scout-report\.md</path>\s*<content>(.*?)</content>",
            r"<write_to_file>.*?scout-report\.md.*?<content>(.*?)</content>",
        ]

        for pattern in md_patterns:
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                md_content = match.group(1).strip()
                # Save the markdown file and return minimal analysis
                cf_dir = self.project_root / ".context-foundry"
                cf_dir.mkdir(parents=True, exist_ok=True)
                md_path = cf_dir / "scout-report.md"
                md_path.write_text(md_content)
                print(
                    f"📝 Extracted and saved scout-report.md ({len(md_content)} bytes)"
                )

                # Create minimal analysis from markdown
                return {
                    "project_type": "web application",
                    "project_name": "project",
                    "description": "Project created from scout report",
                    "core_features": [
                        {
                            "name": "Main Feature",
                            "description": "See scout-report.md",
                            "priority": "P0",
                        }
                    ],
                    "technical_stack": {
                        "language": "Unknown",
                        "framework": "Unknown",
                        "additional_libraries": [],
                    },
                    "file_structure": [],
                    "implementation_order": [],
                    "challenges": [],
                    "best_practices": [],
                }

        return None

    def _convert_analysis_to_findings(self, analysis: dict):
        """Convert AI analysis to Finding objects for downstream consumption"""
        # Create a finding for each core feature
        for feature in analysis.get("core_features", []):
            self.findings.append(
                Finding(
                    title=f"Implement: {feature.get('name', 'Unknown feature')}",
                    finding_type="enhancement",
                    priority=feature.get("priority", "P1"),
                    category=["new-project", "feature"],
                    description=feature.get("description", ""),
                    effort="medium",
                )
            )

        # Add a meta-finding for the project structure
        if analysis.get("file_structure"):
            self.findings.append(
                Finding(
                    title="Create project file structure",
                    finding_type="enhancement",
                    priority="P0",
                    category=["new-project", "setup"],
                    description=f"Create files: {', '.join(analysis['file_structure'][:5])}...",
                    effort="small",
                )
            )

    def _save_new_project_analysis(self, analysis: dict):
        """Save the new project analysis as scout report"""
        cf_dir = self.project_root / ".context-foundry"
        cf_dir.mkdir(parents=True, exist_ok=True)

        # Include actually-queried codex patterns in the JSON output
        analysis_with_codex = analysis.copy()
        analysis_with_codex["_codex_actually_queried"] = self.codex_patterns_applied
        analysis_with_codex["_codex_available"] = self.codex_available
        analysis_with_codex["_detected_project_type"] = self.detected_project_type

        # Save JSON
        json_path = cf_dir / "scout_report.json"
        json_path.write_text(json.dumps(analysis_with_codex, indent=2))

        # Save Markdown
        md_path = cf_dir / "scout-report.md"
        md_content = f"""# Scout Report - New Project Analysis

## Project Overview
- **Type**: {analysis.get('project_type', 'Unknown')}
- **Name**: {analysis.get('project_name', 'Unknown')}
- **Description**: {analysis.get('description', 'N/A')}

## Codex Patterns Applied

"""
        # Show warning if codex was unavailable
        if not self.codex_available:
            md_content += "**⚠️ WARNING: Codex module was unavailable. Patterns below are LLM-generated, not verified.**\n\n"

        # Use ACTUALLY queried patterns first, fall back to LLM-generated
        if self.codex_patterns_applied:
            md_content += "**Source: Pre-queried from Context Codex**\n\n"
            md_content += "| Pattern ID | Title | Query | Relevance |\n"
            md_content += "|------------|-------|-------|----------|\n"
            for pattern in self.codex_patterns_applied:
                pattern_id = pattern.get("pattern_id", "unknown")
                title = pattern.get("title", pattern_id)[:40]
                query = pattern.get("query", "N/A")[:30]
                relevance = pattern.get("relevance", "N/A")
                md_content += f"| `{pattern_id}` | {title} | {query} | {relevance} |\n"
        else:
            # Fall back to LLM-generated patterns (with warning)
            codex_patterns = analysis.get("codex_patterns_applied", [])
            if codex_patterns:
                md_content += (
                    "**Source: LLM-generated (not verified against codex)**\n\n"
                )
                md_content += "| Pattern ID | Relevance |\n"
                md_content += "|------------|----------|\n"
                for pattern in codex_patterns:
                    if isinstance(pattern, dict):
                        pattern_id = pattern.get("pattern_id", "unknown")
                        relevance = pattern.get("relevance", "N/A")
                    else:
                        pattern_id = str(pattern)
                        relevance = "Applied"
                    md_content += f"| `{pattern_id}` | {relevance} |\n"
            else:
                md_content += "_No codex patterns were applied to this analysis._\n"

        md_content += f"""
## Technical Stack
- **Language**: {analysis.get('technical_stack', {}).get('language', 'Not specified')}
- **Framework**: {analysis.get('technical_stack', {}).get('framework', 'Not specified')}
- **Libraries**: {', '.join(analysis.get('technical_stack', {}).get('additional_libraries', []))}

## Core Features
"""
        for i, feature in enumerate(analysis.get("core_features", []), 1):
            md_content += f"\n### {i}. {feature.get('name', 'Feature')}\n"
            md_content += f"- **Priority**: {feature.get('priority', 'P1')}\n"
            md_content += f"- **Description**: {feature.get('description', 'N/A')}\n"

        md_content += f"""
## Recommended File Structure
```
{chr(10).join(analysis.get('file_structure', ['No structure specified']))}
```

## Implementation Order
{chr(10).join(f"1. {item}" for item in analysis.get('implementation_order', []))}

## Potential Challenges
{chr(10).join(f"- {c}" for c in analysis.get('challenges', []))}

## Best Practices
{chr(10).join(f"- {bp}" for bp in analysis.get('best_practices', []))}
"""
        md_path.write_text(md_content)
        print(f"📝 Saved scout report to {md_path}")

    def _save_findings(self, findings: List[Finding], working_directory: Path):
        """Save findings to JSON and Markdown for other agents"""
        cf_dir = working_directory / ".context-foundry"
        cf_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON - include codex patterns and availability in the JSON output
        json_path = cf_dir / "scout_report.json"
        report_data = {
            "findings": [f.to_dict() for f in findings],
            "detected_project_type": self.detected_project_type,
            "codex_patterns_applied": self.codex_patterns_applied,
            "codex_available": self.codex_available,
        }
        json_path.write_text(json.dumps(report_data, indent=2))

        # Save Markdown
        md_path = cf_dir / "scout-report.md"
        md_content = "# Scout Report\n\n"

        # ALWAYS add Codex Patterns Applied section (not conditional on detected_type)
        md_content += "## Codex Patterns Applied\n\n"

        # Show warning if codex was unavailable
        if not self.codex_available:
            md_content += "**⚠️ WARNING: Codex module was unavailable. Analysis proceeded without pattern lookup.**\n\n"

        if self.detected_project_type:
            md_content += f"**Detected Project Type:** {self.detected_project_type}\n\n"
        else:
            md_content += "**Detected Project Type:** generic\n\n"

        # Use the actual codex patterns that were queried (stored in self.codex_patterns_applied)
        if self.codex_patterns_applied:
            md_content += "**Source: Pre-queried from Context Codex**\n\n"
            md_content += "| Pattern ID | Title | Query | Relevance |\n"
            md_content += "|------------|-------|-------|----------|\n"
            for pattern in self.codex_patterns_applied:
                pattern_id = pattern.get("pattern_id", "unknown")
                title = pattern.get("title", pattern_id)[:40]
                query = pattern.get("query", "N/A")[:30]
                relevance = pattern.get("relevance", "N/A")
                md_content += f"| `{pattern_id}` | {title} | {query} | {relevance} |\n"
        else:
            if self.codex_available:
                md_content += "_No matching patterns found in Context Codex._\n"
            else:
                md_content += "_Codex unavailable - could not query for patterns._\n"
        md_content += "\n"

        md_content += "## Findings\n\n"
        for f in findings:
            md_content += f"### {f.title}\n"
            md_content += f"- **Type:** {f.finding_type}\n"
            md_content += f"- **Priority:** {f.priority}\n"
            md_content += f"- **File:** {f.file_path}\n"
            md_content += f"\n{f.description}\n\n"
        md_path.write_text(md_content)

    def get_system_prompt(self) -> str:
        """Return the system prompt used for AI analysis"""
        # This is dynamically generated in _ai_analyze_findings, but we can return the base persona here
        return "You are an expert code analyst evaluating static analysis findings."

    def scan(self) -> List[Finding]:
        """Run all scans and return findings"""

        print("🔍 Scout Agent starting autonomous scan...")
        print()

        # Run all analysis passes (original scanners)
        self._scan_missing_tests()
        self._scan_security_patterns()
        self._scan_performance_issues()
        self._scan_error_handling()
        self._scan_dependencies()
        self._scan_code_quality()
        self._scan_architectural_debt()

        # Run new balanced opportunity scanners
        self._scan_feature_opportunities()
        self._scan_api_enhancements()
        self._scan_developer_experience()
        self._scan_modern_language_features()
        self._scan_observability()
        self._scan_user_experience()
        self._scan_configuration()
        self._scan_extensibility()

        print(f"✅ Scout found {len(self.findings)} issues")
        print()

        # Deduplicate and prioritize
        self._deduplicate()
        self._sort_by_priority()

        # AI-powered multi-perspective filtering
        # Note: We return raw findings here because AI analysis is now done in run()
        # or called explicitly with event_callback
        return self.findings

    # ... (keeping existing scanner methods) ...

    def _ai_analyze_findings(
        self,
        findings: List[Finding],
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        codex_context: str = "",
    ) -> List[Finding]:
        """
        Use LLM to analyze findings through multiple expert perspectives.

        Args:
            findings: List of findings to analyze
            event_callback: Optional callback for events
            codex_context: Pre-queried codex results (actual data, not instructions)

        Returns filtered list of high-priority findings worthy of GitHub issues
        """
        if not findings:
            return []

        # Use the pre-queried codex context (actual results, not prompt instructions)
        # This ensures codex was actually invoked, not just suggested to the LLM
        codex_section = codex_context if codex_context else ""

        # Ensure diverse sample for AI analysis
        # Take top findings from each type to avoid one type dominating
        findings_by_type = {}
        for f in findings:
            if f.finding_type not in findings_by_type:
                findings_by_type[f.finding_type] = []
            findings_by_type[f.finding_type].append(f)

        # Build diverse sample: top 5 from each type, prioritizing critical types
        critical_types = ["security", "bug", "performance"]
        other_types = [t for t in findings_by_type.keys() if t not in critical_types]

        findings_to_analyze = []

        # Always include ALL security/bug/performance issues (they're rare and critical)
        for ftype in critical_types:
            if ftype in findings_by_type:
                findings_to_analyze.extend(findings_by_type[ftype])

        # Add top 5 from each other type
        for ftype in other_types:
            findings_to_analyze.extend(findings_by_type[ftype][:5])

        # Cap at 30 total
        findings_to_analyze = findings_to_analyze[:30]

        # Format findings as structured data for Claude
        findings_json = []
        for i, finding in enumerate(findings_to_analyze, 1):
            findings_json.append(
                {
                    "id": i,
                    "title": finding.title,
                    "type": finding.finding_type,
                    "priority": finding.priority,
                    "category": finding.category,
                    "description": finding.description,
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "evidence": finding.evidence,
                    "effort": finding.effort,
                }
            )

        # Create the multi-perspective analysis prompt
        system_prompt = (
            "You are an expert code analyst evaluating static analysis findings."
        )

        user_prompt = f"""You are analyzing {len(findings_to_analyze)} code findings from a static analysis tool for the Context Foundry project.

Your task: Evaluate each finding through 6 expert lenses and select the top 5-10 findings that should become GitHub issues.
{codex_section}
## Expert Perspectives:

🔒 **Security Analyst**: Critical vulnerabilities, attack vectors, data exposure risks
⚙️ **DevOps Engineer**: Deployment risks, operational concerns, reliability issues
📊 **Functional Consultant**: User impact, business value, feature gaps
💼 **Business SME**: ROI, strategic alignment, competitive advantage
👨‍💻 **Developer**: Technical debt, maintainability, developer experience
🏗️ **Architect**: System design, scalability, architectural coherence

## Findings to Analyze:

```json
{json.dumps(findings_json, indent=2)}
```

## Instructions:

1. Analyze each finding through ALL 6 perspectives
2. Score each finding 0-10 for overall priority (considering all perspectives)
3. Select the top 5-10 findings that should become GitHub issues
4. **IMPORTANT**: Prioritize DIVERSITY of issue types:
   - Prefer security, bug, and performance issues over enhancement
   - If multiple "Add tests" issues exist, select at most 2-3
   - Ensure variety: bugs, security, performance, debt, features
   - "Add tests" issues are valuable but shouldn't dominate the backlog
5. For each selected finding, provide:
   - Overall priority score (0-10)
   - Which expert perspectives rated it highly (and why)
   - Recommended GitHub labels
   - Updated priority (P0-P4)
   - Reasoning

## Output Format:

Return ONLY valid JSON in this exact format:

```json
{{
  "prioritized_findings": [
    {{
      "id": 1,
      "score": 9,
      "expert_perspectives": {{
        "security": "Critical SQL injection risk - HIGH",
        "devops": "Could cause production outages - HIGH",
        "developer": "Easy fix, high impact - MEDIUM"
      }},
      "github_labels": ["security", "p0", "bug"],
      "priority": "P0",
      "reasoning": "Multi-perspective summary of why this is important"
    }}
  ]
}}
```

Return ONLY the JSON, no other text."""

        try:
            # Use LLMProvider to generate response
            response_text = self.llm_provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                working_directory=self.project_root,
                event_callback=event_callback,
            )

            # Extract JSON from response (Claude might wrap it in markdown)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            analysis = json.loads(response_text)

            # Map AI-prioritized findings back to Finding objects
            prioritized = []
            for item in analysis.get("prioritized_findings", []):
                finding_id = item["id"] - 1  # Convert 1-indexed to 0-indexed
                if 0 <= finding_id < len(findings_to_analyze):
                    original_finding = findings_to_analyze[finding_id]

                    # Update finding with AI insights
                    original_finding.priority = item.get(
                        "priority", original_finding.priority
                    )
                    original_finding.research = {
                        "ai_score": item.get("score"),
                        "expert_perspectives": item.get("expert_perspectives", {}),
                        "reasoning": item.get("reasoning", ""),
                        "github_labels": item.get("github_labels", []),
                    }

                    prioritized.append(original_finding)

            print(
                f"  ✅ AI filtered {len(findings_to_analyze)} findings → {len(prioritized)} high-priority issues"
            )
            print("  📊 Top issues by expert consensus:")
            for i, finding in enumerate(prioritized[:5], 1):
                score = finding.research.get("ai_score", 0) if finding.research else 0
                print(
                    f"     {i}. [{finding.priority}] {finding.title[:60]} (score: {score}/10)"
                )

            return prioritized if prioritized else findings

        except Exception as e:
            print(f"  ⚠️  AI analysis failed: {e}")
            print(f"  Falling back to original {len(findings)} findings")
            return findings

    def _scan_missing_tests(self):
        """Find files without test coverage"""

        print("  📋 Scanning for missing tests...")

        # Find all Python files
        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            # Skip test files themselves
            if self._is_test_path(py_file):
                continue

            # Skip __init__.py
            if py_file.name == "__init__.py":
                continue

            # Check if corresponding test exists (any matching test file)
            test_files = self._get_test_file_path(py_file)

            if not test_files:
                # Check if file has meaningful code (>20 lines, has functions)
                if self._has_testable_code(py_file):
                    self.findings.append(
                        Finding(
                            title=f"Add tests for {py_file.relative_to(self.project_root)}",
                            finding_type="enhancement",
                            priority="P2",
                            category=["testing", "quality"],
                            description=f"No test coverage found for {py_file.name}. File contains testable functions but lacks unit tests.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )

    def _scan_security_patterns(self):
        """Detect common security anti-patterns"""

        print("  🔒 Scanning for security vulnerabilities...")

        # Get all Python files but exclude test files and dependencies (third-party code we don't control)
        all_py_files = list(self.project_root.glob("**/*.py"))
        py_files = [
            f
            for f in all_py_files
            if not self._is_test_path(f) and not self._is_dependency_path(f)
        ]

        security_patterns = [
            (r"\beval\s*\(", "Dangerous use of eval() - code injection risk"),
            (r"\bexec\s*\(", "Dangerous use of exec() - code injection risk"),
            (
                r"pickle\.loads?\s*\(",
                "Unsafe pickle usage - arbitrary code execution risk",
            ),
            (
                r"subprocess\.(call|run|Popen).*shell\s*=\s*True",
                "Shell injection risk with shell=True",
            ),
            (r"os\.system\s*\(", "Command injection risk with os.system()"),
            (r"\.format\([^)]*\%", "SQL injection risk - use parameterized queries"),
        ]

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for pattern, warning in security_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[: match.start()].count("\n") + 1

                        # Skip false positives
                        should_skip = False

                        # Get the full line for context checking
                        if 0 < line_num <= len(lines):
                            full_line = lines[line_num - 1].strip()

                            # Skip false positives: comments and string literals in pattern definitions
                            if full_line.startswith("#"):
                                should_skip = True
                            elif full_line.startswith('"""') or full_line.startswith(
                                "'''"
                            ):
                                should_skip = True
                            # Skip if it's in a regex pattern string (common in security scanners)
                            # This includes patterns like: (r'os\.system\s*\(', 'description')
                            elif full_line.startswith("(") and (
                                "r'" in full_line or 'r"' in full_line
                            ):
                                should_skip = True
                            # Skip documentation examples showing unsafe patterns (lines with # ❌ UNSAFE)
                            elif "# ❌ UNSAFE" in full_line or "# UNSAFE" in full_line:
                                should_skip = True

                        if should_skip:
                            continue

                        self.findings.append(
                            Finding(
                                title=f"Security: {warning} in {py_file.name}",
                                finding_type="security",
                                priority="P0",  # Security is always high priority
                                category=["security", "vulnerability"],
                                description=f"{warning}\n\nFound at line {line_num} in {py_file.relative_to(self.project_root)}",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=line_num,
                                evidence=match.group(0),
                                effort="small",
                            )
                        )
            except Exception:
                pass

    def _scan_performance_issues(self):
        """Detect performance anti-patterns"""

        print("  ⚡ Scanning for performance issues...")

        # Check database usage
        db_files = list(self.project_root.glob("**/task_queue.py"))

        for db_file in db_files:
            try:
                content = db_file.read_text()

                # Check for missing indexes
                if "CREATE TABLE" in content and "CREATE INDEX" not in content:
                    self.findings.append(
                        Finding(
                            title=f"Performance: Missing database indexes in {db_file.name}",
                            finding_type="performance",
                            priority="P2",
                            category=["performance", "database"],
                            description="Database tables created without indexes. This will cause slow queries as data grows.",
                            file_path=str(db_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for N+1 query patterns
                if content.count("execute(") > 10:
                    self.findings.append(
                        Finding(
                            title=f"Performance: Potential N+1 query pattern in {db_file.name}",
                            finding_type="performance",
                            priority="P3",
                            category=["performance", "database"],
                            description="Multiple database execute() calls detected. Consider batch operations or joins to reduce query count.",
                            file_path=str(db_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )
            except Exception:
                pass

    def _scan_error_handling(self):
        """Find missing error handling"""

        print("  ⚠️  Scanning for error handling gaps...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Count subprocess calls without error handling
                subprocess_calls = len(
                    re.findall(r"subprocess\.(run|call|Popen)", content)
                )
                try_blocks = len(re.findall(r"try:", content))

                if subprocess_calls > try_blocks:
                    self.findings.append(
                        Finding(
                            title=f"Reliability: Add error handling for subprocess calls in {py_file.name}",
                            finding_type="bug",
                            priority="P2",
                            category=["reliability", "error-handling"],
                            description=f"Found {subprocess_calls} subprocess calls but only {try_blocks} try/except blocks. Subprocess failures will crash the program.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except Exception:
                pass

    def _scan_dependencies(self):
        """Check for outdated or vulnerable dependencies"""

        print("  📦 Scanning dependencies...")

        # Check if requirements.txt exists
        req_file = self.project_root / "requirements.txt"

        if req_file.exists():
            try:
                # Run pip-audit if available (would need to be installed)
                # For now, just check for old Python version requirement
                content = req_file.read_text()

                # Simple heuristic: check for unpinned versions
                unpinned = []
                for line in content.splitlines():
                    if line.strip() and not line.startswith("#"):
                        if "==" not in line and ">=" not in line:
                            unpinned.append(line.strip())

                if unpinned:
                    self.findings.append(
                        Finding(
                            title="Dependencies: Pin package versions for reproducibility",
                            finding_type="enhancement",
                            priority="P3",
                            category=["dependencies", "reliability"],
                            description=f"Found {len(unpinned)} unpinned dependencies: {', '.join(unpinned[:3])}. Pin versions to ensure reproducible builds.",
                            file_path="requirements.txt",
                            effort="small",
                        )
                    )
            except Exception:
                pass

    def _scan_code_quality(self):
        """Detect code quality issues"""

        print("  ✨ Scanning code quality...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Check for very long files (>500 lines)
                if len(lines) > 500:
                    self.findings.append(
                        Finding(
                            title=f"Code Quality: Refactor large file {py_file.name} ({len(lines)} lines)",
                            finding_type="debt",
                            priority="P4",
                            category=["code-quality", "maintainability"],
                            description=f"File has {len(lines)} lines. Consider breaking into smaller, focused modules for better maintainability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="large",
                        )
                    )

                # Check for missing docstrings
                func_count = content.count("def ")
                docstring_count = content.count('"""')

                if func_count > 3 and docstring_count < func_count * 0.3:
                    self.findings.append(
                        Finding(
                            title=f"Documentation: Add docstrings to {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["documentation", "maintainability"],
                            description=f"Only {docstring_count}/{func_count} functions have docstrings. Add documentation for better maintainability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except Exception:
                pass

    def _scan_architectural_debt(self):
        """Identify architectural issues that need architect input"""

        print("  🏗️  Scanning for architectural debt...")

        # Check for SQLite usage in high-concurrency scenarios
        db_files = list(self.project_root.glob("**/task_queue.py"))

        for db_file in db_files:
            try:
                content = db_file.read_text()

                if "sqlite3" in content and "check_same_thread=False" in content:
                    finding = Finding(
                        title="Architecture: Evaluate database alternatives to SQLite",
                        finding_type="enhancement",
                        priority="P2",
                        category=["architecture", "performance", "scalability"],
                        description="SQLite is used with threading disabled (check_same_thread=False). This indicates concurrency concerns. Consider PostgreSQL or Supabase for better concurrent access.",
                        file_path=str(db_file.relative_to(self.project_root)),
                        effort="large",
                    )
                    # Mark for architect review
                    finding.needs_architect = True
                    self.findings.append(finding)
            except Exception:
                pass

    def _scan_feature_opportunities(self):
        """Find opportunities for new features (commented code, TODOs, stubs)"""

        print("  🌱 Scanning for feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    line_stripped = line.strip()

                    # Find TODO comments for features
                    if "TODO" in line_stripped and any(
                        keyword in line_stripped.lower()
                        for keyword in ["add", "implement", "feature", "support"]
                    ):
                        self.findings.append(
                            Finding(
                                title=f"Feature: {line_stripped.replace('# TODO:', '').replace('# TODO', '').strip()[:80]}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["feature", "opportunity"],
                                description=f"TODO comment suggests new feature: {line_stripped}",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=i,
                                evidence=line_stripped,
                                effort="medium",
                            )
                        )

                    # Find stub methods (pass or raise NotImplementedError)
                    if "def " in line:
                        # Check next few lines for stub indicators
                        func_name = re.search(r"def\s+(\w+)", line)
                        if func_name and i < len(lines):
                            next_lines = "\n".join(lines[i : min(i + 5, len(lines))])
                            if (
                                "pass" in next_lines
                                and "NotImplementedError" not in next_lines
                            ):
                                if not any(
                                    x in next_lines
                                    for x in ["try:", "except:", "finally:"]
                                ):
                                    self.findings.append(
                                        Finding(
                                            title=f"Feature: Implement stub method {func_name.group(1)} in {py_file.name}",
                                            finding_type="enhancement",
                                            priority="P3",
                                            category=["feature", "stub"],
                                            description=f"Method {func_name.group(1)} is a stub (only contains 'pass'). Consider implementing or removing.",
                                            file_path=str(
                                                py_file.relative_to(self.project_root)
                                            ),
                                            line_number=i,
                                            effort="medium",
                                        )
                                    )
                            elif "NotImplementedError" in next_lines:
                                self.findings.append(
                                    Finding(
                                        title=f"Feature: Implement {func_name.group(1)} in {py_file.name}",
                                        finding_type="enhancement",
                                        priority="P3",
                                        category=["feature", "stub"],
                                        description=f"Method {func_name.group(1)} raises NotImplementedError. Feature is planned but not implemented.",
                                        file_path=str(
                                            py_file.relative_to(self.project_root)
                                        ),
                                        line_number=i,
                                        effort="medium",
                                    )
                                )

                # Find large commented-out code blocks (potential features)
                commented_blocks = re.findall(r"(#.*\n){5,}", content)
                if commented_blocks:
                    self.findings.append(
                        Finding(
                            title=f"Feature: Review commented code in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["feature", "cleanup"],
                            description=f"Found {len(commented_blocks)} large commented-out code blocks. These may be features waiting to be implemented or dead code to remove.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except Exception:
                pass

    def _scan_api_enhancements(self):
        """Find opportunities to improve API completeness"""

        print("  🔌 Scanning for API enhancements...")

        # Look for API/endpoint files
        api_files = (
            list(self.project_root.glob("**/api*.py"))
            + list(self.project_root.glob("**/routes*.py"))
            + list(self.project_root.glob("**/endpoints*.py"))
        )

        for api_file in api_files:
            try:
                content = api_file.read_text()

                # Check for missing pagination on list endpoints
                if "def list" in content.lower() or "get_all" in content.lower():
                    if (
                        "limit" not in content.lower()
                        and "offset" not in content.lower()
                        and "page" not in content.lower()
                    ):
                        self.findings.append(
                            Finding(
                                title=f"API: Add pagination to list endpoint in {api_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["api", "scalability"],
                                description="List endpoint doesn't implement pagination. This will cause performance issues with large datasets.",
                                file_path=str(api_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for incomplete CRUD operations
                has_get = bool(re.search(r"def\s+get", content, re.IGNORECASE))
                has_post = bool(
                    re.search(r"def\s+(post|create)", content, re.IGNORECASE)
                )
                has_put = bool(re.search(r"def\s+(put|update)", content, re.IGNORECASE))
                has_delete = bool(re.search(r"def\s+delete", content, re.IGNORECASE))

                crud_ops = {
                    "GET": has_get,
                    "POST": has_post,
                    "PUT": has_put,
                    "DELETE": has_delete,
                }
                missing_ops = [op for op, exists in crud_ops.items() if not exists]

                if len(missing_ops) > 0 and len(missing_ops) < 4:
                    self.findings.append(
                        Finding(
                            title=f"API: Complete CRUD operations in {api_file.name}",
                            finding_type="enhancement",
                            priority="P3",
                            category=["api", "completeness"],
                            description=f"API has partial CRUD implementation. Missing: {', '.join(missing_ops)}. Consider adding for completeness.",
                            file_path=str(api_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )

                # Check for missing rate limiting
                if "app.route" in content or "@router" in content:
                    if (
                        "rate_limit" not in content.lower()
                        and "ratelimit" not in content.lower()
                        and "throttle" not in content.lower()
                    ):
                        self.findings.append(
                            Finding(
                                title=f"API: Add rate limiting to {api_file.name}",
                                finding_type="enhancement",
                                priority="P2",
                                category=["api", "security", "reliability"],
                                description="API endpoints lack rate limiting. This leaves the service vulnerable to abuse and DoS attacks.",
                                file_path=str(api_file.relative_to(self.project_root)),
                                effort="medium",
                            )
                        )
            except Exception:
                pass

    def _scan_developer_experience(self):
        """Find opportunities to improve code maintainability"""

        print("  👨‍💻 Scanning for developer experience improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Check for magic numbers
                magic_numbers = []
                for i, line in enumerate(lines, 1):
                    # Skip comments and strings
                    if "#" in line:
                        line = line[: line.index("#")]

                    # Find numeric literals that aren't 0, 1, -1
                    numbers = re.findall(r"\b([2-9]\d+)\b", line)
                    if numbers and "def " not in line:
                        magic_numbers.extend([(i, num) for num in numbers])

                if len(magic_numbers) > 5:
                    self.findings.append(
                        Finding(
                            title=f"DX: Replace magic numbers with named constants in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "maintainability"],
                            description=f"Found {len(magic_numbers)} magic numbers. Use named constants for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for unclear variable names
                unclear_vars = []
                for match in re.finditer(
                    r"\b(x|y|z|tmp|temp|data|val|var|foo|bar)\s*=", content
                ):
                    line_num = content[: match.start()].count("\n") + 1
                    unclear_vars.append((line_num, match.group(1)))

                if len(unclear_vars) > 3:
                    self.findings.append(
                        Finding(
                            title=f"DX: Use descriptive variable names in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "readability"],
                            description=f"Found {len(unclear_vars)} unclear variable names (x, tmp, data, etc). Use descriptive names for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for complex functions (>50 lines)
                func_pattern = re.compile(r"^( *)def\s+(\w+)", re.MULTILINE)
                func_matches = list(func_pattern.finditer(content))

                for i, match in enumerate(func_matches):
                    func_start = content[: match.start()].count("\n") + 1
                    func_indent = len(match.group(1))

                    # Find end of function (next function at same or lower indent, or EOF)
                    func_end = len(lines)
                    if i + 1 < len(func_matches):
                        next_indent = len(func_matches[i + 1].group(1))
                        if next_indent <= func_indent:
                            func_end = (
                                content[: func_matches[i + 1].start()].count("\n") + 1
                            )

                    func_length = func_end - func_start

                    if func_length > 50:
                        self.findings.append(
                            Finding(
                                title=f"DX: Refactor complex function {match.group(2)} in {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["dx", "maintainability"],
                                description=f"Function {match.group(2)} is {func_length} lines long. Consider breaking into smaller functions.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=func_start,
                                effort="medium",
                            )
                        )

                # Check for missing type hints (Python 3.5+)
                func_count = content.count("def ")
                type_hint_count = content.count(" -> ")

                if func_count > 5 and type_hint_count < func_count * 0.2:
                    self.findings.append(
                        Finding(
                            title=f"DX: Add type hints to {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "type-safety"],
                            description=f"Only {type_hint_count}/{func_count} functions have return type hints. Add type hints for better IDE support and error detection.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )
            except Exception:
                pass

    def _scan_modern_language_features(self):
        """Find opportunities to use modern Python features"""

        print("  🚀 Scanning for modern language feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for old-style string formatting
                old_format_count = len(re.findall(r"%[sd]", content))
                format_count = len(re.findall(r"\.format\(", content))
                fstring_count = len(re.findall(r'f["\']', content))

                if (old_format_count > 3 or format_count > 5) and fstring_count < (
                    old_format_count + format_count
                ) * 0.3:
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use f-strings in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["modernization", "readability"],
                            description="Found old-style string formatting (%s, .format()). Consider using f-strings for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for dict() instead of dict literal
                dict_constructor = len(re.findall(r"\bdict\(\s*\w+\s*=", content))
                if dict_constructor > 3:
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use dict literals in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["modernization", "performance"],
                            description=f"Found {dict_constructor} dict() constructor calls. Use dict literals {{}} for better performance.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for potential dataclass usage (lots of __init__ boilerplate)
                if "__init__" in content and "self." in content:
                    init_assignments = len(re.findall(r"self\.\w+\s*=\s*\w+", content))
                    if init_assignments > 5 and "dataclass" not in content:
                        self.findings.append(
                            Finding(
                                title=f"Modernize: Consider using dataclass in {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["modernization", "boilerplate"],
                                description=f"Found class with {init_assignments} __init__ assignments. Consider using @dataclass to reduce boilerplate.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for missing context managers (open() without with)
                opens = re.findall(r"(\w+)\s*=\s*open\(", content)
                with_opens = re.findall(r"with\s+open\(", content)

                if len(opens) > len(with_opens):
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use context managers (with statement) in {py_file.name}",
                            finding_type="bug",
                            priority="P3",
                            category=["modernization", "reliability"],
                            description="Found open() calls without 'with' statement. Use context managers to ensure files are properly closed.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except Exception:
                pass

    def _scan_observability(self):
        """Find opportunities to add logging and monitoring"""

        print("  📊 Scanning for observability improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for error handlers that don't log
                except_blocks = re.findall(r"except\s+\w+.*?:", content)
                has_logging = (
                    "logging" in content or "logger" in content or "print" in content
                )

                if len(except_blocks) > 0 and not has_logging:
                    self.findings.append(
                        Finding(
                            title=f"Observability: Add logging to error handlers in {py_file.name}",
                            finding_type="enhancement",
                            priority="P3",
                            category=["observability", "debugging"],
                            description=f"Found {len(except_blocks)} exception handlers but no logging. Add logging for better debugging in production.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for long-running operations without progress tracking
                if "for " in content or "while " in content:
                    has_progress = "tqdm" in content or "progress" in content.lower()
                    has_subprocess = "subprocess" in content

                    if has_subprocess and not has_progress:
                        self.findings.append(
                            Finding(
                                title=f"Observability: Add progress tracking to {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["observability", "ux"],
                                description="Found long-running operations without progress tracking. Consider adding progress indicators for better user experience.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for missing function entry/exit logging in critical paths
                if py_file.name in [
                    "builder_agent.py",
                    "architect_agent.py",
                    "scout_agent.py",
                ]:
                    func_count = content.count("def ")
                    log_count = content.count("print(") + content.count("logger.")

                    if func_count > 5 and log_count < func_count:
                        self.findings.append(
                            Finding(
                                title=f"Observability: Add detailed logging to {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["observability", "debugging"],
                                description=f"Critical path file with {func_count} functions but only {log_count} log statements. Add more logging for better observability.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="medium",
                            )
                        )
            except Exception:
                pass

    def _scan_user_experience(self):
        """Find opportunities to improve user-facing features"""

        print("  😊 Scanning for user experience improvements...")

        # Check CLI files
        cli_files = (
            list(self.project_root.glob("**/cli*.py"))
            + list(self.project_root.glob("**/main.py"))
            + [self.project_root / "foundry"]
        )

        for cli_file in cli_files:
            if not cli_file.exists():
                continue

            try:
                content = cli_file.read_text()

                # Check for missing --help text
                if "argparse" in content or "click" in content:
                    help_count = content.count("help=")
                    arg_count = content.count("add_argument") + content.count(
                        "@click.option"
                    )

                    if arg_count > 0 and help_count < arg_count * 0.5:
                        self.findings.append(
                            Finding(
                                title=f"UX: Add help text to CLI arguments in {cli_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["ux", "documentation"],
                                description=f"Only {help_count}/{arg_count} CLI arguments have help text. Add --help documentation for better UX.",
                                file_path=str(cli_file.relative_to(self.project_root))
                                if cli_file.is_relative_to(self.project_root)
                                else cli_file.name,
                                effort="small",
                            )
                        )

                # Check for destructive operations without confirmation
                destructive_patterns = [r"delete", r"remove", r"drop", r"truncate"]
                for pattern in destructive_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        if "input(" not in content and "confirm" not in content.lower():
                            self.findings.append(
                                Finding(
                                    title=f"UX: Add confirmation prompts for destructive operations in {cli_file.name}",
                                    finding_type="enhancement",
                                    priority="P2",
                                    category=["ux", "safety"],
                                    description="Found destructive operations (delete/remove) without confirmation prompts. Add user confirmation to prevent accidents.",
                                    file_path=str(
                                        cli_file.relative_to(self.project_root)
                                    )
                                    if cli_file.is_relative_to(self.project_root)
                                    else cli_file.name,
                                    effort="small",
                                )
                            )
                            break

                # Check for missing error messages (silent failures)
                if "except" in content:
                    except_pass = len(re.findall(r"except.*:\s*pass", content))
                    if except_pass > 0:
                        self.findings.append(
                            Finding(
                                title=f"UX: Replace silent failures with error messages in {cli_file.name}",
                                finding_type="bug",
                                priority="P2",
                                category=["ux", "reliability"],
                                description=f"Found {except_pass} silent failure(s) (except: pass). Users won't know when operations fail.",
                                file_path=str(cli_file.relative_to(self.project_root))
                                if cli_file.is_relative_to(self.project_root)
                                else cli_file.name,
                                effort="small",
                            )
                        )
            except Exception:
                pass

    def _scan_configuration(self):
        """Find opportunities to improve configuration management"""

        print("  ⚙️  Scanning for configuration improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for hardcoded values that should be env vars
                hardcoded_patterns = [
                    (r"https?://localhost:\d+", "URL"),
                    (
                        r'(api_key|password|secret)\s*=\s*["\'](?!env|get)[^"\']+["\']',
                        "Secret",
                    ),
                    (r"/tmp/[\w-]+", "Path"),
                    (r"timeout\s*=\s*\d+", "Timeout"),
                ]

                for pattern, config_type in hardcoded_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # Don't flag if already using env vars
                        if "os.getenv" in content or "os.environ" in content:
                            continue

                        self.findings.append(
                            Finding(
                                title=f"Config: Move hardcoded {config_type.lower()} to environment variables in {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["config", "deployment"],
                                description=f"Found hardcoded {config_type.lower()}. Use environment variables for better configurability across environments.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )
                        break

                # Check for missing config validation
                if "os.getenv" in content or "os.environ" in content:
                    has_validation = (
                        "required" in content.lower()
                        or "assert" in content
                        or "raise" in content
                    )

                    if not has_validation:
                        self.findings.append(
                            Finding(
                                title=f"Config: Add validation for environment variables in {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["config", "reliability"],
                                description="Environment variables are used but not validated. Add validation to fail fast with clear error messages.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )
            except Exception:
                pass

        # Check for .env.example
        if (self.project_root / ".env").exists() and not (
            self.project_root / ".env.example"
        ).exists():
            self.findings.append(
                Finding(
                    title="Config: Add .env.example file",
                    finding_type="enhancement",
                    priority="P3",
                    category=["config", "documentation"],
                    description="Found .env file but no .env.example. Create an example file to document required environment variables.",
                    file_path=".env",
                    effort="small",
                )
            )

    def _scan_extensibility(self):
        """Find opportunities to make the codebase more extensible"""

        print("  🔌 Scanning for extensibility improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for classes that could be abstract base classes
                if "class " in content:
                    classes = re.findall(r"class\s+(\w+)", content)
                    has_abc = "ABC" in content or "abstractmethod" in content

                    # Look for class hierarchies (inheritance)
                    if len(classes) > 2 and not has_abc:
                        # Check if classes have common method names
                        methods = re.findall(r"def\s+(\w+)", content)
                        method_counts = {}
                        for method in methods:
                            method_counts[method] = method_counts.get(method, 0) + 1

                        repeated_methods = [
                            m for m, count in method_counts.items() if count > 2
                        ]

                        if repeated_methods:
                            self.findings.append(
                                Finding(
                                    title=f"Extensibility: Consider abstract base class in {py_file.name}",
                                    finding_type="enhancement",
                                    priority="P4",
                                    category=["extensibility", "architecture"],
                                    description=f"Found {len(classes)} classes with repeated method names ({', '.join(repeated_methods[:3])}). Consider using ABC for better extensibility.",
                                    file_path=str(
                                        py_file.relative_to(self.project_root)
                                    ),
                                    effort="medium",
                                )
                            )

                # Check for hardcoded logic that could be plugins
                if py_file.name in [
                    "scout_agent.py",
                    "builder_agent.py",
                    "architect_agent.py",
                ]:
                    scan_methods = len(re.findall(r"def\s+_scan_\w+", content))

                    if scan_methods > 5:
                        # Check if plugin system exists
                        has_plugin_system = (
                            "plugin" in content.lower() or "register" in content.lower()
                        )

                        if not has_plugin_system:
                            self.findings.append(
                                Finding(
                                    title=f"Extensibility: Add plugin system to {py_file.name}",
                                    finding_type="enhancement",
                                    priority="P3",
                                    category=["extensibility", "architecture"],
                                    description=f"Found {scan_methods} scan methods. Consider a plugin system to allow users to add custom scanners without modifying core code.",
                                    file_path=str(
                                        py_file.relative_to(self.project_root)
                                    ),
                                    effort="large",
                                )
                            )

                # Check for tightly coupled code
                import_count = len(
                    re.findall(r"^from\s+[\w.]+\s+import", content, re.MULTILINE)
                )
                if import_count > 15:
                    self.findings.append(
                        Finding(
                            title=f"Extensibility: Reduce tight coupling in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["extensibility", "maintainability"],
                            description=f"Found {import_count} imports. High coupling makes testing and reuse difficult. Consider dependency injection or interfaces.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="large",
                        )
                    )
            except Exception:
                pass

    def _get_test_file_path(self, source_file: Path) -> list:
        """Get all possible test file paths for a source file

        Returns list of matching test files including:
        - Exact match: test_<name>.py
        - Pattern match: test_<name>_*.py (e.g., test_mcp_server_comprehensive.py)
        """
        test_name_base = f"test_{source_file.stem}"
        tests_dir = self.project_root / "tests"

        # Look for exact match AND files with suffixes
        # e.g., test_mcp_server.py, test_mcp_server_unit.py, test_mcp_server_*.py
        return list(tests_dir.glob(f"{test_name_base}*.py"))

    def _is_test_path(self, path: Path) -> bool:
        """Return True if the path points to a test/fixture file that should be ignored"""

        try:
            relative_path = path.relative_to(self.project_root)
        except ValueError:
            relative_path = path

        parts = [part.lower() for part in relative_path.parts]
        filename = path.name.lower()

        if (
            filename.startswith("test")
            or filename.endswith("_test.py")
            or filename.endswith("_tests.py")
        ):
            return True

        for part in parts:
            if part.startswith("test"):
                return True
            if part in self.TEST_PATH_KEYWORDS:
                return True

        return False

    def _is_dependency_path(self, path: Path) -> bool:
        """Return True if the path points to a third-party dependency that should be ignored"""

        try:
            relative_path = path.relative_to(self.project_root)
        except ValueError:
            relative_path = path

        parts = [part.lower() for part in relative_path.parts]

        # Check if any path component matches dependency keywords
        for part in parts:
            if part in self.DEPENDENCY_PATH_KEYWORDS:
                return True
            # Also match .venv- prefix (like .venv-test, .venv-dev, etc.)
            if part.startswith(".venv"):
                return True
            if part.startswith("venv"):
                return True

        return False

    def _has_testable_code(self, py_file: Path) -> bool:
        """Check if file has code worth testing"""
        try:
            content = py_file.read_text()

            # Must have at least one function
            if "def " not in content:
                return False

            # Must have >20 lines
            if len(content.splitlines()) < 20:
                return False

            return True
        except Exception:
            return False

    def _deduplicate(self):
        """Remove duplicate findings"""
        seen = set()
        unique = []

        for finding in self.findings:
            key = (finding.title, finding.file_path)
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        self.findings = unique

    def _sort_by_priority(self):
        """Sort findings by priority (P0 > P1 > P2 > P3 > P4)"""
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
        self.findings.sort(key=lambda f: priority_order.get(f.priority, 5))


def main():
    """CLI entry point for testing"""

    project_root = Path(__file__).parent.parent.parent.parent

    scout = ScoutAgent(project_root)
    findings = scout.scan()

    print()
    print("📊 SUMMARY")
    print("=" * 80)
    print()

    for finding in findings[:10]:  # Show top 10
        print(f"{finding.priority} | {finding.finding_type.upper()}: {finding.title}")
        print(f"   {finding.description[:100]}")
        print()


if __name__ == "__main__":
    main()
