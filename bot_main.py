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
import numpy as np
import cv2
import mediapipe as mp
from docx import Document
from fpdf import FPDF

# --- AI Setup (High Quality) ---
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmenter = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# បង្កើត Storage រក្សាទុកចំណូលចិត្ត User
user_languages, user_voices, last_transcription, user_last_image = {}, {}, {}, {}

# --- ១. មុខងារជំនួយការ Export ---
def create_pdf(text):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=text); return pdf.output(dest='S').encode('latin-1')

def create_docx(text):
    doc = Document(); doc.add_paragraph(text)
    target_stream = io.BytesIO(); doc.save(target_stream); return target_stream.getvalue()

def format_to_srt(text):
    return f"1\n00:00:00,000 --> 00:00:10,000\n{text}"

def format_to_vtt(text):
    return f"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n{text}"

# --- ២. KEYBOARDS (៦ ប៊ូតុងពេញលេញ) ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

def get_export_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="ex_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="ex_docx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="ex_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="ex_vtt")],
        [InlineKeyboardButton(text="📊 XLSX", callback_data="ex_xlsx"), InlineKeyboardButton(text="📦 JSON", callback_data="ex_json")]
    ])

# --- ៣. HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("<b>🎙 ស្វាគមន៍មកកាន់ RaaBot Pro v10.0</b>\n          សួស្តីអ្នកទាំងអស់គ្នា! នេះគឺជា Bot ស្វ័យប្រវត្តិសម្រាប់បំប្លែងសំឡេង កាត់ Background ល្បឿនលឿន និងប្តូរពណ៌។\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម👇", reply_markup=get_main_menu())

@dp.message(F.text == "🌐 ប្តូរភាសា")
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇰🇭 ខ្មែរ", callback_data="l_km"), InlineKeyboardButton(text="🇺🇸 English", callback_data="l_en")],
        [InlineKeyboardButton(text="🇯🇵 Japanese", callback_data="l_ja"), InlineKeyboardButton(text="🇨🇳 Chinese", callback_data="l_zh")]
    ])
    await message.answer("<b>🌐 សូមជ្រើសរើសភាសា៖</b>", reply_markup=kb)

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def cmd_voice(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 ភេទស្រី", callback_data="v_fm"), InlineKeyboardButton(text="👨 ភេទប្រុស", callback_data="v_m")],
        [InlineKeyboardButton(text="🛑 ឈប់ប្រើសំឡេង AI", callback_data="v_off")]
    ])
    await message.answer("<b>🎙️ សូមជ្រើសរើសប្រភេទសំឡេង AI៖</b>", reply_markup=kb)

# --- ៤. SPEECH TO TEXT & VOICE AI ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "km")
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer("⏳ <b>កំពុងដំណើរការ...</b>")
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
        
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except Exception as e: await message.answer(f"❌ Error: {str(e)}")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

# --- ៥. REMOVE BACKGROUND (HIGH QUALITY) ---
@dp.message(F.text == "🖼️ កាត់ Background")
async def cmd_remove_bg(message: types.Message):
    await message.answer("<b>🖼️ សូមផ្ញើរូបភាពមកកាន់ខ្ញុំ!</b>")

@dp.message(F.text == "🎨 ប្តូរពណ៌ Background")
async def cmd_change_bg(message: types.Message):
    await message.answer("<b>🎨 សូមផ្ញើរូបភាពមកដើម្បីប្តូរពណ៌!</b>")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    msg = await message.reply("⚡ <b>AI កំពុងកាត់ឱ្យ...</b>")
    try:
        file_i = await bot.get_file(message.photo[-1].file_id)
        p_bytes = await bot.download_file(file_i.file_path)
        input_data = p_bytes.read(); user_last_image[user_id] = input_data
        
        nparr = np.frombuffer(input_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        results = segmenter.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        condition = np.stack((results.segmentation_mask,) * 3, axis=-1) > 0.1
        
        out_img = np.where(condition, img, np.zeros(img.shape, dtype=np.uint8))
        tmp = cv2.cvtColor(out_img, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(tmp, 0, 255, cv2.THRESH_BINARY)
        b, g, r = cv2.split(out_img)
        dst = cv2.merge([b, g, r, alpha], 4)

        _, buffer = cv2.imencode('.png', dst)
        await message.answer_document(BufferedInputFile(buffer.tobytes(), filename="RAA_BG.png"), caption="<b>✅ រួចរាល់!</b>")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៦. CALLBACK HANDLERS ---
@dp.callback_query(F.data.startswith(("v_", "l_", "ex_", "bg_")))
async def handle_callbacks(callback: types.CallbackQuery):
    data, user_id = callback.data, callback.from_user.id
    
    if data.startswith("ex_"):
        f_t = data.replace("ex_", ""); text = last_transcription.get(user_id, "No data")
        if f_t == "pdf": final = create_pdf(text); ext = "pdf"
        elif f_t == "docx": final = create_docx(text); ext = "docx"
        elif f_t == "srt": final = format_to_srt(text).encode('utf-8'); ext = "srt"
        elif f_t == "vtt": final = format_to_vtt(text).encode('utf-8'); ext = "vtt"
        else: final = text.encode('utf-8'); ext = "txt"
        await callback.message.answer_document(BufferedInputFile(final, filename=f"result.{ext}"))
        
    elif data.startswith("v_"):
        if data == "v_off": user_voices.pop(user_id, None)
        else: user_voices[user_id] = data.replace("v_", "")
        await callback.message.edit_text("✅ រួចរាល់!")
    elif data.startswith("l_"):
        user_languages[user_id] = data.replace("l_", "")
        await callback.message.edit_text("✅ កំណត់ភាសារួចរាល់!")
    await callback.answer()

@dp.message(F.text == "ℹ️ ព័ត៌មាន Bot")
async def cmd_info(message: types.Message):
    await message.answer("<b>🤖 RaaBot Pro v10.0</b>\n• Auto Remove BG & Change Color\n• Google Recognition (4 Langs)\n• Dev: THEARA Rupp")

@dp.message(F.text == "👤 ទាក់ទង Admin")
async def cmd_admin(message: types.Message):
    await message.answer(f"<b>Admin:</b> <a href='{ADMIN_URL}'>OG_Raa1</a>")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
