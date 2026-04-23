"""
Example: recharge a sub-customer's SMS credit balance.
"""

from nextsms import NextSMS

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    response = sms.recharge_customer(
        email="customer@example.com",
        smscount=5000,
    )
    if response:
        d = response.data
        print(
            f"Recharged {d['Sms transferred']} SMS to {d['Customer']} | "
            f"Your remaining balance: {d['Your sms balance']}"
        )
