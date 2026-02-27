import config
import requests
import json
import logging
from fyers_client import get_fyers_model

logging.basicConfig(level=logging.INFO)
fyers = get_fyers_model()
token = fyers.token

auth_header = f"{config.FYERS_APP_ID}:{token}"
headers = {
    "Authorization": auth_header,
    "Content-Type": "application/json"
}

payload = {
    "data": [
        {
            "symbol": "NSE:NIFTY2630225300PE",
            "qty": 75,
            "side": 1,
            "type": 2,
            "productType": "MARGIN",
            "limitPrice": 0.0,
            "stopLoss": 0.0
        },
        {
            "symbol": "NSE:NIFTY2630225350PE",
            "qty": 75,
            "side": -1,
            "type": 2,
            "productType": "MARGIN",
            "limitPrice": 0.0,
            "stopLoss": 0.0
        }
    ]
}

url1 = "https://api-t1.fyers.in/api/v3/span_margin"

try:
    print(f"Testing {url1}")
    r = requests.post(url1, headers=headers, json=payload)
    print(f"Status Code: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(f"Failed: {e}")
