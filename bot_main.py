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
from gtts import gTTS

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

# កែជួរទី ២៣ ក្នុង bot_main.py
from aiogram.client.default import DefaultBotProperties # បន្ថែមនៅជួរខាងលើ

bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode="HTML")
)

# កែសម្រួលត្រង់ចំណុចបង្កើត Bot (ជួរទី 23)
bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

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

def get_lang_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese (日本語)", callback_data="setlang_ja")],
        [InlineKeyboardButton(text="🇨🇳 Chinese (中文)", callback_data="setlang_zh")]
    ])
    return keyboard

def get_voice_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 សំឡេងស្រី AI", callback_data="setvoice_female")],
        [InlineKeyboardButton(text="👨 សំឡេងប្រុស AI", callback_data="setvoice_male")],
        [InlineKeyboardButton(text="❌ បិទសំឡេង AI", callback_data="setvoice_none")]
    ])
    return keyboard

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
        "<b>🎙 សូមស្វាគមន៍មកកាន់ Bot បំប្លែងសំឡេងជំនាន់ថ្មី!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>លក្ខណៈពិសេស:</b>\n"
        "✅ បំប្លែងសំឡេងជាអត្ថបទ (ខ្មែរ/ENG/JA/ZH)\n"
        "✅ បង្កើតឯកសារ <b>SRT Subtitle</b>\n"
        "✅ បង្កើតសំឡេង <b>AI Voice</b> (ប្រុស/ស្រី)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>ចំណាំ: បើចង់ឱ្យ Bot និយាយ សូមចុចជ្រើសរើសសំឡេង AI ជាមុនសិន!</i>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI ដែលអ្នកចង់បាន:</b>", reply_markup=get_voice_keyboard())

@dp.callback_query(F.data.startswith("setvoice_"))
async def process_voice_selection(callback: types.CallbackQuery):
    voice_type = callback.data.split("_")[1]
    user_id = callback.from_user.id
    if voice_type == "none":
        user_voices[user_id] = None
        await callback.message.edit_text("<b>❌ បានបិទមុខងារសំឡេង AI</b> (ចេញតែអត្ថបទ និង SRT)")
    else:
        user_voices[user_id] = voice_type
        name = "ស្រី 👩" if voice_type == "female" else "ប្រុស 👨"
        await callback.message.edit_text(f"<b>✅ បានកំណត់យកសំឡេង AI ភេទ:</b> <code>{name}</code>")
    await callback.answer()

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសាដែលអ្នកចង់ប្រើ:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    names = {"km": "Khmer 🇰🇭", "en": "English 🇺🇸", "ja": "Japanese 🇯🇵", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"<b>✅ ភាសាដែលបានរើស:</b> <code>{names[lang_code]}</code>")
    await callback.answer()

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None) # ពិនិត្យមើលថាតើ User បានរើសសំឡេង AI ឬនៅ
    
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}[lang]
    msg = await message.answer("<b>⏳ កំពុងដំណើរការ... សូមរង់ចាំ</b>")
    
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

        # បង្កើតសំឡេង AI លុះត្រាតែបានរើសភេទសំឡេងរួច
        if voice_choice:
            tts = gTTS(text=google_text, lang=lang)
            tts.save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path), caption="<b>🎙️ សំឡេង AI បំប្លែងចេញពីអត្ថបទ</b>")

        # ប្រើ Groq សម្រាប់បង្កើត SRT
        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang,
                prompt="អក្សរខ្មែរមានជើង និងស្រៈត្រឹមត្រូវ។"
            )

        # បង្ហាញអត្ថបទបំប្លែងរួចជាមួយ Highlights
        result_text = f"<b>📝 អត្ថបទបំប្លែងរួច ({lang.upper()}):</b>\n\n<code>{google_text}</code>"
        await message.answer(result_text)

        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            srt_content += f"{i}\n{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n{segment['text'].strip()}\n\n"

        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption=f"<b>🎬 ឯកសារ SRT ({lang.upper()}) រួចរាល់ហើយ!</b>")
        await msg.delete()

    except Exception as e:
        await message.answer(f"<b>❌ កំហុសបច្ចេកទេស:</b> <code>{str(e)}</code>")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    info = (
        "<b>🤖 RaaBot Pro v10.0</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "• <b>Developer:</b> THEARA Rupp\n"
        "• <b>Status:</b> Active (Stable)\n"
        "• <b>Language:</b> KM, EN, JA, ZH"
    )
    await message.answer(info)

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    admin_btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 ផ្ញើសារទៅ Admin", url=ADMIN_URL)]])
    await message.answer("<b>ប្រសិនបើមានបញ្ហា សូមចុចប៊ូតុងខាងក្រោម:</b>", reply_markup=admin_btn)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
