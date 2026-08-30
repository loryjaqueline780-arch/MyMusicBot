import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
import uuid
import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython import VideosSearch

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
        "🎧 **Добро пожаловать в Музыкальный Бот (PRO Версия)!**\n\n"
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
        videos_search = VideosSearch(query, limit=30)
        results = videos_search.result()['result']
        
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
    row1, row2 = [], []
    
    for i, video in enumerate(page_results):
        title = video.get('title', 'Неизвестно')
        duration = video.get('duration', '?:??')
        channel = video.get('channel', {}).get('name', '')
        
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
    status_msg = await callback_query.message.reply("⏳ *Устанавливаю соединение...*")
    await process_download(client, callback_query.from_user.id, vid_id, status_msg)

@app.on_callback_query(filters.regex(r"^dlall_"))
async def download_all(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    if uid not in user_searches: return await callback_query.answer("❌ Результаты устарели.", show_alert=True)
    
    start_idx = page * 10
    page_results = user_searches[uid]['results'][start_idx : start_idx+10]
    status_msg = await callback_query.message.reply(f"📥 *Начинаю пакетную загрузку {len(page_results)} треков...*")
    
    for i, video in enumerate(page_results):
        await status_msg.edit(f"⏳ *Загружаю трек {i+1} из {len(page_results)}...*\n🎵 {video.get('title')}")
        success = await process_download(client, uid, video['id'])
        if not success: 
            break
            
    await status_msg.edit("✅ **Пакетная загрузка успешно завершена!**")

# ==========================================
# PRO YECHIM: 3 TA ZAXIRA API (Fallback Tizimi)
# ==========================================
async def get_audio_url(youtube_url):
    apis = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json",
        "https://cobalt.qewertyy.dev/api/json"
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    data = {"url": youtube_url, "isAudioOnly": True, "aFormat": "mp3"}
    
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        for api in apis:
            try:
                response = await http_client.post(api, json=data, headers=headers)
                if response.status_code == 200:
                    url = response.json().get("url")
                    if url: return url
            except Exception:
                continue # Agar bitta server qotib qolgan bo'lsa, ikkinchisiga o'tadi
    return None

async def process_download(client, chat_id, vid_id, status_message=None):
    youtube_url = f"https://www.youtube.com/watch?v={vid_id}"
    file_name = f"track_{uuid.uuid4().hex[:8]}.mp3"
    
    try:
        # 1-Bosqich: Xavfsiz URL olish (Blokirovkani aylanib o'tish)
        audio_url = await get_audio_url(youtube_url)
        if not audio_url:
            raise Exception("Все резервные серверы заняты. Попробуйте через минуту.")

        if status_message: await status_message.edit("⬇️ *Скачиваю аудиофайл (MP3)...*")
        
        # 2-Bosqich: Tezkor (Asinxron) yuklash
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.get(audio_url)
            if response.status_code != 200:
                raise Exception("Ошибка при загрузке аудиофайла.")
                
            with open(file_name, 'wb') as f:
                f.write(response.content)

        if status_message: await status_message.edit("⬆️ *Отправляю в Telegram...*")
        
        # 3-Bosqich: Ma'lumotlarni yig'ish va jo'natish
        title = "Неизвестный трек"
        performer = "Неизвестный исполнитель"
        
        data_search = user_searches.get(chat_id)
        if data_search:
             for video in data_search['results']:
                  if video.get('id') == vid_id:
                       title = video.get('title', title)
                       performer = video.get('channel', {}).get('name', performer)
                       break
        
        await client.send_audio(
            chat_id=chat_id,
            audio=file_name,
            title=title,
            performer=performer,
            caption="🎧 Скачано через бота"
        )
        if status_message: await status_message.delete()
        return True
        
    except Exception as e:
        error_msg = str(e)
        if status_message: await status_message.edit(f"❌ Ошибка:\n`{error_msg}`")
        return False
    finally:
        if os.path.exists(file_name):
            try: os.remove(file_name)
            except: pass

print("✅ Бот успешно запущен (API Gateway PRO Mode)!")
keep_alive()
app.run()