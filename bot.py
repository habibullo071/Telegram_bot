import static_ffmpeg
# static_ffmpeg ni boshqa har qanday audio kutubxonadan oldin chaqiramiz
static_ffmpeg.add_paths()

import os
import asyncio
import uuid
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shazamio import Shazam
import yt_dlp
from aiohttp import web

TOKEN = os.environ.get("8973306223:AAFkZEqubADjcQH3Mr3Y013wKCEapUiXlQY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
shazam = Shazam()

search_cache = {}

def get_video_keyboard(bot_username: str, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Save", callback_data="save_video")],
            [InlineKeyboardButton(text="📥 Download full song (MP3)", callback_data=f"audio_{user_id}")],
            [InlineKeyboardButton(text="👉 Add to group ⤴️", url=f"https://t.me/{bot_username}?startgroup=true")]
        ]
    )

# Dinamik klaviatura: nechta natija bo'lsa, shuncha tugma chiqadi
def build_search_keyboard(search_id: str, count: int):
    keyboard = []
    row1 = []
    row2 = []

    for i in range(1, count + 1):
        btn = InlineKeyboardButton(text=str(i), callback_data=f"sel_{search_id}_{i}")
        if i <= 5:
            row1.append(btn)
        else:
            row2.append(btn)

    if row1:
        keyboard.append(row1)
    if row2:
        keyboard.append(row2)

    keyboard.append([InlineKeyboardButton(text="❌", callback_data="close_search")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        f"Salom, {html.escape(message.from_user.first_name)}! 👋\n\n"
        "Menga video, ovozli xabar, havola yoki qo'shiq nomini yuboring! 🎵"
    )

async def safe_remove(file_path: str):
    await asyncio.sleep(1)
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

async def recognize_audio(file_path: str):
    try:
        out = await shazam.recognize(file_path)
        track = out.get("track")
        if track:
            return f"{track.get('subtitle', '')} - {track.get('title', '')}"
    except Exception as e:
        print(f"Shazam error: {e}")
    return None

async def process_and_show_10_results(message: types.Message, query: str, wait_msg: types.Message = None):
    clean_query = html.escape(query)
    
    if not wait_msg:
        wait_msg = await message.answer(f"🔍 <b>\"{clean_query}\"</b> qidirilmoqda...", parse_mode="HTML")
    else:
        await wait_msg.edit_text(f"🔍 <b>\"{clean_query}\"</b> bo'yicha variatlar qidirilmoqda...", parse_mode="HTML")

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'socket_timeout': 15,
    }

    try:
        loop = asyncio.get_event_loop()
        
        def search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                first_attempt = f'ytsearch10:"{query}"'
                res = ydl.extract_info(first_attempt, download=False)
                entries = res.get('entries', []) if res else []
                
                if not entries or len(entries) < 3:
                    second_attempt = f'ytsearch10:{query} qo\'shiq'
                    res2 = ydl.extract_info(second_attempt, download=False)
                    entries = res2.get('entries', []) if res2 else []

                return entries

        entries = await loop.run_in_executor(None, search)

        if not entries:
            await wait_msg.edit_text("❌ Hech qanday qo'shiq topilmadi.")
            return

        text = f"🔍 <b>{clean_query}</b>\n\n"
        results_list = []

        count = 1
        for entry in entries:
            if not entry or count > 10:
                continue
            raw_title = entry.get("title", "Noma'lum")
            safe_title = html.escape(raw_title)
            duration = entry.get('duration')
            
            if duration:
                mins, secs = divmod(int(duration), 60)
                dur_str = f"{mins}:{secs:02d}"
            else:
                dur_str = ""

            text += f"{count}. {safe_title} <b>{dur_str}</b>\n"
            
            video_url = entry.get('url') or entry.get('webpage_url')
            if not video_url and entry.get('id'):
                video_url = f"https://www.youtube.com/watch?v={entry.get('id')}"

            results_list.append({
                'url': video_url,
                'title': raw_title
            })
            count += 1

        if not results_list:
            await wait_msg.edit_text("❌ Hech qanday qo'shiq topilmadi.")
            return

        search_id = str(uuid.uuid4())[:8]
        search_cache[search_id] = results_list

        # Topilgan natijalar soniga mos ravishda tugmalar shakllanadi
        await wait_msg.edit_text(
            text, 
            parse_mode="HTML", 
            reply_markup=build_search_keyboard(search_id, len(results_list))
        )

    except Exception as e:
        print(f"Natija qidirishda xato: {e}")
        await wait_msg.edit_text("⚠️ Qo'shiqlar ro'yxatini yuklashda xatolik yuz berdi.")

