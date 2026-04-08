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
ADMIN_URL = "https://t.me/OG_Raa1" # តំណភ្ជាប់ Admin របស់ប្អូន

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# រក្សាទុកភាសាដែល User ជ្រើសរើស (Default: km)
user_languages = {}

# --- KEYBOARDS (Menu Bar) ---
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
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (លាយអង់គ្លេស)", callback_data="setlang_km")],
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
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេងអាជីព!**\n\n"
        "✅ គាំទ្រការនិយាយខ្មែរលាយអង់គ្លេស\n"
        "✅ អក្សរខ្មែរមានដៃជើងត្រឹមត្រូវ (High Accuracy)\n"
        "✅ បង្កើតឯកសារ SRT ដែលមានម៉ោងរត់ត្រឹមត្រូវ"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    await message.answer("សូមជ្រើសរើសភាសាដែលប្អូនចង់ប្រើ៖", reply_markup=get_lang_keyboard())

# មុខងារប៊ូតុង ព័ត៌មាន Bot
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    info_text = (
        "🤖 **SomlengSrtBot v7.5**\n"
        "• បច្ចេកវិទ្យា៖ Google API & Groq AI (Whisper-v3)\n"
        "• សមត្ថភាព៖ បំប្លែងភាសាចម្រុះ (ខ្មែរ/អង់គ្លេស/ចិន)\n"
        "• អ្នកអភិវឌ្ឍន៍៖ THEARA Rupp"
    )
    await message.answer(info_text, parse_mode="Markdown")

# មុខងារប៊ូតុង ទាក់ទង Admin
@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    admin_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ផ្ញើសារទៅកាន់ Admin", url=ADMIN_URL)]
    ])
    await message.answer("ប្រសិនបើប្អូនមានបញ្ហាបច្ចេកទេស សូមទាក់ទងមកកាន់៖", reply_markup=admin_btn)

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("សូមជ្រើសរើសភាសាគោលដៅ៖", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    names = {"km": "ខ្មែរលាយអង់គ្លេស 🇰🇭🇺🇸", "en": "English 🇺🇸", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"✅ បានកំណត់យកភាសា៖ **{names[lang_code]}**")
    await callback.answer()

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    lang = user_languages.get(message.from_user.id, "km")
    msg = await message.answer("⏳ កំពុងស្តាប់ និងបំប្លែងសំឡេង... សូមរង់ចាំ")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        # កំណត់ Prompt សម្រាប់ភាសាចម្រុះ (ខ្មែរ + អង់គ្លេស)
        special_prompt = (
            "នេះគឺជាសំឡេងនិយាយភាសាខ្មែរ ដែលអាចមានលាយជាមួយពាក្យអង់គ្លេសខ្លះៗ។ "
            "សូមសរសេរជាអក្សរខ្មែរឱ្យត្រឹមត្រូវ មានជើងអក្សរ "
            "ហើយបើមានពាក្យអង់គ្លេស សូមរក្សាទុកជាអក្សរអង់គ្លេសដដែល។"
        ) if lang == "km" else ""

        # បំប្លែងជាអក្សរ និង SRT តាមរយៈ Groq (ព្រោះវាឆ្លាត និងផ្ដល់ Time-Sync ច្បាស់)
        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang,
                prompt=special_prompt
            )

        # ផ្ញើលទ្ធផលអត្ថបទ
        await message.answer(f"📝 **អត្ថបទបំប្លែងរួច៖**\n\n{response.text}")

        # បង្កើតឯកសារ SRT ឱ្យស្គាល់ខ្មែរមានជើង និង Time-Sync
        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            srt_content += f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n"

        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption="🎬 ឯកសារ SRT (ខ្មែរលាយអង់គ្លេស) រួចរាល់ហើយ!")
        
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
