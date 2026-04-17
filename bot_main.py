import os
import logging
import asyncio
import requests
import speech_recognition as sr
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardButton, InlineKeyboardMarkup, 
    BufferedInputFile
)
from aiogram.client.default import DefaultBotProperties
from pydub import AudioSegment
from gtts import gTTS

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
# បានប្តូរ API Key ថ្មីដែលប្អូនផ្ដល់ឱ្យ
REMOVE_BG_API_KEY = "BCiTiku3WMfdtPmV8K3ZeEZv" 
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

user_languages = {}
user_voices = {}
last_transcription = {} 

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
            [KeyboardButton(text="🖼️ Remove Background"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
            [KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_file_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="export_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="export_docx")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="export_txt"), InlineKeyboardButton(text="📊 XLSX", callback_data="export_xlsx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="export_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="export_vtt")],
        [InlineKeyboardButton(text="🎞 ASS", callback_data="export_ass"), InlineKeyboardButton(text="📦 JSON", callback_data="export_json")]
    ])

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")]
    ])

def get_voice_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 សំឡេងស្រី AI", callback_data="setvoice_female")],
        [InlineKeyboardButton(text="👨 សំឡេងប្រុស AI", callback_data="setvoice_male")],
        [InlineKeyboardButton(text="❌ បិទសំឡេង AI", callback_data="setvoice_none")]
    ])

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 RaaBot Pro v10.0 (Updated API)</b>\nផ្ញើសំឡេងដើម្បីបំប្លែង ឬផ្ញើរូបភាពដើម្បីកាត់ Background Auto!", reply_markup=get_main_menu())

# --- មុខងារ AUTO REMOVE BACKGROUND (ស្វ័យប្រវត្តិ) ---
@dp.message(F.photo)
async def auto_remove_bg(message: types.Message):
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background ដោយស្វ័យប្រវត្តិ...</b>")
    try:
        file_info = await bot.get_file(photo_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            data={'image_url': file_url, 'size': 'full'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY},
            stream=True
        )
        
        if response.status_code == requests.codes.ok:
            await message.answer_document(
                BufferedInputFile(response.content, filename="RAA_RESULT.png"),
                caption="<b>✅ កាត់រួចរាល់ដោយស្វ័យប្រវត្តិ! (Key ថ្មី)</b>"
            )
            await msg.delete()
        else:
            await msg.edit_text(f"❌ កំហុស API: {response.status_code}\nសូមពិនិត្យមើល Credit ក្នុង API Key របស់ប្អូន។")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

# --- មុខងារសំឡេង (Google Recognition) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    google_lang = {"km": "km-KH", "en": "en-US"}.get(lang, "km-KH")
    
    msg = await message.answer("<b>⏳ កំពុងបំប្លែងដោយ Google...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path, tts_path = f"{file_id}.ogg", f"{file_id}.wav", f"{file_id}_ai.mp3"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)
        
        last_transcription[user_id] = text_result 

        if voice_choice:
            tts = gTTS(text=text_result, lang=lang)
            tts.save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path), caption="<b>🎙️ សំឡេង AI</b>")

        await message.answer(f"<b>📝 អត្ថបទ (Google):</b>\n\n<code>{text_result}</code>")
        await message.answer("<b>✅ រួចរាល់! សូមជ្រើសរើសប្រភេទ File ដើម្បីទាញយក:</b>", reply_markup=get_file_type_keyboard())
        await msg.delete()

    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

# --- មុខងារ EXPORT FILES ---
@dp.callback_query(F.data.startswith("export_"))
async def process_export(callback: types.CallbackQuery):
    file_type = callback.data.split("_")[1]
    user_id = callback.from_user.id
    text = last_transcription.get(user_id, "គ្មានទិន្នន័យ")
    lang = user_languages.get(user_id, "km")

    if file_type == "srt":
        content = f"1\n00:00:00,000 --> 00:00:10,000\n{text}"
        filename = f"sub_{lang}.srt"
    else:
        content = text
        filename = f"file_{lang}.{file_type}"

    await callback.message.answer_document(
        BufferedInputFile(content.encode('utf-8'), filename=filename),
        caption=f"<b>🎬 ឯកសារ {file_type.upper()} ត្រូវបានផលិតរួចរាល់!</b>"
    )
    await callback.answer()

# --- ប៊ូតុង Setup ផ្សេងៗ ---
@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    user_languages[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text("✅ កំណត់ភាសារួចរាល់!")
    await callback.answer()

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI:</b>", reply_markup=get_voice_keyboard())

@dp.callback_query(F.data.startswith("setvoice_"))
async def set_voice(callback: types.CallbackQuery):
    user_voices[callback.from_user.id] = None if callback.data.split("_")[1] == "none" else callback.data.split("_")[1]
    await callback.message.edit_text("✅ បានកំណត់សំឡេង AI រួចរាល់!")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Updated API Key\n• Engine: Google Recognition\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"ទាក់ទង Admin: <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
