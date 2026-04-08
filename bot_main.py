import os
import logging
import asyncio
import speech_recognition as sr
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardButton, InlineKeyboardMarkup, 
    BufferedInputFile
)
from pydub import AudioSegment

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
recognizer = sr.Recognizer()

# --- KEYBOARDS (MENU BAR) ---
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 ប្តូរភាសា (Language)"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
            [KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )
    return keyboard

# --- SRT HELPER ---
def format_timestamp(milliseconds: int):
    td = timedelta(milliseconds=milliseconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

# --- HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេង!**\n\n"
        "• បំប្លែងសំឡេងទៅជាអត្ថបទ (Text)\n"
        "• បង្កើតឯកសារ SRT Subtitle\n"
        "• គាំទ្រភាសាខ្មែរ 🇰🇭 (Google AI)"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("🤖 **Bot Version 4.0**\nEngine: SpeechRecognition & Pydub\nDeveloped by: THEARA Rupp", parse_mode="Markdown")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"ទាក់ទងមកកាន់៖ {ADMIN_URL}")

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    msg = await message.answer("⏳ កំពុងស្ដាប់ និងបំប្លែង... សូមរង់ចាំ")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    
    await bot.download_file(file.file_path, ogg_path)

    try:
        # បំប្លែង File ទៅជា WAV សម្រាប់ SpeechRecognition
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            # ប្រើ Google Recognition ជាមួយភាសាខ្មែរ តាមសំណូមពរ
            text = recognizer.recognize_google(audio_data, language="km-KH")

        # ១. ផ្ញើអត្ថបទធម្មតា
        await message.answer(f"📝 **លទ្ធផលអត្ថបទ៖**\n\n{text}")

        # ២. បង្កើត SRT (ទម្រង់សាមញ្ញសម្រាប់ Google API)
        duration = len(audio_segment)
        srt_content = f"1\n00:00:00,000 --> {format_timestamp(duration)}\n{text}\n"
        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename="subtitle.srt")
        await message.answer_document(srt_file, caption="🎬 ឯកសារ SRT របស់អ្នករួចរាល់ហើយ!")

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ កំហុស៖ {str(e)}")
    finally:
        for path in [ogg_path, wav_path]:
            if os.path.exists(path): os.remove(path)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
