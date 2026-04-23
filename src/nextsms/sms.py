"""
SMS functionality for NextSMS — send single, bulk, check status,
get balance, and validate numbers.
"""

from typing import List, Optional, TYPE_CHECKING

from .client import NextSMSResponse
from .exceptions import NextSMSValidationError
from .utils.validators import PhoneNumberValidator

if TYPE_CHECKING:
    from .client import NextSMSClient


class SMSMixin:
    """SMS feature mixin — applied to NextSMSClient via NextSMS."""

    # ------------------------------------------------------------------
    # Send single SMS
    # ------------------------------------------------------------------

    def send_sms(
        self: "NextSMSClient",
        sender_id: str,
        recipient: str,
        message: str,
        callback_url: Optional[str] = None,
        schedule_time: Optional[str] = None,
    ) -> NextSMSResponse:
        """
        Send a single SMS message.

        Args:
            sender_id: Alphanumeric sender name (max 11 characters)
            recipient: Destination phone number (255XXXXXXXXX format)
            message: SMS text content (max 1600 characters)
            callback_url: Optional webhook URL for delivery reports
            schedule_time: Optional ISO 8601 datetime to schedule delivery

        Returns:
            NextSMSResponse with message_id and status_code in .data

        Raises:
            NextSMSValidationError: Invalid sender_id, recipient, or message
            NextSMSAuthenticationError: Wrong credentials
            NextSMSInsufficientBalanceError: Not enough SMS credits
            NextSMSRateLimitError: Too many requests
        """
        self._validate_sender_id(sender_id)
        if not message or not message.strip():
            raise NextSMSValidationError("Message cannot be empty")
        if len(message) > 1600:
            raise NextSMSValidationError(
                f"Message too long: {len(message)} characters (max 1600)"
            )

        try:
            clean_recipient = PhoneNumberValidator.clean(recipient)
        except ValueError as exc:
            raise NextSMSValidationError(str(exc)) from exc

        payload: dict = {
            "from": sender_id,
            "to": clean_recipient,
            "text": message,
        }
        if callback_url:
            payload["notifyUrl"] = callback_url
        if schedule_time:
            payload["sendAt"] = schedule_time

        response = self.http.request("POST", "api/sms/v1/text/single", json=payload)
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Send bulk SMS
    # ------------------------------------------------------------------

    def send_bulk_sms(
        self: "NextSMSClient",
        sender_id: str,
        recipients: List[str],
        message: str,
        callback_url: Optional[str] = None,
    ) -> NextSMSResponse:
        """
        Send a single message to multiple recipients (max 1000 per call).

        Args:
            sender_id: Alphanumeric sender name (max 11 characters)
            recipients: List of destination phone numbers
            message: SMS text content (max 1600 characters)
            callback_url: Optional webhook URL for delivery reports

        Returns:
            NextSMSResponse with batch_id, total, accepted, rejected in .data

        Raises:
            NextSMSValidationError: Any input is invalid
            NextSMSInsufficientBalanceError: Not enough SMS credits
        """
        self._validate_sender_id(sender_id)
        if not message or not message.strip():
            raise NextSMSValidationError("Message cannot be empty")
        if len(message) > 1600:
            raise NextSMSValidationError(
                f"Message too long: {len(message)} characters (max 1600)"
            )
        if not recipients:
            raise NextSMSValidationError("At least one recipient is required")
        if len(recipients) > 1000:
            raise NextSMSValidationError(
                f"Too many recipients: {len(recipients)} (max 1000 per request)"
            )

        cleaned: List[str] = []
        for phone in recipients:
            try:
                cleaned.append(PhoneNumberValidator.clean(phone))
            except ValueError as exc:
                raise NextSMSValidationError(str(exc)) from exc

        payload: dict = {
            "from": sender_id,
            "to": cleaned,
            "text": message,
        }
        if callback_url:
            payload["notifyUrl"] = callback_url

        response = self.http.request("POST", "api/sms/v1/text/multi", json=payload)
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Check message status
    # ------------------------------------------------------------------

    def get_message_status(
        self: "NextSMSClient",
        message_id: str,
    ) -> NextSMSResponse:
        """
        Retrieve delivery status for a previously sent message.

        Args:
            message_id: The message_id returned by send_sms

        Returns:
            NextSMSResponse with status, status_code, delivered_at, sent_at in .data

        Raises:
            NextSMSValidationError: message_id is empty
            NextSMSAPIError: Message not found or other error
        """
        if not message_id or not message_id.strip():
            raise NextSMSValidationError("message_id cannot be empty")

        response = self.http.request("GET", f"api/sms/v1/reports?messageId={message_id}")
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Account balance
    # ------------------------------------------------------------------

    def get_balance(self: "NextSMSClient") -> NextSMSResponse:
        """
        Retrieve current account balance and SMS credit information.

        Returns:
            NextSMSResponse with balance, currency, sms_remaining, sms_rate in .data

        Raises:
            NextSMSAuthenticationError: Invalid credentials
            NextSMSConnectionError: Network error
        """
        response = self.http.request("GET", "api/sms/v1/balance")
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Number validation
    # ------------------------------------------------------------------

    def validate_number(
        self: "NextSMSClient",
        phone_number: str,
    ) -> NextSMSResponse:
        """
        Validate a phone number via the NextSMS API.

        Also performs local format validation before making the API call.

        Args:
            phone_number: Phone number to validate (255XXXXXXXXX format)

        Returns:
            NextSMSResponse with valid, country_code, operator, is_mobile in .data

        Raises:
            NextSMSValidationError: Phone number format is invalid locally
            NextSMSAPIError: API-level validation error
        """
        try:
            clean = PhoneNumberValidator.clean(phone_number)
        except ValueError as exc:
            raise NextSMSValidationError(str(exc)) from exc

        response = self.http.request("POST", "api/sms/v1/validate-number", json={"phone_number": clean})
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_sender_id(sender_id: str) -> None:
        if not sender_id or not sender_id.strip():
            raise NextSMSValidationError("sender_id cannot be empty")
        if len(sender_id) > 11:
            raise NextSMSValidationError(
                f"sender_id must be at most 11 characters, got {len(sender_id)}"
            )
        if not sender_id.isalnum():
            raise NextSMSValidationError(
                "sender_id must be alphanumeric (letters and digits only)"
            )
