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

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro!</b>\nសូមជ្រើសរើសមុខងារខាងក្រោម៖", reply_markup=get_main_menu())

# --- មុខងារ REMOVE BACKGROUND (កែសម្រួលថ្មី) ---
@dp.message(F.text == "🖼️ Remove Background")
async def menu_rbg(message: types.Message):
    await message.answer("<b>🖼️ របៀបកាត់ Background:</b>\nសូមផ្ញើរូបភាពមកកាន់ Bot រួចចុចប៊ូតុងបញ្ជាក់។")

@dp.message(F.photo)
async def ask_remove_bg(message: types.Message):
    photo_id = message.photo[-1].file_id
    await message.reply(
        "<b>📸 តើប្អូនចង់កាត់ Background រូបភាពនេះមែនទេ?</b>",
        reply_markup=get_remove_bg_confirm(photo_id)
    )

# ផ្នែកនេះសំខាន់បំផុត៖ Handler សម្រាប់ទទួលការចុចប៊ូតុងបញ្ជាក់
@dp.callback_query(F.data.startswith("confirm_rbg_"))
async def process_remove_bg(callback: types.CallbackQuery):
    file_id = callback.data.split("_")[2]
    await callback.message.edit_text("⚡ <b>កំពុងដំណើរការកាត់រូបភាព... សូមរង់ចាំ</b>")
    
    try:
        file_info = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            data={'image_url': file_url, 'size': 'full'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY},
            stream=True
        )
        
        if response.status_code == requests.codes.ok:
            await callback.message.answer_document(
                BufferedInputFile(response.content, filename="RAA_NO_BG.png"),
                caption="<b>✅ កាត់រួចរាល់ក្នុងកម្រិតច្បាស់!</b>"
            )
            await callback.message.delete()
        else:
            await callback.message.edit_text(f"❌ កំហុស API: {response.status_code}")
    except Exception as e:
        await callback.message.edit_text(f"❌ កំហុសបច្ចេកទេស: {str(e)}")

@dp.callback_query(F.data == "cancel_rbg")
async def cancel_remove_bg(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ បានបោះបង់។")

# --- មុខងារបំប្លែងសំឡេង (SRT ប្រើ Google) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}[lang]
    
    msg = await message.answer("<b>⏳ កំពុងបំប្លែងសំឡេង...</b>")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)

        await message.answer(f"<b>📝 អត្ថបទ (Google):</b>\n\n<code>{text_result}</code>")

        # បង្កើត SRT File (Google Recognition)
        srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{text_result}"
        srt_file = BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt")
        await message.answer_document(srt_file, caption=f"<b>🎬 SRT ({lang.upper()}) រួចរាល់!</b>")
        await msg.delete()

    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

# --- មុខងារផ្សេងៗ (Language & Voice) ---
@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="setlang_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")]
    ])
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    user_languages[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text("✅ កំណត់ភាសារួចរាល់!")

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def voice_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ស្រី", callback_data="setvoice_female"), InlineKeyboardButton(text="👨 ប្រុស", callback_data="setvoice_male")]
    ])
    await message.answer("<b>🎙️ ជ្រើសរើសសំឡេង AI:</b>", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("setvoice_"))
async def set_voice(callback: types.CallbackQuery):
    user_voices[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text("✅ កំណត់សំឡេង AI រួចរាល់!")

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\nDev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def admin(message: types.Message):
    await message.answer(f"Admin: {ADMIN_URL}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
