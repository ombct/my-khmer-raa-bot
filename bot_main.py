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

# --- មុខងារ Remove Background Engine (u2netp សម្រាប់ល្បឿន) ---
from rembg import remove, new_session

# Load session ទុកជាមុនដើម្បីកាត់ឱ្យលឿន
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
user_last_image = {} # សម្រាប់រក្សារូបភាពដើមទុករក្សាពណ៌

# --- KEYBOARDS (រក្សាទម្រង់ដើម និងបន្ថែម Menu ពណ៌) ---
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
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="setlang_ja")],
        [InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="setlang_zh")]
    ])

def get_file_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="export_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="export_docx")],
        [InlineKeyboardButton(text="📋 TXT", callback_data="export_txt"), InlineKeyboardButton(text="📊 XLSX", callback_data="export_xlsx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="export_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="export_vtt")],
        [InlineKeyboardButton(text="📦 JSON", callback_data="export_json")]
    ])

def get_color_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬜ ពណ៌ស", callback_data="bg_white"), 
         InlineKeyboardButton(text="⬛ ពណ៌ខ្មៅ", callback_data="bg_black")],
        [InlineKeyboardButton(text="🟦 ពណ៌ខៀវ", callback_data="bg_blue"), 
         InlineKeyboardButton(text="🟥 ពណ៌ក្រហម", callback_data="bg_red")],
        [InlineKeyboardButton(text="🖼️ ភាពថ្លា (Transparent)", callback_data="bg_trans")]
    ])

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n\n"
        "សូមប្រើប្រាស់ Menu ខាងក្រោមដើម្បីចាប់ផ្តើម៖", 
        reply_markup=get_main_menu()
    )

# --- មុខងារកាត់ Background និងប្តូរពណ៌ ---
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background យ៉ាងលឿន...</b>")
    
    try:
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)
        input_data = photo_bytes.read()
        
        # រក្សាទុកសម្រាប់ប្រើពេលប្តូរពណ៌
        user_last_image[user_id] = input_data

        # កាត់បង្ហាញជាភាពថ្លាមុន
        output_data = remove(input_data, session=fast_session)

        await message.answer_document(
            BufferedInputFile(output_data, filename="RAA_NO_BG.png"),
            caption="<b>✅ កាត់រួចរាល់! ប្អូនអាចជ្រើសរើសពណ៌ Background បាន៖</b>",
            reply_markup=get_color_menu()
        )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

@dp.callback_query(F.data.startswith("bg_"))
async def change_bg_color(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    color_code = callback.data.replace("bg_", "")
    
    if user_id not in user_last_image:
        await callback.answer("❌ រកមិនឃើញរូបភាពដើម! សូមផ្ញើរូបភាពម្ដងទៀត។", show_alert=True)
        return

    await callback.message.edit_text(f"🎨 <b>កំពុងប្តូរពណ៌ទៅ {color_code.upper()}...</b>")
    
    try:
        input_data = user_last_image[user_id]
        color_map = {
            "white": (255, 255, 255), "black": (0, 0, 0),
            "blue": (0, 0, 255), "red": (255, 0, 0),
            "trans": (0, 0, 0, 0)
        }
        bg_color = color_map.get(color_code)
        
        output_data = remove(input_data, session=fast_session, bgcolor=bg_color)
        
        await callback.message.answer_document(
            BufferedInputFile(output_data, filename=f"RAA_{color_code}.png"),
            caption=f"<b>✅ រួចរាល់! ពណ៌ {color_code.upper()}</b>"
        )
        await callback.message.delete()
    except Exception as e:
        await callback.message.answer(f"❌ Error: {str(e)}")
    await callback.answer()

# --- មុខងារសំឡេង (រក្សាទម្រង់ដើម និងភាសាទាំង ៤) ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer(f"<b>⏳ កំពុងបំប្លែងសំឡេង ({lang.upper()}) ដោយ Google...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text_result = recognizer.recognize_google(audio_data, language=google_lang)
        last_transcription[user_id] = text_result

        if voice_choice:
            tts_path = f"{file_id}_ai.mp3"
            gTTS(text=text_result, lang=lang).save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path))
            if os.path.exists(tts_path): os.remove(tts_path)

        await message.answer(f"<b>📝 អត្ថបទ (Google):</b>\n\n<code>{text_result}</code>")
        await message.answer("<b>✅ រួចរាល់! សូមជ្រើសរើសប្រភេទ File:</b>", reply_markup=get_file_type_keyboard())
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg_path, wav_path]:
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data.startswith("export_"))
async def process_export(callback: types.CallbackQuery):
    file_type = callback.data.split("_")[1]
    text = last_transcription.get(callback.from_user.id, "មិនមានទិន្នន័យ")
    await callback.message.answer_document(
        BufferedInputFile(text.encode('utf-8'), filename=f"raa_file.{file_type}"),
        caption=f"<b>🎬 ឯកសារ {file_type.upper()} រួចរាល់!</b>"
    )
    await callback.answer()

# --- ប៊ូតុង និងការកំណត់ផ្សេងៗ (រក្សាទម្រង់ដើម) ---
@dp.message(F.text == "🌐 ប្តូរភាសា (Language)")
async def change_lang(message: types.Message):
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា:</b>", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang_code
    await callback.message.edit_text(f"✅ បានកំណត់ភាសាទៅជា: <b>{lang_code.upper()}</b>")
    await callback.answer()

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ស្រី", callback_data="v_female"), 
         InlineKeyboardButton(text="👨 ប្រុស", callback_data="v_male")]
    ])
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI:</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("v_"))
async def set_voice(callback: types.CallbackQuery):
    user_voices[callback.from_user.id] = callback.data.replace("v_", "")
    await callback.message.edit_text("✅ បានកំណត់សំឡេង AI រួចរាល់!")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Auto Remove BG & Change Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>ទាក់ទង Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
