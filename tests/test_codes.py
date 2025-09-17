import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.main import app
from app.models import CodeStatus, CodeType

client = TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch('app.deps.get_supabase') as mock:
        supabase_mock = Mock()
        mock.return_value = supabase_mock
        yield supabase_mock


@pytest.fixture
def sample_code_data():
    """Sample code data."""
    return {
        "code": "TEST-CODE-123",
        "type": "discount",
        "discount_percent": 40,
        "max_uses": 1
    }


def test_create_code_success(mock_supabase, sample_code_data):
    """Test successful code creation."""
    # Mock no existing code
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    
    # Mock successful insert
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "code-id-123", **sample_code_data}
    ]
    
    response = client.post("/codes", json=sample_code_data)
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "TEST-CODE-123" in response.json()["message"]


def test_create_code_duplicate(mock_supabase, sample_code_data):
    """Test creating duplicate code."""
    # Mock existing code
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "existing-id"}
    ]
    
    response = client.post("/codes", json=sample_code_data)
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_get_code_success(mock_supabase):
    """Test getting existing code."""
    mock_data = {
        "id": "code-id-123",
        "code": "TEST-CODE-123",
        "status": "active",
        "type": "discount"
    }
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [mock_data]
    
    response = client.get("/codes/TEST-CODE-123")
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["code"] == "TEST-CODE-123"


def test_get_code_not_found(mock_supabase):
    """Test getting non-existent code."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    
    response = client.get("/codes/NON-EXISTENT")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_mark_code_used_success(mock_supabase):
    """Test marking code as used."""
    # Mock existing active code
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "code-id", "code": "TEST-CODE", "status": "active", "current_uses": 0}
    ]
    
    # Mock successful update
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "code-id", "code": "TEST-CODE", "status": "used", "current_uses": 1}
    ]
    
    response = client.post("/codes/TEST-CODE/mark-used")
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "marked as used" in response.json()["message"]


def test_mark_code_used_already_used(mock_supabase):
    """Test marking already used code."""
    # Mock existing used code
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "code-id", "code": "TEST-CODE", "status": "used", "current_uses": 1}
    ]
    
    response = client.post("/codes/TEST-CODE/mark-used")
    
    assert response.status_code == 409
    assert "already used" in response.json()["detail"]


def test_revoke_code_success(mock_supabase):
    """Test revoking code."""
    # Mock existing code
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "code-id", "code": "TEST-CODE", "status": "active"}
    ]
    
    # Mock successful update
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "code-id", "code": "TEST-CODE", "status": "revoked"}
    ]
    
    response = client.post("/codes/TEST-CODE/revoke")
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "revoked" in response.json()["message"]


def test_allocate_code_success(mock_supabase):
    """Test allocating code."""
    # Mock successful allocation from Postgres function
    mock_supabase.rpc.return_value.execute.return_value.data = [
        {
            "id": "allocated-id",
            "code": "ALLOCATED-CODE",
            "used_at": "2025-09-15T00:00:00Z"
        }
    ]
    
    response = client.post("/codes/allocate")
    
    assert response.status_code == 200
    assert response.json()["code"] == "ALLOCATED-CODE"
    assert response.json()["id"] == "allocated-id"


def test_allocate_code_none_available(mock_supabase):
    """Test allocating code when none available."""
    # Mock no codes available
    mock_supabase.rpc.return_value.execute.return_value.data = []
    
    response = client.post("/codes/allocate")
    
    assert response.status_code == 404
    assert "No available" in response.json()["detail"]


def test_list_codes_with_filters(mock_supabase):
    """Test listing codes with filters."""
    mock_data = [
        {"id": "1", "code": "CODE-1", "status": "active", "type": "discount"},
        {"id": "2", "code": "CODE-2", "status": "active", "type": "discount"}
    ]
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = mock_data
    
    response = client.get("/codes?status=active&type=discount&limit=10")
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["data"]["codes"]) == 2
    assert response.json()["data"]["filters"]["status"] == "active"
