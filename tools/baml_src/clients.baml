// LLM Client Configurations for Context Foundry
// Multi-provider support with fallbacks
// Claude clients removed


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
    temperature 0.0  // Deterministic outputs for type-safe structured validation
  }
}

client<llm> O4Mini {
  provider openai
  options {
    model "o4-mini"
    api_key env.OPENAI_API_KEY
    // o4-mini: Efficiency engine with strong math and visual reasoning
  }
}

client<llm> O4 {
  provider openai
  options {
    model "o4"
    api_key env.OPENAI_API_KEY
    // o4: Full reasoning model for complex structured parsing
  }
}

// Most BAML functions use GPT4oMini client for cost efficiency.
// Architecture parsing uses O4 for reliable structured output with enhanced reasoning.

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
