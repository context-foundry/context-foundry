#!/usr/bin/env python3
"""
Direct test of autonomous build with logging
"""

import sys

# Add context-foundry to path
sys.path.insert(0, "/Users/name/homelab/context-foundry")

from tools.mcp_utils.autonomous_build import autonomous_build_and_deploy_impl

# Run build
result = autonomous_build_and_deploy_impl(
    task="Build a simple weather app with OpenWeatherMap API showing current weather",
    working_directory="/Users/name/homelab/weather-app-logging-test",
    mode="new_project",
    active_tasks={},
)

print(result)