@dp.message(F.voice | F.audio | F.video | F.video_note)
async def handle_media(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    wait_msg = await message.answer("🔄 Qo'shiq aniqlanmoqda...")
    
    media = message.voice or message.audio or message.video or message.video_note
    file = await bot.get_file(media.file_id)
    temp_file = f"temp_{uuid.uuid4().hex}.mp4"
    
    await bot.download_file(file.file_path, temp_file)
    search_query = await recognize_audio(temp_file)
    await safe_remove(temp_file)

    if search_query:
        await process_and_show_10_results(message, search_query, wait_msg)
    else:
        await wait_msg.edit_text("❌ Afsuski, bu musiqani Shazam aniqlay olmadi.")

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
    wait_msg = await message.answer("🔄 ⚙️ <b>Media yuklanmoqda...</b>", parse_mode="HTML")
    
    url = message.text.strip()
    user_id = message.from_user.id
    video_file = f"video_{uuid.uuid4().hex}.mp4"

    ydl_opts = {
        'format': 'best',
        'outtmpl': video_file,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        if os.path.exists(video_file):
            search_query = await recognize_audio(video_file)
            if search_query:
                with open(f"query_{user_id}.txt", "w", encoding="utf-8") as f:
                    f.write(search_query)

            bot_info = await bot.get_me()
            caption_text = f"❤️ @{bot_info.username} downloaded via🚀 📥"
            keyboard = get_video_keyboard(bot_info.username, user_id)
            
            video = types.FSInputFile(video_file)
            await message.answer_video(video=video, caption=caption_text, reply_markup=keyboard)
            await wait_msg.delete()
        else:
            await wait_msg.edit_text("❌ Videoni yuklab bo'lmadi.")
    except Exception as e:
        print(f"Yuklashda xato: {e}")
        await wait_msg.edit_text("❌ Videoni yuklab bo'lmadi.")
    finally:
        await safe_remove(video_file)

@dp.message(F.text)
async def handle_text_search(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await process_and_show_10_results(message, message.text.strip())

async def download_by_url(message: types.Message, url: str, wait_msg: types.Message):
    unique_id = uuid.uuid4().hex
    output_template = f"music_{unique_id}.%(ext)s"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                mp3_filename = base + ".mp3"
                
                if os.path.exists(mp3_filename):
                    filename = mp3_filename
                
                return filename, info.get("title", "Music"), info.get("uploader", "Music Bot")

        downloaded_file, title, performer = await loop.run_in_executor(None, download)

        if downloaded_file and os.path.exists(downloaded_file):
            audio = types.FSInputFile(downloaded_file)
            await message.answer_audio(audio=audio, title=title, performer=performer)
            if wait_msg:
                await wait_msg.delete()
            await safe_remove(downloaded_file)
        else:
            if wait_msg:
                await wait_msg.edit_text("❌ Qo'shiq yuklanmadi.")
    except Exception as e:
        print(f"Download music error: {e}")
        if wait_msg:
            await wait_msg.edit_text("⚠️ Qo'shiqni yuklashda xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("sel_"))
async def handle_select_music(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    search_id = parts[1]
    index = int(parts[2]) - 1

    if search_id in search_cache and index < len(search_cache[search_id]):
        selected = search_cache[search_id][index]
        await callback.answer(f"📥 {selected['title']} yuklanmoqda...")
        
        clean_title = html.escape(selected['title'])
        wait_msg = await callback.message.answer(f"📥 <b>\"{clean_title}\"</b> yuklanmoqda...", parse_mode="HTML")
        await download_by_url(callback.message, selected['url'], wait_msg)
    else:
        await callback.answer("⚠️ Ushbu tugma eskirgan. Qayta qidiring.", show_alert=True)

@dp.callback_query(F.data == "close_search")
async def close_search(callback: types.CallbackQuery):
    await callback.message.delete()

@dp.callback_query(F.data == "save_video")
async def save_video(callback: types.CallbackQuery):
    await callback.answer("✅ Video Saqlanganlar bo'limiga yuborildi!", show_alert=True)
    if callback.message.video:
        await bot.send_video(chat_id=callback.from_user.id, video=callback.message.video.file_id)

@dp.callback_query(F.data.startswith("audio_"))
async def download_audio_button(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]
    query_file = f"query_{user_id}.txt"

    if os.path.exists(query_file):
        await callback.answer("📥 Musiqa ro'yxati tayyorlanmoqda...")
        with open(query_file, "r", encoding="utf-8") as f:
            search_query = f.read()
        
        await process_and_show_10_results(callback.message, search_query)
        await safe_remove(query_file)
    else:
        await callback.answer("⚠️ Ushbu videodagi musiqa aniqlanmadi.", show_alert=True)

async def handle_ping(request):
    return web.Response(text="Bot muvaffaqiyatli ishlayapti!")

async def main():
    # Render port xatosini to'g'rilash uchun soxta Web Server
    PORT = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())