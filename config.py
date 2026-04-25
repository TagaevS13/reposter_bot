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
    instagram_verification_code: str
    instagram_session_path: str
    instagram_share_to_facebook: bool
    instagram_fb_destination_type: str
    instagram_fb_destination_id: str
    instagram_fb_access_token: str
    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_access_token: str
    tiktok_open_id: str
    tiktok_redirect_uri: str
    tiktok_oauth_scope: str
    allowed_user_ids: list[int]
    allowed_usernames: list[str]
    single_instance_lock_file: str
    single_instance_lock_timeout_seconds: int
    instagram_global_lock_file: str
    instagram_global_lock_timeout_seconds: int
    telegram_download_timeout_seconds: int
    telegram_download_retries: int


def _parse_allowed_user_ids(raw: str) -> list[int]:
    result: list[int] = []
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            result.append(int(value))
        except ValueError:
            continue
    return result


def _parse_allowed_usernames(raw: str) -> list[str]:
    result: list[str] = []
    for token in raw.split(","):
        value = token.strip().lower()
        if not value:
            continue
        if value.startswith("@"):
            value = value[1:]
        if value:
            result.append(value)
    return result


def _as_bool(raw: str | None, default: bool = False) -> bool:
    value = (raw or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID", ""),
        instagram_username=os.getenv("INSTAGRAM_USERNAME", ""),
        instagram_password=os.getenv("INSTAGRAM_PASSWORD", ""),
        instagram_verification_code=os.getenv("INSTAGRAM_VERIFICATION_CODE", ""),
        instagram_session_path=os.getenv("INSTAGRAM_SESSION_PATH", ".instagram_session.json"),
        instagram_share_to_facebook=_as_bool(
            os.getenv("INSTAGRAM_SHARE_TO_FACEBOOK"),
            True,
        ),
        instagram_fb_destination_type=os.getenv(
            "INSTAGRAM_FB_DESTINATION_TYPE",
            "",
        ).strip(),
        instagram_fb_destination_id=os.getenv(
            "INSTAGRAM_FB_DESTINATION_ID",
            "",
        ).strip(),
        instagram_fb_access_token=os.getenv(
            "INSTAGRAM_FB_ACCESS_TOKEN",
            "",
        ).strip(),
        tiktok_client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
        tiktok_client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
        tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        tiktok_open_id=os.getenv("TIKTOK_OPEN_ID", ""),
        tiktok_redirect_uri=os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:3000/callback"),
        tiktok_oauth_scope=os.getenv(
            "TIKTOK_OAUTH_SCOPE",
            "user.info.profile,user.info.stats,video.list,video.upload,video.publish",
        ),
        allowed_user_ids=_parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS", "")),
        allowed_usernames=_parse_allowed_usernames(
            os.getenv("ALLOWED_USERNAMES", "")
        ),
        single_instance_lock_file=os.getenv(
            "SINGLE_INSTANCE_LOCK_FILE",
            ".runtime/repost-bot.lock",
        ),
        single_instance_lock_timeout_seconds=int(
            os.getenv("SINGLE_INSTANCE_LOCK_TIMEOUT_SECONDS", "1")
        ),
        instagram_global_lock_file=os.getenv(
            "INSTAGRAM_GLOBAL_LOCK_FILE",
            "C:/Users/ADMIN/.runtime/instagram-publish.lock",
        ),
        instagram_global_lock_timeout_seconds=int(
            os.getenv("INSTAGRAM_GLOBAL_LOCK_TIMEOUT_SECONDS", "300")
        ),
        telegram_download_timeout_seconds=int(
            os.getenv("TELEGRAM_DOWNLOAD_TIMEOUT_SECONDS", "300")
        ),
        telegram_download_retries=int(
            os.getenv("TELEGRAM_DOWNLOAD_RETRIES", "3")
        ),
    )
