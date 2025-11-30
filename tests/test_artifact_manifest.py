"""
Tests for artifact manifest functionality.

Tests:
1. Manifest reading and parsing
2. Path validation (traversal, absolute paths)
3. Artifact detection (manifest-based vs scanning fallback)
4. Hero screenshot detection (case/format flexibility)
5. Architecture file detection (case-insensitivity)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


class TestArtifactManifestUtility:
    """Tests for tools/mcp_utils/artifact_manifest.py"""

    def test_add_artifact_creates_manifest(self):
        """add_artifact creates manifest file if it doesn't exist"""
        from tools.mcp_utils.artifact_manifest import add_artifact, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            result = add_artifact(
                tmpdir,
                "Screenshot",
                "hero.png",
                "docs/screenshots/hero.png",
                "image/png",
            )

            assert result is True
            manifest = read_manifest(tmpdir)
            assert len(manifest["artifacts"]) == 1
            assert manifest["artifacts"][0]["phase"] == "Screenshot"
            assert manifest["artifacts"][0]["path"] == "docs/screenshots/hero.png"

    def test_add_artifact_updates_existing(self):
        """add_artifact updates existing entry with same phase+name"""
        from tools.mcp_utils.artifact_manifest import add_artifact, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            # Add initial artifact
            add_artifact(tmpdir, "Screenshot", "hero.png", "old/path/hero.png")

            # Update with new path
            add_artifact(tmpdir, "Screenshot", "hero.png", "new/path/hero.png")

            manifest = read_manifest(tmpdir)
            assert len(manifest["artifacts"]) == 1
            assert manifest["artifacts"][0]["path"] == "new/path/hero.png"

    def test_add_artifacts_batch(self):
        """add_artifacts_batch adds multiple artifacts at once"""
        from tools.mcp_utils.artifact_manifest import add_artifacts_batch, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            result = add_artifacts_batch(
                tmpdir,
                [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                    },
                    {
                        "phase": "Documentation",
                        "name": "README.md",
                        "path": "README.md",
                    },
                    {
                        "phase": "Deploy",
                        "name": "session-summary.json",
                        "path": ".context-foundry/session-summary.json",
                    },
                ],
            )

            assert result is True
            manifest = read_manifest(tmpdir)
            assert len(manifest["artifacts"]) == 3

    def test_auto_detect_mime_type(self):
        """add_artifact auto-detects MIME type when not provided"""
        from tools.mcp_utils.artifact_manifest import add_artifact, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            add_artifact(tmpdir, "Screenshot", "hero.png", "docs/screenshots/hero.png")

            manifest = read_manifest(tmpdir)
            assert manifest["artifacts"][0]["type"] == "image/png"

    def test_get_phase_artifacts(self):
        """get_phase_artifacts returns only artifacts for specified phase"""
        from tools.mcp_utils.artifact_manifest import (
            add_artifacts_batch,
            get_phase_artifacts,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            add_artifacts_batch(
                tmpdir,
                [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                    },
                    {
                        "phase": "Screenshot",
                        "name": "feature.png",
                        "path": "docs/screenshots/feature.png",
                    },
                    {
                        "phase": "Documentation",
                        "name": "README.md",
                        "path": "README.md",
                    },
                ],
            )

            screenshots = get_phase_artifacts(tmpdir, "Screenshot")
            assert len(screenshots) == 2

            docs = get_phase_artifacts(tmpdir, "Documentation")
            assert len(docs) == 1

    def test_clear_phase_artifacts(self):
        """clear_phase_artifacts removes all artifacts for a phase"""
        from tools.mcp_utils.artifact_manifest import (
            add_artifacts_batch,
            clear_phase_artifacts,
            read_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            add_artifacts_batch(
                tmpdir,
                [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                    },
                    {
                        "phase": "Documentation",
                        "name": "README.md",
                        "path": "README.md",
                    },
                ],
            )

            clear_phase_artifacts(tmpdir, "Screenshot")

            manifest = read_manifest(tmpdir)
            assert len(manifest["artifacts"]) == 1
            assert manifest["artifacts"][0]["phase"] == "Documentation"


