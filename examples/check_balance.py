"""
Example: retrieve account balance and SMS credit information.
"""

from nextsms import NextSMS

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    response = sms.get_balance()
    if response:
        d = response.data
        print(
            f"Balance: {d['balance']} {d['currency']} | "
            f"SMS remaining: {d['sms_remaining']} (rate: {d['sms_rate']} each)"
        )
