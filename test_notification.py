import config
import logging
from fyers_client import get_fyers_model

logging.basicConfig(level=logging.INFO)
fyers = get_fyers_model()

print("\n--- Sending a Test Order to trigger a Fyers Push Notification ---")
print("Because your account has Rs 0.00, this single order will hit the Risk Management System,")
print("be formally recorded as REJECTED due to Insufficient Funds, and generate a Push Notification.\n")

# A standard single order uses Fyers' main order routing which generates an ID even if rejected
data = {
    "symbol": "NSE:NIFTY2630225300PE",
    "qty": 65,
    "type": 2,          # 2 = Market order
    "side": 1,          # 1 = Buy
    "productType": "MARGIN",
    "limitPrice": 0,
    "stopPrice": 0,
    "validity": "DAY",
    "disclosedQty": 0,
    "offlineOrder": False,
}

response = fyers.place_order(data=data)
print("Fyers API Response:")
print(response)

if response.get('s') == 'ok':
    print(f"\nOrder ID Generated: {response.get('id')}")
    print("Check your phone! You should see a Fyers app notification saying the order was rejected due to margin.")
else:
    print(f"\nAPI Error: {response}")
