#!/bin/bash
# Production startup script for Fienta Code Manager

set -e

echo "🚀 Starting Fienta Code Manager API..."

# Create auth directory if it doesn't exist
mkdir -p auth

# If FIENTA_AUTH_STATE is provided, decode and write to auth/state.json
if [ ! -z "$FIENTA_AUTH_STATE" ]; then
    echo "📝 Setting up Fienta authentication state..."
    echo "$FIENTA_AUTH_STATE" | base64 -d > auth/state.json
    echo "✅ Authentication state configured"
else
    echo "⚠️  No FIENTA_AUTH_STATE provided - will need manual login on first run"
fi

# Start the FastAPI application
echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
