# CloudSong Bot

A Telegram bot to search and play music from YouTube, with inline queries support.

## Features
- Search songs, albums, artists.
- Inline query support: `@YourBotUsername <song>`.
- YouTube cookies support to bypass age restrictions or login-only content.
- Commands: `/start`, `/help`, `/about`, `/support`.

## Deployment
1. Add your environment variables:
   - `BOT_TOKEN` → Your Telegram Bot Token
   - `WEBHOOK_URL` → Your Render App webhook URL (e.g., `https://cloudsong.onrender.com/webhook`)
   - `YT_COOKIES_FILE` → Optional, path to `cookies.txt` if needed.

2. Push code to Render.

3. Render automatically installs dependencies from `requirements.txt` and runs the bot using `Procfile`.

## YT-DLP Cookies
- Use cookies in **Netscape HTTP Cookie File format**.
- Set `YT_COOKIES_FILE` to the file name, e.g., `cookies.txt`.
