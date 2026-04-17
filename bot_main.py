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

# --- មុខងារ Remove Background Engine ---
from rembg import remove, new_session

# ប្រើ Model 'u2netp' ដែលដើរលឿន និងមិនលោត Error ក្នុង Server
fast_session = new_session("u2netp") 

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# ទិន្នន័យបណ្តោះអាសន្ន
user_languages = {}
user_voices = {}
last_transcription = {}
user_last_image = {} # សម្រាប់ចងចាំរូបភាពដើម្បីប្តូរពណ៌

# --- KEYBOARDS ---

def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
            [KeyboardButton(text="🖼️ Remove Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
            [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
        ],
        resize_keyboard=True
    )

def get_color_menu():
    # callback_data ត្រូវតែខ្លីដើម្បីកុំឱ្យ Error 'BUTTON_DATA_INVALID'
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬜ ពណ៌ស", callback_data="cls_white"), 
         InlineKeyboardButton(text="⬛ ពណ៌ខ្មៅ", callback_data="cls_black")],
        [InlineKeyboardButton(text="🟦 ពណ៌ខៀវ", callback_data="cls_blue"), 
         InlineKeyboardButton(text="🟥 ពណ៌ក្រហម", callback_data="cls_red")],
        [InlineKeyboardButton(text="🖼️ ភាពថ្លា (Transparent)", callback_data="cls_trans")]
    ])

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="setlang_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="setlang_ja"), InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="setlang_zh")]
    ])

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម៖", 
        reply_markup=get_main_menu()
    )

# មុខងារ Remove Background
@dp.message(F.text == "🖼️ Remove Background")
async def ask_for_photo(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ Bot ដើម្បីកាត់ Background!</b>")

@dp.message(F.text == "🎨 ប្តូរពណ៌ Background")
async def ask_for_photo_color(message: types.Message):
    await message.answer("<b>🎨 សូមផ្ញើរូបភាពមក ដើម្បីជ្រើសរើសពណ៌ Background ថ្មី!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background...</b>")
    
    try:
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)
        input_data = photo_bytes.read()
        
        # រក្សាទុកក្នុង Memory តាម user_id
        user_last_image[user_id] = input_data

        # កាត់យកភាពថ្លា (Transparent) បង្ហាញជាមុន
        output_data = remove(input_data, session=fast_session)

        await message.answer_document(
            BufferedInputFile(output_data, filename="RAA_NO_BG.png"),
            caption="<b>✅ កាត់រួចរាល់! ប្អូនអាចប្តូរពណ៌ Background បាន៖</b>",
            reply_markup=get_color_menu()
        )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

@dp.callback_query(F.data.startswith("cls_"))
async def process_color(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    color_name = callback.data.replace("cls_", "")
    
    if user_id not in user_last_image:
        await callback.answer("❌ រកមិនឃើញរូបភាព! សូមផ្ញើរូបភាពម្ដងទៀត។", show_alert=True)
        return

    await callback.message.edit_text(f"🎨 <b>កំពុងប្តូរពណ៌ទៅ {color_name.upper()}...</b>")
    
    try:
        input_data = user_last_image[user_id]
        color_map = {
            "white": (255, 255, 255), "black": (0, 0, 0),
            "blue": (0, 0, 255), "red": (255, 0, 0), "trans": (0, 0, 0, 0)
        }
        bg_color = color_map.get(color_name)
        
        # ដំណើរការកាត់ និងដាក់ពណ៌ក្នុងពេលតែមួយ (លឿនបំផុត)
        output_data = remove(input_data, session=fast_session, bgcolor=bg_color)
        
        await callback.message.answer_document(
            BufferedInputFile(output_data, filename=f"RAA_{color_name}.png"),
            caption=f"<b>✅ បានប្តូរទៅពណ៌ {color_name.upper()} រួចរាល់!</b>"
        )
        await callback.message.delete()
    except Exception as e:
        await callback.message.answer(f"❌ Error: {str(e)}")
    await callback.answer()

# --- មុខងារសំឡេង (រក្សាទម្រង់ដើម) ---

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
        
        await message.answer(f"<b>📝 អត្ថបទ:</b>\n\n<code>{text_result}</code>")
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
    await callback.message.edit_text(f"✅ បានកំណត់ភាសាទៅជា: <b>{lang_code.upper()}</b>")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Remove Background & Color Change\n• Google Speech to Text\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>ទាក់ទង Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
