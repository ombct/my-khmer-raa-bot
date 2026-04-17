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
from aiogram.client.default import DefaultBotProperties
from groq import Groq
from pydub import AudioSegment
from gtts import gTTS
from rembg import remove # បន្ថែមសម្រាប់ Remove Background
from io import BytesIO
from PIL import Image

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

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

def get_file_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="export_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="export_docx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="export_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="export_vtt")]
    ])

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
        "<b>🎙 សូមស្វាគមន៍មកកាន់ RaaBot Pro!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>លក្ខណៈពិសេស:</b>\n"
        "✅ បំប្លែងសំឡេងជាអត្ថបទ & SRT\n"
        "✅ បង្កើតសំឡេង AI (ប្រុស/ស្រី)\n"
        "✅ <b>Remove Background លើរូបភាព</b> (គ្រាន់តែផ្ញើរូបភាពមក)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>ផ្ញើសំឡេងដើម្បីបំប្លែង ឬផ្ញើរូបភាពដើម្បីកាត់ Background</i>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

# --- មុខងារ REMOVE BACKGROUND ---
@dp.message(F.photo)
async def handle_image(message: types.Message):
    msg = await message.answer("⏳ <b>កំពុងកាត់ Background... សូមរង់ចាំ</b>")
    try:
        # ទាញយករូបភាព
        photo = message.photo[-1]
        image_bytes = BytesIO()
        await bot.download(photo, destination=image_bytes)
        
        # ដំណើរការកាត់ Background
        input_image = Image.open(image_bytes)
        output_image = remove(input_image)
        
        # រក្សាទុកលទ្ធផលក្នុង Memory
        output_bytes = BytesIO()
        output_image.save(output_bytes, format='PNG')
        output_bytes.seek(0)
        
        await message.answer_document(
            BufferedInputFile(output_bytes.read(), filename="no_bg.png"),
            caption="<b>✅ កាត់ Background រួចរាល់!</b>"
        )
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ កំហុសរូបភាព: {str(e)}")

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def choose_voice(message: types.Message):
    await message.answer("<b>🎙️ សូមជ្រើសរើសភេទសំឡេង AI:</b>", reply_markup=get_voice_keyboard())

@dp.callback_query(F.data.startswith("setvoice_"))
async def process_voice_selection(callback: types.CallbackQuery):
    voice_type = callback.data.split("_")[1]
    user_voices[callback.from_user.id] = None if voice_type == "none" else voice_type
    name = "ស្រី 👩" if voice_type == "female" else "ប្រុស 👨"
    txt = f"<b>✅ បានកំណត់យកសំឡេង AI ភេទ:</b> <code>{name}</code>" if voice_type != "none" else "<b>❌ បិទសំឡេង AI</b>"
    await callback.message.edit_text(txt)
    await callback.answer()

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

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    
    google_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}[lang]
    msg = await message.answer("<b>⏳ កំពុងដំណើរការ... សូមរង់ចាំ</b>")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path, tts_path = f"{file_id}.ogg", f"{file_id}.wav", f"{file_id}_ai.mp3"
    await bot.download_file(file.file_path, ogg_path)

    try:
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            google_text = recognizer.recognize_google(audio_data, language=google_lang)

        if voice_choice:
            tts = gTTS(text=google_text, lang=lang)
            tts.save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path), caption="<b>🎙️ សំឡេង AI</b>")

        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=lang,
                prompt="អក្សរខ្មែរមានជើង និងស្រៈត្រឹមត្រូវ។"
            )

        await message.answer(f"<b>📝 អក្សរ ({lang.upper()}):</b>\n<code>{google_text}</code>")

        srt_content = ""
        for i, segment in enumerate(response.segments, start=1):
            srt_content += f"{i}\n{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n{segment['text'].strip()}\n\n"

        await message.answer_document(
            BufferedInputFile(srt_content.encode('utf-8'), filename=f"sub_{lang}.srt"),
            caption=f"<b>🎬 SRT ({lang.upper()}) រួចរាល់!</b>",
            reply_markup=get_file_type_keyboard()
        )
        await msg.delete()
    except Exception as e:
        await message.answer(f"<b>❌ កំហុស:</b> <code>{str(e)}</code>")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n━━━━━━━━━━━━━━━━━━\n• <b>Developer:</b> THEARA Rupp\n• <b>Status:</b> Stable")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer("<b>ទាក់ទង Admin:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Admin", url=ADMIN_URL)]]))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
