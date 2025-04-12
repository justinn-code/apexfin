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



def validate_gift_card(gift_card_type, gift_card_code):
    """
    Function to validate a gift card code.
    This should either manually check the card in your database
    or integrate with an external API to verify the card's balance.

    :param gift_card_type: Type of the gift card (e.g., "Amazon", "Google Play")
    :param gift_card_code: The unique code from the gift card
    :return: True if valid, False otherwise
    """
    # Placeholder logic for validation. Implement your logic here.
    
    # Example: If the gift card is Amazon and the code is valid
    if gift_card_type == "amazon" and gift_card_code == "VALID_AMAZON_CODE":
        return True
    elif gift_card_type == "google_play" and gift_card_code == "VALID_GOOGLE_PLAY_CODE":
        return True
    # Implement further gift card validation logic (or an API call) here.
    
    return False
