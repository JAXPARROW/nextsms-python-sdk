"""
Main NextSMS client with connection pooling and health check.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .utils.http_client import BASE_URL, TEST_BASE_URL, PooledHTTPClient
from .exceptions import (
    NextSMSAPIError,
    NextSMSAuthenticationError,
    NextSMSInsufficientBalanceError,
    NextSMSInvalidSenderError,
    NextSMSRateLimitError,
    NextSMSServerError,
)


@dataclass
class NextSMSResponse:
    """Unified response object returned by every SDK method."""

    success: bool
    status_code: int
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


_API_CODE_EXCEPTIONS = {
    "INVALID_SENDER_ID": NextSMSInvalidSenderError,
    "INVALID_RECIPIENT": NextSMSAPIError,
    "EMPTY_MESSAGE": NextSMSAPIError,
    "MESSAGE_TOO_LONG": NextSMSAPIError,
    "INSUFFICIENT_BALANCE": NextSMSInsufficientBalanceError,
}


class NextSMSClient:
    """
    Main client for the NextSMS API.

    Provides connection pooling, automatic retries, and comprehensive
    error handling. Supports both live and test modes.

    Example::

        client = NextSMSClient(username="YOUR_USERNAME", password="YOUR_PASSWORD")

        if client.is_healthy():
            print("API is up")

        response = client.send_sms(
            sender_id="YOUR_SENDER_ID",
            recipient="255712345678",
            message="Hello!",
        )
        if response:
            print(response.data["message_id"])

        client.close()

    Use as a context manager::

        with NextSMSClient(username="...", password="...") as client:
            client.send_sms(...)
    """

    def __init__(
        self,
        username: str,
        password: str,
        test_mode: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
        pool_connections: int = 10,
        pool_maxsize: int = 100,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Args:
            username: NextSMS account username
            password: NextSMS account password
            test_mode: When True, uses the sandbox URL — no real SMS sent
            timeout: Per-request timeout in seconds
            max_retries: Maximum retry attempts for transient failures
            pool_connections: Number of urllib3 connection pools to cache
            pool_maxsize: Maximum connections per pool
            logger: Optional custom logger
        """
        self.username = username
        self.test_mode = test_mode
        self.logger = logger or logging.getLogger(__name__)

        base_url = TEST_BASE_URL if test_mode else BASE_URL

        self.http = PooledHTTPClient(
            username=username,
            password=password,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            logger=self.logger,
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        """
        Check if the NextSMS API is reachable and credentials are valid.

        Never raises — always returns True or False. Use for monitoring.
        """
        try:
            response = self.http.request("GET", "api/sms/v1/balance", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal response handler
    # ------------------------------------------------------------------

    def _handle_response(self, response) -> NextSMSResponse:
        """Convert a raw requests.Response into a NextSMSResponse."""
        status_code = response.status_code

        # Try to get JSON body
        try:
            body = response.json()
        except ValueError:
            body = {}

        # Success path
        if status_code == 200:
            return NextSMSResponse(
                success=True,
                status_code=status_code,
                message=body.get("message", "OK"),
                data=body,
            )

        # Error path — map HTTP status → exception
        api_code = body.get("code", "")
        api_message = body.get("message", response.text or f"HTTP {status_code}")

        if status_code == 401:
            raise NextSMSAuthenticationError(api_message)
        if status_code == 402:
            raise NextSMSInsufficientBalanceError(api_message, code=api_code, response_data=body)
        if status_code == 429:
            raise NextSMSRateLimitError(api_message, code=api_code, response_data=body)
        if 500 <= status_code < 600:
            raise NextSMSServerError(api_message, code=str(status_code), response_data=body)

        # 4xx with an API-level error code
        exc_class = _API_CODE_EXCEPTIONS.get(api_code, NextSMSAPIError)
        raise exc_class(api_message, code=api_code, response_data=body)

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def close(self):
        """Close underlying HTTP session and free resources."""
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
