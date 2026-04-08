import os
import sqlite3
import logging
import pytz
import asyncio
import fitz  # PyMuPDF
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from groq import Groq

# --- CONFIGURATION ---
# ទាញយកតម្លៃពី Railway Variables ដើម្បីសុវត្ថិភាព
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_ID = int(os.getenv('ADMIN_ID', '7859553795'))
TELEGRAM_ADMIN_URL = os.getenv('ADMIN_URL', 'https://t.me/OG_Raa1')
KH_TIMEZONE = pytz.timezone('Asia/Phnom_Penh')
DB_PATH = os.getenv('DB_PATH', '/app/data/bot_database.db')

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- DATABASE LOGIC ---
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, lang_code TEXT DEFAULT 'km', words_per_sub INTEGER DEFAULT 30)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPERS ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 ទាក់ទង Admin (Telegram)", url=TELEGRAM_ADMIN_URL)],
        [InlineKeyboardButton(text="🔵 Facebook Support", url="https://www.facebook.com/share/15pZ6pZ6pZ/")]
    ])
    return keyboard

# --- HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "👋 **សួស្ដី! ខ្ញុំគឺជា Bot បំប្លែងសំឡេងទៅជាអក្សរ**\n\n"
        "រៀបចំដោយ៖ **THEARA Rupp**\n"
        "📩 ទំនាក់ទំនង Admin៖ [OG_Raa1]\n\n"
        "សូមផ្ញើសារជាសំឡេង (Voice) ឬឯកសារ MP3 មកកាន់ខ្ញុំ ដើម្បីបំប្លែង!"
    )
    await message.answer_photo(
        photo="https://telegra.ph/file/0c1b0c0c0c0c0c0c0c0c0.jpg", # ដាក់ Link រូបភាពអ្នក
        caption=welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    msg = await message.answer("⏳ កំពុងដំណើរការបំប្លែង... សូមរង់ចាំបន្តិច")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    file_path = f"{file_id}.ogg"
    await bot.download_file(file.file_path, file_path)

    try:
        # បំប្លែងសំឡេងទៅជាអក្សរ (កំណត់ឱ្យស្គាល់ខ្មែរច្បាស់)
        with open(file_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_path, audio_file.read()),
                model="whisper-large-v3",
                prompt="នេះគឺជាការបំប្លែងសំឡេងជាភាសាខ្មែរ។ សូមសរសេរជាអក្សរខ្មែរឱ្យបានត្រឹមត្រូវតាមអក្ខរាវិរុទ្ធ មានជើង និងស្រៈត្រឹមត្រូវ។",
                response_format="text",
                language="km"
            )

        result_text = (
            "📝 **ការបំប្លែងសំឡេង៖**\n"
            "🌐 **ភាសា៖** 🇰🇭 ខ្មែរ\n\n"
            f"{transcription}\n\n"
            "• By THEARA Rupp"
        )
        await msg.edit_text(result_text, parse_mode="Markdown")

    except Exception as e:
        await msg.edit_text(f"❌ កើតមានកំហុស៖ {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
