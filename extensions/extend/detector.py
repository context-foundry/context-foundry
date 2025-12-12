"""
Workday Extend Project Detector

Analyzes projects and prompts to detect Workday Extend applications.
"""

import json
from pathlib import Path
from typing import Any, Dict


def detect_extend_project(directory: Path) -> Dict[str, Any]:
    """
    Detect if a project is a Workday Extend application.

    Workday Extend apps have:
    - .amd file (App Metadata Definition)
    - .smd file (Site Metadata Definition)
    - .pmd files (Page Metadata Definition)
    - Optional: .script, .card, .pod files

    Args:
        directory: Path to project directory to analyze

    Returns:
        Dictionary with detection results:
        {
            "is_extend_project": bool,
            "has_amd": bool,
            "has_smd": bool,
            "pmd_files": list,
            "script_files": list,
            "card_files": list,
            "pod_files": list,
            "confidence": "high" | "medium" | "low"
        }

    Example:
        >>> result = detect_extend_project(Path("/path/to/project"))
        >>> if result["is_extend_project"]:
        ...     print(f"Extend project with {len(result['pmd_files'])} pages")
    """
    result = {
        "is_extend_project": False,
        "has_amd": False,
        "has_smd": False,
        "pmd_files": [],
        "script_files": [],
        "card_files": [],
        "pod_files": [],
        "confidence": "low",
    }

    # Check for Extend file types in root directory (flat structure)
    amd_files = list(directory.glob("*.amd"))
    smd_files = list(directory.glob("*.smd"))
    pmd_files = list(directory.glob("*.pmd"))
    script_files = list(directory.glob("*.script"))
    card_files = list(directory.glob("*.card"))
    pod_files = list(directory.glob("*.pod"))

    # Store file names
    result["pmd_files"] = [f.name for f in pmd_files]
    result["script_files"] = [f.name for f in script_files]
    result["card_files"] = [f.name for f in card_files]
    result["pod_files"] = [f.name for f in pod_files]

    # Check for AMD
    if amd_files:
        result["has_amd"] = True
        # Validate it's actually an Extend AMD file
        try:
            with open(amd_files[0], "r", encoding="utf-8") as f:
                amd_content = json.load(f)
                if "applicationId" in amd_content or "tasks" in amd_content:
                    result["confidence"] = "high"
        except (json.JSONDecodeError, UnicodeDecodeError, IOError):
            pass

    # Check for SMD
    if smd_files:
        result["has_smd"] = True

    # Determine if it's an Extend project
    # High confidence: Has AMD and at least one PMD
    # Medium confidence: Has AMD or multiple PMD files
    # Low confidence: Has at least one Extend file type
    if amd_files and pmd_files:
        result["is_extend_project"] = True
        result["confidence"] = "high"
    elif amd_files or len(pmd_files) >= 2:
        result["is_extend_project"] = True
        result["confidence"] = "medium"
    elif pmd_files or script_files or card_files or pod_files:
        result["is_extend_project"] = True
        result["confidence"] = "low"

    return result


def detect_extend_from_prompt(prompt: str) -> bool:
    """
    Detect if user prompt indicates building a Workday Extend application.

    Args:
        prompt: User's project description or prompt

    Returns:
        True if Extend keywords detected, False otherwise

    Example:
        >>> detect_extend_from_prompt("Build a rewards app using Workday Extend")
        True
        >>> detect_extend_from_prompt("Create a PMD application")
        True
        >>> detect_extend_from_prompt("Build a React web app")
        False
    """
    # Keywords that indicate Workday Extend projects
    keywords = [
        # Explicit Extend mentions
        "workday extend",
        "extend app",
        "extend application",
        "pmd application",
        "pmd app",
        "pmd page",
        "pmd-based",
        "pmd based",
        # File type mentions
        ".amd",
        ".smd",
        ".pmd",
        ".script file",
        ".pod file",
        ".card file",
        # Extend-specific concepts
        "page metadata",
        "app metadata",
        "site metadata",
        "workday app builder",
        "app builder",
        "extend builder",
        # Extend components
        "fieldset widget",
        "editbuttonbar",
        "instancelist",
        "securitydomains",
        "taskReference",
        "flowVariables",
        "outboundData",
        "baseUrlType",
        # Workday API patterns
        "workday-common",
        "workday-staffing",
        "workday-wql",
        "apiGatewayEndpoint",
        # Use context foundry extend extension
        "cf-extend",
        "context foundry extend",
        "extend extension",
    ]

    prompt_lower = prompt.lower()
    return any(keyword.lower() in prompt_lower for keyword in keywords)
