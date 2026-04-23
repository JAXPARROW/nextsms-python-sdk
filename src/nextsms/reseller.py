"""
Reseller functionality for NextSMS — recharge and deduct sub-customer SMS credits.
"""

from typing import TYPE_CHECKING

from .client import NextSMSResponse
from .exceptions import NextSMSValidationError

if TYPE_CHECKING:
    from .client import NextSMSClient


class ResellerMixin:
    """Reseller feature mixin — applied to NextSMSClient via NextSMS."""

    # ------------------------------------------------------------------
    # Recharge sub-customer
    # ------------------------------------------------------------------

    def recharge_customer(
        self: "NextSMSClient",
        email: str,
        smscount: int,
    ) -> NextSMSResponse:
        """
        Transfer SMS credits from your reseller account to a sub-customer.

        Args:
            email: Sub-customer email address registered with NextSMS
            smscount: Number of SMS credits to transfer (must be positive)

        Returns:
            NextSMSResponse with Customer, Sms transferred, Your sms balance in .data

        Raises:
            NextSMSValidationError: email is empty or smscount is not positive
            NextSMSAuthenticationError: Invalid credentials
            NextSMSInsufficientBalanceError: Not enough credits to transfer
        """
        self._validate_reseller_params(email, smscount)

        payload = {"email": email, "smscount": smscount}
        response = self.http.request(
            "POST", "api/reseller/v1/sub_customer/recharge", json=payload
        )
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Deduct sub-customer
    # ------------------------------------------------------------------

    def deduct_customer(
        self: "NextSMSClient",
        email: str,
        smscount: int,
    ) -> NextSMSResponse:
        """
        Recover SMS credits from a sub-customer back to your reseller account.

        Args:
            email: Sub-customer email address registered with NextSMS
            smscount: Number of SMS credits to deduct (must be positive)

        Returns:
            NextSMSResponse with Customer, Sms deducted, Your sms balance,
            Customer sms balance in .data

        Raises:
            NextSMSValidationError: email is empty or smscount is not positive
            NextSMSAuthenticationError: Invalid credentials
            NextSMSInsufficientBalanceError: Customer has insufficient balance
        """
        self._validate_reseller_params(email, smscount)

        payload = {"email": email, "smscount": smscount}
        response = self.http.request(
            "POST", "api/reseller/v1/sub_customer/deduct", json=payload
        )
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_reseller_params(email: str, smscount: int) -> None:
        if not email or not email.strip():
            raise NextSMSValidationError("email cannot be empty")
        if not isinstance(smscount, int) or smscount <= 0:
            raise NextSMSValidationError(
                f"smscount must be a positive integer, got {smscount!r}"
            )
