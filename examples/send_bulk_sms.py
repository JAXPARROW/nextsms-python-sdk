"""
Example: send one message to multiple recipients.
"""

from nextsms import NextSMS, NextSMSValidationError

RECIPIENTS = [
    "255712345678",
    "255712345679",
    "255712345680",
]

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    try:
        response = sms.send_bulk_sms(
            sender_id="YOUR_SENDER_ID",
            recipients=RECIPIENTS,
            message="Bulk announcement from NextSMS SDK!",
        )
        if response:
            data = response.data
            print(
                f"Batch submitted — id={data['batch_id']} "
                f"accepted={data['accepted']} rejected={data['rejected']}"
            )
    except NextSMSValidationError as e:
        print(f"Validation error: {e}")
