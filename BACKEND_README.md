# Fienta Code Manager - Backend API

Unified FastAPI backend that integrates your existing Fienta/Node.js scripts, email tools, and CSV utilities without rewriting them. The backend orchestrates these as background jobs tracked in Supabase.

## Architecture

- **FastAPI Backend**: REST API with async job orchestration
- **Supabase Integration**: Single source of truth for all data
- **Job Executor**: Wraps existing Node.js/Playwright and Python scripts
- **Webhook Receiver**: Handles Make.com/Fienta webhooks with idempotency
- **Code Lifecycle**: Explicit code management (never auto-consumed)

## Key Features

✅ **Integration without loss** - Your existing scripts are preserved and wrapped  
✅ **Webhook idempotency** - Duplicate events are safely handled  
✅ **Explicit code lifecycle** - Codes are only marked used via API calls  
✅ **Background job tracking** - All automation runs are logged in Supabase  
✅ **CLI compatibility** - You can still run scripts manually  
✅ **Race-safe code allocation** - Uses Postgres function for atomic operations  

## Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp env.example .env

# Edit .env with your credentials:
# - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
# - MAKE_TOKEN for webhook authentication
# - FIENTA_EMAIL and FIENTA_PASSWORD for automation
```

### 2. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies (for Fienta automation)
npm install
```

### 3. Run Locally

```bash
# Development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python
python -m app.main
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## API Endpoints

### Webhook Integration

- `POST /integrations/make/webhook` - Receive Make.com webhooks
- `GET /integrations/webhooks/processed` - List processed webhooks

### Code Lifecycle

- `POST /codes` - Create new code
- `GET /codes` - List codes with filters
- `GET /codes/{code}` - Get specific code
- `POST /codes/allocate` - Atomically allocate and mark code as used
- `POST /codes/{code}/mark-used` - Explicitly mark code as used
- `POST /codes/{code}/revoke` - Revoke a code
- `PUT /codes/{code}` - Update code properties

### Automation Jobs

- `POST /automation/fienta/create-codes` - Create codes from CSV/XLSX
- `POST /automation/fienta/rename-codes` - Rename existing codes
- `POST /automation/fienta/update-discount` - Update discount percentages
- `POST /automation/csv/diff` - Generate CSV diff reports
- `POST /automation/xlsx-to-csv` - Convert XLSX to CSV

### Job Management

- `GET /batch-jobs` - List all jobs with filters
- `GET /batch-jobs/{job_id}` - Get job details
- `POST /batch-jobs/{job_id}/cancel` - Cancel running job
- `GET /batch-jobs/{job_id}/logs` - Get job logs
- `GET /batch-jobs/running/status` - Get running jobs status
- `GET /batch-jobs/stats/summary` - Get job statistics

### Email & Links

- `POST /email/send` - Send email via background job
- `POST /links` - Create short link with UTM parameters
- `GET /links/{short_id}/redirect` - Redirect and track clicks

## Usage Examples

### Create Fienta Codes from CSV

```bash
curl -X POST "http://localhost:8000/automation/fienta/create-codes" \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "data/new_codes.csv",
    "dry_run": false,
    "headless": true
  }'
```

### Rename Codes with Prefix

```bash
curl -X POST "http://localhost:8000/automation/fienta/rename-codes" \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "data/existing_codes.csv",
    "rename_prefix": "MOB-",
    "rename_pad_length": 3,
    "rename_start": 1,
    "dry_run": false
  }'
```

### Allocate Code Atomically

```bash
curl -X POST "http://localhost:8000/codes/allocate?code_type=discount"
# Returns: {"code": "ALLOCATED-123", "id": "uuid", "allocated_at": "2025-09-15T..."}
```

### Process Webhook

```bash
curl -X POST "http://localhost:8000/integrations/make/webhook" \
  -H "Content-Type: application/json" \
  -H "x-make-token: your-webhook-token" \
  -d '{
    "event_id": "order-123",
    "event_type": "order.created",
    "order": {
      "id": "fienta-order-456",
      "buyer_email": "customer@example.com",
      "total": 100.0
    }
  }'
