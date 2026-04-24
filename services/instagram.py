import logging
from pathlib import Path

from instagrapi import Client
from runtime_lock import FileLock


logger = logging.getLogger("bot_publish.instagram")


class InstagramPublisher:
    def __init__(
        self,
        username: str,
        password: str,
        verification_code: str = "",
        session_path: str = ".instagram_session.json",
        global_lock_path: str = "C:/Users/ADMIN/.runtime/instagram-publish.lock",
        global_lock_timeout_seconds: int = 300,
    ) -> None:
        self.username = username
        self.password = password
        self.verification_code = verification_code
        self.session_path = Path(session_path)
        self.global_lock_path = global_lock_path
        self.global_lock_timeout_seconds = max(1, int(global_lock_timeout_seconds))
        self.client = Client()
        self.client.request_timeout = 30

    def _login_for_publish(self, verification_code: str) -> None:
        code = (verification_code or self.verification_code or "").strip()
        if not code:
            raise RuntimeError("Instagram 2FA code is required for publishing.")

        # Force explicit login each publish so 2FA code is requested every time.
        self.client = Client()
        self.client.request_timeout = 30
        logger.info("Instagram auth start for user=%s", self.username)
        try:
            self.client.login(
                self.username,
                self.password,
                verification_code=code,
            )
            logger.info("Instagram login with 2FA verification code succeeded")
        except TypeError:
            # Older instagrapi builds may not accept named verification arg.
            self.client.login(self.username, self.password)
            logger.info("Instagram login fallback without explicit 2FA arg succeeded")

        self.client.dump_settings(str(self.session_path))
        logger.info("Instagram session dumped to %s", self.session_path)

    def publish(self, file_path: str, media_type: str, caption: str, verification_code: str) -> None:
        with FileLock(
            self.global_lock_path,
            timeout_seconds=self.global_lock_timeout_seconds,
        ):
            self._login_for_publish(verification_code)
            if media_type == "photo":
                logger.info("Instagram photo upload started path=%s", file_path)
                self.client.photo_upload(path=file_path, caption=caption or "")
                logger.info("Instagram photo upload completed")
                return
            logger.info("Instagram video upload started path=%s", file_path)
            self.client.video_upload(path=file_path, caption=caption or "")
            logger.info("Instagram video upload completed")
