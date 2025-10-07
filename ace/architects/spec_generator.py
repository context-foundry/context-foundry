"""Generate SPEC.yaml from SPEC.md"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class SpecYamlGenerator:
    """Generate machine-readable SPEC.yaml from specification"""

    SPEC_YAML_PROMPT = """
You have written a detailed specification (SPEC.md). Now generate a machine-readable SPEC.yaml.

SPEC.md CONTENT:
{spec_content}

PROJECT TYPE: {project_type}

Generate a SPEC.yaml that captures the essential contract:

FOR API PROJECTS:
- List all endpoints (name, method, path, request schema, response schema)
- Include expected status codes
- List required environment variables
- Add example request/response for key endpoints

FOR CLI PROJECTS:
- List all commands (name, args, flags)
- Specify expected exit codes
- List required environment variables

FOR WEB PROJECTS:
- List key pages to verify (path, title_contains)
- Specify base_url
- List required environment variables

Keep it minimal - only what's needed to generate contract tests.
Include concrete examples in the 'example' field where helpful.

Output ONLY the YAML content, no markdown fences or explanations.
"""

    API_EXAMPLE_TEMPLATE = """
kind: api
service: {service_name}
env:
  required: []
  optional: []
contract:
  base_url: http://localhost:3000
  endpoints:
    - name: health
      method: GET
      path: /health
      response:
        status: [200]
        json:
          status: string
"""

    CLI_EXAMPLE_TEMPLATE = """
kind: cli
binary: {binary_name}
env:
  required: []
  optional: []
commands:
  - name: help
    args: []
    flags:
      - name: --help
        short: -h
        description: Show help
    exit_codes:
      0: success
"""

    WEB_EXAMPLE_TEMPLATE = """
kind: web
base_url: http://localhost:3000
env:
  required: []
  optional: []
pages:
  - path: /
    title_contains: Home
    status: 200
"""

    def __init__(self, ai_client):
        """Initialize spec generator.

        Args:
            ai_client: AIClient instance for generating YAML
        """
        self.ai_client = ai_client

    def generate(self, spec_md_content: str, project_type: str = "api") -> str:
        """Generate SPEC.yaml from SPEC.md.

        Args:
            spec_md_content: Content of SPEC.md
            project_type: Type of project (api/cli/web)

        Returns:
            SPEC.yaml content as string

        Raises:
            ValueError: If generated YAML is invalid
        """
        # Build prompt
        prompt = self.SPEC_YAML_PROMPT.format(
            spec_content=spec_md_content,
            project_type=project_type
        )

        # Add example template based on project type
        if project_type == "api":
            prompt += "\n\nExample structure:\n" + self.API_EXAMPLE_TEMPLATE.format(service_name="example-service")
        elif project_type == "cli":
            prompt += "\n\nExample structure:\n" + self.CLI_EXAMPLE_TEMPLATE.format(binary_name="example-cli")
        elif project_type == "web":
            prompt += "\n\nExample structure:\n" + self.WEB_EXAMPLE_TEMPLATE

        # Use architect agent for generation (appropriate for planning/spec work)
        response = self.ai_client.architect(prompt)

        spec_yaml = response.content.strip()

        # Remove markdown fences if present
        if spec_yaml.startswith("```yaml"):
            spec_yaml = spec_yaml[7:]  # Remove ```yaml
        elif spec_yaml.startswith("```"):
            spec_yaml = spec_yaml[3:]  # Remove ```

        if spec_yaml.endswith("```"):
            spec_yaml = spec_yaml[:-3]  # Remove closing ```

        spec_yaml = spec_yaml.strip()

        # Validate it's proper YAML
        try:
            yaml.safe_load(spec_yaml)
        except yaml.YAMLError as e:
            raise ValueError(f"Generated invalid YAML: {e}")

        return spec_yaml

    def generate_from_file(self, spec_md_path: Path, project_type: str = "api") -> str:
        """Generate SPEC.yaml from SPEC.md file.

        Args:
            spec_md_path: Path to SPEC.md file
            project_type: Type of project (api/cli/web)

        Returns:
            SPEC.yaml content as string

        Raises:
            FileNotFoundError: If SPEC.md doesn't exist
            ValueError: If generated YAML is invalid
        """
        if not spec_md_path.exists():
            raise FileNotFoundError(f"SPEC.md not found: {spec_md_path}")

        spec_md_content = spec_md_path.read_text()
        return self.generate(spec_md_content, project_type)


def detect_project_type(spec_content: str) -> str:
    """Detect project type from SPEC.md content.

    Args:
        spec_content: Content of SPEC.md

    Returns:
        Project type: 'api', 'cli', or 'web'
    """
    spec_lower = spec_content.lower()

    # Count keyword occurrences for each type
    api_keywords = ['api', 'endpoint', 'rest', 'http', 'route', 'get', 'post', 'put', 'delete']
    cli_keywords = ['cli', 'command', 'terminal', 'shell', 'argument', 'flag', 'option']
    web_keywords = ['web', 'page', 'website', 'frontend', 'browser', 'html', 'css']

    api_score = sum(1 for keyword in api_keywords if keyword in spec_lower)
    cli_score = sum(1 for keyword in cli_keywords if keyword in spec_lower)
    web_score = sum(1 for keyword in web_keywords if keyword in spec_lower)

    # Return type with highest score
    scores = {
        'api': api_score,
        'cli': cli_score,
        'web': web_score
    }

    # Default to API if all scores are equal
    detected_type = max(scores, key=scores.get)

    # If web and api have similar scores, prefer api (REST APIs often have web frontends)
    if abs(scores['api'] - scores['web']) <= 2 and scores['api'] > 0:
        return 'api'

    return detected_type
