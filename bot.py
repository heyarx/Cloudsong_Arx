import os
import uuid
import requests
from fastapi import FastAPI, Request
from telegram import Update, InlineQueryResultAudio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
OWNER_USERNAME = "@hey_arnab02"
YT_COOKIES_FILE = os.environ.get("YT_COOKIES_FILE")  # Cookie support
# ----------------------------------------

# ---------------- YT-DLP OPTIONS ----------------
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'skip_download': True,
}
if YT_COOKIES_FILE:
    ydl_opts['cookiefile'] = YT_COOKIES_FILE

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to CloudSong Bot!\n\n"
        "Send a song name or use inline mode anywhere:\n"
        "`@YourBotUsername <song>`\n"
        "Type /help for instructions."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Instructions:\n"
        "- Send any song, album, artist, or movie name.\n"
        "- Use inline mode: `@YourBotUsername <song>`\n"
        "- Commands:\n"
        "  /about → Bot info\n"
        "  /support → Contact owner"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"☁️ CloudSong Bot v1.0\nOwner: {OWNER_USERNAME}\n"
        "A professional Telegram bot to search and deliver music from YouTube."
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💬 For support, contact: {OWNER_USERNAME}"
    )

# ---------------- YOUTUBE SEARCH ----------------
def search_youtube(query: str):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            return info['webpage_url'], info['title']
    except Exception as e:
        print("yt-dlp search error:", e)
        return None, None

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text(f"🔎 Searching for: {query} ...")

    url, title = search_youtube(query)
    if url and title:
        await update.message.reply_text(f"🎵 {title}\n{url}")
    else:
        await update.message.reply_text("❌ Could not find the song. Try another name.")

# ---------------- INLINE SEARCH ----------------
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    url, title = search_youtube(query)
    if url and title:
        results = [
            InlineQueryResultAudio(
                id=str(uuid.uuid4()),
                audio_url=url,
                title=title
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
    else:
        await update.inline_query.answer([], switch_pm_text="No results found", switch_pm_parameter="start")

# ---------------- FASTAPI APP ----------------
app = FastAPI()
bot_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("about", about))
bot_app.add_handler(CommandHandler("support", support))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
bot_app.add_handler(InlineQueryHandler(inline_search))

# Root route
@app.get("/")
async def root():
    return {"status": "CloudSong Bot is live 🚀"}

# Webhook route
@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        return {"ok": True}
    except Exception as e:
        print("❌ Error in webhook:", e)
        return {"ok": False, "error": str(e)}

# ---------------- SET WEBHOOK ----------------
def set_telegram_webhook():
    if WEBHOOK_URL:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("✅ Webhook set successfully!")
            else:
                print(f"⚠️ Webhook failed: {response.text}")
        except Exception as e:
            print(f"⚠️ Error setting webhook: {e}")
    else:
        print("⚠️ WEBHOOK_URL not set in environment variables!")

# ---------------- RUN ----------------
if __name__ == "__main__":
    import uvicorn
    set_telegram_webhook()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 CloudSong Bot is running on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
