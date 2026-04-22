from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import load_settings
from services.instagram import InstagramPublisher
from services.telegram_channel import publish_to_channel
from services.tiktok import TikTokCredentials, TikTokPublisher


class PublishStates(StatesGroup):
    choosing_destination = State()
    choosing_text_mode = State()
    waiting_text = State()


@dataclass
class MediaPayload:
    file_id: str
    media_type: str
    extension: str


router = Router()
settings = load_settings()
instagram = InstagramPublisher(
    username=settings.instagram_username,
    password=settings.instagram_password,
)
tiktok = TikTokPublisher(
    TikTokCredentials(
        client_key=settings.tiktok_client_key,
        client_secret=settings.tiktok_client_secret,
        access_token=settings.tiktok_access_token,
        open_id=settings.tiktok_open_id,
    )
)


def destination_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1) Instagram + TG канал", callback_data="dst:ig_tg"
                )
            ],
            [InlineKeyboardButton(text="2) TikTok", callback_data="dst:tiktok")],
        ]
    )


def text_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без текста (по умолчанию)", callback_data="txt:no")],
            [InlineKeyboardButton(text="Публикация с текстом", callback_data="txt:yes")],
        ]
    )


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Отправь фото или видео, и я спрошу куда публиковать.\n"
        "По умолчанию публикация идет без текста."
    )


@router.message(F.photo | F.video)
async def media_handler(message: Message, state: FSMContext) -> None:
    if message.photo:
        media = MediaPayload(
            file_id=message.photo[-1].file_id,
            media_type="photo",
            extension="jpg",
        )
    else:
        media = MediaPayload(
            file_id=message.video.file_id,
            media_type="video",
            extension="mp4",
        )

    await state.set_data(
        {
            "file_id": media.file_id,
            "media_type": media.media_type,
            "extension": media.extension,
            "destination": "",
            "caption": "",
        }
    )
    await state.set_state(PublishStates.choosing_destination)
    await message.answer("Куда публикуем?", reply_markup=destination_keyboard())


@router.callback_query(PublishStates.choosing_destination, F.data.startswith("dst:"))
async def destination_selected(callback: CallbackQuery, state: FSMContext) -> None:
    destination = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(destination=destination)
    await state.set_state(PublishStates.choosing_text_mode)
    await callback.message.answer(
        "Добавить текст к публикации?", reply_markup=text_mode_keyboard()
    )
    await callback.answer()


@router.callback_query(PublishStates.choosing_text_mode, F.data == "txt:no")
async def no_text_selected(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(caption="")
    await callback.answer("Публикую без текста.")
    await publish_from_state(callback.message, state, bot)


@router.callback_query(PublishStates.choosing_text_mode, F.data == "txt:yes")
async def with_text_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PublishStates.waiting_text)
    await callback.message.answer("Отправь текст для публикации.")
    await callback.answer()


@router.message(PublishStates.waiting_text, F.text)
async def text_received(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.update_data(caption=message.text.strip())
    await publish_from_state(message, state, bot)


async def publish_from_state(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    file_id = data["file_id"]
    media_type = data["media_type"]
    extension = data["extension"]
    destination = data["destination"]
    caption = data.get("caption", "")

    temp_file = None
    try:
        temp_file = await download_to_temp(bot, file_id, extension)

        if destination == "ig_tg":
            if not settings.telegram_channel_id:
                raise RuntimeError("TELEGRAM_CHANNEL_ID не заполнен.")
            await publish_to_channel(
                bot=bot,
                channel_id=settings.telegram_channel_id,
                file_path=temp_file,
                media_type=media_type,
                caption=caption,
            )

            if settings.instagram_username and settings.instagram_password:
                await asyncio.to_thread(instagram.publish, temp_file, media_type, caption)
            else:
                raise RuntimeError("Instagram не настроен: заполните логин и пароль в .env.")

            await message.answer("Опубликовано: Instagram + TG канал.")
        elif destination == "tiktok":
            if media_type != "video":
                raise RuntimeError("TikTok поддерживает только видео.")
            await tiktok.publish_video(video_path=temp_file, title=caption)
            await message.answer("Видео отправлено в TikTok на публикацию.")
        else:
            raise RuntimeError("Не выбрано направление публикации.")

        await state.clear()
    except Exception as error:
        await message.answer(f"Ошибка публикации: {error}")
        await state.clear()
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


async def download_to_temp(bot: Bot, file_id: str, extension: str) -> str:
    tg_file = await bot.get_file(file_id)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}")
    temp.close()
    with open(temp.name, "wb") as target_file:
        await bot.download_file(tg_file.file_path, target_file)
    return temp.name


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
