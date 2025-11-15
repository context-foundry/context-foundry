# Glass Pane API Documentation

Complete reference for Glass Pane REST API and SSE endpoints.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://glass.contextfoundry.dev`

## Authentication

No authentication required. This is a read-only dashboard for monitoring Context Foundry builds.

## Content Type

All requests and responses use `application/json` unless otherwise specified.

---

## REST API Endpoints

### Jobs

#### GET /api/jobs

List all jobs with optional filtering.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| status | string | No | Filter by status: `running`, `completed`, `failed` |
| limit | integer | No | Number of jobs to return (default: 50, max: 200) |
| offset | integer | No | Pagination offset (default: 0) |

**Example Request:**

```bash
curl http://localhost:8000/api/jobs?status=running&limit=10
```

**Example Response:**

```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "running",
      "started_at": "2025-11-14T20:00:00Z",
      "completed_at": null,
      "project_name": "glass-pane",
      "current_phase": "Architect",
      "tokens_used": 18500,
      "total_files": 12
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Response Fields:**

- `jobs` (array): List of job objects
- `total` (integer): Total number of jobs matching filters
- `limit` (integer): Requested limit
- `offset` (integer): Requested offset

**Status Codes:**

- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Server error

---

#### GET /api/jobs/{job_id}

Get detailed information about a specific job.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string (UUID) | Yes | Job identifier |

**Example Request:**

```bash
curl http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Example Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "started_at": "2025-11-14T20:00:00Z",
  "completed_at": null,
  "project_name": "glass-pane",
  "current_phase": "Architect",
  "tokens_used": 18500,
  "total_files": 12,
  "phases": [
    {
      "phase": "Scout",
      "status": "completed",
      "started_at": "2025-11-14T20:00:00Z",
      "completed_at": "2025-11-14T20:05:00Z"
    },
    {
      "phase": "Architect",
      "status": "active",
      "started_at": "2025-11-14T20:05:00Z",
      "completed_at": null
    }
  ]
}
```

**Status Codes:**

- `200 OK`: Success
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Server error

---

### Logs

#### GET /api/jobs/{job_id}/logs

Get logs for a specific job with optional filtering.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string (UUID) | Yes | Job identifier |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| level | string | No | Filter by level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| search | string | No | Text search in log messages |
| limit | integer | No | Number of logs (default: 100, max: 1000) |
| offset | integer | No | Pagination offset (default: 0) |
| since_id | integer | No | Get logs after this ID (for incremental fetches) |

**Example Request:**

```bash
curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000/logs?level=ERROR&limit=50"
```

**Example Response:**

```json
{
  "logs": [
    {
      "id": 1,
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2025-11-14T20:00:01Z",
      "level": "INFO",
      "message": "Starting Scout phase"
    },
    {
      "id": 2,
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2025-11-14T20:00:05Z",
      "level": "ERROR",
      "message": "Failed to connect to API"
    }
  ],
  "total": 1523,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:**

- `200 OK`: Success
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Server error

---

### Files

#### GET /api/files

Get file content from project directory.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | Relative file path (e.g., `src/App.tsx`) |

**Example Request:**

```bash
curl "http://localhost:8000/api/files?path=src/App.tsx"
```

**Example Response:**

```json
{
  "path": "src/App.tsx",
  "content": "import React from 'react';\n\nfunction App() {\n  return <div>Hello</div>;\n}\n\nexport default App;",
  "size": 102,
  "modified_at": "2025-11-14T20:10:00Z"
}
```

**Status Codes:**

- `200 OK`: Success
- `403 Forbidden`: Path outside project directory (security)
- `404 Not Found`: File not found
- `500 Internal Server Error`: Server error

---

## Server-Sent Events (SSE)

### GET /sse/jobs/{job_id}/updates

Subscribe to real-time updates for a specific job.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string (UUID) | Yes | Job identifier |

**Example Request:**

```javascript
const eventSource = new EventSource('/sse/jobs/550e8400-e29b-41d4-a716-446655440000/updates');

eventSource.addEventListener('phase_update', (event) => {
  const data = JSON.parse(event.data);
  console.log('Phase:', data.phase, 'Status:', data.status);
});

eventSource.addEventListener('log_batch', (event) => {
  const data = JSON.parse(event.data);
  console.log('New logs:', data.logs);
});
```

**Event Types:**

#### phase_update

Triggered when build phase changes.

```
event: phase_update
data: {"phase": "Builder", "status": "building", "description": "Creating components"}
```

**Fields:**
- `phase` (string): Current phase (`Scout`, `Architect`, `Builder`, `Test`, `Deploy`)
- `status` (string): Phase status (`pending`, `active`, `completed`, `failed`)
- `description` (string): Human-readable description

---

#### file_created

Triggered when a new file is created.

```
event: file_created
data: {"path": "src/App.tsx", "timestamp": "2025-11-14T20:10:00Z"}
```

**Fields:**
- `path` (string): File path relative to project root
- `timestamp` (string): ISO 8601 timestamp

---

#### log_batch

Triggered when new logs are available (batched).

```
event: log_batch
data: {"logs": [{"id": 100, "timestamp": "2025-11-14T20:10:05Z", "level": "INFO", "message": "Component created"}]}
```

**Fields:**
- `logs` (array): Array of log entries

---

#### metrics_update

Triggered when build metrics change.

```
event: metrics_update
data: {"tokens_used": 25000, "duration": 600, "files": 15}
```

**Fields:**
- `tokens_used` (integer): Total tokens consumed
- `duration` (integer): Elapsed time in seconds
- `files` (integer): Total files created

---

#### job_status_change

Triggered when job status changes.

```
event: job_status_change
data: {"status": "completed"}
```

**Fields:**
- `status` (string): New status (`running`, `completed`, `failed`)

---

#### heartbeat

Keep-alive ping (every 30 seconds).

```
event: heartbeat
data: {"timestamp": "2025-11-14T20:10:30Z"}
```

**Fields:**
- `timestamp` (string): ISO 8601 timestamp

---

## Data Models

### Job

```typescript
{
  id: string;                    // UUID
  status: 'running' | 'completed' | 'failed';
  started_at: string;            // ISO 8601
  completed_at: string | null;
  project_name: string;
  current_phase: Phase | null;
  tokens_used: number;
  total_files: number;
}
```

### Phase

```typescript
enum Phase {
  Scout = 'Scout',
  Architect = 'Architect',
  Builder = 'Builder',
  Test = 'Test',
  Deploy = 'Deploy'
}

enum PhaseStatus {
  Pending = 'pending',
  Active = 'active',
  Completed = 'completed',
  Failed = 'failed'
}
```

### Log

```typescript
{
  id: number;
  job_id: string;
  timestamp: string;            // ISO 8601
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}
```

---

## Error Handling

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes:**

- `400 Bad Request`: Invalid request parameters
- `403 Forbidden`: Access denied (e.g., path traversal attempt)
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

---

## Rate Limiting

Currently no rate limiting is enforced. In production, consider implementing:

- 100 requests per minute for REST API
- 10 concurrent SSE connections per IP

---

## CORS

Cross-Origin Resource Sharing (CORS) is enabled for configured origins.

**Development**: `http://localhost:5173`
**Production**: `https://glass.contextfoundry.dev`

---

## Interactive Documentation

When the backend is running, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Client Examples

### JavaScript/TypeScript

```typescript
// Fetch jobs
const response = await fetch('/api/jobs?status=running');
const data = await response.json();

// Subscribe to updates
const eventSource = new EventSource(`/sse/jobs/${jobId}/updates`);

eventSource.addEventListener('phase_update', (event) => {
  const { phase, status, description } = JSON.parse(event.data);
  console.log(`Phase: ${phase}, Status: ${status}`);
});
```

### Python

```python
import requests
from sseclient import SSEClient

# Fetch jobs
response = requests.get('http://localhost:8000/api/jobs?status=running')
jobs = response.json()['jobs']

# Subscribe to updates
url = f'http://localhost:8000/sse/jobs/{job_id}/updates'
for event in SSEClient(url):
    if event.event == 'phase_update':
        data = json.loads(event.data)
        print(f"Phase: {data['phase']}, Status: {data['status']}")
```

### cURL

```bash
# Get jobs
curl http://localhost:8000/api/jobs

# Get specific job
curl http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000

# Get logs
curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000/logs?limit=50"

# Subscribe to SSE (requires curl 7.68+)
curl -N http://localhost:8000/sse/jobs/550e8400-e29b-41d4-a716-446655440000/updates
```

---

## Changelog

### v1.0.0 (2025-11-14)

- Initial API release
- REST endpoints for jobs, logs, files
- SSE support for real-time updates
- Interactive documentation

---

## Support

For API questions or issues:
- Check interactive docs: http://localhost:8000/docs
- Review examples in this document
- Open GitHub issue with reproduction steps
