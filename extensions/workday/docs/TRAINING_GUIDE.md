# Workday Extension Training Guide

This guide explains how to "train" the Workday extension by adding new patterns to the Pattern Library.

## Overview

The Workday extension uses a JSON-based Pattern Library located at `extensions/workday/patterns/workday-expertise.json`. This file contains structured knowledge about Workday business processes, best practices, and common issues, extracted from training materials (transcripts, docs).

## Automated Pattern Extraction (Recommended)

We have implemented a BAML-based tool to automate the extraction of patterns from transcripts.

### Prerequisites
- Ensure you have the BAML client installed and configured.
- Ensure you have an OpenAI API key set in your environment (`OPENAI_API_KEY`).

### Usage

1.  Place new transcript files (`.txt`) in the `extensions/workday/` directory.
2.  Run the extraction script:
    ```bash
    python3 tools/extract_patterns.py
    ```
3.  The script will:
    *   Read all `.txt` files in the directory.
    *   Analyze them using the `ExtractPatterns` BAML function.
    *   Append new, unique patterns to `patterns/workday-expertise.json`.
4.  **Review**: Always manually review the changes to `workday-expertise.json` to ensure quality.

## Manual Pattern Extraction (Legacy)

If you prefer to extract patterns manually:

1.  **Analyze Source Material**: Read the transcript or documentation (e.g., `extensions/workday/*.txt`).
2.  **Identify the Pattern**: Look for:
    *   **Process**: "How to [Action]" (e.g., "How to Hire a Worker").
    *   **Best Practices**: "Always do X", "Ensure Y".
    *   **Anti-Patterns**: "Don't do Z", "Common mistake is...".
    *   **Troubleshooting**: "If you see error X, do Y".
3.  **Add to JSON**:
    *   Open `extensions/workday/patterns/workday-expertise.json`.
    *   Add a new entry to the `patterns` array.

### Pattern Schema

```json
{
  "pattern_id": "unique-id-kebab-case",
  "category": "business-process | security | integration | reporting",
  "description": "Brief description of what this pattern covers",
  "applies_to": ["module-name", "feature-name"],
  "node_types": ["Workday Task Name", "Business Object"],
  "best_practices": [
    "Do this thing",
    "Do that thing"
  ],
  "anti_patterns": [
    "Don't do this",
    "Avoid that"
  ],
  "common_issues": [
    {
      "issue_id": "issue-id",
      "description": "What goes wrong",
      "solution": "How to fix it"
    }
  ]
}
```

## Example Extraction

**Source Text**:
> "When creating a job requisition, always ensure you select the correct supervisory organization. A common mistake is selecting the manager's organization instead of the hiring organization."

**JSON Entry**:
```json
{
  "pattern_id": "create-job-requisition",
  "best_practices": ["Select the correct hiring supervisory organization"],
  "anti_patterns": ["Selecting the manager's organization instead of the hiring organization"]
}
```
