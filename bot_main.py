import os, logging, asyncio, io, json
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

# --- AI Setup (Mediapipe - ស្រាលជាង rembg ឆ្ងាយណាស់) ---
mp_selfie = mp.solutions.selfie_segmentation
segmenter = mp_selfie.SelfieSegmentation(model_selection=1)

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_URL = "https://t.me/OG_Raa1"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
recognizer = sr.Recognizer()
logging.basicConfig(level=logging.INFO)

# Storage
user_languages, user_voices, last_transcription = {}, {}, {}

# --- ១. មុខងារបំប្លែង Format ---
def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=text.encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

def create_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    target = io.BytesIO()
    doc.save(target)
    return target.getvalue()

# --- ២. KEYBOARDS ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 ប្តូរភាសា"), KeyboardButton(text="🎙️ ជ្រើសរើសសំឡេង AI")],
        [KeyboardButton(text="🖼️ កាត់ Background"), KeyboardButton(text="🎨 ប្តូរពណ៌ Background")],
        [KeyboardButton(text="ℹ️ ព័ត៌មាន Bot"), KeyboardButton(text="👤 ទាក់ទង Admin")]
    ], resize_keyboard=True)

def get_export_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF", callback_data="ex_pdf"), InlineKeyboardButton(text="📝 DOCX", callback_data="ex_docx")],
        [InlineKeyboardButton(text="🎬 SRT", callback_data="ex_srt"), InlineKeyboardButton(text="📺 VTT", callback_data="ex_vtt")]
    ])

# --- ៣. Command Start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("<b>🎙 RaaBot Pro v10.0 (Updated)</b>\nរាល់មុខងារទាំងអស់ត្រូវបានកែសម្រួលឱ្យមានស្ថេរភាព!", reply_markup=get_main_menu())

# --- ៤. មុខងារ Speech to Text ---
@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    uid = message.from_user.id
    lang = user_languages.get(uid, "km")
    g_lang = {"km": "km-KH", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}.get(lang, "km-KH")
    
    msg = await message.answer("⏳ <b>កំពុងបំប្លែង...</b>")
    fid = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(fid)
    ogg, wav = f"{fid}.ogg", f"{fid}.wav"
    await bot.download_file(file.file_path, ogg)
    
    try:
        AudioSegment.from_file(ogg).export(wav, format="wav")
        with sr.AudioFile(wav) as source:
            text = recognizer.recognize_google(recognizer.record(source), language=g_lang)
        last_transcription[uid] = text
        
        if uid in user_voices:
            tts_p = f"{fid}.mp3"
            gTTS(text=text, lang=lang).save(tts_p)
            await message.answer_voice(BufferedInputFile.from_file(tts_p))
            os.remove(tts_p)
            
        await message.answer(f"<b>📝 អត្ថបទ៖</b>\n<code>{text}</code>", reply_markup=get_export_keyboard())
        await msg.delete()
    except: await msg.edit_text("❌ មិនអាចបំប្លែងបាន!")
    finally:
        for p in [ogg, wav]: 
            if os.path.exists(p): os.remove(p)

# --- ៥. មុខងារកាត់ Background (ប្រើ Mediapipe លឿនជាងមុន) ---
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    msg = await message.reply("⚡ <b>AI កំពុងកាត់រូបភាព...</b>")
    try:
        fid = message.photo[-1].file_id
        file = await bot.get_file(fid)
        p_bytes = await bot.download_file(file.file_path)
        
        # បំប្លែងរូបភាព
        nparr = np.frombuffer(p_bytes.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # កាត់ BG
        res = segmenter.process(rgb_img)
        mask = res.segmentation_mask > 0.5
        b, g, r = cv2.split(img)
        a = (mask * 255).astype(np.uint8)
        rgba = cv2.merge([b, g, r, a])
        
        _, buffer = cv2.imencode('.png', rgba)
        await message.answer_document(BufferedInputFile(buffer.tobytes(), filename="RAA_BG.png"), caption="<b>✅ កាត់រួចរាល់!</b>")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Error: {str(e)}")

# --- ៦. Callback Handles ---
@dp.callback_query(F.data.startswith(("ex_", "l_", "v_")))
async def callbacks(callback: types.CallbackQuery):
    uid = callback.from_user.id
    data = callback.data
    
    if data.startswith("ex_"):
        mode = data.replace("ex_", "")
        text = last_transcription.get(uid, "No data")
        if mode == "pdf": 
            file_data = create_pdf(text); ext = "pdf"
        elif mode == "docx": 
            file_data = create_docx(text); ext = "docx"
        elif mode == "srt":
            file_data = f"1\n00:00:00,000 --> 00:00:10,000\n{text}".encode('utf-8'); ext = "srt"
        else:
            file_data = f"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n{text}".encode('utf-8'); ext = "vtt"
            
        await callback.message.answer_document(BufferedInputFile(file_data, filename=f"result.{ext}"))
    
    elif data.startswith("l_"):
        user_languages[uid] = data.replace("l_", "")
        await callback.message.edit_text("✅ ប្តូរភាសារួចរាល់!")
    elif data.startswith("v_"):
        if data == "v_off": user_voices.pop(uid, None)
        else: user_voices[uid] = data.replace("v_", "")
        await callback.message.edit_text("✅ រួចរាល់!")
        
    await callback.answer()

@dp.message(F.text == "🌐 ប្តូរភាសា")
async def cmd_l(m: types.Message): await cmd_lang(m)

@dp.message(F.text == "🎙️ ជ្រើសរើសសំឡេង AI")
async def cmd_v(m: types.Message): await cmd_voice(m)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
