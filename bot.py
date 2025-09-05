import os
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InputFile, BotCommand
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

# ---------------- DOWNLOAD FOLDER ----------------
DOWNLOAD_DIR = "/tmp/downloads"  # Safe path on Render
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- FASTAPI APP ----------------
app = FastAPI()
bot_app = Application.builder().token(BOT_TOKEN).build()

# ---------------- YT-DLP OPTIONS ----------------
def get_audio_opts():
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    if YT_COOKIES_FILE:
        opts['cookiefile'] = YT_COOKIES_FILE
    return opts

# ---------------- HELPERS ----------------
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
    opts = get_audio_opts()
    info_data = await asyncio.to_thread(
        lambda: yt_dlp.YoutubeDL(opts).extract_info(f"ytsearch1:{query}", download=True)
    )
    if not info_data.get('entries'):
        raise ValueError("No search results found")
    info = info_data['entries'][0]
    filename = yt_dlp.YoutubeDL(opts).prepare_filename(info)
    if not filename.endswith(".mp3"):
        filename = filename.rsplit(".", 1)[0] + ".mp3"
    title = info.get('title', 'Song')
    logging.info(f"✅ Downloaded file path: {os.path.abspath(filename)}")
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
        f"{greeting}, {user.first_name}! 👋\nSend me a song name and I will deliver it immediately."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Commands:\n"
        "/start - Start bot\n"
        "/help - Instructions\n"
        "/about - About bot\n"
        "/features - Bot features\n"
        "/donate - Support owner\n"
        "/support - Contact owner\n"
        "/privacy - Privacy policy\n"
        "/terms - Terms & conditions\n"
        "Simply send a song name to get the audio!"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"☁️ CloudSong Bot v1.0\nOwner: {OWNER_USERNAME}\nA Telegram bot to search and deliver music from YouTube."
    )

async def features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Features:\n"
        "- Instant song delivery\n"
        "- High-quality audio\n"
        "- Typing indicator while downloading\n"
        "- Auto cleanup after 72 hours"
    )

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💸 Support the bot development by donating here:\nhttps://www.paypal.me/yourlink"
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 Contact the owner: {OWNER_USERNAME}")

async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Privacy Policy:\nWe do not store your data. All songs are downloaded temporarily and deleted after 72 hours."
    )

async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Terms & Conditions:\nUse this bot responsibly. Do not share copyrighted content illegally."
    )

# ---------------- SEND SONG ----------------
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
        if os.path.exists(file_path):
            await update.message.chat.send_action(action=ChatAction.UPLOAD_AUDIO)
            await update.message.reply_audio(audio=InputFile(file_path), title=title)
            logging.info(f"✅ Sent audio for: {title}")
            asyncio.create_task(delete_file_later(file_path))
        else:
            await update.message.reply_text("❌ Error: Audio file not found after download.")

    except Exception as e:
        await update.message.reply_text(f"❌ Could not download the song. Try another name.\nError: {e}")
        logging.error(f"yt-dlp download error: {e}")

# ---------------- REGISTER HANDLERS ----------------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("about", about))
bot_app.add_handler(CommandHandler("features", features))
bot_app.add_handler(CommandHandler("donate", donate))
bot_app.add_handler(CommandHandler("support", support))
bot_app.add_handler(CommandHandler("privacy", privacy))
bot_app.add_handler(CommandHandler("terms", terms))

bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_song))

# ---------------- SET BOT COMMANDS ----------------
async def set_bot_commands():
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Instructions"),
        BotCommand("about", "About the bot"),
        BotCommand("features", "Bot features"),
        BotCommand("donate", "Support owner"),
        BotCommand("support", "Contact owner"),
        BotCommand("privacy", "Privacy policy"),
        BotCommand("terms", "Terms & conditions")
    ]
    await bot_app.bot.set_my_commands(commands)

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
    await set_bot_commands()

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
