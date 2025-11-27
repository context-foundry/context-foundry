# WorkWise API Routes

This directory contains all API routes for the WorkWise learning platform. All routes are implemented using Next.js 14 App Router format with proper error handling, validation, and caching.

## API Route Overview

| Route | Method | Purpose | Cache Strategy |
|-------|--------|---------|----------------|
| `/api/generate/scenario` | POST | Generate interactive branching scenarios | Tier 3 (Server KV) |
| `/api/generate/quiz` | POST | Generate 5-question multiple choice quizzes | Tier 3 (Server KV) |
| `/api/generate/image` | POST | Generate DALL-E 3 images | None (on-demand) |
| `/api/generate/hint` | POST | Generate contextual hints | None (on-demand) |
| `/api/certificate` | POST | Generate PDF certificates | None (unique per user) |

---

## 1. POST /api/generate/scenario

Generate interactive branching scenarios for teaching Workday patterns.

### Request Body

```typescript
{
  patternId: string;      // Required: Pattern ID to generate scenario for
  simple?: boolean;       // Optional: Generate simplified scenario (3-4 nodes)
}
```

### Response

```typescript
{
  patternId: string;
  patternName: string;
  title: string;
  description: string;
  nodes: ScenarioNode[];
  startNodeId: string;
  generatedAt: string;
  cacheSource: 'tier1' | 'tier2' | 'tier3' | 'generated';
}
```

### Example

```bash
curl -X POST http://localhost:3000/api/generate/scenario \
  -H "Content-Type: application/json" \
  -d '{
    "patternId": "workday-pattern-001"
  }'
```

### Features
- Uses GPT-4o for generation
- Validates against pattern best practices
- Server-side caching (Tier 3) for 30 days
- Returns 5-7 decision points with branching outcomes
- Includes success and failure paths

### Error Responses
- `400` - Invalid request body or pattern ID
- `404` - Pattern not found
- `429` - Rate limit exceeded
- `500` - Server error or generation failure

---

## 2. POST /api/generate/quiz

Generate 5-question multiple choice quizzes with 70% passing score.

### Request Body

```typescript
{
  patternId: string;                          // Required: Pattern ID
  difficulty?: 'easy' | 'medium' | 'hard';   // Optional: Quiz difficulty
  adaptive?: boolean;                         // Optional: Adaptive difficulty
}
```

### Response

```typescript
{
  patternId: string;
  patternName: string;
  questions: QuizQuestion[];  // Exactly 5 questions
  passingScore: 70;
  totalPoints: 100;
  generatedAt: string;
  cacheSource: 'tier1' | 'tier2' | 'tier3' | 'generated';
}
```

### Example

```bash
curl -X POST http://localhost:3000/api/generate/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "patternId": "workday-pattern-001",
    "difficulty": "medium"
  }'
```

### Features
- Uses GPT-4o for generation
- Exactly 5 questions, 4 options each
- Questions test different best practices
- Passing score: 70% (4 out of 5 correct)
- Server-side caching (Tier 3) for 30 days
- Detailed explanations referencing source material

### Error Responses
- `400` - Invalid request body or pattern ID
- `404` - Pattern not found
- `429` - Rate limit exceeded
- `500` - Server error or generation failure

---

## 3. POST /api/generate/image

Generate images using DALL-E 3 for scenarios, patterns, or achievements.

### Request Body

```typescript
{
  patternId: string;                              // Required: Pattern ID
  type: 'scenario' | 'pattern' | 'achievement';  // Required: Image type

  // Required if type === 'scenario'
  scenarioTitle?: string;
  scenarioDescription?: string;

  // Required if type === 'achievement'
  achievementName?: string;
  achievementDescription?: string;
}
```

### Response

```typescript
{
  imageUrl: string;
  metadata: {
    patternId: string;
    patternName: string;
    type: string;
    size: string;
    quality: string;
    generatedAt: string;
  };
}
```

### Example

```bash
curl -X POST http://localhost:3000/api/generate/image \
  -H "Content-Type: application/json" \
  -d '{
    "patternId": "workday-pattern-001",
    "type": "pattern"
  }'
```

### Image Presets

- **Scenario**: 1792x1024, standard quality
- **Pattern**: 1024x1024, standard quality
- **Achievement**: 1024x1024, HD quality

### Features
- Uses DALL-E 3 for generation
- Professional business illustration style
- No caching (images expensive, on-demand only)
- Validates prompts to prevent content policy violations

### Error Responses
- `400` - Invalid request body, missing required fields, or content policy violation
- `404` - Pattern not found
- `429` - Rate limit exceeded
- `500` - Server error or generation failure

---

## 4. POST /api/generate/hint

Generate contextual hints using GPT-4o-mini for cost efficiency.

