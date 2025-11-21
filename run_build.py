import sys
from context_foundry.tools.mcp_utils.autonomous_build import (
    autonomous_build_and_deploy_impl,
)

# The context-foundry directory should be in the PYTHONPATH environment variable

if __name__ == "__main__":
    print(sys.path)

    task = "Implement a simple web server with a single endpoint /hello that returns 'Hello, World!' in Python."
    working_directory = "/Users/name/homelab/test_multi_provider_2"

    # Call the autonomous build function
    result = autonomous_build_and_deploy_impl(
        task=task,
        working_directory=working_directory,
        active_tasks={},  # Provide an empty dict for active_tasks
    )

    print(result)
