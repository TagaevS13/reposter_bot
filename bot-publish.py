from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
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
from runtime_lock import FileLock
from services.instagram import InstagramPublisher
from services.telegram_channel import publish_to_channel
from services.tiktok import TikTokCredentials, TikTokPublisher


def setup_logging() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "bot-publish.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


class PublishStates(StatesGroup):
    choosing_destination = State()
    choosing_text_mode = State()
    waiting_text = State()
    waiting_instagram_2fa = State()


@dataclass
class MediaPayload:
    file_id: str
    media_type: str
    extension: str


router = Router()
settings = load_settings()
logger = logging.getLogger("bot_publish")
instagram = InstagramPublisher(
    username=settings.instagram_username,
    password=settings.instagram_password,
    verification_code=settings.instagram_verification_code,
    session_path=settings.instagram_session_path,
    global_lock_path=settings.instagram_global_lock_file,
    global_lock_timeout_seconds=settings.instagram_global_lock_timeout_seconds,
)
tiktok = TikTokPublisher(
    TikTokCredentials(
        client_key=settings.tiktok_client_key,
        client_secret=settings.tiktok_client_secret,
        access_token=settings.tiktok_access_token,
        open_id=settings.tiktok_open_id,
    )
)
ALLOWED_USERS = set(settings.allowed_user_ids)
ALLOWED_USERNAMES = set(settings.allowed_usernames)


def _is_allowed_user(user_id: int | None, username: str | None) -> bool:
    if not ALLOWED_USERS and not ALLOWED_USERNAMES:
        return True
    if user_id is not None and user_id in ALLOWED_USERS:
        return True
    normalized_username = (username or "").strip().lower()
    if normalized_username.startswith("@"):
        normalized_username = normalized_username[1:]
    return bool(normalized_username and normalized_username in ALLOWED_USERNAMES)


async def _reject_if_not_allowed_message(message: Message, state: FSMContext | None = None) -> bool:
    user_id = message.from_user.id if message.from_user else None
    username = message.from_user.username if message.from_user else None
    if _is_allowed_user(user_id, username):
        return False
    if state is not None:
        await state.clear()
    await message.answer("Этот бот приватный. Доступ ограничен.")
    logger.warning("Rejected access for user_id=%s username=%s", user_id, username)
    return True


async def _reject_if_not_allowed_callback(callback: CallbackQuery, state: FSMContext | None = None) -> bool:
    user_id = callback.from_user.id if callback.from_user else None
    username = callback.from_user.username if callback.from_user else None
    if _is_allowed_user(user_id, username):
        return False
    if state is not None:
        await state.clear()
    await callback.answer("Доступ запрещен.", show_alert=True)
    if callback.message:
        await callback.message.answer("Этот бот приватный. Доступ ограничен.")
    logger.warning(
        "Rejected callback access for user_id=%s username=%s",
        user_id,
        username,
    )
    return True
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
    if await _reject_if_not_allowed_message(message, state):
        return
    logger.info("Received /start from user_id=%s", message.from_user.id if message.from_user else "unknown")
    await state.clear()
    await message.answer(
        "Отправь фото или видео, и я спрошу куда публиковать.\n"
        "По умолчанию публикация идет без текста."
    )


@router.message(F.photo | F.video | F.document | F.video_note)
async def media_handler(message: Message, state: FSMContext) -> None:
    if await _reject_if_not_allowed_message(message, state):
        return
    logger.info(
        "Received media message_id=%s from user_id=%s",
        message.message_id,
        message.from_user.id if message.from_user else "unknown",
    )
    if message.photo:
        media = MediaPayload(
            file_id=message.photo[-1].file_id,
            media_type="photo",
            extension="jpg",
        )
    elif message.video:
        media = MediaPayload(
            file_id=message.video.file_id,
            media_type="video",
            extension="mp4",
        )
    elif message.document and (message.document.mime_type or "").startswith("video/"):
        extension = "mp4"
        if message.document.file_name:
            extension = Path(message.document.file_name).suffix.lstrip(".") or "mp4"
        media = MediaPayload(
            file_id=message.document.file_id,
            media_type="video",
            extension=extension,
        )
    elif message.video_note:
        media = MediaPayload(
            file_id=message.video_note.file_id,
            media_type="video",
            extension="mp4",
        )
    else:
        await message.answer("Поддерживаются фото и видео.")
        return

    await state.set_data(
        {
            "file_id": media.file_id,
            "media_type": media.media_type,
            "extension": media.extension,
            "source_user_id": message.from_user.id if message.from_user else None,
            "destination": "",
            "caption": "",
            "instagram_2fa_code": "",
        }
    )
    await state.set_state(PublishStates.choosing_destination)
    await message.answer("Куда публикуем?", reply_markup=destination_keyboard())


