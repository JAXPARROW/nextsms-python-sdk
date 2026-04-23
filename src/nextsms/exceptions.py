"""
Custom exception hierarchy for NextSMS SDK.
All exceptions inherit from NextSMSError for easy catching.
"""


class NextSMSError(Exception):
    """Base exception for all NextSMS SDK errors"""
    pass


class NextSMSAuthenticationError(NextSMSError):
    """Invalid credentials (HTTP 401)"""
    pass


class NextSMSValidationError(NextSMSError):
    """Input validation failed (e.g., invalid phone number, bad sender ID)"""
    pass


class NextSMSAPIError(NextSMSError):
    """API returned an error response"""
    def __init__(self, message: str, code: str = None, response_data: dict = None):
        super().__init__(message)
        self.code = code
        self.response_data = response_data or {}


class NextSMSRateLimitError(NextSMSAPIError):
    """Rate limit exceeded (HTTP 429)"""
    pass


class NextSMSInsufficientBalanceError(NextSMSAPIError):
    """Not enough SMS credits (HTTP 402)"""
    pass


class NextSMSInvalidSenderError(NextSMSAPIError):
    """Sender ID not allowed or incorrectly formatted"""
    pass


class NextSMSConnectionError(NextSMSError):
    """Network-level error (timeout, DNS failure)"""
    pass


class NextSMSServerError(NextSMSAPIError):
    """NextSMS server error (HTTP 5xx)"""
    pass
