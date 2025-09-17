import pytest
from unittest.mock import Mock, patch
import os
import sys

# Add app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests."""
    with patch('app.config.settings') as mock:
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_service_role_key = "test-service-key"
        mock.make_token = "test-make-token"
        mock.fienta_email = "test@example.com"
        mock.fienta_password = "test-password"
        mock.environment = "test"
        mock.log_level = "INFO"
        mock.cors_origins = ["http://localhost:3000"]
        mock.job_timeout_seconds = 60
        mock.max_concurrent_jobs = 1
        yield mock


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for dependency injection."""
    with patch('app.deps.get_supabase_client') as mock:
        client_mock = Mock()
        mock.return_value = client_mock
        yield client_mock


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "job_type": "fienta.create_codes",
        "args": {
            "csv_path": "test.csv",
            "dry_run": True,
            "headless": True
        }
    }
