from aiogram import Bot
from aiogram.types import FSInputFile


async def publish_to_channel(
    bot: Bot,
    channel_id: str,
    file_path: str,
    media_type: str,
    caption: str,
) -> None:
    if media_type == "photo":
        await bot.send_photo(
            chat_id=channel_id,
            photo=FSInputFile(file_path),
            caption=caption or None,
        )
        return

    await bot.send_video(
        chat_id=channel_id,
        video=FSInputFile(file_path),
        caption=caption or None,
    )
