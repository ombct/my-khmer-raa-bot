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
ADMIN_URL = "https://t.me/OG_Raa1"
# API Key របស់ Remove.bg ដែលប្អូនបានផ្ដល់ឱ្យ
REMOVE_BG_API_KEY = "c7MsDwJLr4Gv3eGjNBPRyFo4" 

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

user_languages = {}
user_voices = {}

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

def get_remove_bg_confirm(file_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Remove Background ឥឡូវនេះ", callback_data=f"confirm_rbg_{file_id}")],
        [InlineKeyboardButton(text="❌ បោះបង់", callback_data="cancel_rbg")]
    ])

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese (日本語)", callback_data="setlang_ja")],
        [InlineKeyboardButton(text="🇨🇳 Chinese (中文)", callback_data="setlang_zh")]
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
    welcome_text = (
        "<b>🎙 <u>ស្វាគមន៍មកកាន់ RaaBot Pro (Full Config)</u></b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Google Engine:</b> បំប្លែងសំឡេងជាអត្ថបទ & SRT លឿន\n"
        "✅ <b>Voice:</b> បង្កើតសំឡេង AI (ប្រុស/ស្រី)\n"
        "✅ <b>Remove BG:</b> កាត់រូបភាព 8K (ទាមទារចុចប៊ូតុង)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <i>ទាក់ទង Admin: <a href='https://t.me/OG_Raa1'>OG_Raa1</a></i>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

# --- មុខងារ MENU REMOVE BACKGROUND ---
@dp.message(F.text == "🖼️ Remove Background")
async def menu_rbg_info(message: types.Message):
    await message.answer("<b>🖼️ របៀបកាត់ Background:</b>\nសូមផ្ញើរូបភាពមកកាន់ Bot រួចចុចប៊ូតុងបញ្ជាក់ដើម្បីចាប់ផ្ដើម។")

# --- មុខងារ REMOVE BACKGROUND (កែសម្រួលឱ្យដំណើរការវិញ 100%) ---
@dp.message(F.photo)
async def ask_remove_bg(message: types.Message):
    photo_id = message.photo[-1].file_id
    await message.reply(
        "<b>📸 ប្អូនបានផ្ញើរូបភាពមក! តើប្អូនចង់កាត់ Background មែនទេ?</b>",
        reply_markup=get_remove_bg_confirm(photo_id)
    )

@dp.callback_query(F.data.startswith("confirm_rbg_"))
async def process_remove_bg(callback: types.CallbackQuery):
    file_id = callback.data.split("_")[2]
    await callback.message.edit_text("⚡ <b>កំពុងដំណើរការកាត់រូបភាព... សូមរង់ចាំ</b>")
    
    try:
        # ទាញយករូបភាពពី Telegram
        file_info = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        
        # ផ្ញើទៅ Remove.bg API
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            data={'image_url': file_url, 'size': 'full'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY},
            stream=True
        )
        
        if response.status_code == requests.codes.ok:
            # ផ្ញើលទ្ធផលត្រឡប់មកវិញជាឯកសារ
            await callback.message.answer_document(
                BufferedInputFile(response.content, filename="RAA_NO_BG.png"),
                caption="<b>✅ កាត់រួចរាល់ក្នុងកម្រិតច្បាស់!</b>"
            )
            await callback.message.delete()
        else:
            await callback.message.edit_text(f"❌ កំហុស API: {response.text}")
    except Exception as e:
        await callback.message.edit_text(f"❌ កំហុសបច្ចេកទេស: {str(e)}")

@dp.callback_query(F.data == "cancel_rbg")
async def cancel_remove_bg(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ បានបោះបង់ការកាត់ Background។")

# --- មុខងារបំប្លែងសំឡេង (SRT ប្រើ Google) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    
    # កំណត់ភាសាសម្រាប់ Google
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}[lang]
    msg = await message.answer("<b>⏳ កំពុងបំប្លែងដោយ Google Recognition...</b>")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path, tts_path = f"{file_id}.ogg", f"{file_id}.wav", f"{file_id}_ai.mp3"
    await bot.download_file(file.file_path, ogg_path)

    try:
        # បំប្លែង OGG ទៅ WAV សម្រាប់ Google Speech
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            # ប្រើ Google Recognition
            text_result = recognizer.recognize_google(audio_data, language=google_lang)

        # បង្កើតសំឡេង AI បើអ្នកប្រើជ្រើសរើស
        if voice_choice:
            tts = gTTS(text=text_result, lang=lang)
            tts.save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path), caption="<b>🎙️ សំឡេង AI</b>")

        await message.answer(f"<b>📝 អត្ថបទ (Google):</b>\n\n<code>{text_result}</code>")

        # បង្កើត SRT File (Google Recognition)
        srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{text_result}"
        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption=f"<b>🎬 SRT ({lang.upper()}) រួចរាល់!</b>")
        await msg.delete()

    except Exception as e:
        await message.answer(f"<b>❌ Error:</b> <code>{str(e)}</code>")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

# --- មុខងារ Setup ផ្សេងៗ (Language & Voice) ---
@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    names = {"km": "Khmer 🇰🇭", "en": "English 🇺🇸", "ja": "Japanese 🇯🇵", "zh": "Chinese 🇨🇳"}
    await callback.message.edit_text(f"<b>✅ ភាសាដែលបានរើស:</b> <code>{names[lang_code]}</code>")
    await callback.answer()

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI:</b>", reply_markup=get_voice_keyboard())

@dp.callback_query(F.data.startswith("setvoice_"))
async def process_voice_selection(callback: types.CallbackQuery):
    voice_type = callback.data.split("_")[1]
    user_voices[callback.from_user.id] = None if voice_type == "none" else voice_type
    name = "ស្រី 👩" if voice_type == "female" else "ប្រុស 👨"
    await callback.message.edit_text(f"<b>✅ បានកំណត់យកសំឡេង AI ភេទ:</b> <code>{name}</code>")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Engine: Google Recognition\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>ទាក់ទង Admin:</b> <a href='https://t.me/OG_Raa1'>OG_Raa1</a>")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
