# nextsms-python-sdk

Enterprise-ready Python SDK for the [NextSMS](https://nextsms.co.tz) API — Tanzania's leading bulk SMS gateway.

Supports sending single and bulk SMS messages, checking delivery status, querying account balance, validating phone numbers, and managing reseller sub-customer credits. Built with connection pooling, duplicate-safe automatic retries, and a clean exception hierarchy.

## Installation

```bash
pip install nextsms-python-sdk
```

## Quick start

```python
from nextsms import NextSMS

sms = NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD")

# Check API health
print(sms.is_healthy())  # True

# Send a single SMS
resp = sms.send_sms(
    sender_id="YOUR_SENDER_ID",
    recipient="255712345678",
    message="Hello from NextSMS SDK!",
)
print(resp.data["messages"][0]["messageId"])

# Check delivery status
status = sms.get_message_status("499303667522447963")
print(status.data["results"][0]["status"]["name"])  # DELIVERED

# Check account balance
bal = sms.get_balance()
print(bal.data["sms_balance"])

sms.close()
```

Use as a context manager to auto-close the HTTP session:

```python
with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    sms.send_sms(sender_id="YOUR_SENDER_ID", recipient="255712345678", message="Hello!")
```

## Features

### Single SMS

```python
resp = sms.send_sms(
    sender_id="YOUR_SENDER_ID",       # max 11 alphanumeric characters
    recipient="255712345678",   # or local format: "0712345678"
    message="Your OTP is 1234",
    callback_url="https://myapp.com/dlr",   # optional delivery report webhook
    schedule_time="2024-06-01T10:00:00Z",   # optional scheduled delivery
)
```

### Bulk SMS

```python
resp = sms.send_bulk_sms(
    sender_id="YOUR_SENDER_ID",
    recipients=["255712345678", "255754711158", "0765000000"],
    message="Hello everyone!",
)
```

### Delivery status

```python
status = sms.get_message_status(message_id="499303667522447963")
print(status.data["results"][0]["delivery"])  # DELIVERED / PENDING / FAILED
```

### Account balance

```python
bal = sms.get_balance()
print(bal.data["sms_balance"])
```

### Phone number validation

```python
result = sms.validate_number("255712345678")
```

### Reseller — recharge sub-customer

```python
resp = sms.recharge_customer(email="customer@example.com", smscount=5000)
```

### Reseller — deduct sub-customer

```python
resp = sms.deduct_customer(email="customer@example.com", smscount=2000)
```

## Phone number formats

The SDK accepts both international (`255712345678`) and local Tanzanian (`0712345678`) formats. Numbers are normalised to `255XXXXXXXXX` before being sent to the API.

## Error handling

All exceptions inherit from `NextSMSError`:

```python
from nextsms import (
    NextSMS,
    NextSMSAuthenticationError,
    NextSMSInsufficientBalanceError,
    NextSMSValidationError,
    NextSMSRateLimitError,
    NextSMSServerError,
    NextSMSConnectionError,
    NextSMSAmbiguousResponseError,
)

try:
    sms.send_sms(sender_id="YOUR_SENDER_ID", recipient="255712345678", message="Hi")
except NextSMSAuthenticationError:
    print("Bad credentials")
except NextSMSInsufficientBalanceError:
    print("Top up your account")
except NextSMSValidationError as e:
    print(f"Invalid input: {e}")
except NextSMSAmbiguousResponseError:
    # Sent, but no response came back: NextSMS may have delivered it.
    # Check get_logs() / delivery reports before resending.
    print("Unknown outcome, not resending blindly")
except NextSMSServerError:
    # 5xx on a send: the message may or may not have been accepted.
    print("NextSMS server error")
```

`NextSMSAmbiguousResponseError` subclasses `NextSMSConnectionError`, so an
existing `except NextSMSConnectionError` still catches it.

## Configuration

```python
sms = NextSMS(
    username="YOUR_USERNAME",
    password="YOUR_PASSWORD",
    test_mode=False,        # True → sandbox, no real SMS sent
    timeout=30,             # per-request timeout in seconds
    max_retries=3,          # automatic retries (0 = disable all retries)
    pool_connections=10,    # urllib3 connection pools
    pool_maxsize=100,       # max connections per pool
    backoff_factor=2.0,     # waits 2 s, 4 s, 8 s between retries (max 30 s)
)
```

### Retry policy

Sending an SMS is not idempotent: resending a request that NextSMS already
accepted delivers (and bills) a duplicate SMS. The SDK therefore only retries
automatically when it is certain the request was **not** processed:

| Outcome | GET (balance, logs, status) | POST (send SMS, reseller, validate) |
|---|---|---|
| Connection error before sending (DNS, refused, connect timeout) | retried | retried |
| HTTP 429 Too Many Requests | retried | retried |
| HTTP 500 / 502 / 503 / 504 | retried | **not retried** → `NextSMSServerError` |
| Read timeout / connection lost after sending | retried | **not retried** → `NextSMSAmbiguousResponseError` |

Waits honour the server's `Retry-After` header (capped at 60 s); otherwise
`backoff_factor * 2 ** (n - 1)` seconds before the n-th retry, capped at 30 s.
Pass `max_retries=0` if your application implements its own retry policy.

## Response object

Every SDK method returns a `NextSMSResponse`:

```python
resp.success      # bool
resp.status_code  # int (HTTP status)
resp.message      # str
resp.data         # dict (full API response body)
bool(resp)        # True if success
```

## Requirements

- Python 3.10+
- `requests >= 2.25.0`
- `urllib3 >= 1.26.0`

## Changelog

### 0.2.0

**Behaviour change: POST requests are no longer retried on 5xx or timeouts.**
Before 0.2.0 the SDK silently resent `send_sms`, `send_bulk_sms` and other
POST requests on HTTP 500/502/503/504, read timeouts and dropped connections.
When NextSMS had already accepted the message, this sent duplicate SMS to the
recipient and billed each copy. If your code relied on that silent resend, it
will now get an exception instead and must decide itself whether to resend
(ideally after checking `get_logs()` / delivery reports).

- **Safe POST retries**: POST is retried only when the request certainly was
  not processed: connection errors before sending, and HTTP 429.
  GET requests (balance, logs, status) still retry on connection errors, read
  timeouts, 429 and 500/502/503/504.
- **New exception `NextSMSAmbiguousResponseError`** (subclass of
  `NextSMSConnectionError`): raised when a POST was sent but no response came
  back (read timeout, connection reset), so the outcome is unknown.
- **Longer 429 backoff + `Retry-After`**: the `Retry-After` header is honoured
  (capped at 60 s); otherwise waits are 2 s, 4 s, 8 s (capped at 30 s), up from
  0 s, 1 s, 2 s, which just re-hit the rate limiter. The first retry now waits too.
- **New `backoff_factor` option** on `NextSMS` / `NextSMSClient` (default `2.0`).
- **`max_retries=0`** now cleanly disables every automatic retry, for
  applications that own their retry policy. Negative values raise `ValueError`.
- **Secure dependency floors**: `requests>=2.33.0` and `urllib3>=2.8.0` (the
  lowest versions with no known vulnerabilities as of release); `urllib3` is now
  an explicit dependency. These need **Python 3.10+**, so Python 3.8 / 3.9
  (both end-of-life) are no longer supported.

### 0.1.3

- Add `get_logs()` for bulk delivery-report lookups.

## License

MIT — see [LICENSE](LICENSE).
