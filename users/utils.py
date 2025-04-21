import os
import requests
from decimal import Decimal
from .models import GiftCard

def check_usdt_payment(user, expected_amount, transaction_id):
    """
    Strictly verifies USDT (TRC20) payment using TronScan API.
    Checks:
      - Transaction is confirmed
      - Token is USDT
      - Correct recipient address
      - Amount is enough
    """
    tron_api = f"https://apilist.tronscanapi.com/api/transaction-info?hash={transaction_id}"

    YOUR_RECEIVING_WALLET = TK9MzgkdryfdVJy6UfHeU6mv1yhESnbKYT

    try:
        response = requests.get(tron_api)
        response.raise_for_status()
        data = response.json()

        if not data.get("confirmed", False):
            print("[USDT] Transaction not yet confirmed.")
            return False

        contract_data = data.get("contractData", {})
        amount = Decimal(data.get("amount", 0)) / Decimal("1000000")
        recipient = contract_data.get("to_address")
        token_info = data.get("tokenInfo", {})
        token_name = token_info.get("tokenName", "")

        if token_name == "USDT" and recipient == YOUR_RECEIVING_WALLET and amount >= expected_amount:
            return True
        else:
            print(f"[USDT] Invalid: token={token_name}, recipient={recipient}, amount={amount}")
            return False

    except Exception as e:
        print(f"[USDT] Error verifying payment: {e}")
        return False



def check_gift_card_payment(user, expected_amount, gift_card_code):
    try:
        gift_card = GiftCard.objects.get(code=gift_card_code, is_used=False)

        if Decimal(gift_card.value) >= expected_amount:
            return True
        else:
            print(f"[Gift Card] Card value too low: {gift_card.value} < {expected_amount}")
            return False
    except GiftCard.DoesNotExist:
        print("[Gift Card] Invalid or already used code.")
        return False


def save_uploaded_file(uploaded_file, folder="tmp_uploads"):
    """
    Saves the uploaded file to a temporary folder (safe for Fly.io).
    Returns the saved file path or None on error.
    """
    try:
        os.makedirs(f"/tmp/{folder}", exist_ok=True)
        file_path = os.path.join("/tmp", folder, uploaded_file.name)

        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        print(f"[File Upload] Saved to {file_path}")
        return file_path

    except Exception as e:
        print(f"[File Upload] Error saving file: {e}")
        return None
