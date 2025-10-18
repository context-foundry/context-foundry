#!/usr/bin/env python3
"""
Blueprint Manager

Manages .context-foundry/ directory for preserving project blueprints.
Ensures fix/enhance modes can access original build context.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BlueprintManager:
    """Manages project-local .context-foundry/ directory."""

    CONTEXT_DIR_NAME = ".context-foundry"

    CANONICAL_FILES = {
        "research": "RESEARCH.md",
        "spec": "SPEC.md",
        "spec_yaml": "SPEC.yaml",
        "plan": "PLAN.md",
        "tasks": "TASKS.md"
    }

    def __init__(self, project_dir: Path):
        """Initialize blueprint manager.

        Args:
            project_dir: Path to project directory
        """
        self.project_dir = Path(project_dir)
        self.context_dir = self.project_dir / self.CONTEXT_DIR_NAME
        self.history_dir = self.context_dir / "history"
        self.manifest_file = self.context_dir / "manifest.json"

    def is_foundry_project(self) -> bool:
        """Check if project was built by Context Foundry.

        Returns:
            True if .context-foundry/ exists
        """
        return self.context_dir.exists() and self.manifest_file.exists()

    def initialize(self, project_name: str, task_description: str, mode: str = "build") -> None:
        """Initialize .context-foundry/ directory.

        Args:
            project_name: Project name
            task_description: Task description
            mode: Session mode (build/fix/enhance)
        """
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Create or update manifest
        if self.manifest_file.exists():
            manifest = json.loads(self.manifest_file.read_text())
        else:
            manifest = {
                "project": project_name,
                "created": datetime.now().isoformat(),
                "sessions": [],
                "current_research": self.CANONICAL_FILES["research"],
                "current_spec": self.CANONICAL_FILES["spec"],
                "current_plan": self.CANONICAL_FILES["plan"],
                "current_tasks": self.CANONICAL_FILES["tasks"]
            }

        self.manifest_file.write_text(json.dumps(manifest, indent=2))

    def save_blueprints(
        self,
        research: str,
        spec: str,
        plan: str,
        tasks: str,
        session_id: str,
        mode: str,
        task_description: str,
        spec_yaml: Optional[str] = None
    ) -> None:
        """Save blueprint files to .context-foundry/.

        Args:
            research: Research content
            spec: Specification content
            plan: Plan content
            tasks: Tasks content
            session_id: Session identifier
            mode: Session mode (build/fix/enhance)
            task_description: Task description
            spec_yaml: Optional SPEC.yaml content (Phase 2+)
        """
        # Ensure directory exists
        self.context_dir.mkdir(parents=True, exist_ok=True)

        # Save canonical files (latest versions)
        (self.context_dir / self.CANONICAL_FILES["research"]).write_text(research)
        (self.context_dir / self.CANONICAL_FILES["spec"]).write_text(spec)
        (self.context_dir / self.CANONICAL_FILES["plan"]).write_text(plan)
        (self.context_dir / self.CANONICAL_FILES["tasks"]).write_text(tasks)

        # Save SPEC.yaml if provided (Phase 2+)
        if spec_yaml:
            (self.context_dir / self.CANONICAL_FILES["spec_yaml"]).write_text(spec_yaml)

        # Save to history
        session_history_dir = self.history_dir / f"{mode}_{session_id}"
        session_history_dir.mkdir(parents=True, exist_ok=True)

        (session_history_dir / "RESEARCH.md").write_text(research)
        (session_history_dir / "SPEC.md").write_text(spec)
        (session_history_dir / "PLAN.md").write_text(plan)
        (session_history_dir / "TASKS.md").write_text(tasks)

        # Save SPEC.yaml to history if provided
        if spec_yaml:
            (session_history_dir / "SPEC.yaml").write_text(spec_yaml)

        # Update manifest
        self._update_manifest(session_id, mode, task_description)

    def load_canonical_blueprints(self) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Load canonical (latest) blueprint files.

        Returns:
            Tuple of (research, spec, spec_yaml, plan, tasks) content, or None if not found
        """
        if not self.is_foundry_project():
            return None, None, None, None, None

        research = self._read_file(self.context_dir / self.CANONICAL_FILES["research"])
        spec = self._read_file(self.context_dir / self.CANONICAL_FILES["spec"])
        spec_yaml = self._read_file(self.context_dir / self.CANONICAL_FILES["spec_yaml"])
        plan = self._read_file(self.context_dir / self.CANONICAL_FILES["plan"])
        tasks = self._read_file(self.context_dir / self.CANONICAL_FILES["tasks"])

        return research, spec, spec_yaml, plan, tasks

    def get_session_history(self) -> List[Dict]:
        """Get session history from manifest.

        Returns:
            List of session metadata dictionaries
        """
        if not self.manifest_file.exists():
            return []

        manifest = json.loads(self.manifest_file.read_text())
        return manifest.get("sessions", [])

    def get_latest_session(self, mode: Optional[str] = None) -> Optional[Dict]:
        """Get latest session metadata.

        Args:
            mode: Filter by mode (build/fix/enhance), or None for any

        Returns:
            Session metadata dictionary or None
        """
        sessions = self.get_session_history()

        if mode:
            sessions = [s for s in sessions if s.get("type") == mode]

        if not sessions:
            return None

        return sessions[-1]

    def _update_manifest(self, session_id: str, mode: str, task_description: str) -> None:
        """Update manifest with new session.

        Args:
            session_id: Session identifier
            mode: Session mode
            task_description: Task description
        """
        if self.manifest_file.exists():
            manifest = json.loads(self.manifest_file.read_text())
        else:
            manifest = {
                "project": self.project_dir.name,
                "created": datetime.now().isoformat(),
                "sessions": []
            }

        # Add new session
        session_entry = {
            "timestamp": session_id.split('_', 1)[-1] if '_' in session_id else session_id,
            "type": mode,
            "task": task_description,
            "status": "complete",
            "completed": datetime.now().isoformat(),
            "history_path": f"history/{mode}_{session_id}"
        }

        manifest["sessions"].append(session_entry)

        # Update canonical file references
        manifest["current_research"] = self.CANONICAL_FILES["research"]
        manifest["current_spec"] = self.CANONICAL_FILES["spec"]
        manifest["current_plan"] = self.CANONICAL_FILES["plan"]
        manifest["current_tasks"] = self.CANONICAL_FILES["tasks"]

        self.manifest_file.write_text(json.dumps(manifest, indent=2))

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Read file content safely.

        Args:
            file_path: Path to file

        Returns:
            File content or None if not found
        """
        if file_path.exists():
            return file_path.read_text()
        return None

    def migrate_from_central(self, central_blueprints_dir: Path, session_id: str) -> bool:
        """Migrate blueprints from central storage to local .context-foundry/.

        Args:
            central_blueprints_dir: Path to central blueprints directory
            session_id: Session identifier (e.g., "20251004_214024")

        Returns:
            True if migration successful
        """
        # Find blueprint files by session ID
        research_file = central_blueprints_dir / "specs" / f"RESEARCH_{session_id}.md"
        spec_file = central_blueprints_dir / "specs" / f"SPEC_{session_id}.md"
        plan_file = central_blueprints_dir / "plans" / f"PLAN_{session_id}.md"
        tasks_file = central_blueprints_dir / "tasks" / f"TASKS_{session_id}.md"

        if not all([research_file.exists(), spec_file.exists(), plan_file.exists(), tasks_file.exists()]):
            print(f"⚠️  Warning: Not all blueprint files found for session {session_id}")
            return False

        # Read content
        research = research_file.read_text()
        spec = spec_file.read_text()
        plan = plan_file.read_text()
        tasks = tasks_file.read_text()

        # Save to local .context-foundry/
        self.save_blueprints(
            research=research,
            spec=spec,
            plan=plan,
            tasks=tasks,
            session_id=session_id,
            mode="build",  # Original build
            task_description="Migrated from central blueprints"
        )

        print(f"✅ Migrated blueprints for session {session_id} to {self.context_dir}")
        return True


def migrate_project(project_name: str, session_id: str, central_blueprints_dir: Path = None) -> bool:
    """Migrate a project from central blueprints to local .context-foundry/.

    Args:
        project_name: Project name
        session_id: Session identifier
        central_blueprints_dir: Path to central blueprints (default: ./blueprints)

    Returns:
        True if successful
    """
    if central_blueprints_dir is None:
        central_blueprints_dir = Path("blueprints")

    project_dir = Path("examples") / project_name
    if not project_dir.exists():
        print(f"❌ Project directory not found: {project_dir}")
        return False

    blueprint_mgr = BlueprintManager(project_dir)
    blueprint_mgr.initialize(project_name, "Original build", "build")

    return blueprint_mgr.migrate_from_central(central_blueprints_dir, session_id)


def main():
    """CLI for blueprint management."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage .context-foundry/ directories")
    parser.add_argument("command", choices=["migrate", "info", "history"])
    parser.add_argument("project", help="Project name or directory")
    parser.add_argument("--session", help="Session ID for migration")

    args = parser.parse_args()

    if args.command == "migrate":
        if not args.session:
            print("❌ --session required for migration")
            return 1

        success = migrate_project(args.project, args.session)
        return 0 if success else 1

    elif args.command == "info":
        project_dir = Path("examples") / args.project
        blueprint_mgr = BlueprintManager(project_dir)

        if blueprint_mgr.is_foundry_project():
            print(f"✅ {args.project} is a Context Foundry project")
            print(f"📁 Context directory: {blueprint_mgr.context_dir}")

            manifest = json.loads(blueprint_mgr.manifest_file.read_text())
            print(f"📅 Created: {manifest.get('created')}")
            print(f"🔢 Sessions: {len(manifest.get('sessions', []))}")
        else:
            print(f"❌ {args.project} is not a Context Foundry project")
            print(f"   No .context-foundry/ directory found")

    elif args.command == "history":
        project_dir = Path("examples") / args.project
        blueprint_mgr = BlueprintManager(project_dir)

        sessions = blueprint_mgr.get_session_history()
        if not sessions:
            print(f"No session history for {args.project}")
            return 0

        print(f"📚 Session History for {args.project}:\n")
        for i, session in enumerate(sessions, 1):
            print(f"{i}. [{session['type'].upper()}] {session['timestamp']}")
            print(f"   Task: {session['task']}")
            print(f"   Status: {session['status']}")
            print(f"   Completed: {session.get('completed', 'N/A')}")
            print()

    return 0


if __name__ == "__main__":
    exit(main())
