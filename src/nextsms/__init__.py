"""
NextSMS Python SDK — enterprise-ready client for the NextSMS API.
"""

from .client import NextSMSClient, NextSMSResponse
from .sms import SMSMixin
from .reseller import ResellerMixin
from .exceptions import (
    NextSMSError,
    NextSMSAuthenticationError,
    NextSMSValidationError,
    NextSMSAPIError,
    NextSMSRateLimitError,
    NextSMSInsufficientBalanceError,
    NextSMSInvalidSenderError,
    NextSMSConnectionError,
    NextSMSServerError,
)


class NextSMS(NextSMSClient, SMSMixin, ResellerMixin):
    """
    Complete NextSMS client — entry point for all SDK features.

    Example::

        from nextsms import NextSMS

        sms = NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD")

        # Health check
        print(sms.is_healthy())

        # Send SMS
        resp = sms.send_sms(
            sender_id="YOUR_SENDER_ID",
            recipient="255712345678",
            message="Hello from NextSMS SDK!",
        )
        print(resp.data["message_id"])

        # Bulk send
        resp = sms.send_bulk_sms(
            sender_id="YOUR_SENDER_ID",
            recipients=["255712345678", "255712345679"],
            message="Bulk hello!",
        )
        print(resp.data["batch_id"])

        sms.close()
    """


__version__ = "0.1.3"

__all__ = [
    "NextSMS",
    "NextSMSClient",
    "NextSMSResponse",
    "NextSMSError",
    "NextSMSAuthenticationError",
    "NextSMSValidationError",
    "NextSMSAPIError",
    "NextSMSRateLimitError",
    "NextSMSInsufficientBalanceError",
    "NextSMSInvalidSenderError",
    "NextSMSConnectionError",
    "NextSMSServerError",
]
