import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/Users/name/homelab/context-foundry")

try:
    from context_foundry.daemon import dashboard

    print("Successfully imported dashboard")

    # Check if re-exported functions exist
    required_funcs = [
        "_get_file_info",
        "_read_artifact_manifest",
        "_get_phase_artifacts",
        "_get_job_phases",
        "_serialize_job",
        "build_status_payload",
        "_build_phase_snapshot",
        "_read_conversation_preview",
    ]

    for name in required_funcs:
        if not hasattr(dashboard, name):
            print(f"ERROR: Missing function {name}")
            sys.exit(1)
        print(f"Found {name}")

    # Test basic functionality of one utility
    # We need a file that definitely exists and we have permission to read
    test_file = Path(__file__)
    info = dashboard._get_file_info(test_file)
    if not info or info["path"] != str(test_file):
        print(f"ERROR: _get_file_info failed. Got: {info}")
        sys.exit(1)
    print(f"Functionality check passed: {info}")

    print("Verification successful!")

except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
