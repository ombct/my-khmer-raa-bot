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

# រក្សាទុកការកំណត់របស់អ្នកប្រើ (Default: km, words=3)
user_settings = {}

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🔢 ចំនួនពាក្យ")],
            [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

# ប៊ូតុងជ្រើសរើស Format ដូចក្នុងរូបភាពទី ៤
def get_format_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="fmt_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="fmt_docx")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="fmt_txt"), InlineKeyboardButton(text="📊 XLSX", callback_data="fmt_xlsx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="fmt_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="fmt_vtt")],
        [InlineKeyboardButton(text="🎞 ASS", callback_data="fmt_ass"), InlineKeyboardButton(text="📦 JSON", callback_data="fmt_json")]
    ])
    return keyboard

# --- SRT & FORMAT HELPERS ---
def format_timestamp(seconds: float, fmt="srt"):
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    if fmt == "vtt":
        return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

# --- HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot ប្រែសម្រួល!**\n\n"
        "ផ្ញើឯកសារអូឌីយ៉ូ ឬសារជាសំឡេងមកខ្ញុំ ហើយខ្ញុំនឹង៖\n"
        "• ប្រែសម្រួលជាអត្ថបទដោយប្រើ A.I\n"
        "• បង្កើតជាឯកសារ SRT subtitle និងទម្រង់ជាច្រើនទៀត"
    )
    user_settings[message.from_user.id] = {'lang': 'km', 'words': 3}
    await message.answer(welcome_text, reply_markup=get_main_menu())

# មុខងារកំណត់ចំនួនពាក្យ (/words)
@dp.message(F.text == "🔢 ចំនួនពាក្យ")
async def cmd_words(message: types.Message):
    await message.answer("ប្រើពាក្យបញ្ជា `/words [លេខ]` ដើម្បីកំណត់ចំនួនពាក្យក្នុងមួយ Subtitle\nឧទាហរណ៍៖ `/words 5`", parse_mode="Markdown")

@dp.message(Command("words"))
async def set_words(message: types.Message):
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        count = int(args[1])
        user_id = message.from_user.id
        if user_id not in user_settings: user_settings[user_id] = {'lang': 'km'}
        user_settings[user_id]['words'] = count
        await message.answer(f"✅ បានកំណត់ចំនួនពាក្យក្នុងមួយ subtitle: {count}")
    else:
        await message.answer("❌ សូមបញ្ជាក់ជាលេខ។ ឧទាហរណ៍៖ `/words 3`")

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {'lang': 'km', 'words': 3})
    
    msg = await message.answer(f"⏳ កំពុងដំណើរការ... (ភាសា: {settings['lang']}, ពាក្យ: {settings['words']})")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=settings['lang'],
                prompt="អក្សរខ្មែរមានជើង និងស្រៈត្រឹមត្រូវ។"
            )

        # បង្ហាញអត្ថបទប្រែសម្រួល (រូបភាពទី ២)
        await message.answer(f"📝 **ការប្រែសម្រួល៖**\n\n{response.text}")
        
        # រក្សាទុក segments ក្នុង context ដើម្បីប្រើពេល User ចុចរើស Format
        user_settings[user_id]['last_segments'] = response.segments
        
        await msg.edit_text("✨ បំប្លែងរួចរាល់! សូមជ្រើសរើសទម្រង់ឯកសារដែលអ្នកចង់បាន៖", reply_markup=get_format_keyboard())

    except Exception as e:
        await msg.edit_text(f"❌ កំហុស៖ {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data.startswith("fmt_"))
async def process_format(callback: types.CallbackQuery):
    fmt = callback.data.split("_")[1]
    user_id = callback.from_user.id
    segments = user_settings.get(user_id, {}).get('last_segments')
    
    if not segments:
        await callback.answer("❌ រកមិនឃើញទិន្នន័យសំឡេងចុងក្រោយឡើយ។", show_alert=True)
        return

    content = ""
    filename = f"file.{fmt}"
    
    if fmt == "srt":
        for i, s in enumerate(segments, 1):
            content += f"{i}\n{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}\n{s['text'].strip()}\n\n"
    elif fmt == "txt":
        content = "\n".join([s['text'].strip() for s in segments])
    elif fmt == "vtt":
        content = "WEBVTT\n\n" + "\n".join([f"{format_timestamp(s['start'], 'vtt')} --> {format_timestamp(s['end'], 'vtt')}\n{s['text'].strip()}\n" for s in segments])
    else:
        content = f"ទម្រង់ {fmt.upper()} នឹងគាំទ្រក្នុងពេលឆាប់ៗនេះ!  فی الحالប្រើ SRT ឬ TXT សិន។"

    file = BufferedInputFile(content.encode('utf-8'), filename=filename)
    await callback.message.answer_document(file, caption=f"✅ ឯកសារ {fmt.upper()} របស់អ្នករួចរាល់!")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
