import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def settings():
    load_dotenv(ROOT / ".env")
    mode = os.getenv("APP_MODE", "local")
    secret = os.getenv("FLASK_SECRET_KEY")
    region = os.getenv("AWS_REGION")
    topic = os.getenv("SNS_TOPIC_ARN", "")
    if mode not in {"local", "aws"}:
        raise RuntimeError("APP_MODE must be local or aws.")
    if mode == "aws":
        parts = topic.split(":")
        if (len(secret or "") < 32 or not region or len(parts) != 6
                or parts[:1] != ["arn"] or parts[2:4] != ["sns", region]
                or not parts[4].isdigit() or not parts[5] or parts[5].endswith(".fifo")):
            raise RuntimeError("AWS mode requires a strong secret, AWS_REGION, and a same-region standard SNS topic ARN.")
        if os.getenv("FLASK_DEBUG") == "1":
            raise RuntimeError("Disable Flask debug mode for AWS deployment.")
    return {
        "APP_MODE": mode,
        "SECRET_KEY": secret or secrets.token_hex(32),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": os.getenv("COOKIE_SECURE") == "1",
        "MAX_CONTENT_LENGTH": 32 * 1024,
        "DATABASE": ROOT / "instance" / "moviemagic.sqlite3",
        "REGION": region,
        "USERS_TABLE": os.getenv("DYNAMODB_USERS_TABLE", "MovieMagic_Users"),
        "BOOKINGS_TABLE": os.getenv("DYNAMODB_BOOKINGS_TABLE", "MovieMagic_Bookings"),
        "TOPIC_ARN": topic,
        "PRIVATE_EMAIL": os.getenv("SNS_PRIVATE_EMAIL_ENABLED") == "1",
    }
