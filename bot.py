import os
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InputFile
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
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
def get_audio_opts():
    opts = {
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
        opts['cookiefile'] = YT_COOKIES_FILE
    return opts

# ---------------- FASTAPI APP ----------------
app = FastAPI()
bot_app = Application.builder().token(BOT_TOKEN).build()

# ---------------- HELPER FUNCTIONS ----------------
def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good Morning"
    elif 12 <= hour < 17:
        return "Good Afternoon"
    elif 17 <= hour < 21:
        return "Good Evening"
    else:
        return "Hello"

async def download_youtube(query: str):
    os.makedirs("downloads", exist_ok=True)
    opts = get_audio_opts()
    info_data = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).extract_info(f"ytsearch3:{query}", download=True))
    if not info_data.get('entries'):
        raise ValueError("No search results found")
    info = info_data['entries'][0]
    filename = yt_dlp.YoutubeDL(opts).prepare_filename(info)
    title = info.get('title', 'Song')
    return filename, title

async def delete_file_later(file_path: str, delay: int = 259200):
    await asyncio.sleep(delay)
    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info(f"🗑️ Deleted file after 72 hours: {file_path}")

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    greeting = get_greeting()
    await update.message.reply_text(
        f"{greeting}, {user.first_name}! 👋\nSend me a song name and I will deliver it to you immediately."
    )

# ---------------- SEND SONG HANDLER ----------------
async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if not query_text:
        await update.message.reply_text("❌ Please provide a song name!")
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)
    await update.message.reply_text(f"🎵 Downloading song for: {query_text} ...")
    
    file_path = None
    try:
        file_path, title = await download_youtube(query_text)
        await update.message.reply_audio(audio=InputFile(file_path), title=title)
        logging.info(f"✅ Sent audio for: {title}")
        if file_path:
            asyncio.create_task(delete_file_later(file_path))

    except Exception as e:
        await update.message.reply_text(f"❌ Could not download the song. Try another name.\nError: {e}")
        logging.error(f"yt-dlp download error: {e}")

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_song))

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
