"""
Example: send a single SMS.
"""

from nextsms import NextSMS, NextSMSValidationError, NextSMSInsufficientBalanceError

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    try:
        response = sms.send_sms(
            sender_id="YOUR_SENDER_ID",
            recipient="255712345678",
            message="Hello from NextSMS Python SDK!",
            callback_url="https://yourdomain.com/webhooks/sms/dlr",
        )
        if response:
            print(f"Sent! message_id={response.data['message_id']}")
    except NextSMSValidationError as e:
        print(f"Validation error: {e}")
    except NextSMSInsufficientBalanceError:
        print("Not enough SMS credits.")
