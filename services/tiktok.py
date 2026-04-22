from __future__ import annotations

import os
from dataclasses import dataclass

import aiohttp


@dataclass
class TikTokCredentials:
    client_key: str
    client_secret: str
    access_token: str
    open_id: str

    def is_complete(self) -> bool:
        return all(
            [
                self.client_key,
                self.client_secret,
                self.access_token,
                self.open_id,
            ]
        )


class TikTokPublisher:
    BASE_URL = "https://open.tiktokapis.com"

    def __init__(self, credentials: TikTokCredentials) -> None:
        self.credentials = credentials

    async def publish_video(self, video_path: str, title: str = "") -> None:
        if not self.credentials.is_complete():
            raise RuntimeError("TikTok credentials are not fully configured.")

        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        file_size = os.path.getsize(video_path)
        headers = {
            "Authorization": f"Bearer {self.credentials.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        init_payload = {
            "post_info": {
                "title": title[:2200],
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/v2/post/publish/video/init/",
                headers=headers,
                json=init_payload,
            ) as init_response:
                init_json = await init_response.json()
                if init_response.status >= 300:
                    raise RuntimeError(f"TikTok init failed: {init_json}")

            data = init_json.get("data", {})
            upload_url = data.get("upload_url")
            if not upload_url:
                raise RuntimeError(f"Upload URL is missing: {init_json}")

            with open(video_path, "rb") as source_file:
                binary = source_file.read()

            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            }
            async with session.put(
                upload_url,
                data=binary,
                headers=upload_headers,
            ) as upload_response:
                if upload_response.status >= 300:
                    body = await upload_response.text()
                    raise RuntimeError(f"TikTok upload failed: {body}")
