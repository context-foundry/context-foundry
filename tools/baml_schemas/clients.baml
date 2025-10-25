// LLM Client Configurations for Context Foundry
// Multi-provider support with fallbacks

client<llm> GPT4 {
  provider openai
  options {
    model "gpt-4o"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> GPT4Turbo {
  provider openai
  options {
    model "gpt-4-turbo-preview"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> GPT35Turbo {
  provider openai
  options {
    model "gpt-3.5-turbo"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> Claude35Sonnet {
  provider anthropic
  options {
    model "claude-sonnet-4-5-20250929"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 8000
  }
}

client<llm> Claude35Haiku {
  provider anthropic
  options {
    model "claude-3-5-haiku-20241022"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 8000
  }
}

client<llm> Claude3Opus {
  provider anthropic
  options {
    model "claude-3-opus-20240229"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 8000
  }
}

// Retry policies for reliability
retry_policy StandardRetry {
  max_retries 3
  strategy {
    type exponential_backoff
  }
}

retry_policy AggressiveRetry {
  max_retries 5
  strategy {
    type exponential_backoff
  }
}
