# Telegram Media Publisher Bot

Бот принимает фото/видео в Telegram и спрашивает:
1. Куда публиковать:
   - `Instagram + Telegram канал`
   - `TikTok`
2. Нужен ли текст:
   - `Без текста (по умолчанию)`
   - `Публикация с текстом`

## Быстрый старт

1. Установи Python 3.11+.
2. Установи зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Скопируй `.env.example` в `.env` и заполни значения.
4. Запусти:
   ```bash
   python bot.py
   ```

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather
- `TELEGRAM_CHANNEL_ID` — username канала (`@channel_name`) или numeric chat id
- `INSTAGRAM_USERNAME` — логин Instagram аккаунта
- `INSTAGRAM_PASSWORD` — пароль Instagram аккаунта
- `TIKTOK_CLIENT_KEY` — TikTok app client key
- `TIKTOK_CLIENT_SECRET` — TikTok app client secret
- `TIKTOK_ACCESS_TOKEN` — access token для Content Posting API
- `TIKTOK_OPEN_ID` — open_id пользователя TikTok

## Что нужно для TikTok

Чтобы включить публикацию в TikTok, предоставь:

1. `Client Key` приложения TikTok Developer
2. `Client Secret` приложения TikTok Developer
3. `Access Token` пользователя с правом публикации
4. `Open ID` пользователя
5. Подтверждение, что у приложения есть доступ к `Content Posting API` (publish/upload scope)

## Важно

- Для TikTok бот публикует только видео.
- Для Instagram используются логин/пароль аккаунта.
- Бот должен быть админом в вашем Telegram-канале с правом отправки сообщений.
