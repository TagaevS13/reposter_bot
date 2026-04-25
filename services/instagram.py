import logging
from pathlib import Path

from instagrapi import Client
from instagrapi.types import StoryMedia
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
        self._is_authenticated = False

    def _login_for_publish(self, verification_code: str) -> None:
        if self._is_authenticated:
            return
        code = (verification_code or self.verification_code or "").strip()
        if not code:
            raise RuntimeError("Instagram 2FA code is required for publishing.")

        # Create a fresh client once per process start. After successful login we
        # keep this authenticated session in memory and reuse it for next publishes.
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
        self._is_authenticated = True

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

    def share_feed_post_to_story(self, media_pk_or_id: str, background_path: str) -> str:
        """
        Re-share a feed post to stories using feed_media sticker flow.
        The direct /share_to_story endpoint is not available for all accounts.
        """
        media_pk = self.client.media_pk(str(media_pk_or_id))
        media_info = self.client.media_info_v1(media_pk)
        sticker = StoryMedia(
            media_pk=int(media_pk),
            user_id=int(media_info.user.pk),
        )
        with FileLock(
            self.global_lock_path,
            timeout_seconds=self.global_lock_timeout_seconds,
        ):
            story = self.client.photo_upload_to_story(
                path=background_path,
                medias=[sticker],
            )
        return str(story.pk)

    def _feed_extra_data(self) -> dict[str, str]:
        if self.share_to_facebook:
            return {"share_to_facebook": 1}
        return {}
