#!/usr/bin/env python3
"""
Fix Roblox Studio Controller Issue

This script fixes the issue where controllers are broken in Roblox Studio
due to the Virtual Gamepad Controller Emulator feature stealing the first
controller slot (Gamepad1), causing additional gamepads to become 2 or 3,
which prevents character movement.

The fix works by finding and renaming the ControlsEmulator.rbxm file that
causes the issue.

Platform Support: Windows, macOS
"""

import os
import sys
import platform
from pathlib import Path
from datetime import datetime
import shutil


def get_roblox_versions_path():
    """Get the Roblox Versions directory path based on the platform."""
    system = platform.system()

    if system == "Windows":
        # Windows: %localappdata%/Roblox/Versions/
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise RuntimeError("Could not find LOCALAPPDATA environment variable")
        return Path(local_appdata) / "Roblox" / "Versions"

    elif system == "Darwin":  # macOS
        # macOS: ~/Library/Logs/Roblox/
        # Note: Roblox on macOS has a different structure, but we'll search for it
        home = Path.home()
        possible_paths = [
            home / "Library" / "Application Support" / "Roblox" / "Versions",
            Path("/Applications/RobloxStudio.app/Contents/Resources"),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # If not found, we'll search the entire Roblox directory
        roblox_dir = home / "Library" / "Application Support" / "Roblox"
        if roblox_dir.exists():
            return roblox_dir

        raise RuntimeError("Could not find Roblox installation directory on macOS")

    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def find_controls_emulator_files(base_path):
    """
    Recursively search for ControlsEmulator.rbxm files.

    Returns a list of Path objects for all found files.
    """
    controls_emulator_files = []

    print(f"Searching for ControlsEmulator.rbxm in {base_path}...")

    # Walk through all subdirectories
    for root, dirs, files in os.walk(base_path):
        if "ControlsEmulator.rbxm" in files:
            file_path = Path(root) / "ControlsEmulator.rbxm"
            controls_emulator_files.append(file_path)
            print(f"  Found: {file_path}")

    return controls_emulator_files


def get_latest_version_folder(versions_path):
    """
    Find the most recently modified version folder.
    This is typically the latest Roblox Studio version.
    """
    if not versions_path.exists():
        return None

    version_folders = [
        f
        for f in versions_path.iterdir()
        if f.is_dir() and f.name.startswith("version-")
    ]

    if not version_folders:
        return None

    # Sort by modification time, most recent first
    latest = max(version_folders, key=lambda f: f.stat().st_mtime)
    return latest


def rename_controls_emulator(file_path, dry_run=False):
    """
    Rename the ControlsEmulator.rbxm file to disable it.

    Args:
        file_path: Path to the ControlsEmulator.rbxm file
        dry_run: If True, only show what would be done without actually doing it

    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        print(f"  ❌ File does not exist: {file_path}")
        return False

    # Create backup name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"ControlsEmulator.rbxm.disabled_{timestamp}"
    backup_path = file_path.parent / backup_name

    try:
        if dry_run:
            print("  [DRY RUN] Would rename:")
            print(f"    From: {file_path}")
            print(f"    To:   {backup_path}")
            return True
        else:
            # Rename the file
            shutil.move(str(file_path), str(backup_path))
            print("  ✅ Renamed successfully:")
            print(f"    From: {file_path}")
            print(f"    To:   {backup_path}")
            return True

    except PermissionError:
        print("  ❌ Permission denied. Try running as administrator/sudo.")
        return False
    except Exception as e:
        print(f"  ❌ Error renaming file: {e}")
        return False


def restore_controls_emulator(base_path):
    """
    Restore a previously disabled ControlsEmulator.rbxm file.
    """
    print(f"Searching for disabled ControlsEmulator files in {base_path}...")

    disabled_files = []
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.startswith("ControlsEmulator.rbxm.disabled_"):
                file_path = Path(root) / file
                disabled_files.append(file_path)

    if not disabled_files:
        print("  No disabled ControlsEmulator files found.")
        return False

    print(f"\nFound {len(disabled_files)} disabled file(s):")
    for i, file_path in enumerate(disabled_files, 1):
        print(f"  {i}. {file_path}")

    # Restore the most recent one
    latest = max(disabled_files, key=lambda f: f.stat().st_mtime)
    original_path = latest.parent / "ControlsEmulator.rbxm"

    try:
        shutil.move(str(latest), str(original_path))
        print(f"\n✅ Restored: {original_path}")
        return True
    except Exception as e:
        print(f"\n❌ Error restoring file: {e}")
        return False


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix Roblox Studio controller issues by disabling Virtual Gamepad Controller Emulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fix the controller issue (renames ControlsEmulator.rbxm)
  python fix_studio_controllers.py

  # Preview what would be done without making changes
  python fix_studio_controllers.py --dry-run

  # Restore the original file
  python fix_studio_controllers.py --restore

  # Search in a specific directory
  python fix_studio_controllers.py --path "C:\\Program Files\\Roblox"
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually renaming files",
    )

    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore a previously disabled ControlsEmulator.rbxm file",
    )

    parser.add_argument(
        "--path",
        type=str,
        help="Custom path to search for ControlsEmulator.rbxm (overrides automatic detection)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Roblox Studio Controller Fix")
    print("=" * 70)
    print()
    print("Issue: Virtual Gamepad Controller Emulator steals Gamepad1 slot,")
    print("       causing character movement to fail in Studio.")
    print()
    print("Solution: Rename ControlsEmulator.rbxm to disable the emulator.")
    print("=" * 70)
    print()

    try:
        # Determine search path
        if args.path:
            base_path = Path(args.path)
            if not base_path.exists():
                print(f"❌ Error: Specified path does not exist: {base_path}")
                return 1
        else:
            try:
                base_path = get_roblox_versions_path()
            except RuntimeError as e:
                print(f"❌ Error: {e}")
                print("\nTip: Use --path to specify a custom search directory")
                return 1

        print(f"Platform: {platform.system()}")
        print(f"Search path: {base_path}")
        print()

        # Restore mode
        if args.restore:
            return 0 if restore_controls_emulator(base_path) else 1

        # Find all ControlsEmulator.rbxm files
        controls_files = find_controls_emulator_files(base_path)

        if not controls_files:
            print("❌ No ControlsEmulator.rbxm files found.")
            print("\nPossible reasons:")
            print("  1. Roblox Studio is not installed")
            print("  2. The file has already been renamed")
            print("  3. Different installation directory (use --path)")
            print("\nTip: Try searching your entire Roblox directory:")
            print(f"  python {sys.argv[0]} --path /path/to/roblox")
            return 1

        print(f"\n{'=' * 70}")
        print(f"Found {len(controls_files)} file(s) to rename")
        print(f"{'=' * 70}\n")

        # Rename each file
        success_count = 0
        for i, file_path in enumerate(controls_files, 1):
            print(f"File {i}/{len(controls_files)}:")
            if rename_controls_emulator(file_path, dry_run=args.dry_run):
                success_count += 1
            print()

        # Summary
        print(f"{'=' * 70}")
        if args.dry_run:
            print(
                f"DRY RUN COMPLETE: {success_count}/{len(controls_files)} files would be renamed"
            )
            print("\nRun without --dry-run to apply changes.")
        else:
            print(
                f"COMPLETE: {success_count}/{len(controls_files)} files renamed successfully"
            )

            if success_count > 0:
                print("\n✅ Controller issue should now be fixed!")
                print("\nNext steps:")
                print("  1. Restart Roblox Studio if it's running")
                print("  2. Connect your controller")
                print("  3. Test character movement in Studio")
                print("\nTo restore the original behavior:")
                print(f"  python {sys.argv[0]} --restore")
        print(f"{'=' * 70}")

        return 0 if success_count == len(controls_files) else 1

    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
