from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    
    # Webhook auth
    make_token: Optional[str] = None
    
    # Fienta credentials for automation
    fienta_email: Optional[str] = None
    fienta_password: Optional[str] = None
    fienta_base_url: str = "https://fienta.com"
    
    # Email/Gmail credentials
    gmail_credentials_path: Optional[str] = None
    gmail_token_path: Optional[str] = None
    
    # App settings
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "http://localhost:3000", 
        "https://preview-cmo-system-design-kzmjzsgx8ycwmsao2aga.vusercontent.net",
        "https://your-frontend-domain.com",
        "https://fienta-code-manager.vercel.app",
        "https://fienta-code-manager-*.vercel.app"
    ]
    
    # Monitoring settings
    enable_monitoring: bool = False  # Disabled - use manual API calls instead
    fienta_event_id: str = "118714"
    
    # Job execution
    job_timeout_seconds: int = 3600  # 1 hour
    max_concurrent_jobs: int = 3
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables


settings = Settings()
