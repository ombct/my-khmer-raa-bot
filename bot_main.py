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
API_TOKEN = '8625986459:AAF7pTil2tV5GfL1VIYvAxE1tIg5kzGShqY'
GROQ_API_KEY = 'Gsk_IqkjIZEU1FM3qDHu60pkWGdyb3FYJSstjUdxio12jDGtmWJoAfX0'
ADMIN_ID = 7859553795  
TELEGRAM_ADMIN_URL = "https://t.me/OG_Raa1" 
KH_TIMEZONE = pytz.timezone('Asia/Phnom_Penh')
DB_PATH = os.getenv('DB_PATH', 'bot_database.db')

groq_client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, lang_code TEXT DEFAULT 'km', words_per_sub INTEGER DEFAULT 3)''')
    conn.commit()
    conn.close()

def get_user_config(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT lang_code, words_per_sub FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res if res else ('km', 3)

# --- SRT FORMATTER ---
def format_timestamp(seconds):
    td = datetime.utcfromtimestamp(seconds)
    return td.strftime('%H:%M:%S,%f')[:-3]

def split_text_by_words(text, n):
    words = text.split()
    return [' '.join(words[i:i+n]) for i in range(0, len(words), n)]

def create_srt(segments, words_per_sub):
    srt_content, full_text = "", ""
    counter = 1
    for seg in segments:
        text = seg['text'].strip()
        full_text += text + " "
        parts = split_text_by_words(text, words_per_sub)
        duration = seg['end'] - seg['start']
        part_dur = duration / len(parts) if len(parts) > 0 else 0
        for i, part in enumerate(parts):
            start = seg['start'] + (i * part_dur)
            end = start + part_dur
            srt_content += f"{counter}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{part}\n\n"
            counter += 1
    return srt_content, full_text.strip()

# --- PDF TO TEXT ---
def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

# --- HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    
    lang, words = get_user_config(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 ទាក់ទង Admin (Telegram)", url=TELEGRAM_ADMIN_URL)],
        [InlineKeyboardButton(text="🔵 Facebook Support", url="https://www.facebook.com/share/1GkfDZEVcK/")]
    ])
    
    msg = (
        "🎙️ **សូមស្វាគមន៍មកកាន់ Khmer Bot ប្រែសម្លេង!**\n\n"
        "ផ្ញើឯកសារអូឌីយ៉ូ ឬ PDF មកខ្ញុំ ហើយខ្ញុំនឹង:\n"
        "• ប្រែសម្លេងជាអត្ថបទ & SRT Subtitle\n"
        "• ទាញយកអត្ថបទចេញពី PDF (PDF to Text)\n\n"
        f"🌐 ភាសាបច្ចុប្បន្ន: **{ '🇰🇭 ខ្មែរ (កម្ពុជា)' if lang == 'km' else '🇺🇸 English' }**\n"
        f"📝 ពាក្យក្នុងមួយ subtitle: **{words}**\n\n"
        "• បង្កើតដោយ **THEARA Rupp**\n"
        f"📩 ទំនាក់ទំនង Admin: [OG_Raa1]({TELEGRAM_ADMIN_URL})"
    )
    await message.reply(msg, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(F.audio | F.voice)
async def handle_audio(message: types.Message):
    wait = await message.reply("⏳ កំពុងដំណើរការ... សូមរង់ចាំ")
    file_id = message.audio.file_id if message.audio else message.voice.file_id
    file = await bot.get_file(file_id)
    path = f"tmp_{file_id}.mp3"
    await bot.download_file(file.file_path, path)
    try:
        lang, words = get_user_config(message.from_user.id)
        with open(path, "rb") as f:
            trans = groq_client.audio.transcriptions.create(file=(path, f.read()), model="whisper-large-v3", language=lang, response_format="verbose_json")
        srt, raw = create_srt(trans.segments, words)
        await message.reply(f"📝 **ការប្រែសម្លេង៖**\n🌐 **ភាសា៖** { '🇰🇭 ខ្មែរ' if lang == 'km' else '🇺🇸 English' }\n\n{raw}\n\n• By THEARA Rupp")
        doc = BufferedInputFile(srt.encode('utf-8-sig'), filename=f"subtitle_{lang}.srt")
        await bot.send_document(message.chat.id, doc)
        await wait.delete()
    except Exception as e: await message.reply(f"❌ Error: {e}")
    finally: 
        if os.path.exists(path): os.remove(path)

@dp.message(F.document)
async def handle_pdf(message: types.Message):
    if message.document.file_name.lower().endswith('.pdf'):
        wait = await message.reply("⏳ កំពុងទាញយកអត្ថបទពី PDF...")
        file = await bot.get_file(message.document.file_id)
        path = f"tmp_{message.document.file_id}.pdf"
        await bot.download_file(file.file_path, path)
        try:
            text = extract_text_from_pdf(path)
            if text.strip():
                for i in range(0, len(text), 4000):
                    await message.reply(f"📝 **អត្ថបទពី PDF៖**\n\n{text[i:i+4000]}")
            else: await message.reply("⚠️ មិនអាចរកឃើញអត្ថបទក្នុង PDF នេះទេ។")
        finally:
            await wait.delete()
            if os.path.exists(path): os.remove(path)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
