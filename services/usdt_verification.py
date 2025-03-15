import requests

TRONSCAN_API_URL = "https://api.tronscan.org/api/transaction-info"

def verify_usdt_payment(txn_hash, required_amount):
    """
    Verifies if a USDT transaction is valid and meets the required amount.
    """
    try:
        response = requests.get(f"{TRONSCAN_API_URL}?hash={txn_hash}")
        data = response.json()

        # Check if transaction exists
        if "contractData" not in data:
            return False, "Transaction not found."

        contract_data = data["contractData"]
        if contract_data.get("contract_address") != "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj":  # USDT TRC20 contract address
            return False, "Invalid USDT transaction."

        transaction_amount = int(contract_data.get("amount", 0)) / 1_000_000  # Convert from SUN to USDT
        if transaction_amount < required_amount:
            return False, f"Insufficient amount. Expected {required_amount} USDT, got {transaction_amount} USDT."

        return True, "Payment verified successfully."
    
    except Exception as e:
        return False, f"Verification error: {str(e)}"
