"""Manual test: send a real verification email via Resend and check outbox.

Usage:
    python scripts/test_resend_send.py [recipient_email]
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from notifications import EmailChannel  # noqa: E402
from app.services.customer_email_templates import render_verification_email  # noqa: E402


async def main():
    recipient = sys.argv[1] if len(sys.argv) > 1 else "bibicarssite@gmail.com"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "test_database")]

    subject, html, text = render_verification_email("482913", name="Marina", ttl_minutes=10)
    ch = EmailChannel(db)
    print(f"Sending verification email to {recipient} ...")
    result = await ch.send(to=recipient, subject=subject, html=html, text=text, event="customer_email_verify")
    print("send() result:", result)

    # Read last outbox record for this recipient
    doc = await db.email_outbox.find_one({"to": recipient}, sort=[("created_at", -1)])
    if doc:
        print("outbox.status        =", doc.get("status"))
        print("outbox.provider      =", doc.get("provider"))
        print("outbox.provider_status =", doc.get("provider_status"))
        print("outbox.fallback_used =", doc.get("fallback_used"))
        print("outbox.fallback_from =", doc.get("fallback_from"))
        print("outbox.provider_error=", doc.get("provider_error"))
        print("outbox.provider_response=", str(doc.get("provider_response"))[:300])
    else:
        print("No outbox record found")


if __name__ == "__main__":
    asyncio.run(main())
