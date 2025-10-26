/**
 * Anthropic Client Configuration with Agent Skills Support
 *
 * This client is configured to work with Anthropic's Claude models
 * and supports the Agent Skills progressive disclosure pattern.
 */

client<llm> AnthropicClient {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 4096
    temperature 0.7
  }
}

/**
 * Alternative client for testing/development with different settings
 */
client<llm> AnthropicClientDev {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 2048
    temperature 0.5
  }
}
