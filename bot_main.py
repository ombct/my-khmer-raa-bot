import os
import sqlite3
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from groq import Groq

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = os.getenv('ADMIN_URL', 'https://t.me/OG_Raa1')
DB_PATH = "bot_database.db" # កែទីតាំងឱ្យសាមញ្ញបំផុតដើម្បីកុំឱ្យ Error

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()

# --- HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = "👋 សួស្ដី! ផ្ញើសំឡេងមកដើម្បីបំប្លែងជាអក្សរខ្មែរ។"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 ទាក់ទង Admin", url=ADMIN_URL)]
    ])
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    msg = await message.answer("⏳ កំពុងបំប្លែង... សូមរង់ចាំ")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    file_path = f"{file_id}.ogg"
    await bot.download_file(file.file_path, file_path)

    try:
        with open(file_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_path, audio_file.read()),
                model="whisper-large-v3",
                prompt="នេះគឺជាការបំប្លែងសំឡេងជាភាសាខ្មែរ។ សូមសរសេរជាអក្សរខ្មែរឱ្យបានត្រឹមត្រូវ។",
                language="km" # បង្ខំឱ្យ AI ប្រើភាសាខ្មែរ
            )
        await msg.edit_text(f"📝 លទ្ធផល៖\n\n{transcription.text}")
    except Exception as e:
        await msg.edit_text(f"❌ កំហុស៖ {str(e)}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
