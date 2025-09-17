# Multi-stage build for FastAPI backend with Node.js support
FROM node:18-slim as node-base

# Install Node.js dependencies for Fienta automation
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

# Install Playwright browsers
RUN npx playwright install --with-deps chromium

# Python stage
FROM python:3.11-slim

# Install Node.js in Python image
COPY --from=node-base /usr/local/bin/node /usr/local/bin/
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Node.js files and dependencies
COPY --from=node-base /app/node_modules ./node_modules
COPY package*.json ./
COPY tsconfig.json ./
COPY src/ ./src/
COPY dist/ ./dist/

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers in the final image (required at runtime)
RUN npx playwright install --with-deps chromium

# Build TypeScript if needed
RUN npm run build

# Copy application code
COPY app/ ./app/
COPY archive/ ./archive/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p logs auth temp data

# Copy archived scripts (needed for email functionality)
COPY archive/email_outreach/ ./archive/email_outreach/

# Make startup script executable
RUN chmod +x scripts/startup.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV NODE_PATH=/app/node_modules

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application via startup script
CMD ["./scripts/startup.sh"]
