"""
Tests for SMS functionality — send_sms, send_bulk_sms,
get_message_status, get_balance, validate_number.
"""

import pytest
from unittest.mock import Mock, patch

from nextsms import NextSMS, NextSMSResponse
from nextsms.exceptions import NextSMSValidationError

PATCH_TARGET = "nextsms.client.PooledHTTPClient"


def _make_client():
    """Return a NextSMS client whose HTTP layer is fully mocked."""
    with patch(PATCH_TARGET) as cls:
        http_mock = Mock()
        cls.return_value = http_mock
        client = NextSMS(username="u", password="p")

    # client.http is now the Mock instance created inside the patch
    # Overwrite _handle_response so it always returns a success response
    client._handle_response = Mock(
        return_value=NextSMSResponse(success=True, status_code=200, message="OK", data={})
    )
    return client


class TestSendSMS:
    def setup_method(self):
        self.client = _make_client()

    def test_valid_call_hits_endpoint(self):
        self.client.send_sms(
            sender_id="NANOTECH",
            recipient="255712345678",
            message="Hello",
        )
        self.client.http.request.assert_called_once_with(
            "POST", "api/sms/v1/text/single", json={
                "from": "NANOTECH",
                "to": "255712345678",
                "text": "Hello",
            }
        )

    def test_optional_callback_url_included(self):
        self.client.send_sms(
            sender_id="NANOTECH",
            recipient="255712345678",
            message="Hello",
            callback_url="https://example.com/dlr",
        )
        _, kwargs = self.client.http.request.call_args
        assert kwargs["json"]["notifyUrl"] == "https://example.com/dlr"

    def test_schedule_time_included(self):
        self.client.send_sms(
            sender_id="NANOTECH",
            recipient="255712345678",
            message="Scheduled",
            schedule_time="2024-05-01T10:00:00Z",
        )
        _, kwargs = self.client.http.request.call_args
        assert kwargs["json"]["sendAt"] == "2024-05-01T10:00:00Z"

    def test_local_format_phone_accepted(self):
        self.client.send_sms(
            sender_id="NANOTECH",
            recipient="0712345678",
            message="Hello",
        )
        _, kwargs = self.client.http.request.call_args
        assert kwargs["json"]["to"] == "255712345678"

    def test_empty_message_raises(self):
        with pytest.raises(NextSMSValidationError, match="empty"):
            self.client.send_sms(
                sender_id="NANOTECH",
                recipient="255712345678",
                message="",
            )

    def test_message_too_long_raises(self):
        with pytest.raises(NextSMSValidationError, match="too long"):
            self.client.send_sms(
                sender_id="NANOTECH",
                recipient="255712345678",
                message="x" * 1601,
            )

    def test_empty_sender_id_raises(self):
        with pytest.raises(NextSMSValidationError):
            self.client.send_sms(
                sender_id="",
                recipient="255712345678",
                message="Hello",
            )

    def test_sender_id_too_long_raises(self):
        with pytest.raises(NextSMSValidationError, match="11"):
            self.client.send_sms(
                sender_id="TOOLONGSENDER",
                recipient="255712345678",
                message="Hello",
            )

    def test_invalid_phone_raises(self):
        with pytest.raises(NextSMSValidationError):
            self.client.send_sms(
                sender_id="NANOTECH",
                recipient="123",
                message="Hello",
            )

    def test_non_alphanumeric_sender_raises(self):
        with pytest.raises(NextSMSValidationError, match="alphanumeric"):
            self.client.send_sms(
                sender_id="NANO!",
                recipient="255712345678",
                message="Hello",
            )


class TestSendBulkSMS:
    def setup_method(self):
        self.client = _make_client()

    def test_valid_bulk_call(self):
        self.client.send_bulk_sms(
            sender_id="NANOTECH",
            recipients=["255712345678", "255712345679"],
            message="Bulk hello",
        )
        self.client.http.request.assert_called_once_with(
            "POST", "api/sms/v1/text/multi", json={
                "from": "NANOTECH",
                "to": ["255712345678", "255712345679"],
                "text": "Bulk hello",
            }
        )

    def test_empty_recipients_raises(self):
        with pytest.raises(NextSMSValidationError, match="one recipient"):
            self.client.send_bulk_sms(
                sender_id="NANOTECH",
                recipients=[],
                message="Hello",
            )

    def test_too_many_recipients_raises(self):
        with pytest.raises(NextSMSValidationError, match="1000"):
            self.client.send_bulk_sms(
                sender_id="NANOTECH",
                recipients=[f"2557123456{i:02d}" for i in range(1001)],
                message="Hello",
            )

    def test_invalid_recipient_in_list_raises(self):
        with pytest.raises(NextSMSValidationError):
            self.client.send_bulk_sms(
                sender_id="NANOTECH",
                recipients=["255712345678", "bad-number"],
                message="Hello",
            )


class TestGetMessageStatus:
    def setup_method(self):
        self.client = _make_client()

    def test_calls_logs_endpoint_without_filters(self):
        self.client.get_message_status("msg_123")
        self.client.http.request.assert_called_once_with(
            "GET", "api/sms/v1/logs", params={"limit": 100}
        )

    def test_calls_logs_endpoint_with_filters(self):
        self.client.get_message_status(
            "msg_123", to="255712345678", sent_since="2020-02-01", sent_until="2020-02-20", limit=5
        )
        self.client.http.request.assert_called_once_with(
            "GET", "api/sms/v1/logs",
            params={"limit": 5, "to": "255712345678", "sentSince": "2020-02-01", "sentUntil": "2020-02-20"},
        )

    def test_empty_message_id_raises(self):
        with pytest.raises(NextSMSValidationError, match="empty"):
            self.client.get_message_status("")

    def test_filters_results_to_matching_message_id(self):
        self.client._handle_response = Mock(
            return_value=NextSMSResponse(
                success=True, status_code=200, message="OK",
                data={"results": [
                    {"messageId": "other", "status": {"groupName": "DELIVERED"}},
                    {"messageId": "msg_123", "status": {"groupName": "PENDING"}},
                ]},
            )
        )
        result = self.client.get_message_status("msg_123")
        assert result.data["results"] == [{"messageId": "msg_123", "status": {"groupName": "PENDING"}}]

    def test_no_match_returns_empty_results(self):
        self.client._handle_response = Mock(
            return_value=NextSMSResponse(
                success=True, status_code=200, message="OK",
                data={"results": [{"messageId": "other", "status": {"groupName": "DELIVERED"}}]},
            )
        )
        result = self.client.get_message_status("msg_123")
        assert result.data["results"] == []


class TestGetBalance:
    def setup_method(self):
        self.client = _make_client()

    def test_calls_balance_endpoint(self):
        self.client.get_balance()
        self.client.http.request.assert_called_once_with("GET", "api/sms/v1/balance")


class TestValidateNumber:
    def setup_method(self):
        self.client = _make_client()

    def test_calls_validate_endpoint(self):
        self.client.validate_number("255712345678")
        self.client.http.request.assert_called_once_with(
            "POST", "api/sms/v1/validate-number", json={"phone_number": "255712345678"}
        )

    def test_local_format_cleaned_before_call(self):
        self.client.validate_number("0712345678")
        _, kwargs = self.client.http.request.call_args
        assert kwargs["json"]["phone_number"] == "255712345678"

    def test_invalid_phone_raises_before_api_call(self):
        with pytest.raises(NextSMSValidationError):
            self.client.validate_number("not-a-number")
        self.client.http.request.assert_not_called()
