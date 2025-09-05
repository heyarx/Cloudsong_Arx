import os
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
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
def get_audio_opts(bitrate="192"):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': bitrate,
        }],
    }
    if YT_COOKIES_FILE:
        opts['cookiefile'] = YT_COOKIES_FILE
    return opts

def get_video_opts(resolution="720"):
    format_map = {
        "360": "bestvideo[height<=360]+bestaudio/best",
        "720": "bestvideo[height<=720]+bestaudio/best",
        "1080": "bestvideo[height<=1080]+bestaudio/best",
    }
    opts = {
        'format': format_map.get(resolution, "bestvideo+bestaudio/best"),
        'noplaylist': True,
        'quiet': True,
        'outtmpl': 'downloads/%(id)s.%(ext)s',
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

async def download_youtube(query: str, mode: str, quality: str = None, resolution: str = None):
    os.makedirs("downloads", exist_ok=True)
    if mode == "audio":
        opts = get_audio_opts(quality or "192")
    else:
        opts = get_video_opts(resolution or "720")

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
        f"{greeting}, {user.first_name}! 👋\nChoose what you want to receive:",
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

    if mode == "audio":
        await query.edit_message_text(
            "✅ Audio mode selected. Choose quality:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("128 kbps", callback_data="audio_128")],
                [InlineKeyboardButton("192 kbps", callback_data="audio_192")],
                [InlineKeyboardButton("320 kbps", callback_data="audio_320")]
            ])
        )
    else:
        await query.edit_message_text(
            "✅ Video mode selected. Choose resolution:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("360p", callback_data="video_360")],
                [InlineKeyboardButton("720p", callback_data="video_720")],
                [InlineKeyboardButton("1080p", callback_data="video_1080")]
            ])
        )

async def set_quality_resolution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    mode = data[0]
    value = data[1]

    context.user_data['mode'] = mode
    if mode == "audio":
        context.user_data['quality'] = value
        await query.edit_message_text(f"✅ Audio quality set to {value} kbps.\nNow send me the song name!")
    else:
        context.user_data['resolution'] = value
        await query.edit_message_text(f"✅ Video resolution set to {value}p.\nNow send me the song name!")

# ---------------- SEND SONG HANDLER ----------------
async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    mode = context.user_data.get('mode')
    if not mode:
        await update.message.reply_text("❌ Please select a mode first using /start!")
        return

    quality = context.user_data.get('quality')
    resolution = context.user_data.get('resolution')

    await update.message.chat.send_action(action=ChatAction.UPLOAD_AUDIO if mode=="audio" else ChatAction.UPLOAD_VIDEO)
    await update.message.reply_text(f"🎵 Downloading {mode} for: {query_text} ...")
    
    file_path = None
    try:
        file_path, title = await download_youtube(query_text, mode, quality, resolution)
        if mode == "audio":
            await update.message.reply_audio(audio=InputFile(file_path), title=title)
        else:
            await update.message.reply_video(video=InputFile(file_path), caption=title)

        logging.info(f"✅ Sent {mode} for: {title}")
        if file_path:
            asyncio.create_task(delete_file_later(file_path))

    except Exception as e:
        await update.message.reply_text(f"❌ Could not download the song. Try another name.\nError: {e}")
        logging.error(f"yt-dlp download error: {e}")

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(set_mode, pattern="mode_"))
bot_app.add_handler(CallbackQueryHandler(set_quality_resolution, pattern="audio_|video_"))
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
