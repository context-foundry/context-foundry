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

client<llm> GPT4oMini {
  provider openai
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
  }
}

// Claude clients removed - Context Foundry uses OpenAI GPT-4o-mini for BAML
// to avoid Anthropic API charges. All BAML functions use GPT4oMini client.

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
