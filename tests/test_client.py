"""
Tests for NextSMSClient — is_healthy, _handle_response, context manager.
"""

import pytest
from unittest.mock import Mock, patch
from requests import Response

from nextsms import NextSMS, NextSMSResponse
from nextsms.exceptions import (
    NextSMSAuthenticationError,
    NextSMSInsufficientBalanceError,
    NextSMSRateLimitError,
    NextSMSServerError,
    NextSMSAPIError,
)

# client.py imports PooledHTTPClient into its own namespace, so patch there.
PATCH_TARGET = "nextsms.client.PooledHTTPClient"


def _make_response(status_code: int, json_data: dict = None, text: str = "") -> Mock:
    resp = Mock(spec=Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no json")
    return resp


class TestIsHealthy:
    def test_returns_true_on_200(self):
        with patch(PATCH_TARGET) as cls:
            instance = Mock()
            instance.request.return_value = _make_response(200, {})
            cls.return_value = instance

            client = NextSMS(username="u", password="p")
            assert client.is_healthy() is True

    def test_returns_false_on_401(self):
        with patch(PATCH_TARGET) as cls:
            instance = Mock()
            instance.request.return_value = _make_response(401, {})
            cls.return_value = instance

            client = NextSMS(username="u", password="p")
            assert client.is_healthy() is False

    def test_returns_false_on_exception(self):
        with patch(PATCH_TARGET) as cls:
            instance = Mock()
            instance.request.side_effect = Exception("network down")
            cls.return_value = instance

            client = NextSMS(username="u", password="p")
            assert client.is_healthy() is False


class TestHandleResponse:
    def setup_method(self):
        with patch(PATCH_TARGET):
            self.client = NextSMS(username="u", password="p")

    def test_200_returns_nextsms_response(self):
        resp = _make_response(200, {"message": "OK", "message_id": "abc"})
        result = self.client._handle_response(resp)
        assert isinstance(result, NextSMSResponse)
        assert result.success is True
        assert result.data["message_id"] == "abc"

    def test_401_raises_auth_error(self):
        resp = _make_response(401, {"message": "Unauthorized"})
        with pytest.raises(NextSMSAuthenticationError):
            self.client._handle_response(resp)

    def test_402_raises_insufficient_balance(self):
        resp = _make_response(402, {"code": "INSUFFICIENT_BALANCE", "message": "No credits"})
        with pytest.raises(NextSMSInsufficientBalanceError):
            self.client._handle_response(resp)

    def test_429_raises_rate_limit(self):
        resp = _make_response(429, {"code": "RATE_LIMITED", "message": "Slow down"})
        with pytest.raises(NextSMSRateLimitError):
            self.client._handle_response(resp)

    def test_500_raises_server_error(self):
        resp = _make_response(500, {"message": "Internal error"})
        with pytest.raises(NextSMSServerError):
            self.client._handle_response(resp)

    def test_400_api_error_code(self):
        resp = _make_response(400, {"code": "EMPTY_MESSAGE", "message": "No message"})
        with pytest.raises(NextSMSAPIError) as exc_info:
            self.client._handle_response(resp)
        assert exc_info.value.code == "EMPTY_MESSAGE"

    def test_nextsms_response_bool_true(self):
        r = NextSMSResponse(success=True, status_code=200, message="OK")
        assert bool(r) is True

    def test_nextsms_response_bool_false(self):
        r = NextSMSResponse(success=False, status_code=400, message="Bad")
        assert bool(r) is False


class TestContextManager:
    def test_context_manager_calls_close(self):
        with patch(PATCH_TARGET) as cls:
            instance = Mock()
            cls.return_value = instance

            with NextSMS(username="u", password="p"):
                pass

            instance.close.assert_called_once()


class TestTestMode:
    def test_test_mode_uses_test_url(self):
        from nextsms.utils.http_client import TEST_BASE_URL
        with patch(PATCH_TARGET) as cls:
            cls.return_value = Mock()
            NextSMS(username="u", password="p", test_mode=True)
            _, init_kwargs = cls.call_args
            assert init_kwargs.get("base_url") == TEST_BASE_URL

    def test_live_mode_uses_live_url(self):
        from nextsms.utils.http_client import BASE_URL
        with patch(PATCH_TARGET) as cls:
            cls.return_value = Mock()
            NextSMS(username="u", password="p", test_mode=False)
            _, init_kwargs = cls.call_args
            assert init_kwargs.get("base_url") == BASE_URL
