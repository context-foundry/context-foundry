import json
import sys
import asyncio
from pathlib import Path

# Add tools directory to path to import baml_client if needed,
# but usually it's installed in the venv.
# Assuming running from root or with venv activated.

try:
    # Add baml_client directory to path for import
    tools_dir = Path(__file__).parent
    baml_client_dir = tools_dir / "baml_client"
    sys.path.insert(0, str(baml_client_dir))

    from baml_client import b as baml_client
except ImportError as e:
    print("Error: baml_client not found. Make sure BAML is compiled and installed.")
    print(f"Import error: {e}")
    sys.exit(1)

WORKDAY_EXT_DIR = Path(__file__).parent.parent / "extensions" / "workday"
PATTERNS_FILE = WORKDAY_EXT_DIR / "patterns/workday-expertise.json"


def load_expertise():
    if PATTERNS_FILE.exists():
        with open(PATTERNS_FILE, "r") as f:
            return json.load(f)
    return {
        "patterns": [],
        "common_issues": [],
        "project_types": {},
        "version": "1.0",
        "tags": [],
    }


def save_expertise(data):
    with open(PATTERNS_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def extract_from_file(file_path):
    print(f"Processing {file_path.name}...")
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Call BAML function (async)
        patterns = await baml_client.ExtractPatterns(transcript_text=content)
        return patterns
    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        return []


async def main():
    if not WORKDAY_EXT_DIR.exists():
        print(f"Error: Directory {WORKDAY_EXT_DIR} not found.")
        return

    expertise_data = load_expertise()
    existing_ids = {p["pattern_id"] for p in expertise_data.get("patterns", [])}

    # Find all txt files
    txt_files = list(WORKDAY_EXT_DIR.glob("*.txt"))
    print(f"Found {len(txt_files)} transcripts.")

    new_patterns_count = 0

    for txt_file in txt_files:
        # Optional: Skip if already processed?
        # For now, we'll just check if the pattern ID exists to avoid duplicates.

        extracted_patterns = await extract_from_file(txt_file)

        for pattern in extracted_patterns:
            # Convert BAML object to dict
            p_dict = {
                "pattern_id": pattern.pattern_id,
                "category": pattern.category,
                "description": pattern.description,
                "applies_to": pattern.applies_to,
                "node_types": pattern.node_types,
                "best_practices": pattern.best_practices,
                "anti_patterns": pattern.anti_patterns,
                "common_issues": [
                    {
                        "issue_id": issue.issue_id,
                        "description": issue.description,
                        "solution": issue.solution,
                    }
                    for issue in pattern.common_issues
                ],
            }

            if p_dict["pattern_id"] not in existing_ids:
                expertise_data["patterns"].append(p_dict)
                existing_ids.add(p_dict["pattern_id"])
                new_patterns_count += 1
                print(f"  + Added pattern: {p_dict['pattern_id']}")
            else:
                print(f"  . Skipped duplicate: {p_dict['pattern_id']}")

    if new_patterns_count > 0:
        save_expertise(expertise_data)
        print(
            f"\nSuccessfully added {new_patterns_count} new patterns to workday-expertise.json"
        )
    else:
        print("\nNo new patterns found.")


if __name__ == "__main__":
    asyncio.run(main())
