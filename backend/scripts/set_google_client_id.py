"""One-off: persist the Google OAuth Client ID into app_settings.auth.google
so GIS customer sign-in works AND the admin Auth Settings UI shows/edits it.
Run: python scripts/set_google_client_id.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from settings_service import SettingsService  # noqa: E402

CLIENT_ID = "310106754743-q9ojfr8h1m34ks6fuvn17pgf92i8pmaj.apps.googleusercontent.com"


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    svc = SettingsService(db)
    await svc.ensure_defaults()
    before = await svc.get_auth()
    print("BEFORE google.clientId:", (before.get("google") or {}).get("clientId"))
    await svc.patch_auth(
        {"google": {"clientId": CLIENT_ID}, "features": {"googleEnabled": True}},
        by="set_google_client_id_script",
    )
    after = await svc.get_auth()
    print("AFTER google.clientId:", (after.get("google") or {}).get("clientId"))
    print("googleEnabled:", (after.get("features") or {}).get("googleEnabled"))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
