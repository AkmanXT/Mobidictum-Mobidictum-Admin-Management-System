import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch('app.deps.get_supabase') as mock:
        supabase_mock = Mock()
        mock.return_value = supabase_mock
        yield supabase_mock


@pytest.fixture
def webhook_payload():
    """Sample webhook payload."""
    return {
        "event_id": "test-event-123",
        "event_type": "order.created",
        "order": {
            "id": "order-456",
            "buyer_email": "test@example.com",
            "buyer_name": "Test User",
            "total": 100.0,
            "currency": "EUR",
            "created_at": "2025-09-15T00:00:00Z",
            "items": [
                {"name": "Test Item", "quantity": 1, "price": 100.0}
            ]
        }
    }


def test_webhook_missing_token(webhook_payload):
    """Test webhook endpoint without token."""
    response = client.post("/integrations/make/webhook", json=webhook_payload)
    assert response.status_code == 401
    assert "Invalid webhook token" in response.json()["detail"]


def test_webhook_invalid_token(webhook_payload):
    """Test webhook endpoint with invalid token."""
    headers = {"x-make-token": "invalid-token"}
    response = client.post("/integrations/make/webhook", json=webhook_payload, headers=headers)
    assert response.status_code == 401


@patch('app.config.settings.make_token', 'test-token')
def test_webhook_valid_token_new_event(mock_supabase, webhook_payload):
    """Test webhook with valid token and new event."""
    # Mock Supabase responses
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []  # No existing webhook
    mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []  # No existing order
    
    headers = {"x-make-token": "test-token"}
    response = client.post("/integrations/make/webhook", json=webhook_payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "test-event-123" in response.json()["message"]


@patch('app.config.settings.make_token', 'test-token')
def test_webhook_duplicate_event(mock_supabase, webhook_payload):
    """Test webhook with duplicate event_id."""
    # Mock existing webhook
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "existing"}]
    
    headers = {"x-make-token": "test-token"}
    response = client.post("/integrations/make/webhook", json=webhook_payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "already processed" in response.json()["message"]


def test_webhook_missing_event_id():
    """Test webhook without event_id."""
    payload = {"event_type": "order.created", "order": {}}
    headers = {"x-make-token": "test-token"}
    
    with patch('app.config.settings.make_token', 'test-token'):
        response = client.post("/integrations/make/webhook", json=payload, headers=headers)
    
    assert response.status_code == 400
    assert "Missing event_id" in response.json()["detail"]


def test_list_processed_webhooks(mock_supabase):
    """Test listing processed webhooks."""
    mock_data = [
        {"id": "1", "event_id": "event-1", "event_type": "order.created"},
        {"id": "2", "event_id": "event-2", "event_type": "order.completed"}
    ]
    
    mock_supabase.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value.data = mock_data
    
    response = client.get("/integrations/webhooks/processed")
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["data"]["webhooks"]) == 2
