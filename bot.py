import asyncio
import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped, AudioVideoPiped
from pytgcalls.types.stream import Stream, StreamAudioEnded
from yt_dlp import YoutubeDL
from collections import deque
import re

# =================== CONFIGURATION ===================
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("vc_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

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

# =================== YOUTUBE DOWNLOAD & CONFIG ===================
ydl_audio_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

ydl_video_opts = {
    'format': 'best[height<=720]+bestaudio/best[ext=mp4]', 
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

# =================== PLAY LOGIC ===================
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
            # Video stream with optimization
            stream = AudioVideoPiped(
                file_path,
                video_parameters={
                    'width': 854,
                    'height': 480,
                    'frame_rate': 24
                }
            )
        else:
            # Simple audio stream
            stream = AudioPiped(file_path)
        
        await pytgcalls.play(
            chat_id,
            stream
        )
        current_playing[chat_id] = {'title': title, 'file': file_path}
    except Exception as e:
        print(f"Error playing: {e}")
        await play_next(chat_id)

# =================== TELEGRAM COMMANDS ===================
@app.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply_text(
        f"👋 **Hello {message.from_user.mention}!**\n\n"
        "🎵 **I'm a Music & Video Player Bot!**\n\n"
        "**📋 Available Commands:**\n"
        "▶️ `/play` <song name/URL> - Play audio\n"
        "🎥 `/vplay` <video name/URL> - Play video\n"
        "⏭️ `/skip` - Skip current song\n"
        "⏹️ `/stop` - Stop playing & clear queue\n"
        "📜 `/queue` - Show current queue\n"
        "ℹ️ `/current` - Show current playing song\n\n"
        "**💡 Examples:**\n"
        "`/play Shape of You`\n"
        "`/vplay https://youtu.be/example`\n\n"
        "**Made with ❤️ | Powered by Pyrogram**"
    )

@app.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    await message.reply_text(
        "**📚 Bot Commands Help:**\n\n"
        "**Music Commands:**\n"
        "• `/play <name/URL>` - Play audio in voice chat\n"
        "• `/vplay <name/URL>` - Play video in voice chat\n"
        "• `/skip` - Skip to next song\n"
        "• `/stop` - Stop playback & clear queue\n\n"
        "**Queue Commands:**\n"
        "• `/queue` - View current queue\n"
        "• `/current` - See what's playing now\n\n"
        "**Other Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/help` - Show this message\n\n"
        "**🔥 Pro Tips:**\n"
        "✓ You can search by song name\n"
        "✓ Or paste direct YouTube URL\n"
        "✓ Bot auto-plays queue songs\n\n"
        "**Need support? Contact admin!**"
    )

@app.on_message(filters.command("play"))
async def cmd_play(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** `/play <song name or URL>`\n\n**Example:** `/play Shape of You`")
        return
    
    query = message.text.split(None, 1)[1]
    url = extract_url(query)
    
    msg = await message.reply_text("🔍 **Searching...**")
    
    if not url:
        url, title = await search_youtube(query)
        if not url:
            await msg.edit("❌ **No results found!**")
            return
    else:
        title = query
    
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    queues[chat_id].append((url, False))
    
    if current_playing.get(chat_id) is None:
        await msg.edit(f"▶️ **Now Playing:**\n{title}")
        await play_next(chat_id)
    else:
        await msg.edit(f"➕ **Added to queue:**\n{title}")

@app.on_message(filters.command("vplay"))
async def cmd_vplay(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** `/vplay <video name or URL>`\n\n**Example:** `/vplay Despacito`")
        return
    
    query = message.text.split(None, 1)[1]
    url = extract_url(query)
    
    msg = await message.reply_text("🔍 **Searching video...**")
    
    if not url:
        url, title = await search_youtube(query)
        if not url:
            await msg.edit("❌ **No results found!**")
            return
    else:
        title = query
    
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    queues[chat_id].append((url, True))
    
    if current_playing.get(chat_id) is None:
        await msg.edit(f"🎥 **Now Playing Video:**\n{title}")
        await play_next(chat_id)
    else:
        await msg.edit(f"➕ **Added to queue:**\n{title}")

@app.on_message(filters.command("skip"))
async def cmd_skip(client, message: Message):
    chat_id = message.chat.id
    if current_playing.get(chat_id):
        await pytgcalls.leave_call(chat_id)
        await message.reply_text("⏭️ **Skipped!**")
        await play_next(chat_id)
    else:
        await message.reply_text("❌ **Nothing is playing!**")

@app.on_message(filters.command("stop"))
async def cmd_stop(client, message: Message):
    chat_id = message.chat.id
    if current_playing.get(chat_id):
        await pytgcalls.leave_call(chat_id)
        if chat_id in queues:
            queues[chat_id] = deque()
        current_playing[chat_id] = None
        await message.reply_text("⏹️ **Stopped and cleared queue!**")
    else:
        await message.reply_text("❌ **Nothing is playing!**")

@app.on_message(filters.command("queue"))
async def cmd_queue(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        await message.reply_text("📜 **Queue is empty!**")
        return
    
    queue_text = "**📜 Current Queue:**\n\n"
    for i, (url, is_video) in enumerate(queues[chat_id], 1):
        mode = "🎥 Video" if is_video else "🎵 Audio"
        queue_text += f"{i}. {mode}\n"
    
    await message.reply_text(queue_text)

@app.on_message(filters.command("current"))
async def cmd_current(client, message: Message):
    chat_id = message.chat.id
    if current_playing.get(chat_id):
        title = current_playing[chat_id].get('title', 'Unknown')
        await message.reply_text(f"🎵 **Now Playing:**\n{title}")
    else:
        await message.reply_text("❌ **Nothing is playing right now!**")

# =================== STREAM END HANDLER ===================
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
