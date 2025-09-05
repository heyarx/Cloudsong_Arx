import os
import uuid
import logging
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InputFile
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    filters
)
import yt_dlp
import requests

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
OWNER_USERNAME = "@hey_arnab02"
YT_COOKIES_FILE = os.environ.get("YT_COOKIES_FILE")  # Optional
PORT = int(os.environ.get("PORT", 10000))

# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- YT-DLP OPTIONS ----------------
ydl_opts_audio = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

if YT_COOKIES_FILE:
    ydl_opts_audio['cookiefile'] = YT_COOKIES_FILE

# ---------------- FASTAPI APP ----------------
app = FastAPI()
bot_app = Application.builder().token(BOT_TOKEN).build()

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to CloudSong Bot!\n\n"
        "Just send the song name and I'll deliver it directly!\n"
        "Type /help for more instructions."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Instructions:\n"
        "- Send any song name → Get audio file + YouTube link\n"
        "- /about → Bot info\n"
        "- /support → Contact owner"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"☁️ CloudSong Bot v1.0\nOwner: {OWNER_USERNAME}\n"
        "A professional Telegram bot to search and deliver music from YouTube."
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 For support, contact: {OWNER_USERNAME}")

# ---------------- YOUTUBE SEARCH & DOWNLOAD ----------------
async def auto_send_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return
    await update.message.reply_text(f"🎵 Downloading: {query} ...")
    audio_file = None
    try:
        # Download audio in thread to avoid blocking
        info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts_audio).extract_info(f"ytsearch:{query}", download=True)['entries'][0])
        audio_file = yt_dlp.YoutubeDL(ydl_opts_audio).prepare_filename(info)
        title = info.get('title', 'Song')
        url = info.get('webpage_url', '')

        # Send audio
        await update.message.reply_audio(audio=InputFile(audio_file), title=title)

        # Send YouTube link
        if url:
            await update.message.reply_text(f"📺 YouTube Link: {url}")

    except Exception as e:
        await update.message.reply_text("❌ Could not download the song. Try another name.")
        logging.error(f"yt-dlp download error: {e}")
    finally:
        if audio_file and os.path.exists(audio_file):
            os.remove(audio_file)

# ---------------- INLINE QUERY (optional, link only) ----------------
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return
    try:
        with yt_dlp.YoutubeDL({'format': 'bestaudio', 'noplaylist': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            url = info.get('webpage_url')
            title = info.get('title')
        if url and title:
            from telegram import InlineQueryResultArticle, InputTextMessageContent
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    input_message_content=InputTextMessageContent(f"{title}\n{url}")
                )
            ]
            await update.inline_query.answer(results, cache_time=0)
    except Exception as e:
        logging.error(f"Inline search error: {e}")
        await update.inline_query.answer([], switch_pm_text="No results found", switch_pm_parameter="start")

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("about", about))
bot_app.add_handler(CommandHandler("support", support))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_send_song))
bot_app.add_handler(InlineQueryHandler(inline_search))

# ---------------- FASTAPI ROUTES ----------------
@app.get("/")
async def root():
    return {"status": "CloudSong Bot is live 🚀"}

@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        return {"ok": True}
    except Exception as e:
        logging.error(f"❌ Error in webhook: {e}")
        return {"ok": False, "error": str(e)}

# ---------------- STARTUP / SHUTDOWN ----------------
@app.on_event("startup")
async def startup_event():
    await bot_app.initialize()
    await bot_app.start()
    logging.info("✅ Bot application started!")
    if WEBHOOK_URL:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}"
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                logging.info("✅ Webhook set successfully!")
            else:
                logging.warning(f"⚠️ Webhook failed: {resp.text}")
        except Exception as e:
            logging.warning(f"⚠️ Error setting webhook: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    await bot_app.stop()
    await bot_app.shutdown()
    logging.info("🛑 Bot application stopped!")

# ---------------- RUN ----------------
if __name__ == "__main__":
    import uvicorn
    logging.info(f"🚀 CloudSong Bot is running on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
