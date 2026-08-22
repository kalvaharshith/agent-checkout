import os
from pathlib import Path

from dotenv import load_dotenv
import razorpay

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

key_id = os.getenv("RAZORPAY_KEY_ID")
key_secret = os.getenv("RAZORPAY_KEY_SECRET")

if not key_id or not key_secret:
    raise RuntimeError(
        "Missing Razorpay credentials. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env"
    )

client = razorpay.Client(auth=(key_id, key_secret))

response = client.order.create(
    {
        "amount": 50000,
        "currency": "INR",
        "receipt": "test_receipt_001",
        "payment_capture": 1,
    }
)

print(response)
