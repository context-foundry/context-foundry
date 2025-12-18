"""
Prompt Loading Utilities for Relay

Functions for loading prompt templates from the prompts/relay directory.
Based on: https://github.com/leonvanzyl/autonomous-coding
"""

from pathlib import Path
from typing import Optional


# Resolve prompts directory relative to this file
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "relay"


def load_prompt(name: str) -> str:
    """
    Load a prompt template from the prompts/relay directory.

    Args:
        name: Name of the prompt file (without extension)

    Returns:
        Prompt content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    # Try .md first, then .txt
    for ext in [".md", ".txt"]:
        prompt_path = PROMPTS_DIR / f"{name}{ext}"
        if prompt_path.exists():
            return prompt_path.read_text()

    raise FileNotFoundError(f"Prompt not found: {name} in {PROMPTS_DIR}")


def get_initialization_prompt(feature_count: int = 200) -> str:
    """
    Load the initializer prompt with optional feature count override.

    Args:
        feature_count: Target number of features to generate

    Returns:
        Formatted initializer prompt
    """
    prompt = load_prompt("initializer_prompt")

    # Adjust feature counts if specified differently
    if feature_count != 200:
        prompt = prompt.replace(
            "with 200 detailed end-to-end test cases",
            f"with {feature_count} detailed end-to-end test cases",
        )

    return prompt


def get_coding_agent_prompt() -> str:
    """Load the coding agent prompt for continuation sessions."""
    return load_prompt("coding_prompt")


def get_app_spec_template() -> str:
    """Get the default app_spec.txt template."""
    return load_prompt("app_spec_template")


def copy_spec_to_project(project_dir: Path, spec_content: Optional[str] = None) -> Path:
    """
    Copy or create the app spec file in the project directory.

    Args:
        project_dir: Project directory path
        spec_content: Optional custom spec content. If None, uses template.

    Returns:
        Path to the created spec file
    """
    spec_dest = project_dir / "app_spec.txt"

    if spec_content:
        spec_dest.write_text(spec_content)
    else:
        # Use template
        try:
            template = get_app_spec_template()
            spec_dest.write_text(template)
        except FileNotFoundError:
            # Create minimal spec
            spec_dest.write_text(
                "# Application Specification\n\n"
                "Describe your application requirements here.\n"
            )

    return spec_dest


def get_system_prompt() -> str:
    """Get the system prompt for Claude agents."""
    return (
        "You are an expert full-stack developer building a production-quality "
        "web application. Focus on quality over speed. Every feature must work "
        "perfectly through the UI with real data (no mock data)."
    )


def format_feature_context(
    feature_id: str,
    feature_description: str,
    acceptance_criteria: list[str],
    regression_features: list[dict],
) -> str:
    """
    Format context for a coding agent session.

    Args:
        feature_id: ID of the feature to implement
        feature_description: Description of the feature
        acceptance_criteria: List of acceptance criteria
        regression_features: List of features to regression test

    Returns:
        Formatted context string to prepend to the coding prompt
    """
    context = f"""## CURRENT SESSION CONTEXT

### Feature to Implement
- **ID:** {feature_id}
- **Description:** {feature_description}

### Acceptance Criteria
"""
    for i, criterion in enumerate(acceptance_criteria, 1):
        context += f"{i}. {criterion}\n"

    if regression_features:
        context += "\n### Regression Tests (verify these still work FIRST)\n"
        for feat in regression_features:
            context += f"- [{feat['id']}] {feat['description']}\n"

    context += "\n---\n\n"
    return context
