"""
Pytest configuration and shared fixtures for NextSMS SDK tests.
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nextsms import NextSMS
from nextsms.client import NextSMSResponse


@pytest.fixture
def mock_client():
    """NextSMS client with a mocked HTTP layer."""
    with patch("nextsms.utils.http_client.PooledHTTPClient") as mock_http_cls:
        mock_http = Mock()
        mock_http_cls.return_value = mock_http

        client = NextSMS(username="test_user", password="test_pass")
        client._handle_response = Mock()
        return client, mock_http


@pytest.fixture
def client():
    """Real NextSMS client with the HTTP session mocked at request level."""
    with patch("nextsms.utils.http_client.PooledHTTPClient.request") as mock_request:
        c = NextSMS(username="test_user", password="test_pass")
        yield c, mock_request


@pytest.fixture
def success_send_sms_response():
    return NextSMSResponse(
        success=True,
        status_code=200,
        message="Message sent",
        data={
            "status": "success",
            "message_id": "msg_20240423_123456",
            "recipient": "255712345678",
            "status_code": "PENDING",
        },
    )


@pytest.fixture
def success_bulk_sms_response():
    return NextSMSResponse(
        success=True,
        status_code=200,
        message="Bulk sent",
        data={
            "status": "success",
            "batch_id": "batch_20240423_123456",
            "total": 2,
            "accepted": 2,
            "rejected": 0,
            "messages": [
                {"recipient": "255712345678", "message_id": "msg_001", "status": "accepted"},
                {"recipient": "255712345679", "message_id": "msg_002", "status": "accepted"},
            ],
        },
    )


@pytest.fixture
def success_balance_response():
    return NextSMSResponse(
        success=True,
        status_code=200,
        message="OK",
        data={
            "balance": 1250.50,
            "currency": "TZS",
            "sms_remaining": 12505,
            "sms_rate": 0.10,
        },
    )


@pytest.fixture
def success_status_response():
    return NextSMSResponse(
        success=True,
        status_code=200,
        message="OK",
        data={
            "message_id": "msg_20240423_123456",
            "recipient": "255712345678",
            "status": "DELIVERED",
            "status_code": "DELIVERY",
            "delivered_at": "2024-04-23T10:05:30Z",
            "sent_at": "2024-04-23T10:00:00Z",
        },
    )


@pytest.fixture
def success_validate_response():
    return NextSMSResponse(
        success=True,
        status_code=200,
        message="OK",
        data={
            "valid": True,
            "phone_number": "255712345678",
            "country_code": "TZ",
            "operator": "Vodacom",
            "is_mobile": True,
        },
    )
