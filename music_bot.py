import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython import VideosSearch
import yt_dlp

# 1. API VA TOKEN MA'LUMOTLARI
api_id = 34019495
api_hash = "3c89cf48606380405e9bd3adcb5dc165"
BOT_TOKEN = "514440846:AAHTjUfBDhpVmxDfY0AJSaQEE8sjJ_E6YZk" # Sizning tokeningiz

# 24/7 ishlashi uchun uyg'otkich
from keep_alive import keep_alive

app = Client("music_session", api_id=api_id, api_hash=api_hash, bot_token=BOT_TOKEN)

# Foydalanuvchilarning qidiruv natijalarini xotirada saqlash (Sahifalar uchun)
user_searches = {}

# ==========================================
# /START BUYRUG'I (Rus tilida)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    text = (
        "🎧 **Добро пожаловать в Музыкальный Бот!**\n\n"
        "Отправьте мне название песни или имя исполнителя, "
        "и я найду для вас музыку в высоком качестве (MP3)."
    )
    await message.reply(text)

# ==========================================
# MUSIQA QIDIRISH 
# ==========================================
@app.on_message(filters.text & filters.private)
async def search_music(client, message):
    query = message.text
    if query.startswith("/"): return 
    
    uid = message.from_user.id
    status_msg = await message.reply("🔍 *Ищу музыку...*")
    
    try:
        # 30 ta natija qidiramiz (sahifalarga bo'lish uchun)
        videos_search = VideosSearch(query, limit=30)
        results = videos_search.result()['result']
        
        if not results:
            await status_msg.edit("❌ Ничего не найдено. Попробуйте изменить запрос.")
            return
            
        user_searches[uid] = {'query': query, 'results': results}
        
        # 1-sahifani ko'rsatamiz
        await show_page(client, message, uid, 0, status_msg)
        
    except Exception as e:
        await status_msg.edit(f"❌ Ошибка при поиске: {e}")

# ==========================================
# SAHIFALARNI KO'RSATISH FUNKSIYASI (1-10)
# ==========================================
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
    
    for i, video in enumerate(page_results):
        title = video.get('title', 'Неизвестно')
        duration = video.get('duration', '?:??')
        channel = video.get('channel', {}).get('name', '')
        text += f"**{i+1}.** {title} ({duration})\n"
        if channel: text += f"👤 {channel}\n\n"
        else: text += "\n"
        
    # TUGMALAR YASASH
    buttons = []
    
    row1 = []
    for i in range(min(5, len(page_results))):
        row1.append(InlineKeyboardButton(str(i+1), callback_data=f"dl_{page_results[i]['id']}"))
    if row1: buttons.append(row1)
    
    row2 = []
    for i in range(5, len(page_results)):
        row2.append(InlineKeyboardButton(str(i+1), callback_data=f"dl_{page_results[i]['id']}"))
    if row2: buttons.append(row2)
    
    if len(page_results) > 1:
        buttons.append([InlineKeyboardButton(f"📥 Скачать все {len(page_results)}", callback_data=f"dlall_{page}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    if end_idx < len(results):
        nav_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}"))
    if nav_row: buttons.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if status_msg:
        await status_msg.edit(text, reply_markup=reply_markup, disable_web_page_preview=True)
    else:
        await message.edit(text, reply_markup=reply_markup, disable_web_page_preview=True)

# ==========================================
# SAHIFAGA O'TISH
# ==========================================
@app.on_callback_query(filters.regex(r"^page_"))
async def change_page(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    
    if uid not in user_searches:
        return await callback_query.answer("❌ Результаты устарели. Сделайте поиск заново.", show_alert=True)
        
    await show_page(client, callback_query.message, uid, page)

# ==========================================
# BITTA MUSIQANI YUKLASH
# ==========================================
@app.on_callback_query(filters.regex(r"^dl_"))
async def download_single(client, callback_query):
    vid_id = callback_query.data.split("_")[1]
    status_msg = await callback_query.message.reply("⏳ *Загрузка трека...*")
    await process_download(client, callback_query.from_user.id, vid_id, status_msg)
    await status_msg.delete()

# ==========================================
# BARCHASINI YUKLASH (10 ta)
# ==========================================
@app.on_callback_query(filters.regex(r"^dlall_"))
async def download_all(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    
    if uid not in user_searches:
        return await callback_query.answer("❌ Результаты устарели. Сделайте поиск заново.", show_alert=True)
        
    start_idx = page * 10
    page_results = user_searches[uid]['results'][start_idx : start_idx+10]
    
    status_msg = await callback_query.message.reply(f"📥 *Начинаю загрузку {len(page_results)} треков...*")
    
    for i, video in enumerate(page_results):
        await status_msg.edit(f"⏳ *Загружаю трек {i+1} из {len(page_results)}...*\n🎵 {video.get('title')}")
        await process_download(client, uid, video['id'])
        
    await status_msg.edit("✅ **Все треки успешно загружены!**")

# ==========================================
# MP3 YUKLASH LOGIKASI
# ==========================================
async def process_download(client, chat_id, vid_id, status_message=None):
    url = f"https://www.youtube.com/watch?v={vid_id}"
    file_name = f"{vid_id}.mp3"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{vid_id}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Неизвестный трек')
            performer = info.get('uploader', 'Неизвестный исполнитель')
        
        await client.send_audio(
            chat_id=chat_id,
            audio=file_name,
            title=title,
            performer=performer,
            caption="🎧 Скачано через бота"
        )
    except Exception as e:
        if status_message:
            pass 
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

print("✅ Музыкальный бот успешно запущен!")
keep_alive()
app.run()