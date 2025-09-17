from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import os

from app.config import settings
from app.routers import webhooks, codes, automation, jobs, email, links, monitoring, actions
from app.services.scheduler import start_monitoring, stop_monitoring

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Reduce noise from verbose HTTP libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Fienta Code Manager API",
    description="Backend service for managing Fienta discount codes, webhooks, and automation jobs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhooks.router)
app.include_router(codes.router)
app.include_router(automation.router)
app.include_router(jobs.router)
app.include_router(email.router)
app.include_router(links.router)
app.include_router(monitoring.router)
app.include_router(actions.router)


# Ensure all errors return JSON consistently
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "data": exc.errors(),
        },
    )


# Monitoring startup logic moved to combined startup event below


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Fienta Code Manager API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": "now()"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if settings.environment == "development" else "An error occurred"
        }
    )


@app.on_event("startup")
async def combined_startup_event():
    """Combined application startup event."""
    logger.info("Starting Fienta Code Manager API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Test Supabase connection
    try:
        from app.deps import get_supabase_client
        supabase = get_supabase_client()
        # Simple test query
        result = supabase.table("codes").select("id").limit(1).execute()
        logger.info("Supabase connection successful")
    except Exception as e:
        logger.error(f"Supabase connection failed: {str(e)}")
        raise e
    
    # Start monitoring scheduler if enabled  
    if settings.enable_monitoring:
        logger.info("🔄 Starting monitoring scheduler...")
        await start_monitoring()
    else:
        logger.info("📴 Monitoring scheduler disabled in settings")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("🛑 Shutting down Fienta Code Manager API")
    
    # Stop monitoring scheduler
    await stop_monitoring()
    logger.info("Shutting down Fienta Code Manager API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.environment == "development"
    )
