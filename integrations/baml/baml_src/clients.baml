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

/**
 * OpenAI Client Configuration (Dual-Provider Support)
 *
 * Use this client for cost-effective tasks that don't require Agent Skills.
 *
 * Cost Comparison:
 * - GPT-4o-mini: $0.15/$0.60 per 1M tokens (input/output)
 * - Claude 3.5 Sonnet: $3.00/$15.00 per 1M tokens
 *
 * Use Cases:
 * - Simple text generation and summaries
 * - Data extraction without document parsing
 * - Cost-sensitive workloads
 * - High-volume batch processing
 *
 * Note: OpenAI doesn't have Agent Skills, but supports Function Calling
 */
client<llm> OpenAIClient {
  provider openai
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
    max_tokens 4096
    temperature 0.7
  }
}

/**
 * OpenAI GPT-4o Client (Higher Quality, Still Cost-Effective)
 *
 * Use when you need better quality than gpt-4o-mini but still want
 * lower costs than Claude 3.5 Sonnet.
 *
 * GPT-4o: $2.50/$10.00 per 1M tokens (input/output)
 */
client<llm> OpenAIGPT4oClient {
  provider openai
  options {
    model "gpt-4o"
    api_key env.OPENAI_API_KEY
    max_tokens 4096
    temperature 0.7
  }
}
