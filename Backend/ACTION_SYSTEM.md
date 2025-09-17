# Fienta Action Processing System

## Overview

The Action Processing System enables your frontend to work with Fienta operations through a **database-driven approach**. Instead of making direct API calls, the frontend updates Supabase records with special metadata, and the backend automatically processes these changes into real Fienta operations.

## How It Works

```
Frontend → Supabase → Backend Processor → Fienta → Status Update
```

1. **Frontend Action**: User clicks a button (delete, create, update)
2. **Database Write**: Frontend updates Supabase record with action metadata
3. **Backend Detection**: Action processor detects pending actions every 30 seconds
4. **Fienta Operation**: Backend runs Node.js/Playwright scripts against Fienta
5. **Status Update**: Backend updates database with success/failure status

## Benefits

- ✅ **No API Changes**: Frontend keeps working with Supabase directly
- ✅ **Near Real-time**: Actions processed every 30 seconds
- ✅ **Reliable**: Failed actions are retried and logged
- ✅ **Auditable**: Full action history with timestamps
- ✅ **Scalable**: Queue-based processing with rate limiting

## Supported Operations

### Code Management
- **Create**: `status='creating'` with creation parameters
- **Update**: `status='updating'` with `new_*` fields in metadata
- **Delete**: `status='deleting'` with deletion metadata
- **Rename**: `status='renaming'` with `new_code` in metadata

### Other Operations
- **Orders**: Status updates and metadata changes
- **Links**: URL shortening and tracking
- **Organizations**: External system synchronization

## Usage Examples

### Frontend: Delete a Code

```javascript
// Instead of calling DELETE /api/codes/MY-CODE
// Just update the Supabase record:

await supabase
  .from('codes')
  .update({
    status: 'deleting',
    updated_at: new Date().toISOString(),
    metadata: {
      ...existing_metadata,
      action: 'delete',
      requested_at: new Date().toISOString(),
      previous_status: 'active'
    }
  })
  .eq('code', 'MY-CODE');
```

### Backend: Automatic Processing

```python
# Backend automatically detects the change and:
# 1. Runs: npx tsx src/cli.ts delete --code=MY-CODE
# 2. Updates status to 'deleted' on success
# 3. Reverts status and logs error on failure
```

## API Endpoints

### Action Management
- `POST /api/actions/codes/create` - Request code creation
- `POST /api/actions/codes/{code}/update` - Request code update  
- `POST /api/actions/codes/{code}/delete` - Request code deletion
- `POST /api/actions/codes/{code}/rename` - Request code rename

### Monitoring
- `GET /api/actions/status` - Get pending actions count
- `GET /api/actions/history` - Get action history
- `POST /api/actions/process-now` - Manually trigger processing

## Database Schema

### Action Metadata Pattern

```json
{
  "action": "delete|create|update|rename",
  "requested_at": "2025-09-15T10:30:00Z",
  "request_method": "api|frontend|webhook",
  "previous_status": "active",
  
  // For creation
  "discount_percent": 20,
  "max_uses": 5,
  
  // For updates  
  "new_discount_percent": 30,
  "new_max_uses": 10,
  
  // For rename
  "new_code": "NEW-CODE-NAME",
  
  // Completion tracking
  "created_in_fienta_at": "2025-09-15T10:31:00Z",
  "updated_in_fienta_at": "2025-09-15T10:31:00Z", 
  "deleted_in_fienta_at": "2025-09-15T10:31:00Z",
  
  // Error handling
  "action_failed": true,
  "action_error": "Connection timeout",
  "failed_at": "2025-09-15T10:31:00Z"
}
```

### Status Lifecycle

```
Creating → Active (success) or Failed (error)
Active → Updating → Active (success) or Previous Status (error)
Active → Deleting → Deleted (success) or Active (error)
Active → Renaming → New Record Created (success) or Active (error)
```

## Configuration

### Environment Variables

```bash
# Required for action processing
FIENTA_EMAIL=your-fienta-email
FIENTA_PASSWORD=your-fienta-password
FIENTA_EVENT_ID=118714

# Scheduler settings
ENABLE_MONITORING=true
ACTION_CHECK_INTERVAL=30  # seconds
```

### Scheduler Settings

- **Action Processing**: Every 30 seconds
- **Full Monitoring**: Every 15 minutes  
- **Rate Limiting**: 0.5s between Fienta operations
- **Timeout**: 3 minutes per operation

## Testing

### Run Test Suite
```bash
python test_action_system.py
```

### Monitor System
```bash
python action_dashboard.py
```

### Manual Testing
```bash
# Create a test code
curl -X POST "http://localhost:8000/api/actions/codes/create" \
  -H "Content-Type: application/json" \
  -d '{"code": "TEST-123", "discount_percent": 20}'

# Check action status
curl "http://localhost:8000/api/actions/status"

# Delete the test code
curl -X POST "http://localhost:8000/api/actions/codes/TEST-123/delete"
```

## Frontend Integration

### v0 Prompt for Delete Button

```
Replace the "Revoke" button with a "Delete" button that:

1. Updates the code record in Supabase:
   - Set status to 'deleting'
   - Add metadata.action = 'delete'
   - Add metadata.requested_at = current timestamp
   - Add metadata.previous_status = current status

2. Show immediate UI feedback:
   - Change button to "Deleting..." with spinner
   - Disable the button
   - Add orange/yellow badge showing "Processing"

3. Optional: Poll for completion:
   - Check status every 5 seconds
   - When status becomes 'deleted', remove from list
   - If status reverts, show error and re-enable

4. Filter deleted codes:
   - Default view: hide codes with status='deleted'
   - Add toggle to "Show Deleted" codes
```

### React Example

```jsx
const handleDelete = async (code) => {
  setDeleting(true);
  
  try {
    await supabase
      .from('codes')
      .update({
        status: 'deleting',
        updated_at: new Date().toISOString(),
        metadata: {
          action: 'delete',
          requested_at: new Date().toISOString(),
          previous_status: codeData.status
        }
      })
      .eq('code', code);
    
    // Show "Deleting..." state
    // Optional: Start polling for completion
    
  } catch (error) {
    console.error('Delete request failed:', error);
    setDeleting(false);
  }
};
```

## Troubleshooting

### Common Issues

1. **Actions Not Processing**
   - Check scheduler status: `GET /api/monitoring/status`
   - Verify Node.js CLI works: `npx tsx src/cli.ts --help`
   - Check logs for error messages

2. **Fienta Operations Failing**
   - Verify credentials in `.env` file
   - Test manual operation: `npx tsx src/cli.ts create --code=TEST`
   - Check for Fienta site changes

3. **Database Permission Errors**
   - Verify Supabase service role key
   - Check table permissions in Supabase dashboard
   - Ensure `metadata` column is JSONB type

### Debug Commands

```bash
# Check action processor status
curl "http://localhost:8000/api/actions/status"

# Manually trigger action processing  
curl -X POST "http://localhost:8000/api/actions/process-now"

# View recent action history
curl "http://localhost:8000/api/actions/history?limit=10"
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │    Supabase     │    │    Backend      │
│                 │    │                 │    │                 │
│ User clicks     │───▶│ Update record   │───▶│ Action Processor│
│ Delete button   │    │ status='deleting'│    │ (every 30s)     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │    Supabase     │    │ Node.js/Playwright│
│                 │    │                 │    │                 │
│ Sees 'deleted'  │◀───│ Update status   │◀───│ Execute deletion│
│ status          │    │ status='deleted'│    │ in Fienta       │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

This system gives you the speed of direct database updates with the reliability of proper Fienta synchronization!
