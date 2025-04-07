# utils.py
import requests
from decimal import Decimal

def verify_usdt_payment(transaction_id, expected_amount):
    tron_scan_api = f"https://api.tronscan.org/api/transaction-info?hash={transaction_id}"

    try:
        response = requests.get(tron_scan_api)
        if response.status_code == 200:
            data = response.json()

            # Adjust this extraction according to the TronScan API response structure
            confirmed_amount = Decimal(data.get("amount", "0")) / Decimal("1000000")  # Convert from SUN to TRX
            if confirmed_amount >= expected_amount:
                return True
    except Exception as e:
        print(f"Error verifying payment: {e}")

    return False
