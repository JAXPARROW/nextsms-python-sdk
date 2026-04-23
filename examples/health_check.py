"""
Example: health check — verify the API is reachable and credentials are valid.
"""

from nextsms import NextSMS

client = NextSMS(username="YOUR_USERNAME", password="YOUR_PASSWORD")

if client.is_healthy():
    print("NextSMS API is up and credentials are valid.")
else:
    print("NextSMS API is unreachable or credentials are wrong.")

client.close()
