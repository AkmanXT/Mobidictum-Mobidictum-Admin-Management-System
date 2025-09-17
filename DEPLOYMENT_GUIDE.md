# Fienta Code Manager - Deployment Guide

## Quick Deploy to Render

### 1. Prerequisites
- GitHub repository with this code
- Supabase project set up
- Fienta account with admin access

### 2. Environment Variables Needed

**Required Secret Variables (set in Render Dashboard):**
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
FIENTA_EMAIL=your-fienta-admin-email
FIENTA_PASSWORD=your-fienta-password
```

**Public Variables (already in render.yaml):**
```
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_MONITORING=false
FIENTA_BASE_URL=https://fienta.com
FIENTA_EVENT_ID=118714
CORS_ORIGINS=https://your-frontend-domain.com,https://preview-cmo-system-design-kzmjzsgx8ycwmsao2aga.vusercontent.net
```

### 3. Deploy Steps

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Ready for production deployment"
   git push origin main
   ```

2. **Create Render Service:**
   - Go to https://render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the render.yaml configuration

3. **Set Environment Variables:**
   - In Render dashboard → Environment tab
   - Add the 4 required secret variables listed above
   - Public variables are already configured in render.yaml

4. **Deploy:**
   - Click "Create Web Service"
   - Render will build using Docker and deploy automatically
   - Build time: ~5-10 minutes (includes Playwright browser installation)

### 4. Verify Deployment

Once deployed, your API will be available at:
```
https://your-service-name.onrender.com
```

**Test endpoints:**
- Health check: `GET /health`
- API docs: `GET /docs`
- Code deletion: `POST /api/actions/codes/{code}/delete`
- Manual action processing: `POST /api/actions/process`

### 5. Update Frontend

Update your frontend's API base URL to point to the deployed Render service:
```javascript
const API_BASE_URL = 'https://your-service-name.onrender.com'
```

## Architecture

- **Runtime:** Docker container with Python 3.11 + Node.js 18
- **Framework:** FastAPI with Uvicorn
- **Browser Automation:** Playwright with Chromium
- **Database:** Supabase (PostgreSQL)
- **Monitoring:** Disabled by default (use manual API calls)

## Security Notes

- All secrets are environment variables (not in code)
- CORS is properly configured for your domains
- Service runs in production mode with appropriate logging
- Playwright runs in headless mode for security

## Troubleshooting

**Build Issues:**
- Check Render build logs for specific errors
- Ensure all environment variables are set correctly

**Runtime Issues:**
- Check application logs in Render dashboard
- Verify Supabase connection in startup logs
- Test health endpoint first

**Fienta Automation Issues:**
- Check if Fienta credentials are valid
- Monitor logs for Playwright timeouts
- Use manual action processing endpoint for debugging
