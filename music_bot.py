import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import imageio_ffmpeg 

# 1. API VA TOKEN MA'LUMOTLARI
api_id = 34019495
api_hash = "3c89cf48606380405e9bd3adcb5dc165"
BOT_TOKEN = "514440846:AAHTjUfBDhpVmxDfY0AJSaQEE8sjJ_E6YZk"

from keep_alive import keep_alive

app = Client("music_session", api_id=api_id, api_hash=api_hash, bot_token=BOT_TOKEN)

user_searches = {}

def format_time(seconds):
    if not seconds: return "?:??"
    try:
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h: return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except:
        return "?:??"

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    text = (
        "🎧 **Добро пожаловать в Музыкальный Бот!**\n\n"
        "Отправьте мне название песни или имя исполнителя."
    )
    await message.reply(text)

@app.on_message(filters.text & filters.private)
async def search_music(client, message):
    query = message.text
    if query.startswith("/"): return 
    
    uid = message.from_user.id
    status_msg = await message.reply("🔍 *Ищу музыку...*")
    
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(f"ytsearch30:{query}", download=False))
        
        results = list(info.get('entries', []))
        
        if not results:
            await status_msg.edit("❌ Ничего не найдено. Попробуйте изменить запрос.")
            return
            
        user_searches[uid] = {'query': query, 'results': results}
        await show_page(client, message, uid, 0, status_msg)
        
    except Exception as e:
        await status_msg.edit(f"❌ Ошибка при поиске: {e}")

async def show_page(client, message, uid, page, status_msg=None):
    data = user_searches.get(uid)
    if not data: return
    
    results = data['results']
    query = data['query']
    
    start_idx = page * 10
    end_idx = start_idx + 10
    page_results = results[start_idx:end_idx] 
    
    if not page_results: return
    
    text = f"🔎 Результаты по запросу: **{query}**\nСтраница: {page+1}\n\n"
    buttons = []
    row1 = []
    row2 = []
    
    for i, video in enumerate(page_results):
        title = video.get('title', 'Неизвестно')
        duration = format_time(video.get('duration'))
        channel = video.get('uploader', '')
        
        text += f"**{i+1}.** {title} ({duration})\n"
        if channel: text += f"👤 {channel}\n\n"
        else: text += "\n"
        
        vid_id = video.get('id')
        if i < 5: row1.append(InlineKeyboardButton(str(i+1), callback_data=f"dl_{vid_id}"))
        else: row2.append(InlineKeyboardButton(str(i+1), callback_data=f"dl_{vid_id}"))
            
    if row1: buttons.append(row1)
    if row2: buttons.append(row2)
    if len(page_results) > 1: buttons.append([InlineKeyboardButton(f"📥 Скачать все {len(page_results)}", callback_data=f"dlall_{page}")])
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    if end_idx < len(results): nav_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}"))
    if nav_row: buttons.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(buttons)
    if status_msg: await status_msg.edit(text, reply_markup=reply_markup, disable_web_page_preview=True)
    else: await message.edit(text, reply_markup=reply_markup, disable_web_page_preview=True)

@app.on_callback_query(filters.regex(r"^page_"))
async def change_page(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    if uid not in user_searches: return await callback_query.answer("❌ Результаты устарели.", show_alert=True)
    await show_page(client, callback_query.message, uid, page)

@app.on_callback_query(filters.regex(r"^dl_"))
async def download_single(client, callback_query):
    vid_id = callback_query.data.split("_")[1]
    status_msg = await callback_query.message.reply("⏳ *Загрузка трека...*")
    await process_download(client, callback_query.from_user.id, vid_id, status_msg)

@app.on_callback_query(filters.regex(r"^dlall_"))
async def download_all(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    if uid not in user_searches: return await callback_query.answer("❌ Результаты устарели.", show_alert=True)
    
    start_idx = page * 10
    page_results = user_searches[uid]['results'][start_idx : start_idx+10]
    status_msg = await callback_query.message.reply(f"📥 *Начинаю загрузку {len(page_results)} треков...*")
    
    for i, video in enumerate(page_results):
        await status_msg.edit(f"⏳ *Загружаю трек {i+1} из {len(page_results)}...*\n🎵 {video.get('title')}")
        success = await process_download(client, uid, video['id'])
        if not success: 
            await status_msg.reply(f"❌ Xatolik sababli {i+1}-trektda to'xtadi.")
            break
            
    await status_msg.edit("✅ **Загрузка завершена!**")

async def process_download(client, chat_id, vid_id, status_message=None):
    url = f"https://www.youtube.com/watch?v={vid_id}"
    
    uid_str = str(uuid.uuid4())[:8]
    base_name = f"track_{uid_str}"
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{base_name}.%(ext)s',
        'ffmpeg_location': ffmpeg_path, 
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
        # YOUTUBE'NI ALDASH UCHUN NIQOB (Android mijozi):
        'extractor_args': {'youtube': {'client': ['android']}}
    }
    
    try:
        loop = asyncio.get_event_loop()
        def download_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
                
        info = await loop.run_in_executor(None, download_sync)
        
        if status_message:
            await status_message.edit("⬆️ *Отправляю в Telegram...*")
            
        file_to_send = None
        if os.path.exists(f"{base_name}.mp3"):
            file_to_send = f"{base_name}.mp3"
        else:
            for ext in ['m4a', 'webm', 'opus']:
                if os.path.exists(f"{base_name}.{ext}"):
                    file_to_send = f"{base_name}.{ext}"
                    break
        
        if not file_to_send:
            raise Exception("Fayl konvertatsiya qilinmadi.")

        title = info.get('title', 'Неизвестный трек')
        performer = info.get('uploader', 'Неизвестный исполнитель')
        
        await client.send_audio(
            chat_id=chat_id,
            audio=file_to_send,
            title=title,
            performer=performer,
            caption="🎧 Скачано через бота"
        )
        if status_message:
            await status_message.delete()
        return True
    except Exception as e:
        error_msg = str(e)
        if status_message:
            await status_message.edit(f"❌ Ошибка:\n`{error_msg[:200]}`")
        else:
            await client.send_message(chat_id, f"❌ Ошибка:\n`{error_msg[:200]}`")
        return False
    finally:
        for ext in ['mp3', 'm4a', 'webm', 'opus']:
            f = f"{base_name}.{ext}"
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

print("✅ Музыкальный бот успешно запущен!")
keep_alive()
app.run()