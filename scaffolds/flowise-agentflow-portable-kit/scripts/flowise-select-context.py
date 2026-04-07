#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def score_pattern(query: str, pattern: dict) -> int:
    q = query.lower()
    return sum(1 for keyword in pattern.get("keywords", []) if keyword.lower() in q)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=".flowise-kit/manifest.json")
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", default="artifacts/flowise/selected-context.json")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())

    scored = []
    for pattern in manifest.get("patterns", []):
        score = score_pattern(args.query, pattern)
        if score > 0:
            scored.append((score, pattern))

    if not scored:
        # Fall back to the first two patterns so the workflow still has context.
        scored = [(0, p) for p in manifest.get("patterns", [])[:2]]

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    selected_patterns = [item[1] for item in scored[: manifest["defaults"]["max_patterns"]]]

    max_examples = manifest["defaults"]["max_examples"]
    max_templates = manifest["defaults"]["max_templates"]

    examples = []
    templates = []
    expertise_paths = []
    benchmark_ids = []

    for pattern in selected_patterns:
        for path in pattern.get("examples", []):
            if path not in examples and len(examples) < max_examples:
                examples.append(path)
        for path in pattern.get("templates", []):
            if path not in templates and len(templates) < max_templates:
                templates.append(path)
        for path in pattern.get("expertise_paths", []):
            if path not in expertise_paths:
                expertise_paths.append(path)
        for bench in pattern.get("benchmarks", []):
            if bench not in benchmark_ids:
                benchmark_ids.append(bench)

    result = {
        "query": args.query,
        "selected_patterns": [p["id"] for p in selected_patterns],
        "examples": examples,
        "templates": templates,
        "expertise_paths": expertise_paths,
        "benchmarks": benchmark_ids,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