```

## Background Jobs

All automation tasks run as background jobs tracked in the `batch_jobs` table:

1. **Job Creation**: API creates job record with `status=pending`
2. **Job Execution**: JobExecutor runs your existing scripts
3. **Logging**: stdout/stderr captured to filesystem and database
4. **Results**: Job results and status updated in Supabase

### Job Types

- `fienta.create_codes` - Wraps `npm run dev -- --csv ... --email ... --password ...`
- `fienta.rename_codes` - Wraps `npm run dev -- --renamePrefix ... --email ...`
- `fienta.update_discount` - Wraps `npm run dev -- --updateDiscountPercent ...`
- `fienta.csv_diff` - Wraps `npm run dev -- --diffOld ... --diffNew ...`
- `email.send` - Uses archived Gmail scripts
- `csv.xlsx_to_csv` - Wraps `npm run xlsx:to:csv`

## Deployment

### Render (Recommended)

1. Connect your GitHub repo to Render
2. Use the provided `render.yaml` configuration
3. Set environment variables in Render dashboard
4. Deploy automatically on git push

### Docker

```bash
# Build image
docker build -t fienta-backend .

# Run container
docker run -p 8000:8000 --env-file .env fienta-backend
```

### Docker Compose

```bash
# Run with PostgreSQL
docker-compose up -d
```

## Environment Variables

### Required

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (not anon key)
- `MAKE_TOKEN` - Webhook authentication token
- `FIENTA_EMAIL` - Fienta account email
- `FIENTA_PASSWORD` - Fienta account password

### Optional

- `GMAIL_CREDENTIALS_PATH` - Path to Gmail OAuth credentials
- `GMAIL_TOKEN_PATH` - Path to Gmail OAuth token
- `ENVIRONMENT` - `development` or `production`
- `LOG_LEVEL` - `DEBUG`, `INFO`, `WARNING`, `ERROR`
- `JOB_TIMEOUT_SECONDS` - Max job execution time (default: 3600)

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_webhooks.py -v
```

## Integration with Frontend

The frontend should:

1. **Read data** using Supabase anon key with RLS
2. **Trigger actions** via backend API endpoints
3. **Poll job status** for long-running operations
4. **Display results** from `batch_jobs.results`

Example frontend flow:
```typescript
// Trigger code creation
const response = await fetch('/automation/fienta/create-codes', {
  method: 'POST',
  body: JSON.stringify({ csv_path: 'data.csv', dry_run: false })
});
const { job_id } = await response.json();

// Poll job status
const jobStatus = await fetch(`/batch-jobs/${job_id}`);
const job = await jobStatus.json();
// job.data.status: 'pending' | 'running' | 'completed' | 'failed'
```

## Security

- **Service role key** stays backend-only
- **Webhook token** validates Make.com requests
- **CORS** restricted to your frontend domain
- **RLS** enforced on frontend Supabase queries
- **No secrets** in logs or API responses

## Monitoring

- **Health endpoint**: `GET /health`
- **Job statistics**: `GET /batch-jobs/stats/summary`
- **Running jobs**: `GET /batch-jobs/running/status`
- **Webhook history**: `GET /integrations/webhooks/processed`
- **Logs**: Available at `/batch-jobs/{id}/logs` and in `logs/` directory

## Troubleshooting

### Job Failures

1. Check job logs: `GET /batch-jobs/{job_id}/logs`
2. Verify credentials in environment
3. Ensure Node.js scripts work locally: `npm run dev -- --help`
4. Check filesystem permissions for `logs/` directory

### Webhook Issues

1. Verify `MAKE_TOKEN` matches Make.com configuration
2. Check processed webhooks: `GET /integrations/webhooks/processed`
3. Test webhook locally with curl (see examples above)

### Code Allocation

1. Ensure `allocate_code` Postgres function exists in Supabase
2. Verify codes table has active codes available
3. Check composite indexes for performance

## CLI Compatibility

Your existing CLI usage remains unchanged:

```bash
# Still works exactly as before
npm run dev -- --csv data/codes.csv --renamePrefix MOB- --email your@email --password "***"
```

The backend simply wraps these commands as background jobs while preserving all functionality.
