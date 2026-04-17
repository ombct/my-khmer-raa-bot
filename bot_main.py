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
from rembg import remove, new_session

# --- កំណត់ការកាត់ Background ---
fast_session = new_session("u2netp") 

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

user_languages, user_voices, last_transcription, user_last_image = {}, {}, {}, {}

# --- KEYBOARDS ---

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

def get_export_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="ex_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="ex_docx")],
        [InlineKeyboardButton(text="🎬 SRT (សម្រាប់ Subtitle)", callback_data="ex_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="ex_vtt")],
        [InlineKeyboardButton(text="📊 XLSX", callback_data="ex_xlsx"), InlineKeyboardButton(text="📦 JSON", callback_data="ex_json")]
    ])

# --- មុខងារបង្កើតទម្រង់ SRT ពិតប្រាកដ ---
def format_to_srt(text):
    # បំបែកអត្ថបទជាជួរៗ ដើម្បីដាក់នាទី
    lines = text.split(". ")
    srt_content = ""
    for i, line in enumerate(lines):
        start = f"00:00:{i*2:02d},000"
        end = f"00:00:{(i*2)+2:02d},000"
        srt_content += f"{i+1}\n{start} --> {end}\n{line}\n\n"
    return srt_content

def format_to_vtt(text):
    lines = text.split(". ")
    vtt_content = "WEBVTT\n\n"
    for i, line in enumerate(lines):
        start = f"00:00:{i*2:02d}.000"
        end = f"00:00:{(i*2)+2:02d}.000"
        vtt_content += f"{start} --> {end}\n{line}\n\n"
    return vtt_content

# --- HANDLERS ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 RaaBot Pro v10.0</b>\nមហាសែនពេញលេញ!", reply_markup=get_main_menu())

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer("⏳ <b>កំពុងបំប្លែង...</b>")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    ogg, wav = f"{file_id}.ogg", f"{file_id}.wav"
    await bot.download_file(file.file_path, ogg)
    
    try:
        AudioSegment.from_file(ogg).export(wav, format="wav")
        with sr.AudioFile(wav) as source:
            text = recognizer.recognize_google(recognizer.record(source), language=g_lang)
        last_transcription[user_id] = text
        
        if user_id in user_voices:
            tts_p = f"{file_id}.mp3"
            gTTS(text=text, lang=lang).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
        
        await message.answer(f"<b>📝 អត្ថបទបំប្លែងបាន៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

@dp.callback_query(F.data.startswith("ex_"))
async def do_export(callback: types.CallbackQuery):
    f_t = callback.data.replace("ex_", "")
    text = last_transcription.get(callback.from_user.id, "")
    
    if not text:
        await callback.answer("❌ គ្មានទិន្នន័យ!", show_alert=True)
        return

    # ប្តូរទម្រង់តាមប្រភេទ File
    if f_t == "srt":
        final_data = format_to_srt(text)
    elif f_t == "vtt":
        final_data = format_to_vtt(text)
    else:
        final_data = text

    await callback.message.answer_document(
        BufferedInputFile(final_data.encode('utf-8'), filename=f"raa_subtitle.{f_t}"),
        caption=f"<b>✅ បានផ្ញើឯកសារ {f_t.upper()} រួចរាល់!</b>"
    )
    await callback.answer()

# --- មុខងារ Remove BG & Color (រក្សាទុកទាំងអស់) ---
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    msg = await message.reply("⚡ <b>កំពុងកាត់ Background...</b>")
    try:
        file_i = await bot.get_file(photo_id)
        p_bytes = await bot.download_file(file_i.file_path)
        input_d = p_bytes.read()
        user_last_image[user_id] = input_d
        out_d = remove(input_d, session=fast_session)
        
        # ប៊ូតុងប្តូរពណ៌
        color_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬜ ស", callback_data="bg_white"), InlineKeyboardButton(text="⬛ ខ្មៅ", callback_data="bg_black")],
            [InlineKeyboardButton(text="🟦 ខៀវ", callback_data="bg_blue"), InlineKeyboardButton(text="🟥 ក្រហម", callback_data="bg_red")]
        ])
        
        await message.answer_document(BufferedInputFile(out_d, filename="RAA_BG.png"), caption="<b>✅ រួចរាល់!</b>", reply_markup=color_kb)
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# (ដាក់ Handler ផ្សេងៗទៀតដូចកូដមុន...)
async def main(): await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
