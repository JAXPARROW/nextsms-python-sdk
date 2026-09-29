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
        to: Optional[str] = None,
        sent_since: Optional[str] = None,
        sent_until: Optional[str] = None,
        limit: int = 100,
    ) -> NextSMSResponse:
        """
        Retrieve delivery status for a previously sent message.

        NextSMS has no "look up this one messageId" endpoint — the real API
        (GET /api/sms/v1/logs) only supports filtering by sender (`from`),
        recipient (`to`), a sent-date range, and pagination; each returned
        log entry carries its own `messageId`. This fetches a page of logs
        and picks out the matching entry client-side.

        Narrowing with `to` (and ideally `sent_since`/`sent_until`) is
        strongly recommended on any account with real send volume — without
        it, the target message can fall outside the fetched page and look
        like "not found" even though it exists.

        Args:
            message_id: The message_id returned by send_sms
            to: Recipient number to narrow the search (recommended)
            sent_since: Lower bound on send date, e.g. "2020-02-01"
            sent_until: Upper bound on send date, e.g. "2020-02-20"
            limit: Max log entries to scan for a match (API max: 500)

        Returns:
            NextSMSResponse whose .data["results"] holds either the one
            matching log entry, or is empty if it wasn't in the fetched page.

        Raises:
            NextSMSValidationError: message_id is empty
            NextSMSAPIError: Message not found or other error
        """
        if not message_id or not message_id.strip():
            raise NextSMSValidationError("message_id cannot be empty")

        params: dict = {"limit": limit}
        if to:
            params["to"] = to
        if sent_since:
            params["sentSince"] = sent_since
        if sent_until:
            params["sentUntil"] = sent_until

        response = self.http.request("GET", "api/sms/v1/logs", params=params)
        result = self._handle_response(response)

        if result.success:
            match = next(
                (r for r in result.data.get("results", []) if str(r.get("messageId")) == str(message_id)),
                None,
            )
            result.data = {"results": [match] if match else []}

        return result

    # ------------------------------------------------------------------
    # Bulk log fetch (many messages, one request)
    # ------------------------------------------------------------------

    def get_logs(
        self: "NextSMSClient",
        to: Optional[str] = None,
        sent_since: Optional[str] = None,
        sent_until: Optional[str] = None,
        limit: int = 500,
    ) -> NextSMSResponse:
        """
        Fetch a page of raw send-log entries — the same underlying data
        `get_message_status()` scans for a single messageId, but returned
        as-is so a caller checking many messages at once can match them
        all against one response instead of issuing one request per
        message.

        Without `to`, this returns the account's own most recent log
        entries (observed in practice: several hundred entries spanning
        many recipients from one call) rather than anything scoped to a
        single recipient — useful for a delivery-status sweep across many
        outstanding messages, where most targets are recent enough to
        appear in this one page. Any messageId not found here may still
        be resolved with a narrower `get_message_status(message_id, to=...)`
        call, which is more reliable for older messages but costs one
        request each.

        Args:
            to: Recipient number to narrow the search (omit for account-wide)
            sent_since: Lower bound on send date, e.g. "2020-02-01"
            sent_until: Upper bound on send date, e.g. "2020-02-20"
            limit: Max log entries to return (API max: 500)

        Returns:
            NextSMSResponse whose .data["results"] is the raw list of log
            entries (each with its own "messageId"), unfiltered.
        """
        params: dict = {"limit": limit}
        if to:
            params["to"] = to
        if sent_since:
            params["sentSince"] = sent_since
        if sent_until:
            params["sentUntil"] = sent_until

        response = self.http.request("GET", "api/sms/v1/logs", params=params)
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