### Request Body

```typescript
{
  patternId: string;      // Required: Pattern ID
  context: string;        // Required: Current question/scenario context
  userProgress?: string;  // Optional: What user has attempted
}
```

### Response

```typescript
{
  hint: string;                // 1-2 sentence hint
  relatedConcepts: string[];   // Related concepts to explore
  costEstimate: number;        // Estimated cost in USD
}
```

### Example

```bash
curl -X POST http://localhost:3000/api/generate/hint \
  -H "Content-Type: application/json" \
  -d '{
    "patternId": "workday-pattern-001",
    "context": "Question about security validation",
    "userProgress": "Tried option A and B, both incorrect"
  }'
```

### Features
- Uses GPT-4o-mini for cost savings
- Maximum 150 output tokens
- Does not reveal direct answers
- References pattern best practices
- No caching (hints are contextual)

### Error Responses
- `400` - Invalid request body
- `404` - Pattern not found
- `429` - Rate limit exceeded
- `500` - Server error or generation failure

---

## 5. POST /api/certificate

Generate PDF certificates for milestone achievements.

### Request Body

```typescript
{
  milestoneId: string;           // Required: Milestone ID
  userName: string;              // Required: User's full name
  patternsCompleted?: number;    // Optional: Override patterns completed
  averageScore?: number;         // Optional: Override average score
}
```

### Response

Binary PDF file with headers:
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="..."`

### Example

```bash
curl -X POST http://localhost:3000/api/certificate \
  -H "Content-Type: application/json" \
  -d '{
    "milestoneId": "milestone-25",
    "userName": "John Doe"
  }' \
  --output certificate.pdf
```

### Eligible Milestones

- `milestone-25` - Apprentice (25 patterns)
- `milestone-50` - Practitioner (50 patterns)
- `milestone-100` - Expert (100 patterns)
- `milestone-169` - Master (all patterns)

### Features
- Uses @react-pdf/renderer
- Professional certificate design
- Unique certificate ID (WORKWISE-{MILESTONE}-{TIMESTAMP}-{RANDOM})
- Includes completion statistics
- Landscape A4 format

### Error Responses
- `400` - Invalid request body or ineligible milestone
- `404` - Milestone not found
- `500` - PDF rendering error

---

## Common Features

### Error Handling

All routes implement consistent error handling:

```typescript
// Validation errors (400)
{
  error: "Invalid request body",
  details: [...] // Zod validation issues
}

// Not found errors (404)
{
  error: "Pattern not found: {id}"
}

// Rate limiting (429)
{
  error: "Rate limit exceeded. Please try again later."
}

// Server errors (500)
{
  error: "Failed to generate {resource}",
  message: "..." // Error details
}
```

### Validation

All routes use Zod schemas for:
- Request body validation
- Response validation
- Type safety

### Cost Tracking

All OpenAI API calls are logged with:
- Model used
- Token counts (input/output)
- Estimated cost
- Cache hit/miss status

See `lib/utils/cost-tracker.ts` for cost monitoring utilities.

### Caching Strategy

**Tier 1** (Build-time): Static pre-generated content
**Tier 2** (Client-side): IndexedDB cache (7 days)
**Tier 3** (Server-side): Vercel KV cache (30 days) ← Used by quiz/scenario routes

### CORS Headers

All routes include appropriate CORS and caching headers:

```typescript
headers: {
  'Cache-Control': 'public, s-maxage=604800, stale-while-revalidate=86400'
}
```

---

## Development

### Environment Variables

Required in `.env.local`:

```bash
OPENAI_API_KEY=sk-...
KV_URL=...
KV_REST_API_URL=...
KV_REST_API_TOKEN=...
KV_REST_API_READ_ONLY_TOKEN=...
```

### Testing

```bash
# Run development server
npm run dev

# Test API routes
curl http://localhost:3000/api/generate/quiz -X POST -H "Content-Type: application/json" -d '{"patternId":"test"}'
```

### Monitoring

- Check cost logs: `npm run analyze-costs`
- View cache statistics in development console
- Monitor validation reports for content quality

---

## Architecture Notes

### Why GPT-4o for quiz/scenario?
- Superior reasoning for educational content
- Better adherence to validation rules
- Higher quality explanations

### Why GPT-4o-mini for hints?
- Cost-effective for simple requests
- Fast response times
- Sufficient quality for hints

### Why no caching for images?
- DALL-E is expensive ($0.04-$0.12 per image)
- Images should be generated only when explicitly requested
- Storage costs would exceed generation costs

### Why no caching for hints/certificates?
- Hints are highly contextual and user-specific
- Certificates are unique per user and milestone
- Low volume doesn't justify cache complexity
