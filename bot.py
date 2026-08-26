import os
import asyncio
import static_ffmpeg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shazamio import Shazam
import yt_dlp

static_ffmpeg.add_paths()

TOKEN = "8973306223:AAGgh41H9qQ6NwPlGCYNAFT5-eu7FeBNNMg"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_video_keyboard(bot_username: str, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Save", callback_data="save_video")
            ],
            [
                InlineKeyboardButton(text="📥 Download a song", callback_data=f"audio_{user_id}")
            ],
            [
                InlineKeyboardButton(
                    text="👉 Add to group ⤴️", 
                    url=f"https://t.me/{bot_username}?startgroup=true"
                )
            ]
        ]
    )

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}! 👋\n\n"
        "Menga:\n"
        "1. **Qo'shiq nomi** yoki **ovozli xabar** yuboring — MP3 formatda topib beraman 🎵\n"
        "2. **Instagram / TikTok / YouTube havolasini** yuboring — mediani yuklab beraman 📥"
    )

# 1. OVOZLI XABAR ORQALI SHAZAM + MP3 YUKLASH
@dp.message(F.voice | F.audio)
async def recognize_and_send_mp3(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    wait_msg = await message.answer("🔄 Qo'shiq aniqlanmoqda...")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    temp_voice = f"temp_{message.from_user.id}.ogg"
    
    await bot.download_file(file.file_path, temp_voice)

    try:
        shazam = Shazam()
        out = await shazam.recognize(temp_voice)
        track = out.get("track")
        
        if track:
            title = track.get("title", "")
            subtitle = track.get("subtitle", "")
            search_query = f"{subtitle} - {title}"
            
            await wait_msg.edit_text("📥 *MP3 yuklanmoqda...*", parse_mode="Markdown")
            await download_and_send_music(message, search_query, wait_msg)
        else:
            await wait_msg.edit_text("❌ Afsuski, bu qo'shiq topilmadi.")
    except Exception as e:
        await wait_msg.edit_text("⚠️ Qo'shiqni aniqlashda xatolik yuz berdi.")
    finally:
        if os.path.exists(temp_voice):
            os.remove(temp_voice)

# 2. LINK ORQALI MEDIA YUKLASH
@dp.message(F.text.startswith("http"))
async def download_media(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
    wait_msg = await message.answer("🔄 ⚙️ *Media yuklanmoqda...*", parse_mode="Markdown")
    
    url = message.text
    user_id = message.from_user.id
    video_file = f"video_{user_id}.mp4"
    audio_file = f"audio_{user_id}.m4a"

    ydl_video_opts = {
        'format': 'b[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': video_file,
        'quiet': True,
        'no_warnings': True,
    }

    ydl_audio_opts = {
        'format': 'ba/ba*/bestaudio',
        'outtmpl': audio_file,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        loop = asyncio.get_event_loop()
        def process_download():
            with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
                ydl.download([url])
            try:
                with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                    ydl.download([url])
            except Exception:
                pass

        await loop.run_in_executor(None, process_download)

        bot_info = await bot.get_me()
        caption_text = f"❤️ @{bot_info.username} downloaded via🚀 📥"
        keyboard = get_video_keyboard(bot_info.username, user_id)
        
        video = types.FSInputFile(video_file)
        await message.answer_video(video=video, caption=caption_text, reply_markup=keyboard)
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text("❌ Videoni yuklab bo'lmadi. Linkni tekshirib qayta yuboring.")
    finally:
        if os.path.exists(video_file):
            os.remove(video_file)

# 3. MATN QILIB YOZILGAN QO'SHIQ NOMI BO'YICHA MP3 TOPISH
@dp.message(F.text)
async def search_music_by_text(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    wait_msg = await message.answer(f"🔍 *\"{message.text}\"* qidirilmoqda...", parse_mode="Markdown")
    await download_and_send_music(message, message.text, wait_msg)

# MP3 YUKLAB YUBORISH (Qo'shiq nomini to'g'ri qo'yish va tagidagi matnni o'chirish)
async def download_and_send_music(message: types.Message, query: str, wait_msg: types.Message):
    mp3_file = f"music_{message.from_user.id}.m4a"
    ydl_opts = {
        'format': 'ba/ba*/bestaudio',
        'outtmpl': mp3_file,
        'default_search': 'ytsearch1',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        loop = asyncio.get_event_loop()
        
        # Qo'shiq ma'lumotlarini olish
        def fetch_and_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                return info.get('title', query), info.get('uploader', 'Music Bot')

        track_title, track_performer = await loop.run_in_executor(None, fetch_and_download)

        if os.path.exists(mp3_file):
            audio = types.FSInputFile(mp3_file)
            await message.answer_audio(
                audio=audio, 
                title=track_title,
                performer=track_performer
            )
            await wait_msg.delete()
        else:
            await wait_msg.edit_text("❌ Qo'shiq topilmadi.")
    except Exception as e:
        await wait_msg.edit_text("⚠️ Qo'shiqni yuklashda xatolik yuz berdi.")
    finally:
        if os.path.exists(mp3_file):
            os.remove(mp3_file)

# 4. CALLBACK TUGMALAR
@dp.callback_query(F.data == "save_video")
async def save_video_callback(callback: types.CallbackQuery):
    await callback.answer("✅ Video Saqlanganlar bo'limiga yuborildi!", show_alert=True)
    if callback.message.video:
        await bot.send_video(chat_id=callback.from_user.id, video=callback.message.video.file_id)

@dp.callback_query(F.data.startswith("audio_"))
async def download_audio_callback(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]
    audio_file = f"audio_{user_id}.m4a"

    if os.path.exists(audio_file):
        await callback.answer("📥 Audio yuborilmoqda...")
        await bot.send_chat_action(chat_id=callback.from_user.id, action="upload_voice")
        audio = types.FSInputFile(audio_file)
        await bot.send_audio(chat_id=callback.from_user.id, audio=audio)
        os.remove(audio_file)
    else:
        await callback.answer("⚠️ Audio fayl topilmadi. Linkni qayta yuboring.", show_alert=True)

async def main():
    print("Kuy Navo bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())