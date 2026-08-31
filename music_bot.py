import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
import glob
import uuid
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython import VideosSearch
from pytubefix import YouTube

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
        "🎧 **Добро пожаловать в Музыкальный Бот! (PoToken PRO)**\n\n"
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
        await status_msg.edit(f"❌ Ошибка при поиске:\n`{str(e)[:150]}`")

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
        title = video.get('title') or 'Неизвестно'
        duration = video.get('duration') or '?:??'
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
    status_msg = await callback_query.message.reply("⏳ *Подключение к серверам...*")
    await process_download(client, callback_query.from_user.id, vid_id, status_msg)

@app.on_callback_query(filters.regex(r"^dlall_"))
async def download_all(client, callback_query):
    uid = callback_query.from_user.id
    page = int(callback_query.data.split("_")[1])
    if uid not in user_searches: return await callback_query.answer("❌ Результаты устарели.", show_alert=True)
    
    start_idx = page * 10
    page_results = user_searches[uid]['results'][start_idx : start_idx+10]
    status_msg = await callback_query.message.reply(f"📥 *Начинаю пакетную загрузку...*")
    
    for i, video in enumerate(page_results):
        await status_msg.edit(f"⏳ *Загружаю трек {i+1} из {len(page_results)}...*\n🎵 {video.get('title')}")
        success = await process_download(client, uid, video['id'])
        if not success: 
            break
            
    await status_msg.edit("✅ **Загрузка завершена!**")

async def process_download(client, chat_id, vid_id, status_message=None):
    url = f"https://www.youtube.com/watch?v={vid_id}"
    uid_str = str(uuid.uuid4())[:8]
    base_name = f"track_{uid_str}"
    file_to_send = None
    
    loop = asyncio.get_event_loop()
    err_main = ""
    err_api = ""
    
    # 1-DVIGATEL: Pytubefix + PoToken (YouTube himoyasini aylanib o'tish)
    try:
        def download_sync():
            # 'ANDROID_MUSIC' mijozi va 'use_po_token=True' bizni bot emasligimizni isbotlaydi!
            yt = YouTube(url, client='ANDROID_MUSIC', use_po_token=True)
            audio = yt.streams.get_audio_only()
            if not audio:
                raise Exception("Audio stream topilmadi.")
            
            temp_file = f"{base_name}.m4a"
            audio.download(filename=temp_file)
            return temp_file
            
        file_to_send = await loop.run_in_executor(None, download_sync)
        if not os.path.exists(file_to_send): raise Exception("Fayl saqlanmadi.")
        
    except Exception as e:
        err_main = str(e)
        # 2-DVIGATEL: Yangi Maxfiy API'lar (Render'ni bloklamagan serverlar)
        try:
            if status_message: await status_message.edit("🔄 *Двигатель 1 заблокирован, использую Резервные API...*")
            
            def download_fallback():
                # API 1
                try:
                    resp = requests.get(f"https://api.ryzendesu.vip/api/downloader/ytmp3?url={url}", timeout=15)
                    dl_url = resp.json().get('url')
                    if dl_url:
                        audio_data = requests.get(dl_url, timeout=30)
                        fb_file = f"{base_name}.mp3"
                        with open(fb_file, 'wb') as f: f.write(audio_data.content)
                        return fb_file
                except: pass
                
                # API 2
                try:
                    resp = requests.get(f"https://api.siputzx.my.id/api/d/ytmp3?url={url}", timeout=15)
                    dl_url = resp.json().get('data', {}).get('dl')
                    if dl_url:
                        audio_data = requests.get(dl_url, timeout=30)
                        fb_file = f"{base_name}.mp3"
                        with open(fb_file, 'wb') as f: f.write(audio_data.content)
                        return fb_file
                except: pass
                
                raise Exception("Barcha zaxira API'lar ishlamadi.")
                
            file_to_send = await loop.run_in_executor(None, download_fallback)
            if not file_to_send: raise Exception("API faylni bermadi.")
            
        except Exception as e2:
            err_api = str(e2)
            if status_message: await status_message.edit(f"❌ **Барча усуллар чекланди!**\n\n**Xato 1:** `{err_main[:100]}...`\n**Xato 2:** `{err_api[:100]}...`\n\nYouTube IP manzilni bloklagan.")
            return False

    # Musiqani Telegramga jo'natish
    try:
        if status_message: await status_message.edit("⬆️ *Отправляю в Telegram...*")
        
        title = "Неизвестный трек"
        performer = "Неизвестный исполнитель"
        
        data_search = user_searches.get(chat_id)
        if data_search:
             for video in data_search['results']:
                  if video.get('id') == vid_id:
                       title = video.get('title') or title
                       performer = video.get('channel', {}).get('name', performer)
                       break
        
        await client.send_audio(
            chat_id=chat_id,
            audio=file_to_send,
            title=title,
            performer=performer,
            caption="🎧 Скачано через бота (PRO PoToken)"
        )
        if status_message: await status_message.delete()
        return True
    except Exception as send_err:
        if status_message: await status_message.edit("❌ Yuborishda xato yuz berdi.")
        return False
    finally:
        for file in glob.glob(f"{base_name}.*"):
            try: os.remove(file)
            except: pass

print("✅ Бот запущен (PoToken + Secret API Mode)!")
keep_alive()
app.run()