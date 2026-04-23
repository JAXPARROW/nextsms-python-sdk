"""
Example: use test mode — no real SMS is sent and no balance is deducted.
"""

from nextsms import NextSMS

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD", test_mode=True) as sms:
    response = sms.send_sms(
        sender_id="YOUR_SENDER_ID",
        recipient="255712345678",
        message="Test message — sandbox only",
    )
    if response:
        print(f"Test mode response: {response.data}")
