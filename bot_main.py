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
from gtts import gTTS # បន្ថែមសម្រាប់សំឡេង AI

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# វចនានុក្រមរក្សាទុកភាសា និងភេទសំឡេង
user_languages = {}
user_voices = {} 

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
            [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_voice_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 សំឡេងស្រី AI", callback_data="setvoice_female")],
        [InlineKeyboardButton(text="👨 សំឡេងប្រុស AI", callback_data="setvoice_male")]
    ])
    return keyboard

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
        "🎙 **សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេង!**\n\n"
        "កូដត្រូវបានពង្រឹងឱ្យស្គាល់ **អក្សរខ្មែរមានដៃជើង** ត្រឹមត្រូវ (v6.1)\n"
        "ឥឡូវនេះអាចបង្កើតសំឡេង AI ប្រុស-ស្រី បានថែមទៀត!"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    await message.answer("ជ្រើសរើសភាសាគោលដៅ៖", reply_markup=get_lang_keyboard())

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    await message.answer("សូមជ្រើសរើសភេទសំឡេង AI សម្រាប់អត្ថបទបំប្លែង៖", reply_markup=get_voice_keyboard())

@dp.callback_query(F.data.startswith("setvoice_"))
async def process_voice_selection(callback: types.CallbackQuery):
    voice_type = callback.data.split("_")[1]
    user_voices[callback.from_user.id] = voice_type
    name = "ស្រី 👩" if voice_type == "female" else "ប្រុស 👨"
    await callback.message.edit_text(f"✅ បានកំណត់យកសំឡេង AI ភេទ៖ **{name}**")
    await callback.answer()

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
    lang = user_languages.get(message.from_user.id, "km")
    google_lang = {"km": "km-KH", "en": "en-US", "zh": "zh-CN"}[lang]
    
    msg = await message.answer("⏳ កំពុងបំប្លែង និងបង្កើតសំឡេង AI... សូមរង់ចាំ")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path = f"{file_id}.ogg"
    wav_path = f"{file_id}.wav"
    tts_path = f"{file_id}_ai.mp3"
    
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio_segment = AudioSegment.from_file(ogg_path)
        audio_segment.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            google_text = recognizer.recognize_google(audio_data, language=google_lang)

        # បង្កើតសំឡេង AI ពីអត្ថបទ
        tts = gTTS(text=google_text, lang=lang)
        tts.save(tts_path)
        ai_audio = BufferedInputFile.from_file(tts_path, filename="ai_voice.mp3")
        await message.answer_voice(ai_audio, caption="🎙️ សំឡេង AI (បំប្លែងពីអត្ថបទ)")

        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang,
                prompt="នេះគឺជាសំឡេងនិយាយភាសាខ្មែរ។ សូមសរសេរជាអក្សរខ្មែរឱ្យបានត្រឹមត្រូវបំផុតតាមអក្ខរាវិរុទ្ធ មានជើងអក្សរច្បាស់លាស់។"
            )

        await message.answer(f"📝 **អត្ថបទបំប្លែងរួច ({lang.upper()}):**\n\n{google_text}")

        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            srt_content += f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n"

        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption=f"🎬 ឯកសារ SRT រួចរាល់ហើយ!")
        await msg.delete()

    except Exception as e:
        await message.answer(f"❌ កំហុស៖ {str(e)}")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

# --- ព័ត៌មាន និង Admin រក្សានៅដដែល ---
@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    info_text = ("🤖 **ព័ត៌មាន Bot**\n• បំប្លែងសំឡេងទៅ SRT\n• បង្កើតសំឡេង AI (Male/Female)\n• រៀបចំដោយ៖ THEARA Rupp")
    await message.answer(info_text, parse_mode="Markdown")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    admin_btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 ផ្ញើសារទៅ Admin", url=ADMIN_URL)]])
    await message.answer("ប្រសិនបើប្អូនមានបញ្ហា សូមចុចប៊ូតុងខាងក្រោម៖", reply_markup=admin_btn)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
