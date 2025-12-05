import asyncio
import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from yt_dlp import YoutubeDL
from collections import deque
import re

# =================== CONFIGURATION ===================
# Telegram Bot aur API details
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("vc_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

# Queue & current playing
queues = {}
current_playing = {}

# Flask server for uptime
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is online!"

def run_webserver():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# =================== YOUTUBE DOWNLOAD & FFMPEG CONFIG ===================

ydl_audio_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# Video download settings: Best quality jo audio aur video dono support karta ho
ydl_video_opts = {
    'format': 'best[height<=720]+bestaudio/best[ext=mp4]', 
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'postprocessors': [{ # MP4 container mein merge karne ke liye
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }],
}

# --- OPTIMIZED FFMPEG COMMAND FOR SMOOTH STREAMING ---
# File path will be passed as input
def get_optimized_ffmpeg_cmd(input_file_path):
    # Yeh settings video ko 480p par encode karengi, bahut tez aur smooth streaming ke liye
    return [
        'ffmpeg',
        '-i', input_file_path,  # Input downloaded file
        '-c:v', 'libx264',
        '-preset', 'ultrafast',  # Streaming Speed: Maximum
        '-tune', 'zerolatency',  # Latency: Zero (No delay)
        '-profile:v', 'baseline',
        '-b:v', '800k',           # Video Bitrate
        '-s', '854x480',          # Resolution: 480p
        '-r', '24',               # FPS
        '-pix_fmt', 'yuv420p',
        
        '-c:a', 'aac',
        '-b:a', '96k',
        '-ar', '44100',
        '-ac', '2',
        
        '-f', 'mp4', # Output format for PyTgCalls to handle video stream
        'pipe:1'     # Output ko PyTgCalls pipeline mein bhejta hai
    ]

# Rest of the utility functions
def extract_url(text):
    url_pattern = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    match = re.search(url_pattern, text)
    if match:
        return f"https://youtube.com/watch?v={match.group(6)}"
    return None

async def search_youtube(query):
    # ... (Search logic remains the same)
    ydl_opts = {
        'format': 'bestaudio',
        'noplaylist': True,
        'quiet': True,
        'extract_flat': False,
        'default_search': 'ytsearch1:',
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in info:
                video = info['entries'][0]
                return video['webpage_url'], video['title']
    except:
        pass
    return None, None

async def download_media(url, video=False):
    opts = ydl_video_opts if video else ydl_audio_opts
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'Unknown')
            return filename, title
    except:
        return None, None

# =================== MODIFIED PLAY LOGIC ===================
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
    
    if video_mode:
        # --- SMOOTH STREAMING VIA FFMPEG PIPELINE ---
        ffmpeg_command = get_optimized_ffmpeg_cmd(file_path)
        stream = AudioVideoPiped(
            ffmpeg_command,
            audio_parameters=HighQualityAudio(),
            video_parameters=MediumQualityVideo()
        )
        stream_type = StreamType().pulse_stream
    else:
        # --- Simple Audio Stream (No FFmpeg re-encoding needed) ---
        stream = AudioPiped(file_path, audio_parameters=HighQualityAudio())
        stream_type = StreamType().local_stream
    
    await pytgcalls.play(chat_id, stream, stream_type=stream_type)
    current_playing[chat_id] = {'title': title, 'file': file_path}

# =================== TELEGRAM COMMANDS ===================
# ... (cmd_play remains the same)

@app.on_message(filters.command("play"))
async def cmd_play(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("Usage: /play https://www.w3schools.com/sql/sql_or.asp")
        return
    
    query = message.text.split(None, 1)[1]
    url = extract_url(query)
    if not url:
        url, title = await search_youtube(query)
        if not url:
            await message.reply_text("❌ No results found!")
            return
    else:
        title = "Unknown"
    
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    # Audio mode: False
    queues[chat_id].append((url, False)) 
    if current_playing.get(chat_id) is None:
        await message.reply_text(f"▶️ Playing: {title}")
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Added to queue: {title}")

# ... (cmd_vplay remains the same, but now it uses optimized play_next)

@app.on_message(filters.command("vplay"))
async def cmd_vplay(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("Usage: /vplay https://www.w3schools.com/sql/sql_or.asp")
        return
    
    query = message.text.split(None, 1)[1]
    url = extract_url(query)
    if not url:
        url, title = await search_youtube(query)
        if not url:
            await message.reply_text("❌ No results found!")
            return
    else:
        title = "Unknown"
    
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    # Video mode: True (This triggers the FFmpeg optimization in play_next)
    queues[chat_id].append((url, True)) 
    if current_playing.get(chat_id) is None:
        await message.reply_text(f"🎥 Playing video (Optimized): {title}")
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Added to queue: {title}")

# =================== STREAM END ===================
@pytgcalls.on_stream_end()
async def on_stream_end(client, update):
    chat_id = update.chat_id
    if current_playing.get(chat_id) and current_playing[chat_id].get('file'):
        try:
            os.remove(current_playing[chat_id]['file'])
        except:
            pass
    await play_next(chat_id)

# =================== MAIN ===================
async def main():
    os.makedirs("downloads", exist_ok=True)
    threading.Thread(target=run_webserver, daemon=True).start()
    await pytgcalls.start()
    await app.start()
    print("✅ Bot is running!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
