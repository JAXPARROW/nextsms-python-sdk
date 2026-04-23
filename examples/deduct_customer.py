"""
Example: deduct SMS credits from a sub-customer back to your reseller account.
"""

from nextsms import NextSMS

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    response = sms.deduct_customer(
        email="customer@example.com",
        smscount=2000,
    )
    if response:
        d = response.data
        print(
            f"Deducted {d['Sms deducted']} SMS from {d['Customer']} | "
            f"Your balance: {d['Your sms balance']} | "
            f"Customer balance: {d['Customer sms balance']}"
        )
