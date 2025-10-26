/**
 * ============================================================================
 * NO API CLIENTS - MCP DELEGATION ONLY
 * ============================================================================
 *
 * This integration uses Context Foundry's Meta-MCP pattern instead of
 * direct API calls. All LLM operations are performed by spawning fresh
 * Claude Code instances via MCP delegation.
 *
 * BENEFITS:
 * ✅ FREE - Runs on your Claude Code subscription (unlimited usage)
 * ✅ NO API KEYS - Inherits authentication from Claude Code
 * ✅ AGENT SKILLS - Spawned Claude instances have full Agent Skills access
 * ✅ FRESH CONTEXT - Each spawn gets a clean 200K token window
 * ✅ TYPE SAFE - BAML schemas used for validation, not API calls
 *
 * ARCHITECTURE:
 * User → BAML Schema → MCP Delegation → Spawn Claude → Agent Skills → JSON → Validate
 *
 * This file maintains BAML function signatures for documentation and type
 * definitions, but all actual execution goes through MCP delegation to
 * spawned Claude instances.
 *
 * See: integrations/baml/python/examples/mcp_delegation.py
 */

// NOTE: No client configurations needed!
// All operations use Context Foundry's MCP delegation pattern.
// BAML schemas below are used for type definitions and validation only.