class TestHeroFlagFunctionality:
    """Tests for hero flag in manifest artifacts"""

    def test_add_artifact_with_hero_flag(self):
        """add_artifact supports hero flag for Screenshot phase"""
        from tools.mcp_utils.artifact_manifest import add_artifact, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            result = add_artifact(
                tmpdir,
                "Screenshot",
                "main-screenshot.png",
                "images/main-screenshot.png",
                "image/png",
                hero=True,
            )

            assert result is True
            manifest = read_manifest(tmpdir)
            assert manifest["artifacts"][0]["hero"] is True

    def test_hero_flag_maps_to_standard_key(self):
        """Hero flag causes artifact to use standard hero key in dashboard"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create file in custom location
            images_dir = working_path / "custom" / "images"
            images_dir.mkdir(parents=True)
            (images_dir / "my-hero.jpg").write_text("fake jpg")

            # Create manifest with hero flag
            manifest = {
                "artifacts": [
                    {
                        "phase": "Screenshot",
                        "name": "my-hero.jpg",
                        "path": "custom/images/my-hero.jpg",
                        "type": "image/jpeg",
                        "hero": True,
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should be keyed as docs/screenshots/hero.png for UI compatibility
            assert "Screenshot" in result
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]
            # But actual path should still point to original file
            assert (
                "custom/images/my-hero.jpg"
                in result["Screenshot"]["outputs"]["docs/screenshots/hero.png"]["path"]
            )


class TestDashboardManifestParsing:
    """Tests for context_foundry/daemon/dashboard.py manifest parsing"""

    def test_manifest_uses_path_as_key(self):
        """Manifest artifacts are keyed by path, not name"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create manifest with specific path
            manifest = {
                "artifacts": [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                        "type": "image/png",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            # Create the actual file
            screenshots_dir = working_path / "docs" / "screenshots"
            screenshots_dir.mkdir(parents=True)
            (screenshots_dir / "hero.png").write_text("fake png")

            result = _read_artifact_manifest(cf_dir, working_path)

            # Key should be path, not name
            assert "Screenshot" in result
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_rejects_absolute_paths(self):
        """Manifest rejects absolute paths for security"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create manifest with absolute path
            manifest = {
                "artifacts": [
                    {
                        "phase": "Test",
                        "name": "secret",
                        "path": "/etc/passwd",
                        "type": "text/plain",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should return None or empty (absolute path rejected)
            assert result is None or "Test" not in result

    def test_rejects_path_traversal(self):
        """Manifest rejects path traversal attempts"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir) / "project"
            working_path.mkdir()
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create sibling directory with secret file
            evil_dir = Path(tmpdir) / "evil"
            evil_dir.mkdir()
            (evil_dir / "secret.txt").write_text("secret data")

            # Create manifest with traversal path
            manifest = {
                "artifacts": [
                    {
                        "phase": "Test",
                        "name": "secret",
                        "path": "../evil/secret.txt",
                        "type": "text/plain",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should return None or empty (traversal rejected)
            assert result is None or "Test" not in result

    def test_rejects_prefix_collision(self):
        """Manifest rejects paths that share prefix but escape working dir"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create /tmp/xxx/project and /tmp/xxx/project-evil
            working_path = Path(tmpdir) / "project"
            working_path.mkdir()
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            evil_dir = Path(tmpdir) / "project-evil"
            evil_dir.mkdir()
            (evil_dir / "secret.txt").write_text("secret data")

            # Create manifest trying to access project-evil (shares prefix with project)
            manifest = {
                "artifacts": [
                    {
                        "phase": "Test",
                        "name": "secret",
                        "path": "../project-evil/secret.txt",
                        "type": "text/plain",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should return None or empty (prefix collision rejected)
            assert result is None or "Test" not in result

    def test_marks_missing_files(self):
        """Manifest marks files that don't exist as missing"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create manifest for file that doesn't exist
            manifest = {
                "artifacts": [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                        "type": "image/png",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should still be in result but marked as missing
            assert result is not None
            assert "Screenshot" in result
            assert (
                result["Screenshot"]["outputs"]["docs/screenshots/hero.png"]["missing"]
                is True
            )


class TestDashboardArtifactDetection:
    """Tests for _get_phase_artifacts scanning fallback"""

    def _create_mock_job(self, working_dir: str) -> MagicMock:
        """Create a mock Job object with params"""
        job = MagicMock()
        job.params = {"working_directory": working_dir}
        return job

    def test_manifest_takes_priority(self):
        """Manifest artifacts override scanning when present"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create manifest pointing to custom location
            manifest = {
                "artifacts": [
                    {
                        "phase": "Scout",
                        "name": "scout-report.md",
                        "path": "custom/scout-report.md",
                        "type": "text/markdown",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            # Create the custom file
            custom_dir = working_path / "custom"
            custom_dir.mkdir()
            (custom_dir / "scout-report.md").write_text("# Scout Report")

            # Also create file in standard location (should be ignored when manifest present)
            (cf_dir / "scout-report.md").write_text("# Standard Scout Report")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            # Should use manifest (key normalized to filename, but path from custom location)
            assert "Scout" in result
            # Key is normalized to filename-only (scout-report.md is a known artifact name)
            assert "scout-report.md" in result["Scout"]["outputs"]
            # But the actual path should be from the custom location (manifest path)
            assert (
                "custom/scout-report.md"
                in result["Scout"]["outputs"]["scout-report.md"]["path"]
            )

    def test_scanning_fallback_when_no_manifest(self):
        """Scanning fallback works when no manifest present"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create standard files but no manifest
            (cf_dir / "scout-report.md").write_text("# Scout Report")
            (working_path / "README.md").write_text("# Project")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            # Should find via scanning
            assert "Scout" in result
            assert "Documentation" in result

    def test_architecture_case_insensitive_docs(self):
        """Architecture file found case-insensitively in docs/"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create ARCHITECTURE.md (uppercase) in docs/
            docs_dir = working_path / "docs"
            docs_dir.mkdir()
            (docs_dir / "ARCHITECTURE.md").write_text("# Architecture")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Architect" in result
            assert "architecture.md" in result["Architect"]["outputs"]

    def test_architecture_case_insensitive_root(self):
        """Architecture file found case-insensitively at project root"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create Architecture.MD (mixed case) at root
            (working_path / "Architecture.MD").write_text("# Architecture")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Architect" in result
            assert "architecture.md" in result["Architect"]["outputs"]

    def test_architecture_json_case_insensitive(self):
        """architecture.json found case-insensitively"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create ARCHITECTURE.JSON (uppercase) in docs/
            docs_dir = working_path / "docs"
            docs_dir.mkdir()
            (docs_dir / "ARCHITECTURE.JSON").write_text('{"project": "test"}')

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Architect" in result
            assert "architecture.json" in result["Architect"]["outputs"]

    def test_hero_screenshot_case_insensitive(self):
        """Hero screenshot found case-insensitively"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create HERO.png (uppercase) in docs/screenshots/
            screenshots_dir = working_path / "docs" / "screenshots"
            screenshots_dir.mkdir(parents=True)
            (screenshots_dir / "HERO.png").write_text("fake png")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Screenshot" in result
            # Key should be normalized to docs/screenshots/hero.png
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_hero_screenshot_jpg_format(self):
        """Hero screenshot found in jpg format"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create hero.jpg (not png) in docs/screenshots/
            screenshots_dir = working_path / "docs" / "screenshots"
            screenshots_dir.mkdir(parents=True)
            (screenshots_dir / "hero.jpg").write_text("fake jpg")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Screenshot" in result
            # Key should still be docs/screenshots/hero.png for UI compatibility
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_hero_screenshot_webp_format(self):
        """Hero screenshot found in webp format"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create hero.webp in docs/screenshots/
            screenshots_dir = working_path / "docs" / "screenshots"
            screenshots_dir.mkdir(parents=True)
            (screenshots_dir / "hero.webp").write_text("fake webp")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Screenshot" in result
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_hero_screenshot_alternate_location(self):
        """Hero screenshot found in alternate screenshot directories"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create hero.png in screenshots/ (not docs/screenshots/)
            screenshots_dir = working_path / "screenshots"
            screenshots_dir.mkdir()
            (screenshots_dir / "hero.png").write_text("fake png")

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Screenshot" in result
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_session_summary_from_root(self):
        """session-summary.json found at project root as fallback"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create session-summary.json at root (not .context-foundry/)
            (working_path / "session-summary.json").write_text(
                '{"status": "completed"}'
            )

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            assert "Deploy" in result
            assert "session-summary.json" in result["Deploy"]["outputs"]

    def test_session_data_from_detected_location(self):
        """_session data parsed from wherever session-summary was found"""
        from context_foundry.daemon.dashboard import _get_phase_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create session-summary.json at root with specific data
            session_data = {
                "phases": {"Scout": {"status": "completed"}},
                "configuration": {"mode": "test"},
            }
            (working_path / "session-summary.json").write_text(json.dumps(session_data))

            job = self._create_mock_job(tmpdir)
            result = _get_phase_artifacts(job)

            # _session should have the data from root session-summary
            assert "_session" in result
            assert result["_session"]["phases"]["Scout"]["status"] == "completed"


class TestKeyMismatchNormalization:
    """Tests for .context-foundry/ prefix stripping to match frontend expectations"""

    def test_strips_context_foundry_prefix(self):
        """Manifest paths with .context-foundry/ prefix are normalized to match frontend keys"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create file at .context-foundry/scout-report.md
            (cf_dir / "scout-report.md").write_text("# Scout Report")

            # Manifest uses full path with prefix (as prompts originally instructed)
            manifest = {
                "artifacts": [
                    {
                        "phase": "Scout",
                        "name": "scout-report.md",
                        "path": ".context-foundry/scout-report.md",  # Has prefix
                        "type": "text/markdown",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Key should be stripped to match PHASE_FILE_MAP expectation
            assert "Scout" in result
            # Frontend expects "scout-report.md", not ".context-foundry/scout-report.md"
            assert "scout-report.md" in result["Scout"]["outputs"]
            assert ".context-foundry/scout-report.md" not in result["Scout"]["outputs"]

    def test_strips_prefix_for_all_phases(self):
        """Prefix stripping works for all phase types"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create all the files
            (cf_dir / "scout-report.md").write_text("# Scout")
            (cf_dir / "scout_report.json").write_text("{}")
            (cf_dir / "architecture.md").write_text("# Arch")
            (cf_dir / "architecture.json").write_text("{}")
            (cf_dir / "test-report.md").write_text("# Test")

            manifest = {
                "artifacts": [
                    {
                        "phase": "Scout",
                        "name": "scout-report.md",
                        "path": ".context-foundry/scout-report.md",
                    },
                    {
                        "phase": "Scout",
                        "name": "scout_report.json",
                        "path": ".context-foundry/scout_report.json",
                    },
                    {
                        "phase": "Architect",
                        "name": "architecture.md",
                        "path": ".context-foundry/architecture.md",
                    },
                    {
                        "phase": "Architect",
                        "name": "architecture.json",
                        "path": ".context-foundry/architecture.json",
                    },
                    {
                        "phase": "Test",
                        "name": "test-report.md",
                        "path": ".context-foundry/test-report.md",
                    },
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # All should have stripped keys
            assert "scout-report.md" in result["Scout"]["outputs"]
            assert "scout_report.json" in result["Scout"]["outputs"]
            assert "architecture.md" in result["Architect"]["outputs"]
            assert "architecture.json" in result["Architect"]["outputs"]
            assert "test-report.md" in result["Test"]["outputs"]

    def test_non_prefixed_paths_unchanged(self):
        """Paths without .context-foundry/ prefix remain unchanged"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create file at project root
            (working_path / "README.md").write_text("# Readme")

            # Create file in docs/screenshots/
            screenshots_dir = working_path / "docs" / "screenshots"
            screenshots_dir.mkdir(parents=True)
            (screenshots_dir / "hero.png").write_text("fake png")

            manifest = {
                "artifacts": [
                    {
                        "phase": "Documentation",
                        "name": "README.md",
                        "path": "README.md",
                    },
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "docs/screenshots/hero.png",
                    },
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Keys should be unchanged (no prefix to strip)
            assert "README.md" in result["Documentation"]["outputs"]
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]

    def test_strips_leading_dot_slash_prefix(self):
        """Paths with ./.context-foundry/ prefix are normalized"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            (cf_dir / "scout-report.md").write_text("# Scout Report")

            # Manifest uses ./.context-foundry/ (leading ./)
            manifest = {
                "artifacts": [
                    {
                        "phase": "Scout",
                        "name": "scout-report.md",
                        "path": "./.context-foundry/scout-report.md",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should normalize to scout-report.md
            assert "Scout" in result
            assert "scout-report.md" in result["Scout"]["outputs"]
            assert (
                "./.context-foundry/scout-report.md" not in result["Scout"]["outputs"]
            )

    def test_normalizes_backslash_separators(self):
        """Paths with backslash separators are normalized to forward slashes"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            (cf_dir / "scout-report.md").write_text("# Scout Report")

            # Manifest uses backslashes (Windows-style)
            manifest = {
                "artifacts": [
                    {
                        "phase": "Scout",
                        "name": "scout-report.md",
                        "path": ".context-foundry\\scout-report.md",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should normalize to scout-report.md
            assert "Scout" in result
            assert "scout-report.md" in result["Scout"]["outputs"]

    def test_strips_multiple_leading_dot_slashes(self):
        """Paths with multiple leading ./ are normalized"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            (cf_dir / "test-report.md").write_text("# Test Report")

            # Manifest uses ././.context-foundry/ (multiple leading ./)
            manifest = {
                "artifacts": [
                    {
                        "phase": "Test",
                        "name": "test-report.md",
                        "path": "././.context-foundry/test-report.md",
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should normalize to test-report.md
            assert "Test" in result
            assert "test-report.md" in result["Test"]["outputs"]

    def test_normalizes_docs_architecture_to_filename(self):
        """Artifacts in docs/ with known names normalize to filename-only keys"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()
            docs_dir = working_path / "docs"
            docs_dir.mkdir()

            (docs_dir / "ARCHITECTURE.md").write_text("# Architecture")
            (docs_dir / "architecture.json").write_text("{}")

            manifest = {
                "artifacts": [
                    {
                        "phase": "Architect",
                        "name": "arch-md",
                        "path": "docs/ARCHITECTURE.md",
                    },
                    {
                        "phase": "Architect",
                        "name": "arch-json",
                        "path": "docs/architecture.json",
                    },
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Should normalize to filename-only keys (case-normalized)
            assert "Architect" in result
            assert "architecture.md" in result["Architect"]["outputs"]
            assert "architecture.json" in result["Architect"]["outputs"]
            # Original paths should NOT be keys
            assert "docs/ARCHITECTURE.md" not in result["Architect"]["outputs"]
            assert "docs/architecture.json" not in result["Architect"]["outputs"]

    def test_normalizes_root_readme_to_filename(self):
        """README.md at project root normalizes to filename-only key"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            (working_path / "README.md").write_text("# Project")

            manifest = {
                "artifacts": [
                    {"phase": "Documentation", "name": "readme", "path": "README.md"},
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            assert "Documentation" in result
            assert "README.md" in result["Documentation"]["outputs"]

    def test_normalizes_subdirectory_test_report(self):
        """test-report.md in any directory normalizes to filename-only"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()
            docs_dir = working_path / "docs"
            docs_dir.mkdir()

            (docs_dir / "test-report.md").write_text("# Test Report")

            manifest = {
                "artifacts": [
                    {"phase": "Test", "name": "test", "path": "docs/test-report.md"},
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            assert "Test" in result
            assert "test-report.md" in result["Test"]["outputs"]
            assert "docs/test-report.md" not in result["Test"]["outputs"]

    def test_non_standard_artifacts_keep_path(self):
        """Non-standard artifact names keep their full path"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()
            custom_dir = working_path / "custom"
            custom_dir.mkdir()

            (custom_dir / "my-custom-file.md").write_text("# Custom")

            manifest = {
                "artifacts": [
                    {
                        "phase": "Documentation",
                        "name": "custom",
                        "path": "custom/my-custom-file.md",
                    },
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Non-standard filenames keep full path
            assert "Documentation" in result
            assert "custom/my-custom-file.md" in result["Documentation"]["outputs"]

    def test_hero_flag_overrides_prefix_stripping(self):
        """Hero flag maps to standard key regardless of path"""
        from context_foundry.daemon.dashboard import _read_artifact_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            working_path = Path(tmpdir)
            cf_dir = working_path / ".context-foundry"
            cf_dir.mkdir()

            # Create file in .context-foundry with hero flag
            (cf_dir / "screenshot.png").write_text("fake png")

            manifest = {
                "artifacts": [
                    {
                        "phase": "Screenshot",
                        "name": "screenshot.png",
                        "path": ".context-foundry/screenshot.png",
                        "type": "image/png",
                        "hero": True,  # Hero flag takes precedence
                    }
                ]
            }
            (cf_dir / "artifacts.json").write_text(json.dumps(manifest))

            result = _read_artifact_manifest(cf_dir, working_path)

            # Hero flag should map to standard key
            assert "docs/screenshots/hero.png" in result["Screenshot"]["outputs"]
            # Prefix stripping would give "screenshot.png" but hero overrides
            assert "screenshot.png" not in result["Screenshot"]["outputs"]


class TestBatchHeroFlag:
    """Tests for hero flag support in add_artifacts_batch"""

    def test_batch_hero_flag_sets_hero_on_artifact(self):
        """add_artifacts_batch correctly sets hero flag when provided"""
        from tools.mcp_utils.artifact_manifest import add_artifacts_batch, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            result = add_artifacts_batch(
                tmpdir,
                [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "images/hero.png",
                        "hero": True,
                    },
                    {
                        "phase": "Screenshot",
                        "name": "feature.png",
                        "path": "images/feature.png",
                    },
                ],
            )

            assert result is True
            manifest = read_manifest(tmpdir)

            # Find hero artifact
            hero_artifact = next(
                (a for a in manifest["artifacts"] if a["name"] == "hero.png"), None
            )
            feature_artifact = next(
                (a for a in manifest["artifacts"] if a["name"] == "feature.png"), None
            )

            assert hero_artifact is not None
            assert hero_artifact.get("hero") is True

            assert feature_artifact is not None
            assert "hero" not in feature_artifact  # No hero flag on non-hero

    def test_batch_hero_flag_only_for_screenshot_phase(self):
        """Hero flag is only applied for Screenshot phase"""
        from tools.mcp_utils.artifact_manifest import add_artifacts_batch, read_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            cf_dir = Path(tmpdir) / ".context-foundry"
            cf_dir.mkdir()

            result = add_artifacts_batch(
                tmpdir,
                [
                    {
                        "phase": "Screenshot",
                        "name": "hero.png",
                        "path": "images/hero.png",
                        "hero": True,
                    },
                    {
                        "phase": "Documentation",
                        "name": "README.md",
                        "path": "README.md",
                        "hero": True,
                    },  # Invalid
                ],
            )

            assert result is True
            manifest = read_manifest(tmpdir)

            screenshot_artifact = next(
                (a for a in manifest["artifacts"] if a["phase"] == "Screenshot"), None
            )
            doc_artifact = next(
                (a for a in manifest["artifacts"] if a["phase"] == "Documentation"),
                None,
            )

            # Screenshot should have hero
            assert screenshot_artifact.get("hero") is True

            # Documentation should NOT have hero (only valid for Screenshot)
            assert "hero" not in doc_artifact
