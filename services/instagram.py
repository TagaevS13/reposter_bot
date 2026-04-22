from instagrapi import Client


class InstagramPublisher:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.client = Client()
        self._is_authorized = False

    def _login_if_needed(self) -> None:
        if self._is_authorized:
            return
        self.client.login(self.username, self.password)
        self._is_authorized = True

    def publish(self, file_path: str, media_type: str, caption: str) -> None:
        self._login_if_needed()
        if media_type == "photo":
            self.client.photo_upload(path=file_path, caption=caption or "")
            return
        self.client.video_upload(path=file_path, caption=caption or "")
