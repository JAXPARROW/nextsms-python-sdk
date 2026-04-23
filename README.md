# nextsms-python-sdk

Enterprise-ready Python SDK for the [NextSMS](https://nextsms.co.tz) API — Tanzania's leading bulk SMS gateway.

Supports sending single and bulk SMS messages, checking delivery status, querying account balance, validating phone numbers, and managing reseller sub-customer credits. Built with connection pooling, automatic retries, and a clean exception hierarchy.

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
)

try:
    sms.send_sms(sender_id="YOUR_SENDER_ID", recipient="255712345678", message="Hi")
except NextSMSAuthenticationError:
    print("Bad credentials")
except NextSMSInsufficientBalanceError:
    print("Top up your account")
except NextSMSValidationError as e:
    print(f"Invalid input: {e}")
```

## Configuration

```python
sms = NextSMS(
    username="YOUR_USERNAME",
    password="YOUR_PASSWORD",
    test_mode=False,        # True → sandbox, no real SMS sent
    timeout=30,             # per-request timeout in seconds
    max_retries=3,          # retries on 429 / 5xx
    pool_connections=10,    # urllib3 connection pools
    pool_maxsize=100,       # max connections per pool
)
```

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

- Python 3.8+
- `requests >= 2.25.0`

## License

MIT — see [LICENSE](LICENSE).
