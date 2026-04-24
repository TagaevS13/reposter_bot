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
   python bot-publish.py
   ```

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather
- `TELEGRAM_CHANNEL_ID` — username канала (`@channel_name`) или numeric chat id
- `INSTAGRAM_USERNAME` — логин Instagram аккаунта
- `INSTAGRAM_PASSWORD` — пароль Instagram аккаунта
- `INSTAGRAM_VERIFICATION_CODE` — код 2FA (если Instagram его запросил при первом входе)
- `INSTAGRAM_SESSION_PATH` — путь к файлу сессии Instagram (по умолчанию `.instagram_session.json`)
- `TIKTOK_CLIENT_KEY` — TikTok app client key
- `TIKTOK_CLIENT_SECRET` — TikTok app client secret
- `TIKTOK_ACCESS_TOKEN` — access token для Content Posting API
- `TIKTOK_OPEN_ID` — open_id пользователя TikTok
- `TIKTOK_REDIRECT_URI` — redirect URI для OAuth (по умолчанию `http://localhost:3000/callback`)
- `TIKTOK_OAUTH_SCOPE` — scopes для OAuth. Для публикации нужны `video.upload,video.publish`
- `ALLOWED_USER_IDS` — список Telegram user id через запятую для приватного режима (если пусто — бот публичный)
- `ALLOWED_USERNAMES` — список Telegram username через запятую (с `@` или без) для приватного режима
- `SINGLE_INSTANCE_LOCK_FILE` — lock-файл для защиты от двойного запуска одного бота
- `SINGLE_INSTANCE_LOCK_TIMEOUT_SECONDS` — время ожидания lock при старте
- `INSTAGRAM_GLOBAL_LOCK_FILE` — общий lock-файл Instagram между приватными сервисами
- `INSTAGRAM_GLOBAL_LOCK_TIMEOUT_SECONDS` — время ожидания глобального lock для IG-публикации

## Что нужно для TikTok

Чтобы включить публикацию в TikTok, предоставь:

1. `Client Key` приложения TikTok Developer
2. `Client Secret` приложения TikTok Developer
3. `Access Token` пользователя с правом публикации
4. `Open ID` пользователя
5. Подтверждение, что у приложения есть доступ к `Content Posting API` (publish/upload scope)

## TikTok OAuth (PKCE) автоматом

TikTok требует PKCE (`code_challenge` / `code_verifier`). Для этого в проект добавлен helper:

```bash
python tiktok_oauth_helper.py
```

Что делает скрипт:
1. Генерирует PKCE-пару.
2. Печатает готовую ссылку авторизации TikTok.
3. Ждет callback URL (или просто `code`) после подтверждения доступа.
4. Обменивает `code` на токен.
5. Автоматически записывает в `.env`:
   - `TIKTOK_ACCESS_TOKEN`
   - `TIKTOK_OPEN_ID`
   - `TIKTOK_REDIRECT_URI`

Перед запуском helper должны быть заполнены:
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- при необходимости `TIKTOK_REDIRECT_URI` (тот же URI должен быть в TikTok app settings)
- `TIKTOK_OAUTH_SCOPE` должен включать `video.upload,video.publish` для постинга

## Важно

- Для TikTok бот публикует только видео.
- Для Instagram используются логин/пароль аккаунта.
- При каждой публикации в Instagram бот запрашивает 2FA-код в чате Telegram.
- Бот должен быть админом в вашем Telegram-канале с правом отправки сообщений.
- Логи выполнения сохраняются в `logs/bot-publish.log`.
- Для приватного использования заполните `ALLOWED_USER_IDS`, чтобы бот принимал команды только от ваших аккаунтов.