@router.callback_query(PublishStates.choosing_destination, F.data.startswith("dst:"))
async def destination_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if await _reject_if_not_allowed_callback(callback, state):
        return
    destination = callback.data.split(":", maxsplit=1)[1]
    logger.info("Destination selected=%s by user_id=%s", destination, callback.from_user.id if callback.from_user else "unknown")
    await state.update_data(destination=destination)
    await state.set_state(PublishStates.choosing_text_mode)
    await callback.message.answer(
        "Добавить текст к публикации?", reply_markup=text_mode_keyboard()
    )
    await callback.answer()


@router.callback_query(PublishStates.choosing_text_mode, F.data == "txt:no")
async def no_text_selected(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if await _reject_if_not_allowed_callback(callback, state):
        return
    await state.update_data(caption="")
    await callback.answer("Публикую без текста.")
    await request_instagram_2fa_code(callback.message, state, bot)


@router.callback_query(PublishStates.choosing_text_mode, F.data == "txt:yes")
async def with_text_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if await _reject_if_not_allowed_callback(callback, state):
        return
    await state.set_state(PublishStates.waiting_text)
    await callback.message.answer("Отправь текст для публикации.")
    await callback.answer()


@router.message(PublishStates.waiting_text, F.text)
async def text_received(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _reject_if_not_allowed_message(message, state):
        return
    await state.update_data(caption=message.text.strip())
    await request_instagram_2fa_code(message, state, bot)


async def request_instagram_2fa_code(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("destination") == "ig_tg":
        await state.set_state(PublishStates.waiting_instagram_2fa)
        await message.answer("Отправь код 2FA Instagram (из приложения-аутентификатора).")
        return
    await publish_from_state(message, state, bot)


@router.message(PublishStates.waiting_instagram_2fa, F.text)
async def instagram_2fa_received(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _reject_if_not_allowed_message(message, state):
        return
    code = message.text.strip()
    if not code:
        await message.answer("Код 2FA пустой. Отправь действующий код Instagram.")
        return
    await state.update_data(instagram_2fa_code=code)
    await publish_from_state(message, state, bot)


async def publish_from_state(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    file_id = data["file_id"]
    media_type = data["media_type"]
    extension = data["extension"]
    destination = data["destination"]
    caption = data.get("caption", "")
    instagram_2fa_code = data.get("instagram_2fa_code", "")
    source_user_id = data.get("source_user_id")

    temp_file = None
    try:
        logger.info(
            "Start publish flow destination=%s media_type=%s extension=%s user_id=%s",
            destination,
            media_type,
            extension,
            source_user_id if source_user_id is not None else "unknown",
        )
        temp_file = await download_to_temp(bot, file_id, extension)
        logger.info("Media downloaded to temp path=%s", temp_file)

        if destination == "ig_tg":
            result_errors: list[str] = []
            tg_published = False
            ig_published = False

            if not settings.telegram_channel_id:
                result_errors.append("TELEGRAM_CHANNEL_ID не заполнен.")
            else:
                try:
                    await publish_to_channel(
                        bot=bot,
                        channel_id=settings.telegram_channel_id,
                        file_path=temp_file,
                        media_type=media_type,
                        caption=caption,
                    )
                    tg_published = True
                    logger.info("Published to Telegram channel channel_id=%s", settings.telegram_channel_id)
                except TelegramBadRequest as exc:
                    text = str(exc)
                    if "chat not found" in text.lower():
                        result_errors.append(
                            "Не найден TELEGRAM_CHANNEL_ID. Проверь ID канала и добавь бота в канал как администратора."
                        )
                    else:
                        result_errors.append(f"Ошибка отправки в TG: {exc}")
                    logger.exception("Telegram channel publish failed")
                except TelegramForbiddenError:
                    result_errors.append(
                        "Боту запрещено писать в канал. Добавь бота в канал и выдай право публикации сообщений."
                    )
                    logger.exception("Telegram channel publish forbidden")
                except Exception as exc:
                    result_errors.append(f"Ошибка отправки в TG: {exc}")
                    logger.exception("Telegram channel publish failed with unexpected error")

            if settings.instagram_username and settings.instagram_password:
                try:
                    logger.info("Publishing to Instagram account=%s", settings.instagram_username)
                    await asyncio.to_thread(
                        instagram.publish,
                        temp_file,
                        media_type,
                        caption,
                        instagram_2fa_code,
                    )
                    ig_published = True
                    logger.info("Published to Instagram successfully")
                except Exception as exc:
                    result_errors.append(f"Ошибка публикации в Instagram: {exc}")
                    logger.exception("Instagram publish failed")
            else:
                result_errors.append("Instagram не настроен: заполните логин и пароль в .env.")

            if ig_published and tg_published:
                await message.answer("Опубликовано: Instagram + TG канал.")
            elif ig_published and not tg_published:
                await message.answer(
                    "Опубликовано в Instagram. В TG-канал не отправлено: "
                    + " | ".join(result_errors)
                )
            elif tg_published and not ig_published:
                await message.answer(
                    "Отправлено в TG-канал. В Instagram не отправлено: "
                    + " | ".join(result_errors)
                )
            else:
                raise RuntimeError(" | ".join(result_errors) or "Публикация не выполнена.")
        elif destination == "tiktok":
            if media_type != "video":
                raise RuntimeError("TikTok поддерживает только видео.")
            logger.info("Publishing to TikTok")
            await tiktok.publish_video(video_path=temp_file, title=caption)
            logger.info("Published to TikTok successfully")
            await message.answer("Видео отправлено в TikTok на публикацию.")
        else:
            raise RuntimeError("Не выбрано направление публикации.")

        await state.clear()
    except Exception as error:
        logger.exception("Publish flow failed")
        details = str(error).strip() or repr(error)
        await message.answer(f"Ошибка публикации: {type(error).__name__}: {details}")
        await message.answer("Подробный лог сохранен в logs/bot-publish.log")
        await state.clear()
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


async def download_to_temp(bot: Bot, file_id: str, extension: str) -> str:
    tg_file = await bot.get_file(file_id)
    retries = max(1, settings.telegram_download_retries)
    timeout = max(30, settings.telegram_download_timeout_seconds)
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}")
        temp_path = temp.name
        temp.close()
        try:
            with open(temp_path, "wb") as target_file:
                await bot.download_file(
                    tg_file.file_path,
                    target_file,
                    timeout=timeout,
                    chunk_size=64 * 1024,
                )
            if attempt > 1:
                logger.info("Telegram download succeeded on retry %s/%s", attempt, retries)
            return temp_path
        except (asyncio.TimeoutError, TimeoutError) as exc:
            last_exc = exc
            logger.warning(
                "Telegram download timeout attempt %s/%s file_id=%s timeout=%ss",
                attempt,
                retries,
                file_id,
                timeout,
            )
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if attempt < retries:
                await asyncio.sleep(attempt * 2)
        except Exception as exc:
            last_exc = exc
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    assert last_exc is not None
    raise last_exc


async def main() -> None:
    setup_logging()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    with FileLock(
        settings.single_instance_lock_file,
        timeout_seconds=settings.single_instance_lock_timeout_seconds,
    ):
        asyncio.run(main())
