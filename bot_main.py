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
from groq import Groq
from pydub import AudioSegment

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# វចនានុក្រមរក្សាទុកភាសាដែល User ជ្រើសរើស (ក្នុងផលិតកម្មគួរប្រើ Database)
user_languages = {}

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
            [KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_lang_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 អង់គ្លេស (English)", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇨🇳 ចិន (Chinese)", callback_data="setlang_zh")]
    ])
    return keyboard

# --- SRT HELPER ---
def format_timestamp(seconds: float):
    td = timedelta(seconds=seconds)
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
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេងពហុភាសា!**\n\n"
        "សូមជ្រើសរើសភាសាបំប្លែងរបស់អ្នកខាងក្រោម៖"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())
    await message.answer("ជ្រើសរើសភាសាគោលដៅ៖", reply_markup=get_lang_keyboard())

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("សូមជ្រើសរើសភាសាដែលអ្នកចង់បំប្លែង៖", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    
    names = {"km": "ខ្មែរ 🇰🇭", "en": "English 🇺🇸", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"✅ បានកំណត់យកភាសា៖ **{names[lang_code]}**")
    await callback.answer()

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    # ទាញយកភាសាដែល User បានរើស (បើអត់មាន យកខ្មែរជា Default)
    lang = user_languages.get(message.from_user.id, "km")
    google_lang = {"km": "km-KH", "en": "en-US", "zh": "zh-CN"}[lang]
    
    msg = await message.answer("⏳ កំពុងដំណើរការ... សូមរង់ចាំ")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        # ១. បំប្លែងជាអត្ថបទ (Google API)
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)

        # ២. បង្កើត SRT (Groq Whisper)
        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang
            )

        # ផ្ញើលទ្ធផល
        await message.answer(f"📝 **អត្ថបទបំប្លែង ({lang.upper()}):**\n\n{text_result}")

        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            srt_content += f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n"

        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption=f"🎬 ឯកសារ SRT ភាសា {lang.upper()} រួចរាល់!")
        
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ កំហុស៖ {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
