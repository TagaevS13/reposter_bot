from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    instagram_username: str
    instagram_password: str
    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_access_token: str
    tiktok_open_id: str


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID", ""),
        instagram_username=os.getenv("INSTAGRAM_USERNAME", ""),
        instagram_password=os.getenv("INSTAGRAM_PASSWORD", ""),
        tiktok_client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
        tiktok_client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
        tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        tiktok_open_id=os.getenv("TIKTOK_OPEN_ID", ""),
    )
