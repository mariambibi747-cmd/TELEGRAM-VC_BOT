import asyncio
import os
import threading
from collections import deque
import re

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from yt_dlp import YoutubeDL

# =================== CONFIGURATION ===================
# Render Environment Variables se ye value uthayega
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_hash_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_token_here")

app = Client("vc_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

queues = {}
current_playing = {}

# Flask server for uptime (Render Port handling)
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is online and running!"

def run_webserver():
    # Render PORT variable ko respect karega
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# =================== YOUTUBE DOWNLOAD CONFIG ===================
ydl_audio_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
}

ydl_video_opts = {
    'format': 'best[height<=480]', 
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

def extract_url(text):
    url_pattern = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    match = re.search(url_pattern, text)
    if match:
        return f"https://youtube.com/watch?v={match.group(6)}"
    return None

async def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio',
        'noplaylist': True,
        'quiet': True,
        'extract_flat': True, # Faster search
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in info and info['entries']:
                video = info['entries'][0]
                return video['url'], video['title']
    except Exception as e:
        print(f"Search Error: {e}")
    return None, None

async def download_media(url, video=False):
    opts = ydl_video_opts if video else ydl_audio_opts
    try:
        loop = asyncio.get_event_loop()
        # Run downloading in a separate thread to avoid blocking
        filename, title = await loop.run_in_executor(None, _download_worker, url, opts)
        return filename, title
    except Exception as e:
        print(f"Download error: {e}")
        return None, None

def _download_worker(url, opts):
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Audio extraction might change ext, ensuring we return correct path
        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        return filename, info.get('title', 'Unknown')

# =================== PLAY LOGIC (UPDATED FOR V3) ===================
async def play_next(chat_id):
    if chat_id not in queues or not queues[chat_id]:
        current_playing[chat_id] = None
        return
    
    next_item = queues[chat_id].popleft()
    url, video_mode = next_item
    
    file_path, title = await download_media(url, video=video_mode)
    if not file_path:
        await play_next(chat_id)
        return
    
    try:
        if video_mode:
            stream = AudioVideoPiped(
                file_path,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo()
            )
        else:
            stream = AudioPiped(
                file_path,
                audio_parameters=HighQualityAudio()
            )
        
        # V3 Syntax: join_group_call works for both joining and switching
        await pytgcalls.join_group_call(chat_id, stream)
        
        current_playing[chat_id] = {'title': title, 'file': file_path}
        print(f"✅ Playing: {title}")
    except Exception as e:
        print(f"❌ Error playing: {e}")
        # Cleanup if failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except: pass
        await play_next(chat_id)

# =================== COMMANDS ===================
@app.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nI am running on Render with Docker!")

@app.on_message(filters.command(["play", "vplay"]))
async def cmd_play(client, message: Message):
    chat_id = message.chat.id
    is_video = "vplay" in message.command[0]
    
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/play Song Name`")
        return
    
    query = message.text.split(None, 1)[1]
    msg = await message.reply_text("🔍 **Processing...**")
    
    url = extract_url(query)
    title = query
    
    if not url:
        url, title = await search_youtube(query)
        if not url:
            await msg.edit("❌ **Song not found.**")
            return

    if chat_id not in queues:
        queues[chat_id] = deque()
    
    queues[chat_id].append((url, is_video))
    
    if current_playing.get(chat_id) is None:
        await msg.edit(f"▶️ **Playing:** {title}")
        await play_next(chat_id)
    else:
        await msg.edit(f"➕ **Queued:** {title}")

@app.on_message(filters.command(["stop", "leave"]))
async def cmd_stop(client, message: Message):
    chat_id = message.chat.id
    try:
        await pytgcalls.leave_group_call(chat_id)
        current_playing[chat_id] = None
        queues[chat_id] = deque() # Clear queue
        await message.reply_text("⏹️ **Disconnected.**")
    except Exception as e:
        await message.reply_text("❌ Not connected.")

@app.on_message(filters.command("skip"))
async def cmd_skip(client, message: Message):
    chat_id = message.chat.id
    if current_playing.get(chat_id):
        # Current file delete karein
        file_path = current_playing[chat_id].get('file')
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        await message.reply_text("⏭️ **Skipped.**")
        await play_next(chat_id)
    else:
        await message.reply_text("❌ Nothing playing.")

# =================== HANDLERS ===================
@pytgcalls.on_stream_end()
async def on_stream_end(client, update: Update):
    chat_id = update.chat_id
    if current_playing.get(chat_id):
        file_path = current_playing[chat_id].get('file')
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    
    await play_next(chat_id)

async def main():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    # Webserver thread
    threading.Thread(target=run_webserver, daemon=True).start()
    
    print("🚀 Starting Bot...")
    await pytgcalls.start()
    await app.start()
    print("✅ Bot Deployed Successfully!")
    
    # Keep running
    await pytgcalls.idle() # idle() is better for v3

if __name__ == "__main__":
    asyncio.run(main())
                              
