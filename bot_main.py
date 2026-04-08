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
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer/English Mixed)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English Only", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇨🇳 Chinese (中文)", callback_data="setlang_zh")]
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
        "🎙 **Bot បំប្លែងសំឡេងជំនាន់ថ្មី!**\n\n"
        "✨ **ចំណុចពិសេស៖** គាំទ្រការនិយាយខ្មែរលាយអង់គ្លេស\n"
        "✅ អក្សរខ្មែរមានដៃជើង និងពាក្យអង់គ្លេសត្រឹមត្រូវ\n"
        "✅ បង្កើតឯកសារ SRT ដែលមាន Time Sync ល្អបំផុត"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    await message.answer("សូមជ្រើសរើសភាសាគោលដៅ៖", reply_markup=get_lang_keyboard())

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("🤖 **Bot Version 7.0**\nបច្ចេកវិទ្យា៖ Groq AI\nជំនាញ៖ បំប្លែងខ្មែរលាយអង់គ្លេស\nអ្នកអភិវឌ្ឍន៍៖ THEARA Rupp", parse_mode="Markdown")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    admin_btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 ផ្ញើសារទៅ Admin", url=ADMIN_URL)]])
    await message.answer("សម្រាប់ជំនួយផ្សេងៗ សូមទាក់ទង Admin៖", reply_markup=admin_btn)

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("សូមជ្រើសរើសភាសា៖", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    names = {"km": "ខ្មែរលាយអង់គ្លេស 🇰🇭🇺🇸", "en": "English 🇺🇸", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"✅ កំណត់យកភាសា៖ **{names[lang_code]}**")
    await callback.answer()

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    lang = user_languages.get(message.from_user.id, "km")
    msg = await message.answer("⏳ កំពុងស្តាប់ និងបំប្លែងភាសាចម្រុះ... សូមរង់ចាំ")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        # កំណត់ Prompt ពិសេសសម្រាប់ភាសាខ្មែរលាយអង់គ្លេស
        special_prompt = (
            "នេះគឺជាសំឡេងនិយាយភាសាខ្មែរ ដែលអាចមានលាយជាមួយពាក្យអង់គ្លេសខ្លះៗ។ "
            "សូមសរសេរជាអក្សរខ្មែរឱ្យត្រឹមត្រូវ និងរក្សាពាក្យអង់គ្លេសជាអក្សរអង់គ្លេសដដែល "
            "ឧទាហរណ៍៖ 'ខ្ញុំប្រើ iPhone' ឬ 'រៀន Computer'។"
        ) if lang == "km" else ""

        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang,
                prompt=special_prompt
            )

        await message.answer(f"📝 **អត្ថបទបំប្លែងរួច៖**\n\n{response.text}")

        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            srt_content += f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n"

        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption="🎬 ឯកសារ SRT ដែលបំប្លែងពាក្យខ្មែរ និងអង់គ្លេសរួចរាល់!")
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
