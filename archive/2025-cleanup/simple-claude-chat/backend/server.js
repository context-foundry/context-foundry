import express from 'express';
import Anthropic from '@anthropic-ai/sdk';
import cors from 'cors';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors({
  origin: 'http://localhost:5173', // Vite dev server
  credentials: true
}));
app.use(express.json());

// Initialize Anthropic client
const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// Validate API key on startup
if (!process.env.ANTHROPIC_API_KEY) {
  console.error('ERROR: ANTHROPIC_API_KEY is not set in environment variables');
  console.error('Please create a .env file with your API key');
  process.exit(1);
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Chat endpoint
app.post('/api/chat', async (req, res) => {
  try {
    const { messages } = req.body;

    // Validate request
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return res.status(400).json({
        error: 'Invalid request: messages array is required and must not be empty'
      });
    }

    // Validate message format
    for (const msg of messages) {
      if (!msg.role || !msg.content) {
        return res.status(400).json({
          error: 'Invalid message format: each message must have role and content'
        });
      }
      if (!['user', 'assistant'].includes(msg.role)) {
        return res.status(400).json({
          error: 'Invalid role: must be either "user" or "assistant"'
        });
      }
    }

    console.log(`Processing chat request with ${messages.length} messages`);

    // Call Claude API
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      messages: messages
    });

    // Extract the response text
    const assistantMessage = {
      role: 'assistant',
      content: response.content[0].text
    };

    console.log('Successfully received response from Claude API');
    res.json(assistantMessage);

  } catch (error) {
    console.error('Error calling Claude API:', error);

    // Handle specific error types
    if (error.status === 401) {
      return res.status(500).json({
        error: 'Invalid API key. Please check your ANTHROPIC_API_KEY environment variable.'
      });
    }

    if (error.status === 429) {
      return res.status(429).json({
        error: 'Rate limit exceeded. Please try again later.'
      });
    }

    // Generic error response
    res.status(500).json({
      error: error.message || 'An error occurred while processing your request'
    });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Backend server running on http://localhost:${PORT}`);
  console.log(`📡 CORS enabled for http://localhost:5173`);
  console.log(`✅ Claude API key configured`);
});
