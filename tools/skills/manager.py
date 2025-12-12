"""
Skills Manager - Reusable Implementation Capture and Retrieval

Manages the lifecycle of reusable skills using hybrid storage:
- JSON files as primary storage
- Context Codex database for fast search
- Auto-generated markdown for human readability

Based on: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class SkillsManager:
    """
    Manages reusable skills with hybrid storage approach.

    Storage:
        - JSON files: ~/.context-foundry/skills/{category}/{skill_id}.json
        - Markdown: ~/.context-foundry/skills/{category}/{skill_id}.md (auto-generated)
        - Index: ~/.context-foundry/skills/index.json
        - Database: Context Codex (for search)
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Initialize SkillsManager.

        Args:
            skills_dir: Custom skills directory (default: ~/.context-foundry/skills/)
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path.home() / ".context-foundry" / "skills"

        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.skills_dir / "index.json"
        self._ensure_index()

    def _ensure_index(self):
        """Create index.json if it doesn't exist"""
        if not self.index_file.exists():
            index = {
                "version": "1.0",
                "total_skills": 0,
                "last_updated": datetime.now().isoformat(),
                "categories": {},
                "skills": [],
            }
            self.index_file.write_text(json.dumps(index, indent=2))

    def _generate_skill_id(self, title: str) -> str:
        """
        Generate unique skill ID from title.

        Args:
            title: Skill title

        Returns:
            skill_id like "skl-jwt-auth-001"
        """
        # Convert title to slug
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        slug = slug[:30]  # Limit length

        # Find next available number
        existing_ids = self._get_existing_ids(slug)
        counter = 1
        while f"skl-{slug}-{counter:03d}" in existing_ids:
            counter += 1

        return f"skl-{slug}-{counter:03d}"

    def _get_existing_ids(self, slug_prefix: str) -> set:
        """Get all existing skill IDs with given prefix"""
        index = self._load_index()
        return {
            skill["skill_id"]
            for skill in index.get("skills", [])
            if skill["skill_id"].startswith(f"skl-{slug_prefix}")
        }

    def _infer_category(self, tags: List[str]) -> str:
        """
        Infer category from tags.

        Categories: authentication, database, api, testing, deployment, ui, utils
        """
        category_keywords = {
            "authentication": ["auth", "jwt", "oauth", "login", "security", "token"],
            "database": [
                "db",
                "postgres",
                "mysql",
                "sqlite",
                "sql",
                "orm",
                "migration",
            ],
            "api": ["rest", "api", "endpoint", "route", "http", "fastapi", "express"],
            "testing": ["test", "pytest", "jest", "e2e", "integration", "unittest"],
            "deployment": ["deploy", "docker", "kubernetes", "ci", "cd", "nginx"],
            "ui": ["react", "vue", "component", "frontend", "css", "html"],
            "utils": ["util", "helper", "common", "shared"],
        }

        # Check tags against category keywords
        for tag in tags:
            tag_lower = tag.lower()
            for category, keywords in category_keywords.items():
                if any(keyword in tag_lower for keyword in keywords):
                    return category

        return "utils"  # Default category

    def save_skill(
        self,
        title: str,
        description: str,
        code: str,
        file_type: str,
        project_type: str,
        tags: List[str],
        requirements: Optional[List[str]] = None,
        file_path: Optional[str] = None,
        example: Optional[str] = None,
    ) -> str:
        """
        Save a reusable skill.

        Args:
            title: Skill name (e.g., "JWT Authentication")
            description: What this skill does
            code: Complete implementation code
            file_type: Language/framework (python, typescript, etc.)
            project_type: Project context (fastapi, react, etc.)
            tags: Keywords for search
            requirements: Dependencies needed
            file_path: Suggested file path for this code
            example: Usage example

        Returns:
            skill_id of saved skill
        """
        # Generate skill ID and category
        skill_id = self._generate_skill_id(title)
        category = self._infer_category(tags)

        # Create skill object
        skill = {
            "skill_id": skill_id,
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": {
                "title": title,
                "description": description,
                "category": category,
                "file_type": file_type,
                "project_type": project_type,
            },
            "implementation": {
                "code": code,
                "file_path": file_path
                or f"{category}/{title.lower().replace(' ', '_')}.{self._get_extension(file_type)}",
                "dependencies": requirements or [],
                "environment_vars": [],
            },
            "usage": {
                "how_to_use": f"Use this {file_type} code in your {project_type} project",
                "example": example or f"# Add to your project:\n{code[:200]}...",
                "integration_notes": "",
            },
            "metrics": {
                "usage_count": 0,
                "success_rate": None,
                "projects_used": [],
                "last_used": None,
            },
            "tags": tags,
            "related_skills": [],
        }

        # Save to JSON file
        category_dir = self.skills_dir / category
        category_dir.mkdir(exist_ok=True)
        skill_file = category_dir / f"{skill_id}.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        # Generate markdown documentation
        md_file = category_dir / f"{skill_id}.md"
        md_content = self._generate_markdown(skill)
        md_file.write_text(md_content)

        # Update index
        self._update_index(skill)

        logger.info(f"Saved skill: {skill_id} ({title})")
        return skill_id

    def _get_extension(self, file_type: str) -> str:
        """Get file extension from file type"""
        extensions = {
            "python": "py",
            "typescript": "ts",
            "javascript": "js",
            "go": "go",
            "rust": "rs",
            "java": "java",
            "kotlin": "kt",
            "swift": "swift",
        }
        return extensions.get(file_type.lower(), "txt")

    def _generate_markdown(self, skill: Dict[str, Any]) -> str:
        """
        Generate human-readable SKILL.md from skill JSON.

        Args:
            skill: Skill dictionary

        Returns:
            Markdown content
        """
        metadata = skill["metadata"]
        impl = skill["implementation"]
        usage = skill["usage"]
        metrics = skill["metrics"]

        # Format success rate
        if metrics["success_rate"] is not None:
            success_pct = f"{metrics['success_rate'] * 100:.0f}%"
        else:
            success_pct = "Not yet used"

        md = f"""# {metadata["title"]}

**Category**: {metadata["category"]}
**Project Type**: {metadata["project_type"]}
**File Type**: {metadata["file_type"]}
**Success Rate**: {success_pct} ({metrics["usage_count"]} uses)

## Description

{metadata["description"]}

## Implementation

```{metadata["file_type"]}
{impl["code"]}
```

## Dependencies

{self._format_list(impl["dependencies"]) if impl["dependencies"] else "None"}

## Suggested File Path

`{impl["file_path"]}`

## Usage Example

```{metadata["file_type"]}
{usage["example"]}
```

## Tags

{", ".join(f"`{tag}`" for tag in skill["tags"])}

## Metrics

- **Times Used**: {metrics["usage_count"]}
- **Success Rate**: {success_pct}
- **Last Used**: {metrics["last_used"] or "Never"}

---

*Auto-generated from skill {skill["skill_id"]}*
*Created: {skill["created_at"]}*
*Updated: {skill["updated_at"]}*
"""
        return md

    def _format_list(self, items: List[str]) -> str:
        """Format list as markdown bullet points"""
        return "\n".join(f"- {item}" for item in items)

    def _update_index(self, skill: Dict[str, Any]):
        """Update index.json with new skill"""
        index = self._load_index()

        # Add skill summary to index
        skill_summary = {
            "skill_id": skill["skill_id"],
            "title": skill["metadata"]["title"],
            "category": skill["metadata"]["category"],
            "file_path": f"{skill['metadata']['category']}/{skill['skill_id']}.json",
            "tags": skill["tags"],
            "success_rate": skill["metrics"]["success_rate"],
            "usage_count": skill["metrics"]["usage_count"],
            "project_type": skill["metadata"]["project_type"],
        }

        index["skills"].append(skill_summary)
        index["total_skills"] = len(index["skills"])
        index["last_updated"] = datetime.now().isoformat()

        # Update category count
        category = skill["metadata"]["category"]
        index["categories"][category] = index["categories"].get(category, 0) + 1

        self.index_file.write_text(json.dumps(index, indent=2))

    def _load_index(self) -> Dict[str, Any]:
        """Load index.json"""
        if not self.index_file.exists():
            self._ensure_index()

        try:
            return json.loads(self.index_file.read_text())
        except json.JSONDecodeError:
            logger.error("Corrupted index.json, recreating")
            self._ensure_index()
            return json.loads(self.index_file.read_text())

    def search_skills(
        self,
        query: str,
        project_type: Optional[str] = None,
        min_success_rate: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for skills matching criteria.

        This method provides basic JSON-based search. For production, use
        Context Codex database search for better performance.

        Args:
            query: Search query (matches title, description, tags)
            project_type: Filter by project type
            min_success_rate: Minimum success rate (0.0-1.0)
            limit: Maximum results

        Returns:
            List of matching skill summaries
        """
        index = self._load_index()
        results = []

        query_lower = query.lower()

        for skill_summary in index.get("skills", []):
            # Check success rate
            success_rate = skill_summary.get("success_rate")
            if success_rate is not None and success_rate < min_success_rate:
                continue

            # Check project type
            if project_type and skill_summary.get("project_type") != project_type:
                continue

            # Check query match (title, tags)
            if self._matches_query(skill_summary, query_lower):
                # Load full skill details for richer search
                full_skill = self._load_skill(skill_summary["skill_id"])
                if full_skill:
                    # Include description in search
                    if query_lower in full_skill["metadata"]["description"].lower():
                        results.append(skill_summary)
                    elif query_lower in skill_summary["title"].lower():
                        results.append(skill_summary)
                    elif any(
                        query_lower in tag.lower() for tag in skill_summary["tags"]
                    ):
                        results.append(skill_summary)

        # Sort by success rate (descending), then usage count
        results.sort(
            key=lambda s: (s.get("success_rate") or 0, s.get("usage_count") or 0),
            reverse=True,
        )

        return results[:limit]

    def _matches_query(self, skill_summary: Dict[str, Any], query_lower: str) -> bool:
        """Check if skill matches search query"""
        # Check title
        if query_lower in skill_summary["title"].lower():
            return True

        # Check tags
        if any(query_lower in tag.lower() for tag in skill_summary.get("tags", [])):
            return True

        return False

    def load_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Load full skill details from JSON file.

        Args:
            skill_id: Skill ID (e.g., "skl-jwt-auth-001")

        Returns:
            Full skill dictionary or None if not found
        """
        return self._load_skill(skill_id)

    def _load_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Internal method to load skill from filesystem"""
        index = self._load_index()

        # Find skill in index
        skill_summary = next(
            (s for s in index.get("skills", []) if s["skill_id"] == skill_id), None
        )

        if not skill_summary:
            logger.warning(f"Skill not found in index: {skill_id}")
            return None

        # Load JSON file
        skill_file = self.skills_dir / skill_summary["file_path"]

        if not skill_file.exists():
            logger.error(f"Skill file not found: {skill_file}")
            return None

        try:
            return json.loads(skill_file.read_text())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse skill JSON: {e}")
            return None

    def update_metrics(self, skill_id: str, project_name: str, success: bool) -> bool:
        """
        Update skill metrics after usage.

        Args:
            skill_id: Skill ID
            project_name: Project that used this skill
            success: Whether usage was successful

        Returns:
            True if update successful
        """
        skill = self._load_skill(skill_id)
        if not skill:
            logger.error(f"Cannot update metrics: skill {skill_id} not found")
            return False

        # Increment usage count
        skill["metrics"]["usage_count"] += 1
        skill["metrics"]["last_used"] = datetime.now().isoformat()
        skill["updated_at"] = datetime.now().isoformat()

        # Add project usage record
        skill["metrics"]["projects_used"].append(
            {
                "project_name": project_name,
                "used_at": datetime.now().isoformat(),
                "success": success,
            }
        )

        # Calculate success rate
        total = len(skill["metrics"]["projects_used"])
        successes = sum(1 for p in skill["metrics"]["projects_used"] if p["success"])
        skill["metrics"]["success_rate"] = successes / total if total > 0 else 0.0

        # Save updated skill
        self._save_skill(skill)

        # Update index
        self._update_index_metrics(skill)

        logger.info(f"Updated metrics for {skill_id}: {successes}/{total} success rate")
        return True

    def _save_skill(self, skill: Dict[str, Any]):
        """Save skill to JSON file and regenerate markdown"""
        category = skill["metadata"]["category"]
        skill_id = skill["skill_id"]

        # Save JSON
        category_dir = self.skills_dir / category
        skill_file = category_dir / f"{skill_id}.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        # Regenerate markdown
        md_file = category_dir / f"{skill_id}.md"
        md_content = self._generate_markdown(skill)
        md_file.write_text(md_content)

    def _update_index_metrics(self, skill: Dict[str, Any]):
        """Update skill metrics in index.json"""
        index = self._load_index()

        # Find and update skill in index
        for i, skill_summary in enumerate(index.get("skills", [])):
            if skill_summary["skill_id"] == skill["skill_id"]:
                index["skills"][i]["success_rate"] = skill["metrics"]["success_rate"]
                index["skills"][i]["usage_count"] = skill["metrics"]["usage_count"]
                break

        index["last_updated"] = datetime.now().isoformat()
        self.index_file.write_text(json.dumps(index, indent=2))

    def get_stats(self) -> Dict[str, Any]:
        """
        Get skills statistics.

        Returns:
            Statistics dictionary
        """
        index = self._load_index()

        total_skills = index.get("total_skills", 0)
        categories = index.get("categories", {})
        skills = index.get("skills", [])

        # Calculate averages
        total_uses = sum(s.get("usage_count", 0) for s in skills)
        skills_with_metrics = [s for s in skills if s.get("success_rate") is not None]
        avg_success_rate = (
            sum(s["success_rate"] for s in skills_with_metrics)
            / len(skills_with_metrics)
            if skills_with_metrics
            else 0.0
        )

        return {
            "total_skills": total_skills,
            "categories": categories,
            "total_uses": total_uses,
            "avg_success_rate": avg_success_rate,
            "skills_with_metrics": len(skills_with_metrics),
            "last_updated": index.get("last_updated"),
        }
