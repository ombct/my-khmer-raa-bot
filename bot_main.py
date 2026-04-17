import os
import logging
import asyncio
import requests
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

# --- CONFIGURATION ---
API_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_KEY')
ADMIN_URL = "https://t.me/OG_Raa1"

# API Key របស់ប្អូនសម្រាប់ Remove Background
REMOVE_BG_API_KEY = "c7MsDwJLr4Gv3eGjNBPRyFo4" 

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)
logging.basicConfig(level=logging.INFO)

user_languages = {}
user_voices = {}

# --- KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 ប្តូរភាសា (Language)"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
            [KeyboardButton(text="🖼️ កាត់រូបភាព (Background)"), KeyboardButton(text="ℹ️ ព័ត៌មាន Bot")],
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
        "<b>🎙 <u>ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</u></b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌈 <b>មុខងារពិសេសរបស់ប្អូន:</b>\n"
        "🟢 <code>បំប្លែងសំឡេងដោយ Groq AI ច្បាស់ 100%</code>\n"
        "🟡 <code>បង្កើតសំឡេង AI (ប្រុស/ស្រី)</code>\n"
        "🔵 <code>Remove Background ច្បាស់កម្រិត 8K</code>\n"
        "🟣 <code>បំប្លែងឯកសារ PDF/DOCX/SRT/VTT</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <i><b><a href='https://t.me/OG_Raa1'>ទាក់ទងមក Admin បើមានបញ្ហា</a></b></i>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == "🖼️ កាត់រូបភាព (Background)")
async def rbg_info(message: types.Message):
    await message.answer("<b>🖼️ របៀបប្រើប្រាស់:</b>\nសូមផ្ញើរូបភាពដែលប្អូនចង់កាត់មកកាន់ Bot រួចចុចប៊ូតុងបញ្ជាក់ នោះ Bot នឹងកាត់ជូនភ្លាមៗក្នុងកម្រិត 8K!")

# --- មុខងារ REMOVE BACKGROUND (ទាល់តែចុចប៊ូតុងទើបកាត់) ---
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
    await callback.message.edit_text("⚡ <b>កំពុងកាត់ Background កម្រិតច្បាស់ 8K... សូមរង់ចាំ</b>")
    
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
                BufferedInputFile(response.content, filename="RAA_PRO_8K_NO_BG.png"),
                caption="<b>✅ កាត់រួចរាល់ក្នុងកម្រិតច្បាស់ 8K!</b>"
            )
            await callback.message.delete()
        else:
            await callback.message.edit_text(f"❌ កំហុស API: {response.text}")
    except Exception as e:
        await callback.message.edit_text(f"❌ កំហុសបច្ចេកទេស: {str(e)}")

# --- មុខងារបំប្លែងសំឡេងដោយប្រើ Groq AI ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    voice_choice = user_voices.get(user_id, None)
    msg = await message.answer("<b>⏳ កំពុងបំប្លែងដោយ Groq AI (High Accuracy)...</b>")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg_path, wav_path, tts_path = f"{file_id}.ogg", f"{file_id}.wav", f"{file_id}_ai.mp3"
    await bot.download_file(file.file_path, ogg_path)

    try:
        audio = AudioSegment.from_file(ogg_path)
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")
        
        with open(wav_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="km",
                prompt="អត្ថបទនេះជាភាសាខ្មែរ។ សូមសរសេរឱ្យត្រូវតាមវចនានុក្រមខ្មែរ មានជើងអក្សរ និងស្រៈពេញតួ។"
            )

        full_text = response.text
        if voice_choice:
            tts = gTTS(text=full_text, lang=lang)
            tts.save(tts_path)
            await message.answer_voice(BufferedInputFile.from_file(tts_path), caption="<b>🎙️ សំឡេង AI</b>")

        await message.answer(f"<b>📝 អត្ថបទបំប្លែងរួច (Groq AI):</b>\n\n<code>{full_text}</code>")

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
        await message.answer(f"<b>❌ Error:</b> <code>{str(e)}</code>")
    finally:
        for p in [ogg_path, wav_path, tts_path]:
            if os.path.exists(p): os.remove(p)

# --- មុខងារផ្សេងៗ ---
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
    txt = f"<b>✅ បានកំណត់យកសំឡេង AI:</b> <code>{name}</code>" if voice_type != "none" else "<b>❌ បិទសំឡេង AI</b>"
    await callback.message.edit_text(txt)
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n━━━━━━━━━━━━━━━━━━\n• <b>Developer:</b> THEARA Rupp\n• <b>Status:</b> Stable")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer("<b>ទាក់ទង Admin:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Admin", url=ADMIN_URL)]]))

@dp.callback_query(F.data == "cancel_rbg")
async def cancel_remove_bg(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ បានបោះបង់ការកាត់ Background។")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
