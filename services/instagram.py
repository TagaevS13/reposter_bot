import logging
import time
from pathlib import Path
from typing import Any

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
        share_to_facebook: bool = True,
        global_lock_path: str = "C:/Users/ADMIN/.runtime/instagram-publish.lock",
        global_lock_timeout_seconds: int = 300,
    ) -> None:
        self.username = username
        self.password = password
        self.verification_code = verification_code
        self.session_path = Path(session_path)
        self.share_to_facebook = share_to_facebook
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

    def publish(self, file_path: str, media_type: str, caption: str, verification_code: str) -> str:
        with FileLock(
            self.global_lock_path,
            timeout_seconds=self.global_lock_timeout_seconds,
        ):
            self._login_for_publish(verification_code)
            if media_type == "photo":
                logger.info("Instagram photo upload started path=%s", file_path)
                media = self.client.photo_upload(
                    path=file_path,
                    caption=caption or "",
                    extra_data=self._feed_extra_data(),
                )
                logger.info("Instagram photo upload completed")
                return str(media.pk)
            logger.info("Instagram video upload started path=%s", file_path)
            media = self.client.video_upload(
                path=file_path,
                caption=caption or "",
                extra_data=self._feed_extra_data(),
            )
            logger.info("Instagram video upload completed")
            return str(media.pk)

    def share_feed_post_to_story(self, media_pk_or_id: str) -> str:
        media_id = self.client.media_id(media_pk_or_id)
        media_pk = self.client.media_pk(media_id)
        now_ts = int(time.time())
        payload = self.client.with_default_data(
            {
                "source_media_id": media_id,
                "audience": "default",
                "tray_session_id": self.client.generate_uuid(),
                "camera_session_id": self.client.generate_uuid(),
                "story_media_creation_date": now_ts,
                "client_shared_at": now_ts,
                "container_module": "feed_timeline",
            }
        )
        with FileLock(
            self.global_lock_path,
            timeout_seconds=self.global_lock_timeout_seconds,
        ):
            result = self.client.private_request(
                f"media/{media_pk}/share_to_story/",
                data=payload,
                with_signature=False,
            )
        return self._extract_story_pk(result)

    def _feed_extra_data(self) -> dict[str, str]:
        if self.share_to_facebook:
            return {"share_to_facebook": "1"}
        return {}

    def _extract_story_pk(self, result: dict[str, Any]) -> str:
        for key in ("story_media", "media"):
            node = result.get(key)
            if isinstance(node, dict):
                pk = node.get("pk")
                if pk:
                    return str(pk)
        raise RuntimeError(f"Unexpected share_to_story response: {result}")
