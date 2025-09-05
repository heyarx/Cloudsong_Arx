import os
import uuid
import requests
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineQueryResultAudio, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp
import asyncio

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
ydl_opts_link = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'skip_download': True,
}
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
    ydl_opts_link['cookiefile'] = YT_COOKIES_FILE
    ydl_opts_audio['cookiefile'] = YT_COOKIES_FILE

# ---------------- FASTAPI APP ----------------
app = FastAPI()
bot_app = Application.builder().token(BOT_TOKEN).build()

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to CloudSong Bot!\n\n"
        "Commands:\n"
        "/link <song> → Get YouTube link\n"
        "/song <song> → Get actual audio\n"
        "Type /help for more instructions."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Instructions:\n"
        "- /link <song> → Send YouTube link\n"
        "- /song <song> → Send audio file\n"
        "- /about → Bot info\n"
        "- /support → Contact owner\n"
        "- Inline mode: `@YourBotUsername <song>`"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"☁️ CloudSong Bot v1.0\nOwner: {OWNER_USERNAME}\n"
        "A professional Telegram bot to search and deliver music from YouTube."
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 For support, contact: {OWNER_USERNAME}")

# ---------------- YOUTUBE SEARCH ----------------
def search_youtube(query: str):
    try:
        with yt_dlp.YoutubeDL(ydl_opts_link) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            return info['webpage_url'], info['title']
    except Exception as e:
        logging.error(f"yt-dlp search error: {e}")
        return None, None

# ---------------- LINK COMMAND ----------------
async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("❌ Please provide a song name: /link <song name>")
        return
    await update.message.reply_text(f"🔎 Searching link for: {query} ...")
    url, title = search_youtube(query)
    if url and title:
        await update.message.reply_text(f"🎵 {title}\n{url}")
    else:
        await update.message.reply_text("❌ Could not find the song. Try another name.")

# ---------------- SONG COMMAND ----------------
async def song_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("❌ Please provide a song name: /song <song name>")
        return
    await update.message.reply_text(f"🎵 Downloading: {query} ...")
    audio_file = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            audio_file = ydl.prepare_filename(info)
        await update.message.reply_audio(
            audio=InputFile(audio_file),
            title=info.get('title', 'Song')
        )
    except Exception as e:
        await update.message.reply_text("❌ Could not download the song. Try another name.")
        logging.error(f"yt-dlp download error: {e}")
    finally:
        if audio_file and os.path.exists(audio_file):
            os.remove(audio_file)

# ---------------- INLINE QUERY ----------------
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

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("about", about))
bot_app.add_handler(CommandHandler("support", support))
bot_app.add_handler(CommandHandler("link", link_command))
bot_app.add_handler(CommandHandler("song", song_command))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_command))
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
