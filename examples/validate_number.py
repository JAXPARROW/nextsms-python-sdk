"""
Example: validate a Tanzanian phone number via the NextSMS API.
"""

from nextsms import NextSMS, NextSMSValidationError

with NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD") as sms:
    try:
        response = sms.validate_number("255712345678")
        if response:
            d = response.data
            status = "valid" if d["valid"] else "invalid"
            print(f"{d['phone_number']} is {status} — operator: {d.get('operator', 'unknown')}")
    except NextSMSValidationError as e:
        print(f"Local validation failed: {e}")
