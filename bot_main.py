import os
import logging
import asyncio
import io
import speech_recognition as sr
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

# --- ការកំណត់សម្រាប់ការកាត់ឱ្យលឿន និងប្តូរពណ៌ ---
from rembg import remove, new_session
from PIL import Image

# ប្តូរមកប្រើ "u2netp" (ជា Model ស្រាល និងលឿនបំផុតសម្រាប់ Server)
fast_session = new_session("u2netp") 

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

user_languages = {}
user_voices = {}
last_transcription = {}
last_input_data = {}

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

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ (Khmer)", callback_data="setlang_km")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese (日本語)", callback_data="setlang_ja")],
        [InlineKeyboardButton(text="🇨🇳 Chinese (中文)", callback_data="setlang_zh")]
    ])

def get_color_keyboard(file_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬜ ពណ៌ស", callback_data=f"color_white_{file_id}"), InlineKeyboardButton(text="⬛ ពណ៌ខ្មៅ", callback_data=f"color_black_{file_id}")],
        [InlineKeyboardButton(text="🟦 ពណ៌ខៀវ", callback_data=f"color_blue_{file_id}"), InlineKeyboardButton(text="🟥 ពណ៌ក្រហម", callback_data=f"color_red_{file_id}")],
        [InlineKeyboardButton(text="🖼️ ភាពថ្លា", callback_data=f"color_transparent_{file_id}")]
    ])

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម៖", 
        reply_markup=get_main_menu()
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background យ៉ាងលឿន...</b>")
    
    try:
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)
        input_data = photo_bytes.read()
        last_input_data[photo_id] = input_data

        # កាត់ Background (Default ជាភាពថ្លា)
        output_data = remove(input_data, session=fast_session)

        await message.answer_document(
            BufferedInputFile(output_data, filename="RAA_NO_BG.png"),
            caption="<b>✅ កាត់រួចរាល់! តើប្អូនចង់ប្តូរពណ៌ Background ទេ?</b>",
            reply_markup=get_color_keyboard(photo_id)
        )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

@dp.callback_query(F.data.startswith("color_"))
async def process_color(callback: types.CallbackQuery):
    data = callback.data.split("_")
    color_code, file_id = data[1], data[2]
    
    if file_id not in last_input_data:
        await callback.answer("❌ រកមិនឃើញរូបភាពដើម", show_alert=True)
        return

    await callback.message.edit_text(f"🎨 <b>កំពុងដាក់ពណ៌ {color_code.upper()}...</b>")
    
    try:
        input_data = last_input_data[file_id]
        color_map = {"white": (255, 255, 255), "black": (0, 0, 0), "blue": (0, 0, 255), "red": (255, 0, 0)}
        bg_color = color_map.get(color_code, (255, 255, 255)) if color_code != "transparent" else (0,0,0,0)
        
        output_data = remove(input_data, session=fast_session, bgcolor=bg_color)
        
        await callback.message.answer_document(
            BufferedInputFile(output_data, filename=f"RAA_{color_code}.png"),
            caption=f"<b>✅ រួចរាល់! Background ពណ៌ {color_code.upper()}</b>"
        )
        await callback.message.delete()
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()

# --- រក្សាមុខងារសំឡេង និងភាសាទាំង ៤ នៅដដែល ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer(f"<b>⏳ កំពុងបំប្លែងសំឡេង ({lang.upper()})...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)
        
        await message.answer(f"<b>📝 អត្ថបទ:</b>\n<code>{text_result}</code>")
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    await callback.message.edit_text(f"✅ កំណត់ភាសា: <b>{lang_code.upper()}</b>")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
