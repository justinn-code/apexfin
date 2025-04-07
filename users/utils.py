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

# utils.py
def get_client_ip(request):
    """
    Get the user's real IP address, considering proxies or load balancers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_geolocation(ip):
    """
    Get the geolocation info (country, city, region) for the given IP address.
    """
    access_key = '26cdc8ba0897b3f6e65bd107ee7b7ab0'  # Your ipstack API key
    url = f"http://api.ipstack.com/{ip}?access_key={access_key}"
    response = requests.get(url)
    data = response.json()

    # Return geolocation info as a dictionary
    return {
        'country': data.get('country_name'),
        'city': data.get('city'),
        'region': data.get('region_name'),
        'ip': ip  # Optionally store the IP as well for tracking purposes
    }