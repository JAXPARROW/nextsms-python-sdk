"""
Example: check delivery status of a previously sent message.
"""

from nextsms import NextSMS

MESSAGE_ID = "msg_20240423_123456"

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    response = sms.get_message_status(MESSAGE_ID)
    if response:
        d = response.data
        print(
            f"Message {d['message_id']} to {d['recipient']}: "
            f"{d['status']} (delivered_at={d.get('delivered_at', 'N/A')})"
        )
