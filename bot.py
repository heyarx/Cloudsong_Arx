import os
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

ydl_opts_video = {
    'format': 'bestvideo+bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'outtmpl': 'downloads/%(id)s.%(ext)s',
}

if YT_COOKIES_FILE:
    ydl_opts_audio['cookiefile'] = YT_COOKIES_FILE
    ydl_opts_video['cookiefile'] = YT_COOKIES_FILE

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

async def download_youtube(query: str, mode: str):
    opts = ydl_opts_audio if mode == "audio" else ydl_opts_video
    info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).extract_info(f"ytsearch:{query}", download=True)['entries'][0])
    filename = yt_dlp.YoutubeDL(opts).prepare_filename(info)

    # Ensure audio is .mp3
    if mode == "audio" and not filename.endswith(".mp3"):
        new_filename = f"{os.path.splitext(filename)[0]}.mp3"
        os.rename(filename, new_filename)
        filename = new_filename

    title = info.get('title', 'Song')
    return filename, title

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    greeting = get_greeting()
    await update.message.reply_text(
        f"{greeting}, {user.first_name}! 👋\n"
        "Choose what you want to receive:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Audio", callback_data="mode_audio")],
            [InlineKeyboardButton("🎥 Video", callback_data="mode_video")]
        ])
    )
    context.user_data['mode'] = None

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.split("_")[1]
    context.user_data['mode'] = mode
    await query.edit_message_text(f"✅ Mode set to: {mode.capitalize()}\nNow send me the song name!")

# ---------------- SEND SONG HANDLER ----------------
async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    mode = context.user_data.get('mode')
    if not mode:
        await update.message.reply_text("❌ Please select a mode first using /start!")
        return

    await update.message.reply_text(f"🎵 Downloading {mode} for: {query} ...")
    file_path = None
    try:
        file_path, title = await download_youtube(query, mode)
        if mode == "audio":
            await update.message.reply_audio(audio=InputFile(file_path, filename=f"{title}.mp3"), title=title)
        else:
            await update.message.reply_video(video=InputFile(file_path, filename=f"{title}.mp4"), caption=title)
        logging.info(f"✅ Sent {mode} for: {title}")
    except Exception as e:
        await update.message.reply_text("❌ Could not download the song. Try another name.")
        logging.error(f"yt-dlp download error: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(set_mode, pattern="mode_"))
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
